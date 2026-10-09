"""Validate the small page language and preservation of complete site content."""

import json
import sys
import tempfile
import unittest
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build
from test_seminar import fixture_sources, render_page, seminar_fixture


class TemplateTests(unittest.TestCase):
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

    def test_complete_build_keeps_routes_data_and_real_team_logo(self):
        sources = fixture_sources()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(build, "read_json", side_effect=lambda name: sources[name]):
                output = build.build(Path(directory) / "site", today=date(2026, 10, 9))
            self.assertEqual(len(list(output.rglob("*.html"))), 8)
            seminar = (output / "francais-gdt-edp-ot-ml/index.html").read_text(encoding="utf-8")
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
                self.assertTrue(icons[0].endswith("assets/images/parma-logo.png"))
                self.assertIn("class=\"brand-logo\"", document)

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
