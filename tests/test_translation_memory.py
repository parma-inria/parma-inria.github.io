"""Keep reviewed wording across source edits, terminology changes and model upgrades.

All translation calls in these tests are fake; no models or network are needed.
"""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_translations as translations


def sources_for(*paragraphs):
    return {"home": {"introduction": list(paragraphs)}}


def term(french="flot de gradient", italian="flusso di gradiente"):
    return [{"en": "gradient flow", "fr": french, "it": italian}]


class SavedReviewMigrationTests(unittest.TestCase):
    def test_real_memory_contains_valid_saved_wording_for_each_language(self):
        memory = translations.read_memory()
        for language in ("fr", "it"):
            with self.subTest(language=language):
                entries = memory["languages"][language]
                self.assertTrue(entries)
                self.assertEqual(
                    translations.validate_reviewed({"language": language, "translations": entries}, language),
                    entries,
                )
                self.assertEqual(translations.read_reviewed(language), entries)


class TranslationMemoryTests(unittest.TestCase):
    def setUp(self):
        self.memory = {"schema_version": 1, "languages": {"fr": {}, "it": {}}, "glossary": []}
        for name, callback in (
            ("read_memory", lambda: copy.deepcopy(self.memory)),
            ("read_reviewed", lambda language: copy.deepcopy(self.memory["languages"][language])),
        ):
            mocked = patch.object(translations, name, side_effect=callback)
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_model_upgrade_restores_reviews_without_loading_a_model(self):
        source = "We describe numerical methods."
        reviewed = "Nous décrivons des méthodes numériques."
        self.memory["languages"]["fr"] = {source: reviewed}
        cache = translations.empty_cache("fr")
        cache["engine_version"] -= 1
        cache["translations"] = {source: "An obsolete automatic translation."}
        original = copy.deepcopy(cache)

        with patch.object(translations, "MarianTranslator", side_effect=AssertionError("Model loaded")):
            updated = translations.update_cache(
                sources_for(source), "fr", cache=cache, glossary=[]
            )

        self.assertEqual(updated["translations"], {source: reviewed})
        self.assertEqual(updated["engine_version"], translations.ENGINE_VERSION)
        self.assertEqual(cache, original)

    def test_changed_english_gets_a_new_translation_and_other_reviews_stay(self):
        old = "We describe numerical methods."
        changed = "We describe a revised numerical method."
        stable = "We share our research."
        stable_review = "Nous partageons nos recherches."
        self.memory["languages"]["fr"] = {
            old: "Nous décrivons des méthodes numériques.", stable: stable_review,
        }
        cache = translations.empty_cache("fr")
        cache["translations"] = dict(self.memory["languages"]["fr"])
        calls = []

        def echo(pieces):
            calls.extend(pieces)
            return list(pieces)

        updated = translations.update_cache(
            sources_for(changed, stable), "fr", translator=echo, cache=cache, glossary=[]
        )

        self.assertTrue(calls)
        self.assertIn(changed, " ".join(calls))
        self.assertNotIn(stable, " ".join(calls))
        self.assertNotIn(old, " ".join(calls))
        self.assertEqual(updated["translations"][stable], stable_review)
        self.assertNotEqual(updated["translations"][changed], self.memory["languages"]["fr"][old])
        self.assertNotIn(changed, translations.current_reviews(sources_for(changed), "fr", glossary=[]))

    def test_glossary_change_updates_only_the_affected_review(self):
        affected = "A gradient flow describes evolution."
        stable = "We share our research."
        self.memory["glossary"] = term()
        self.memory["languages"]["fr"] = {
            affected: "Un flot de gradient décrit l’évolution.",
            stable: "Nous partageons nos recherches.",
        }
        cache = translations.empty_cache("fr")
        cache["translations"] = dict(self.memory["languages"]["fr"])
        cache["glossary"] = term()
        new_glossary = term(french="écoulement de gradient")

        with patch.object(translations, "MarianTranslator", side_effect=AssertionError("Model loaded")):
            updated = translations.update_cache(
                sources_for(affected, stable), "fr", cache=cache, glossary=new_glossary
            )

        self.assertEqual(updated["translations"][affected], "Un écoulement de gradient décrit l’évolution.")
        self.assertEqual(updated["translations"][stable], self.memory["languages"]["fr"][stable])
        self.assertEqual(updated["glossary"], new_glossary)
        self.assertEqual(self.memory["languages"]["fr"][affected], "Un flot de gradient décrit l’évolution.")

    def test_glossary_change_for_another_language_keeps_automatic_cache(self):
        source = "A gradient flow describes evolution."
        cases = (
            ("fr", "Un flot de gradient décrit l’évolution.", term(italian="evoluzione per gradiente")),
            ("it", "Un flusso di gradiente descrive l’evoluzione.", term(french="écoulement de gradient")),
        )
        for language, target, new_glossary in cases:
            with self.subTest(language=language):
                cache = translations.empty_cache(language)
                cache["translations"] = {source: target}
                cache["glossary"] = term()

                with patch.object(translations, "MarianTranslator", side_effect=AssertionError("Model loaded")):
                    updated = translations.update_cache(
                        sources_for(source), language, cache=cache, glossary=new_glossary
                    )

                self.assertEqual(updated["translations"], cache["translations"])
                self.assertEqual(updated["glossary"], new_glossary)

    def test_unpatchable_review_regenerates_only_its_own_source(self):
        affected = "A gradient flow describes evolution."
        stable = "We share our research."
        self.memory["glossary"] = term()
        self.memory["languages"]["fr"] = {
            affected: "Une évolution par descente décrit ce phénomène.",
            stable: "Nous partageons nos recherches.",
        }
        new_glossary = term(french="écoulement de gradient")
        sources = sources_for(affected, stable)
        reviews = translations.current_reviews(sources, "fr", glossary=new_glossary)
        self.assertNotIn(affected, reviews)
        self.assertEqual(reviews, {stable: self.memory["languages"]["fr"][stable]})
        cache = translations.empty_cache("fr")
        cache["translations"] = dict(self.memory["languages"]["fr"])
        cache["glossary"] = term()
        calls = []

        def echo(pieces):
            calls.extend(pieces)
            return list(pieces)

        updated = translations.update_cache(
            sources, "fr", translator=echo, cache=cache, glossary=new_glossary
        )

        self.assertTrue(calls)
        self.assertNotIn(stable, " ".join(calls))
        self.assertEqual(updated["translations"][stable], self.memory["languages"]["fr"][stable])
        self.assertIn("écoulement de gradient", updated["translations"][affected])

    def test_replacement_requires_complete_words_in_source_and_target(self):
        source = "A gradient flow accompanies gradient flowsheets."
        target = "Un flot de gradient accompagne des flot de gradientogrammes."
        updated = translations.adapt_review(
            source, target, "fr", sources_for(source), term(), term(french="écoulement de gradient")
        )
        self.assertEqual(updated, "Un écoulement de gradient accompagne des flot de gradientogrammes.")

        partial_source = "We document gradient flowsheets."
        self.assertEqual(
            translations.adapt_review(
                partial_source, target, "fr", sources_for(partial_source),
                term(), term(french="écoulement de gradient"),
            ),
            target,
        )

    def test_all_old_occurrences_change_even_when_the_new_term_is_already_present(self):
        source = "A gradient flow and another gradient flow describe evolution."
        target = "Un flot de gradient et un flot décrivent l’évolution."
        updated = translations.adapt_review(
            source, target, "fr", sources_for(source), term(), term(french="flot")
        )
        self.assertEqual(updated, "Un flot et un flot décrivent l’évolution.")

    def test_math_and_code_stay_unchanged_when_reviewed_prose_is_adapted(self):
        source = r"A gradient flow uses $flot de gradient$, `flot de gradient` and \(flot de gradient\)."
        target = r"Un flot de gradient utilise $flot de gradient$, `flot de gradient` et \(flot de gradient\)."
        updated = translations.adapt_review(
            source, target, "fr", sources_for(source), term(), term(french="écoulement de gradient")
        )
        self.assertEqual(
            updated,
            r"Un écoulement de gradient utilise $flot de gradient$, `flot de gradient` et \(flot de gradient\).",
        )


class OverlappingTranslationMemoryTests(unittest.TestCase):
    @staticmethod
    def terms():
        return [
            {"en": "optimal transport", "fr": "transport optimal", "it": "trasporto ottimo"},
            {"en": "semi-discrete optimal transport", "fr": "transport optimal semi-discret", "it": "trasporto ottimo semi-discreto"},
        ]

    def test_changed_shorter_term_does_not_change_an_unchanged_longer_term(self):
        previous = self.terms()
        glossary = copy.deepcopy(previous)
        glossary[0]["it"] = "trasporto OT"
        for source, target, expected in (
            ("We study optimal transport and semi-discrete optimal transport.",
             "Studiamo il trasporto ottimo e il trasporto ottimo semi-discreto.",
             "Studiamo il trasporto OT e il trasporto ottimo semi-discreto."),
            ("We study semi-discrete optimal transport and optimal transport.",
             "Studiamo il trasporto ottimo semi-discreto e il trasporto ottimo.",
             "Studiamo il trasporto ottimo semi-discreto e il trasporto OT."),
        ):
            with self.subTest(source=source):
                self.assertEqual(translations.adapt_review(
                    source, target, "it", sources_for(source), previous, glossary), expected)

    def test_changing_both_overlapping_terms_does_not_cascade_replacements(self):
        previous = self.terms()
        glossary = copy.deepcopy(previous)
        glossary[0]["it"] = "trasporto OT"
        glossary[1]["it"] = "trasporto semi-discreto"
        source = "We study optimal transport and semi-discrete optimal transport."
        target = "Studiamo il trasporto ottimo e il trasporto ottimo semi-discreto."
        self.assertEqual(translations.adapt_review(
            source, target, "it", sources_for(source), previous, glossary),
            "Studiamo il trasporto OT e il trasporto semi-discreto.")

    def test_a_changed_term_needs_its_own_winning_target_match(self):
        previous = self.terms()
        glossary = copy.deepcopy(previous)
        glossary[0]["it"] = "trasporto OT"
        source = "We study optimal transport and semi-discrete optimal transport."
        target = "Studiamo questa disciplina e il trasporto ottimo semi-discreto."
        self.assertIsNone(translations.adapt_review(
            source, target, "it", sources_for(source), previous, glossary))

    def test_shared_target_with_conflicting_preferences_regenerates(self):
        previous = [
            {"en": "gradient flow", "fr": "flux", "it": "flusso"},
            {"en": "particle method", "fr": "flux", "it": "flusso"},
        ]
        glossary = copy.deepcopy(previous)
        glossary[0]["fr"] = "flot de gradient"
        source = "A gradient flow uses a particle method."
        self.assertIsNone(translations.adapt_review(
            source, "Un flux utilise un flux.", "fr", sources_for(source), previous, glossary))

    def test_shared_target_with_the_same_new_preference_is_unambiguous(self):
        previous = [
            {"en": "gradient flow", "fr": "flux", "it": "flusso"},
            {"en": "particle method", "fr": "flux", "it": "flusso"},
        ]
        glossary = copy.deepcopy(previous)
        for row in glossary:
            row["fr"] = "flot"
        source = "A gradient flow uses a particle method."
        self.assertEqual(translations.adapt_review(
            source, "Un flux utilise un flux.", "fr", sources_for(source), previous, glossary),
            "Un flot utilise un flot.")

    def test_new_target_shorter_than_old_target_replaces_all_old_occurrences(self):
        previous = term()
        glossary = term(french="flot")
        source = "A gradient flow and a gradient flow describe evolution."
        target = "Un flot de gradient et un flot décrivent l’évolution."
        self.assertEqual(translations.adapt_review(
            source, target, "fr", sources_for(source), previous, glossary),
            "Un flot et un flot décrivent l’évolution.")

    def test_target_ui_placeholders_and_naked_tex_remain_immutable(self):
        previous = term(french="count")
        glossary = term(french="flot")
        source = r"A gradient flow uses {count}, \count{count} and x^{count}."
        target = r"Un count utilise {count}, \count{count} et x^{count}."
        self.assertEqual(translations.adapt_review(
            source, target, "fr", sources_for(source), previous, glossary),
            r"Un flot utilise {count}, \count{count} et x^{count}.")


if __name__ == "__main__":
    unittest.main()
