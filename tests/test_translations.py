"""Test translation selection and caching without installing or downloading models."""

import copy
from contextlib import nullcontext
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_translations as translations


def fixture():
    return {
        "site": {"name": "ParMA", "pages": [
            {"id": "team", "path": "team-members/", "title": "Team",
             "hero": {"lead": "Meet Mattia Garatti at Université Paris-Saclay."}},
        ], "footer": {"links": [{"label": "Université Paris-Saclay", "url": "https://example.org"}]}},
        "home": {"introduction": ["We study optimal transport."]},
        "team": {"search": {"label": "Find a member"}, "sections": [
            {"title": "Researchers", "members": [
                {"name": "Mattia Garatti", "affiliation": "Université Paris-Saclay",
                 "url": "https://mattiagaratti.github.io", "photo": "photo.jpg"},
            ]},
        ]},
        "seminar": {
            "organizers": [{"name": "Alice Example", "email": "alice@example.org"}],
            "sessions": [{"date": "2027-01-18", "room": "3L15", "talks": [
                {"speaker": "Alice Example", "title": "A scientific title",
                 "abstract": ["We study $\\lambda$ with Alice Example."]},
            ]}],
        },
        "resources": {"sections": [{"title": "Software", "items": [
            {"name": "pysdot", "kind": "Python", "description": "Python tools.",
             "url": "https://example.org", "links": [{"label": "Examples", "url": "https://example.org/code"}]},
        ]}]},
        "contact": {"contacts": [{"role": "Team leader", "name": "Alice Example",
                                   "email": "alice@example.org"}],
                    "location": {"title": "Institut de Mathématique d’Orsay",
                                 "address_lines": ["Building 307, rue Michel Magat"]}},
        "publications": {
            "title": "Recent publications", "link_label": "Read the paper",
            "empty_message": "Recent publications will appear after the next update.",
            "source_name": "HAL", "source_url": "https://hal.science",
            "items": [{"title": "Original scientific title", "authors": ["An Author"],
                       "venue": "A scientific journal", "date": "2026-10-10",
                       "url": "https://hal.science/hal-example"}],
        },
        "ui": {"member_count": "{count} members", "months": ["January", "February"]},
    }


class TranslationTests(unittest.TestCase):
    def setUp(self):
        # Unit fixtures must not depend on the site's editorial language files.
        self.real_review_loader = translations.read_reviewed
        loader = patch.object(translations, "read_reviewed", return_value={})
        loader.start()
        self.addCleanup(loader.stop)

    def test_italian_optimal_transport_term_applies_to_new_text_and_keeps_scientific_titles(self):
        title = "Trasporto Ottimale: an original scientific title"
        sources = {"home": {"introduction": ["A new discussion of optimal transport."]},
                   "publications": {"items": [{"title": title}]}}
        target = "Trasporto Ottimale; trasporto ottimale; TRASPORTO OTTIMALE; `trasporto ottimale`"
        expected = "Trasporto Ottimo; trasporto ottimo; TRASPORTO OTTIMO; `trasporto ottimale`"
        cache = translations.update_cache(sources, "it", lambda pieces: [target for _ in pieces], reviewed={})
        self.assertEqual(cache["translations"][sources["home"]["introduction"][0]], expected)
        localized = translations.localize_sources(sources, "it", cache, reviewed={})
        self.assertEqual(localized["home"]["introduction"], [expected])
        self.assertEqual(localized["publications"]["items"][0]["title"], title)
        self.assertEqual(translations.preferred_terminology(target, "fr"), target)
        self.assertEqual(translations.localize_sources(sources, "en"), sources)

    def test_reviewed_schema_preserves_placeholders_math_and_addresses(self):
        invalid = [
            {"language": "it", "translations": {}},
            {"language": "fr", "translations": {}, "unexpected": True},
            {"language": "fr", "translations": {"Team": ""}},
            {"language": "fr", "translations": {"{count} members": "{total} membres"}},
            {"language": "fr", "translations": {"{count} members": "{{count}} membres"}},
            {"language": "fr", "translations": {"$x$": "$y$"}},
            {"language": "fr", "translations": {r"C^{1, \alpha}": r"C^{1, \beta}"}},
            {"language": "fr", "translations": {"https://example.org": "https://other.org"}},
            {"language": "fr", "translations": {"a@example.org": "b@example.org"}},
        ]
        for reviewed in invalid:
            with self.subTest(reviewed=reviewed), self.assertRaises(translations.TranslationError):
                translations.validate_reviewed(reviewed, "fr")
        valid = {"language": "fr", "translations": {"{count} members": "{count} membres"}}
        self.assertEqual(translations.validate_reviewed(valid, "fr"), valid["translations"])

    def test_reviewed_text_overrides_old_cache_without_changing_english(self):
        sources = {"home": {"introduction": ["An English introduction."]}}
        cache = translations.empty_cache("fr")
        cache["translations"] = {"An English introduction.": "Old translation."}
        reviewed = {"An English introduction.": "Revised introduction."}
        localized = translations.localize_sources(sources, "fr", cache, reviewed=reviewed)
        self.assertEqual(localized["home"]["introduction"], ["Revised introduction."])
        self.assertEqual(cache["translations"]["An English introduction."], "Old translation.")
        self.assertEqual(sources["home"]["introduction"], ["An English introduction."])
        sources["home"]["introduction"] = ["A changed English introduction."]
        changed = translations.localize_sources(sources, "fr", cache, reviewed=reviewed)
        self.assertEqual(changed["home"]["introduction"], ["A changed English introduction."])
        automatic = translations.update_cache(sources, "fr", lambda pieces: ["New translation." for _ in pieces], cache, reviewed=reviewed)
        self.assertEqual(automatic["translations"]["A changed English introduction."], "New translation.")

    def test_fully_reviewed_sources_need_no_model_and_are_idempotent(self):
        sources = {"home": {"introduction": ["A complete introduction."]}, "ui": {"months": ["May"]}}
        reviewed = {"A complete introduction.": "A reviewed introduction.", "May": "Mai"}
        with patch.object(translations, "MarianTranslator", side_effect=AssertionError("Model loaded")):
            first = translations.update_cache(sources, "fr", reviewed=reviewed)
            second = translations.update_cache(sources, "fr", cache=first, reviewed=reviewed)
        self.assertEqual(first, second)
        self.assertEqual(first["translations"]["May"], "Mai")
        self.assertTrue(translations.require_complete(sources, "fr", first, reviewed=reviewed))

    def test_completeness_rejects_a_cache_that_loses_reviewed_corrections(self):
        sources = {"home": {"introduction": ["An English introduction."]}}
        cache = translations.empty_cache("fr")
        cache["translations"] = {"An English introduction.": "Old translation."}
        with self.assertRaises(translations.TranslationError):
            translations.require_complete(sources, "fr", cache, reviewed={"An English introduction.": "Reviewed translation."})

    def test_reviewed_entries_cannot_translate_scientific_titles(self):
        sources = {"publications": {"items": [{"title": "Scientific paper title"}]},
                   "seminar": {"sessions": [{"talks": [{"title": "Scientific talk title"}]}]}}
        reviewed = {"Scientific paper title": "Changed paper", "Scientific talk title": "Changed talk"}
        self.assertEqual(translations.current_reviews(sources, "fr", reviewed), {})
        self.assertEqual(translations.localize_sources(sources, "fr", reviewed=reviewed), sources)

    def test_reviewed_loader_rejects_duplicate_keys_and_missing_files_are_optional(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(translations, "CACHE_DIRECTORY", Path(directory)):
            self.assertEqual(self.real_review_loader("fr"), {})
            path = Path(directory) / "reviewed.fr.json"
            path.write_text('{"language":"fr","translations":{"Team":"A","Team":"B"}}', encoding="utf-8")
            with self.assertRaises(translations.TranslationError):
                self.real_review_loader("fr")
            path.write_text('{"language":"fr","translations":{"Team":"Equipe"}}', encoding="utf-8")
            self.assertEqual(self.real_review_loader("fr"), {"Team": "Equipe"})

    def test_allowlist_protects_bibliography_people_and_addresses(self):
        selected = translations.collect_texts(fixture())
        self.assertIn("We study optimal transport.", selected)
        self.assertIn("Examples", selected)
        self.assertIn("January", selected)
        self.assertIn("{count} members", selected)
        for value in ("Mattia Garatti", "Alice Example", "Université Paris-Saclay",
                      "photo.jpg", "A scientific title", "Original scientific title",
                      "An Author", "A scientific journal", "Building 307, rue Michel Magat"):
            self.assertNotIn(value, selected)

    def test_publication_ui_labels_translate_but_publication_records_remain_original(self):
        sources = fixture()
        selected = translations.collect_texts(sources)
        labels = {key: sources["publications"][key] for key in
                  ("title", "link_label", "empty_message")}
        for value in labels.values():
            self.assertIn(value, selected)
        cache = translations.empty_cache("it")
        cache["translations"] = {value: "Translated " + value for value in labels.values()}
        localized = translations.localize_sources(sources, "it", cache)
        for key, original in labels.items():
            self.assertEqual(localized["publications"][key], "Translated " + original)
        for key in ("items", "source_name", "source_url"):
            self.assertEqual(localized["publications"][key], sources["publications"][key])

    def test_calendar_months_use_canonical_locale_names_without_model_inference(self):
        sources = {"ui": {"months": list(translations.ENGLISH_MONTHS)}}
        for language, march, may in (("fr", "mars", "mai"), ("it", "marzo", "maggio")):
            with self.subTest(language=language):
                cache = translations.empty_cache(language)
                cache["translations"] = {"March": "Incorrect old translation", "May": "May"}
                def must_not_translate(values):
                    self.fail("Calendar names must bypass model inference.")
                updated = translations.update_cache(sources, language, must_not_translate, cache)
                localized = translations.localize_sources(sources, language, updated)
                self.assertEqual(localized["ui"]["months"][2], march)
                self.assertEqual(localized["ui"]["months"][4], may)
                self.assertTrue(translations.require_complete(sources, language, updated))

    def test_localize_returns_independent_copy_and_keeps_missing_english(self):
        sources = fixture()
        original = copy.deepcopy(sources)
        cache = translations.empty_cache("fr")
        cache["translations"] = {"Team": "Équipe", "Find a member": "Trouver un membre"}
        localized = translations.localize_sources(sources, "fr", cache)
        self.assertEqual(localized["site"]["pages"][0]["title"], "Équipe")
        self.assertEqual(localized["home"]["introduction"], sources["home"]["introduction"])
        self.assertEqual(localized["publications"], sources["publications"])
        localized["team"]["sections"][0]["members"][0]["name"] = "Changed locally"
        self.assertEqual(sources, original)

    def test_names_math_urls_code_and_ui_placeholders_bypass_inference(self):
        text = (
            "Contact Mattia Garatti via alice@example.org or https://example.org/path. "
            "Use $\\lambda^2$ and \\(x+y\\), "
            + chr(96) + "print(name)" + chr(96) + ", then show {count} members."
        )
        sources = fixture()
        sources["home"]["introduction"] = [text]
        submitted = []
        def translate(values):
            submitted.extend(values)
            return ["translated " + value for value in values]
        cache = translations.update_cache(sources, "it", translate, translations.empty_cache("it"))
        output = cache["translations"][text]
        for value in ("Mattia Garatti", "alice@example.org", "https://example.org/path.",
                      "$\\lambda^2$", "\\(x+y\\)", "print(name)", "{count}"):
            self.assertIn(value, output)
            self.assertFalse(any(value in fragment for fragment in submitted))

    def test_update_is_idempotent_and_only_changed_source_is_translated(self):
        sources = fixture()
        calls = []
        def translate(values):
            calls.append(values)
            return ["TR:" + value for value in values]
        first = translations.update_cache(sources, "fr", translate, translations.empty_cache("fr"))
        calls.clear()
        second = translations.update_cache(sources, "fr", translate, first)
        self.assertEqual(first, second)
        self.assertEqual(calls, [])
        sources["home"]["introduction"] = ["An entirely new paragraph."]
        third = translations.update_cache(sources, "fr", translate, second)
        self.assertEqual(calls, [["An entirely new paragraph."]])
        self.assertIn("We study optimal transport.", third["translations"])

    def test_bad_output_does_not_mutate_the_previous_cache(self):
        sources = fixture()
        old = translations.empty_cache("it")
        previous = copy.deepcopy(old)
        for bad in (lambda values: [], lambda values: [""] * len(values),
                    lambda values: [None] * len(values)):
            with self.subTest(bad=bad), self.assertRaises(translations.TranslationError):
                translations.update_cache(sources, "it", bad, old)
            self.assertEqual(old, previous)

    def test_malformed_ui_placeholders_and_source_fingerprint_are_rejected(self):
        cache = translations.empty_cache("fr")
        cache["translations"] = {"{count} members": "membres"}
        with self.assertRaises(translations.TranslationError):
            translations.validate_cache(cache, "fr")
        cache["translations"] = {}
        cache["source_sha256"] = "not-a-fingerprint"
        with self.assertRaises(translations.TranslationError):
            translations.validate_cache(cache, "fr")

    def test_complete_cache_is_required_in_ci(self):
        with self.assertRaises(translations.TranslationError):
            translations.require_complete(fixture(), "fr", translations.empty_cache("fr"))

    def test_absent_cache_falls_back_but_corrupt_cache_is_reported(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            translations, "CACHE_DIRECTORY", Path(directory)
        ):
            self.assertEqual(translations.read_cache("it")["translations"], {})
            (Path(directory) / "it.json").write_text('{"schema_version": 1}', encoding="utf-8")
            with self.assertRaises(translations.TranslationError):
                translations.read_cache("it")

    def test_old_engine_and_pre_version_caches_are_safely_invalidated(self):
        for old_version in (None, translations.ENGINE_VERSION - 1):
            with self.subTest(old_version=old_version):
                cache = translations.empty_cache("fr")
                cache["translations"] = {"Team": "Équipe from old engine"}
                if old_version is None:
                    del cache["engine_version"]
                else:
                    cache["engine_version"] = old_version
                validated = translations.validate_cache(cache, "fr")
                self.assertEqual(validated, translations.empty_cache("fr"))
                self.assertEqual(validated["engine_version"], translations.ENGINE_VERSION)
                self.assertIn("Team", cache["translations"])

    def test_older_model_revision_invalidates_cache(self):
        cache = translations.empty_cache("fr")
        cache["model"]["revision"] = "old"
        cache["translations"] = {"Team": "Équipe"}
        self.assertEqual(translations.validate_cache(cache, "fr")["translations"], {})

    def test_french_source_and_lorem_are_left_in_their_original_language(self):
        sources = fixture()
        prose = "Dans le cadre du transport optimal, nous proposons une mesure."
        sources["home"]["introduction"] = [prose, "Lorem ipsum dolor sit amet."]
        self.assertNotIn(prose, translations.collect_texts(sources))
        self.assertNotIn("Lorem ipsum dolor sit amet.", translations.collect_texts(sources))

    def test_failed_second_language_never_saves_first_language(self):
        with patch.object(translations, "load_sources", return_value=fixture()), patch.object(
            translations, "update_cache", side_effect=[translations.empty_cache("fr"),
                                                         translations.TranslationError("model failed")]
        ), patch.object(translations, "save_caches") as save:
            self.assertEqual(translations.main([]), 1)
            save.assert_not_called()

    def test_saving_same_cache_is_stable_and_creates_no_temporary_files(self):
        cache = translations.empty_cache("fr")
        with tempfile.TemporaryDirectory() as directory, patch.object(
            translations, "CACHE_DIRECTORY", Path(directory)
        ):
            translations.save_caches({"fr": cache})
            path = Path(directory) / "fr.json"
            initial = path.read_bytes()
            translations.save_caches({"fr": cache})
            self.assertEqual(initial, path.read_bytes())
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_punctuation_chunks_never_reach_the_model_and_keep_their_slots(self):
        submitted = []
        class FakeOutput:
            def __init__(self, texts):
                self.texts = texts
                self.shape = (len(texts), 4)
        class FakeTokenizer:
            def encode(self, text, add_special_tokens=True):
                return list(range(len(text.split()) + 1))
            def __call__(self, batch, **kwargs):
                submitted.extend(batch)
                return {"input_texts": batch}
            def batch_decode(self, output, **kwargs):
                return ["TR:" + value for value in output.texts]
        class FakeModel:
            def generate(self, input_texts, **kwargs):
                self.assert_prose(input_texts)
                return FakeOutput(input_texts)
            def assert_prose(self, texts):
                for text in texts:
                    if not any(character.isalpha() for character in text):
                        raise AssertionError("Punctuation reached inference.")
        translator = translations.MarianTranslator.__new__(translations.MarianTranslator)
        translator.tokenizer = FakeTokenizer()
        translator.model = FakeModel()
        translator.torch = SimpleNamespace(inference_mode=nullcontext)
        translator.batch_size = 1
        translator.limit = 2
        result = translator([". Alpha. ... Beta!", ". !!!"])
        self.assertEqual(result, [". TR:Alpha. ... TR:Beta!", ". !!!"])
        self.assertEqual(submitted, ["Alpha.", "Beta!"])

    def test_sentence_chunks_respect_model_input_limit_without_truncation(self):
        translator = translations.MarianTranslator.__new__(translations.MarianTranslator)
        translator.limit = 5
        translator._token_count = lambda value: len(value.split()) + 1
        text = "We study several probability measures. Another much longer sentence follows now."
        chunks = translator._chunks(text)
        self.assertTrue(all(translator._token_count(chunk) <= translator.limit for chunk in chunks))
        self.assertEqual(" ".join(chunks), text)


if __name__ == "__main__":
    unittest.main()
