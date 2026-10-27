"""Validate the small page language and preservation of complete site content."""

import json
import shutil
import sys
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build
import check
import update_translations
from test_seminar import fixture_sources, render_page, seminar_fixture


class TemplateTests(unittest.TestCase):
    def setUp(self):
        # Fake translation-cache assertions are independent from reviewed site prose.
        loader = patch.object(update_translations, "read_reviewed", return_value={})
        loader.start()
        self.addCleanup(loader.stop)

    def test_nested_loops_keep_parent_scope_and_if_handles_missing_photo(self):
        template = """{% for section in sections %}{{ section.title }}:
{% for member in section.members %}{% if member.photo %}{{ member.photo }}{% else %}{{ section.title }} / {{ member.name }}{% endif %};{% endfor %}{% endfor %}{{ member }}"""
        context = {"member": "outer", "sections": [
            {"title": "Team", "members": [
                {"name": "A", "photo": None}, {"name": "B", "photo": "photo.jpg"},
            ]},
            {"title": "Alumni", "members": [{"name": "C", "photo": None}]},
        ]}
        rendered = build.render_html(template, context)
        self.assertIn("Team / A", rendered)
        self.assertIn("photo.jpg", rendered)
        self.assertIn("Alumni / C", rendered)
        self.assertTrue(rendered.endswith("outer"))

    def test_text_and_attributes_are_escaped_without_reinterpreting_placeholders(self):
        value = '<img src=x onerror="bad"> & {{ secret }} {% if secret %}'
        rendered = build.render_html('<p title="{{ value }}">{{ value }}</p>', {"value": value})
        self.assertNotIn("<img", rendered)
        self.assertIn("&lt;img src=x onerror=&quot;bad&quot;&gt; &amp;", rendered)
        self.assertIn("{{ secret }} {% if secret %}", rendered)

    def test_static_html_prose_translates_safely_and_respects_excluded_content(self):
        source = """<!doctype html><html><head><title>Original metadata</title></head><body>
          <!-- An English comment stays unchanged. -->
          <p title="Ask &amp; share">  Plain &amp; accessible prose.  </p>
          <p translate="no"><span>Scientific title in its original language.</span></p>
          <pre>Original example.</pre><code>Original code.</code>
          <script>const label = "Original script";</script><style>.original { color: red; }</style>
          <p>{{ home.title }}</p>
        </body></html>"""
        literals = {text: key for _, _, key, text in build.StaticHTMLLiterals(source).literals()}
        self.assertEqual(set(literals), {"Ask & share", "Plain & accessible prose."})
        values = {
            literals["Ask & share"]: 'Translated "attribute" & label',
            literals["Plain & accessible prose."]: '<b>Translated prose</b> {{ secret }} {% if secret %}',
        }
        document = build.render_html(build.html_literal_template(source), {
            "ui": {"html_literals": values}, "home": {"title": "A dynamic heading"},
        })
        self.assertIn('title="Translated &quot;attribute&quot; &amp; label"', document)
        self.assertIn('  &lt;b&gt;Translated prose&lt;/b&gt; {{ secret }} {% if secret %}  ', document)
        self.assertNotIn('<b>Translated prose</b>', document)
        self.assertIn('<p>A dynamic heading</p>', document)
        for preserved in ("Original metadata", "Scientific title in its original language.",
                          "Original example.", "Original code.", "Original script", "An English comment"):
            self.assertIn(preserved, document)

    def test_static_html_catalogue_is_localized_for_each_translation(self):
        page = build.read_text(build.PAGES / "home.html")
        page = page.replace('<body>', '<body><p>A new English sentence.</p>')
        self.assertIn('A new English sentence.', page)
        sources = fixture_sources(seminar=seminar_fixture())
        original_read = build.read_text
        def read_source(path):
            return page if path == build.PAGES / "home.html" else original_read(path)
        with patch.object(build, "read_text", side_effect=read_source):
            catalogue = build.translation_sources(sources)
            self.assertIn('A new English sentence.', catalogue['ui']['html_literals'].values())
            for language in ('fr', 'it'):
                with self.subTest(language=language):
                    cache = update_translations.empty_cache(language)
                    cache['translations'] = {'A new English sentence.': 'Translated static sentence.'}
                    localized = update_translations.localize_sources(catalogue, language, cache=cache)
                    plan = build.plan_seminar(localized['seminar'], date(2026, 10, 9))
                    home = next(item for item in localized['site']['pages'] if item['id'] == 'home')
                    document = build.render_document(home, '../', localized, plan, language, language)
                    self.assertIn('<p>Translated static sentence.</p>', document)
                    self.assertNotIn('<p>A new English sentence.</p>', document)
            self.assertIn('A new English sentence.', catalogue['ui']['html_literals'].values())

    def test_scientific_titles_stay_original_in_each_language_and_archive(self):
        sources = build.translation_sources(fixture_sources(seminar=seminar_fixture()))
        paper_titles = [paper['title'] for paper in sources['publications']['items']]
        talk_titles = [talk['title'] for session in sources['seminar']['sessions'] for talk in session['talks']]
        for language in ('en', 'fr', 'it'):
            with self.subTest(language=language):
                cache = None if language == 'en' else update_translations.empty_cache(language)
                if cache is not None:
                    cache['translations'] = {title: 'SHOULD NEVER REPLACE A SCIENTIFIC TITLE'
                                             for title in paper_titles + talk_titles}
                localized = update_translations.localize_sources(sources, language, cache=cache)
                plan = build.plan_seminar(localized['seminar'], date(2026, 10, 9))
                for page_id, titles, tag in (('home', paper_titles, 'h3'), ('seminar', talk_titles, 'p')):
                    page = next(item for item in localized['site']['pages'] if item['id'] == page_id)
                    document = build.render_document(page, '../', localized, plan, language, language)
                    for title in titles:
                        self.assertIn(build.html.escape(title, quote=True), document)
                    self.assertNotIn('SHOULD NEVER REPLACE A SCIENTIFIC TITLE', document)
                    protected = [attrs for element, attrs in Elements(document).elements
                                 if element == tag and attrs.get('translate') == 'no']
                    self.assertEqual(len(protected), len(titles))
                    if page_id == 'home':
                        for talk in plan['next']['talks']:
                            self.assertIn('<span translate="no">' + build.html.escape(talk['title'], quote=True) + '</span>', document)

    def test_invalid_templates_fail_before_output_is_written(self):
        for template in (
            "{% if name %}yes", "{% for x in names %}x",
            "{% else %}", "{% endif %}", "{% include page %}",
            "{{ value.upper() }}", "{{ value.__class__ }}", "{{ broken", "{{ namexx",
            "{% if name %}yes{% endfor %}",
        ):
            with self.subTest(template=template), self.assertRaises(build.BuildError):
                build.render_html(template, {"name": "A", "names": ["A"], "value": "A"})
        with self.assertRaises(build.BuildError):
            build.render_html("{{ missing }}", {})
        with self.assertRaises(build.BuildError):
            build.render_html("{% for item in name %}{{ item }}{% endfor %}", {"name": "text"})

    def test_seminar_archive_is_closed_and_members_are_always_visible(self):
        sources = fixture_sources(seminar=seminar_fixture())
        plan = build.plan_seminar(sources["seminar"], date(2026, 10, 9))
        document = render_page("seminar", "../", sources, plan)
        parser = Elements(document)
        archives = [attrs for tag, attrs in parser.elements if tag == "details"]
        self.assertTrue(archives)
        self.assertTrue(all("open" not in attrs for attrs in archives))
        team = render_page("team", "../", sources, plan)
        self.assertNotIn("<details", team)
        self.assertIn("Former members", team)
        for section in sources["team"]["sections"]:
            for member in section["members"]:
                self.assertIn(build.html.escape(member["name"], quote=True), team)

    def test_asset_updates_refresh_cached_styles_on_every_route(self):
        sources = fixture_sources(seminar=seminar_fixture())

        def linked_assets(output):
            links = {}
            for file in output.rglob("*.html"):
                elements = Elements(file.read_text(encoding="utf-8")).elements
                stylesheet = next(attrs["href"] for tag, attrs in elements
                                  if tag == "link" and attrs.get("rel") == "stylesheet")
                script = next(attrs["src"] for tag, attrs in elements
                              if tag == "script" and "src" in attrs)
                links[file.relative_to(output)] = (stylesheet, script)
            return links

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            source = temporary / "source"
            output = temporary / "site"
            shutil.copytree(build.ROOT / "assets", source / "assets")
            with patch.object(build, "ROOT", source), patch.object(
                build, "read_json", side_effect=lambda name: sources[name],
            ):
                build.build(output, today=date(2026, 10, 9))
                original = linked_assets(output)
                build.build(output, today=date(2026, 10, 9))
                self.assertEqual(linked_assets(output), original)

                stylesheet = source / "assets/css/site.css"
                with stylesheet.open("a", encoding="utf-8") as file:
                    file.write("\n/* A newly published style change. */\n")
                build.build(output, today=date(2026, 10, 9))
                updated = linked_assets(output)
                self.assertEqual(set(updated), set(original))
                self.assertEqual(len(updated), 20)
                for route, (css_url, js_url) in updated.items():
                    with self.subTest(route=route):
                        old_css, old_js = original[route]
                        self.assertNotEqual(css_url, old_css)
                        self.assertEqual(urlsplit(css_url).path, urlsplit(old_css).path)
                        self.assertTrue(urlsplit(css_url).query)
                        self.assertEqual(js_url, old_js)
                self.assertEqual(check.check_site(output), [])

    def test_complete_build_keeps_routes_data_and_real_team_logo(self):
        sources = fixture_sources()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "read_json", side_effect=lambda name: sources[name]):
                output = build.build(Path(directory) / "site", today=date(2026, 10, 9))
            self.assertEqual(len(list(output.rglob("*.html"))), 4 * len(build.PAGE_IDS))
            seminar = (output / "gdt-ot-pde-ml/index.html").read_text(encoding="utf-8")
            expected = sum(len(session["talks"]) for session in sources["seminar"]["sessions"])
            self.assertEqual(sum(attrs.get("class") == "talk" for _, attrs in Elements(seminar).elements), expected)
            for session in sources["seminar"]["sessions"]:
                for talk in session["talks"]:
                    for paragraph in talk["abstract"]:
                        self.assertIn(build.html.escape(paragraph, quote=True), seminar)
            for file in output.rglob("*.html"):
                document = file.read_text(encoding="utf-8")
                self.assertIn("<!doctype html>", document.lower())
                self.assertIn("<head>", document)
                self.assertIn("<main", document)
                self.assertNotIn("{{", document)
                self.assertNotIn("{%", document)
                icons = [attrs["href"] for tag, attrs in Elements(document).elements
                         if tag == "link" and attrs.get("rel") == "icon"]
                self.assertTrue(icons[0].endswith("assets/images/favicon.png"))
                self.assertTrue(icons[1].endswith("assets/images/favicon.svg"))
                self.assertIn("class=\"brand-logo\"", document)

    def test_translated_routes_keep_every_talk_and_use_equivalent_language_links(self):
        sources = fixture_sources(seminar=seminar_fixture())
        expected_talks = sum(len(session["talks"]) for session in sources["seminar"]["sessions"])
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "read_json", side_effect=lambda name: sources[name]):
                output = build.build(Path(directory) / "site", today=date(2026, 10, 9))
            self.assertEqual(check.check_site(output), [])
            for language, folder in (("en", ""), ("en", "en/"), ("fr", "fr/"), ("it", "it/")):
                for page in sources["site"]["pages"]:
                    document = (output / folder / page["path"] / "index.html").read_text(encoding="utf-8")
                    elements = Elements(document).elements
                    self.assertIn(("html", {"lang": language}), elements)
                    canonical = [attributes["href"] for tag, attributes in elements
                                 if tag == "link" and attributes.get("rel") == "canonical"]
                    canonical_folder = folder if language != "en" else ""
                    self.assertEqual(canonical, [build.PUBLIC_URL + canonical_folder + page["path"]])
                    alternates = {attributes["hreflang"]: attributes["href"] for tag, attributes in elements
                                  if tag == "link" and attributes.get("rel") == "alternate"}
                    self.assertEqual(set(alternates), {"en", "fr", "it", "x-default"})
                    switches = [attributes for tag, attributes in elements
                                if tag == "a" and attributes.get("hreflang")]
                    self.assertEqual(len(switches), 3)
                    for switch in switches:
                        selected_folder = switch["hreflang"] + "/" if switch["hreflang"] != "en" else ""
                        target = (output / folder / page["path"] / switch["href"]).resolve()
                        self.assertEqual(target, (output / selected_folder / page["path"]).resolve())
                    if page["id"] == "seminar":
                        self.assertEqual(sum(attributes.get("class") == "talk" for _, attributes in elements), expected_talks)
                        self.assertEqual(sum(attributes.get("data-upcoming") == "true" for _, attributes in elements), 1)
                        self.assertTrue(all("open" not in attributes for tag, attributes in elements if tag == "details"))

    def test_translation_cache_updates_prose_dates_and_search_without_changing_sources(self):
        sources = build.translation_sources(fixture_sources(seminar=seminar_fixture()))
        source = sources["home"]["introduction"][0]
        cache = update_translations.empty_cache("it")
        cache["translations"] = {
            source: "Introduzione tradotta.",
            "October": "ottobre",
            "Language": "Lingua",
            "{count} members": "{count} membri",
            "{visible} of {total} members shown": "{visible} di {total} membri mostrati",
            "Seminar dates for academic year {start}–{end}": "Date del seminario per l’anno accademico {start}–{end}",
        }
        localized = update_translations.localize_sources(sources, "it", cache=cache)
        self.assertEqual(sources["home"]["introduction"][0], source)
        plan = build.plan_seminar(localized["seminar"], date(2026, 10, 9))
        page = next(item for item in localized["site"]["pages"] if item["id"] == "home")
        context = build.page_context(page, "../", localized, plan, "it", "it")
        document = build.render_document(page, "../", localized, plan, "it", "it")
        self.assertIn("Introduzione tradotta.", document)
        self.assertIn("12 ottobre 2026", document)
        self.assertIn("Alpha speaker", document)
        self.assertEqual(context["locale"]["home_href"], "../it/")
        self.assertTrue(all(link["href"].startswith("../it/") for link in context["navigation"]))
        self.assertEqual(context["programme"]["next"]["date"], "2026-10-12")
        self.assertEqual(context["programme"]["schedule_description"], "Date del seminario per l’anno accademico 2026–2027")
        page = next(item for item in localized["site"]["pages"] if item["id"] == "team")
        team = build.render_document(page, "../../", localized, plan, "it", "it")
        self.assertIn('data-count-template="{count} membri"', team)
        self.assertIn('data-filtered-template="{visible} di {total} membri mostrati"', team)

    def test_external_anchor_check_rejects_same_tab_or_missing_protection(self):
        parser = check.PageLinks()
        parser.feed('<a href="https://example.org">Bad</a>'
                    '<a href="https://example.org/ok" target="_blank" rel="noopener noreferrer">Good</a>'
                    '<a href="mailto:person@example.org">Mail</a>')
        self.assertEqual(parser.external_link_errors, ["https://example.org"])

    def test_build_cannot_overwrite_source_folders_or_repository_ancestors(self):
        for target in (build.ROOT, build.ROOT.parent, build.PAGES, build.CONTENT, build.ROOT / ".git"):
            with self.subTest(target=target), self.assertRaises(build.BuildError):
                build.build(target)


class Elements(HTMLParser):
    def __init__(self, document):
        super().__init__()
        self.elements = []
        self.feed(document)

    def handle_starttag(self, tag, attributes):
        self.elements.append((tag, dict(attributes)))


if __name__ == "__main__":
    unittest.main()
