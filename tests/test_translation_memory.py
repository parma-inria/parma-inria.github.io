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


if __name__ == "__main__":
    unittest.main()
