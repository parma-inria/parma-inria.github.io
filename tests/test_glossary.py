"""Test reusable terminology without loading translation models."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import translation_glossary as glossary
from update_translations import protected_segments


def terms():
    """Keep test preferences independent of the team's editable glossary."""
    return [
        {"en": "optimal transport", "fr": "transport optimal", "it": "trasporto ottimo"},
        {"en": "semi-discrete optimal transport", "fr": "transport optimal semi-discret", "it": "trasporto ottimo semi-discreto"},
        {"en": "Wasserstein distance", "fr": "distance de Wasserstein", "it": "distanza di Wasserstein"},
        {"en": "Wasserstein distances", "fr": "distances de Wasserstein", "it": "distanze di Wasserstein"},
        {"en": "gradient flows", "fr": "flots de gradient", "it": "flussi di gradiente"},
        {"en": "machine learning", "fr": "apprentissage automatique", "it": "apprendimento automatico"},
    ]


class GlossaryTests(unittest.TestCase):
    def render(self, text, language="it", sources=None, entries=None):
        plan = glossary.terminology_segments(
            text, sources or {}, language, protected_segments,
            glossary=terms() if entries is None else entries,
        )
        return "".join(part for _, part in plan)

    def test_schema_rejects_empty_invalid_duplicate_and_immutable_terms(self):
        invalid = [
            {}, [{"en": "x", "fr": "y", "it": "z", "de": "a"}],
            [{"en": "x", "fr": "", "it": "z"}],
            [{"en": 2, "fr": "y", "it": "z"}],
            [{"en": "x", "fr": "$y$", "it": "z"}],
            [{"en": "https://example.org", "fr": "a", "it": "b"}],
            [{"en": "{count}", "fr": "a", "it": "b"}],
            [terms()[0], {"en": " OPTIMAL   TRANSPORT ", "fr": "autre", "it": "altro"}],
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(glossary.GlossaryError):
                glossary.validate_glossary(value)
        original = [{"en": " optimal   transport ", "fr": "transport optimal", "it": "trasporto ottimo"}]
        normalized = glossary.validate_glossary(original)
        self.assertEqual(normalized[0]["en"], "optimal transport")
        self.assertEqual(original[0]["en"], " optimal   transport ")

    def test_reader_rejects_duplicate_json_fields_and_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "glossary.json"
            with self.assertRaises(glossary.GlossaryError):
                glossary.read_glossary(path)
            path.write_text('[{"en":"x","en":"y","fr":"z","it":"a"}]', encoding="utf-8")
            with self.assertRaises(glossary.GlossaryError):
                glossary.read_glossary(path)
            path.write_text('[{"en":"x","fr":"y","it":"z"}]', encoding="utf-8")
            self.assertEqual(glossary.read_glossary(path), [{"en": "x", "fr": "y", "it": "z"}])

    def test_longest_whole_phrase_wins_and_unchanged_text_keeps_its_order(self):
        source = "We study semi-discrete optimal transport and optimal transport."
        self.assertEqual(self.render(source), "We study trasporto ottimo semi-discreto and trasporto ottimo.")
        self.assertEqual(self.render("optimal transportation"), "optimal transportation")
        self.assertEqual(self.render("optimal\n transport", "fr"), "transport optimal")
        matched = glossary.matched_terms(source, {}, protected_segments, terms())
        self.assertEqual([entry["en"] for entry in matched], ["semi-discrete optimal transport", "optimal transport"])
        self.assertEqual(len(glossary.matched_terms("optimal transport and optimal transport", {}, protected_segments, terms())), 1)
        self.assertEqual(self.render(source, "en"), source)

    def test_uppercase_and_heading_case_follow_the_english_source(self):
        examples = {
            "OPTIMAL TRANSPORT": "TRASPORTO OTTIMO",
            "Optimal Transport": "Trasporto ottimo",
            "Optimal transport": "Trasporto ottimo",
            "optimal transport": "trasporto ottimo",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(self.render(source), expected)

    def test_eponym_inside_a_glossary_phrase_remains_an_immutable_name(self):
        examples = {
            "Wasserstein distance": "distanza di Wasserstein",
            "Wasserstein distances": "distanze di Wasserstein",
            "Wasserstein Distance": "Distanza di Wasserstein",
            "WASSERSTEIN DISTANCE": "DISTANZA DI WASSERSTEIN",
            "wasserstein distance": "distanza di wasserstein",
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(self.render(source), expected)

    def test_math_code_urls_emails_and_placeholders_are_not_glossary_input(self):
        immutable = [
            "$optimal transport$", "$$optimal transport$$",
            r"\(optimal transport\)", r"\[optimal transport\]",
            "`gradient flows`", "```machine learning```",
            "https://example.org/optimal transport", "alice@example.org", "{count}",
        ]
        for source in immutable:
            with self.subTest(source=source):
                self.assertEqual(self.render(source), source)
        source = "Use $optimal transport$ and optimal transport."
        self.assertEqual(self.render(source), "Use $optimal transport$ and trasporto ottimo.")

    def test_glossary_cannot_change_or_partially_replace_a_protected_person(self):
        sources = {"team": {"sections": [{"members": [{"name": "Alice Sample", "affiliation": ""}]}]}}
        partial = [{"en": "Sample", "fr": "échantillon", "it": "campione"}]
        changed_name = [{"en": "Alice Sample methods", "fr": "méthodes d'une personne", "it": "metodi di una persona"}]
        for entries, source in ((partial, "Alice Sample"), (changed_name, "Alice Sample methods")):
            self.assertEqual(self.render(source, sources=sources, entries=entries), source)
            self.assertEqual(glossary.matched_terms(source, sources, protected_segments, entries), [])

    def test_fingerprints_ignore_row_order_and_unrelated_target_languages(self):
        original = terms()
        changed = copy.deepcopy(original)
        changed[0]["it"] = "trasporto ottimale"
        self.assertEqual(glossary.glossary_fingerprint(original), glossary.glossary_fingerprint(list(reversed(original))))
        self.assertEqual(glossary.glossary_fingerprint(original, "fr"), glossary.glossary_fingerprint(changed, "fr"))
        self.assertNotEqual(glossary.glossary_fingerprint(original, "it"), glossary.glossary_fingerprint(changed, "it"))
        with self.assertRaises(glossary.GlossaryError):
            glossary.glossary_fingerprint(original, "de")


if __name__ == "__main__":
    unittest.main()
