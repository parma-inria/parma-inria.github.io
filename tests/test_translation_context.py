"""Exercise context translation and safe fallback without installing a model."""

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from translation_context import translate_plans


def needs_translation(text):
    return any(character.isalpha() for character in text)


def prose_piece(text):
    return (text[:len(text) - len(text.lstrip())], text.strip(), text[len(text.rstrip()):])


def translate(plans, translator):
    return translate_plans(plans, translator, needs_translation, prose_piece)


class TranslationContextTests(unittest.TestCase):
    def test_resource_name_can_move_to_natural_french_word_order(self):
        plans = {
            "Visit the SDot website": [(False, "Visit the "), (True, "SDot"), (False, " website")],
            "Visit the Geogram website": [(False, "Visit the "), (True, "Geogram"), (False, " website")],
        }
        calls = []

        def translator(requests):
            calls.append(requests)
            self.assertEqual(requests, ["Visit the ZXQ0ZXQ website"])
            return ["Découvrir le site web de ZXQ0ZXQ"]

        self.assertEqual(translate(plans, translator), {
            "Visit the SDot website": "Découvrir le site web de SDot",
            "Visit the Geogram website": "Découvrir le site web de Geogram",
        })
        self.assertEqual(len(calls), 1)
        self.assertNotIn("SDot", repr(calls))
        self.assertNotIn("Geogram", repr(calls))

    def test_math_url_email_and_name_remain_exact_without_entering_model(self):
        immutable = [r"$\lambda_{2}$", "https://example.org/a?b=2", "alice@example.org", "Alice Example"]
        plan = [(False, "Compare ")]
        for index, value in enumerate(immutable):
            plan.extend([(True, value), (False, " and " if index < 3 else ".")])
        calls = []

        def translator(requests):
            calls.extend(requests)
            return ["Avec ZXQ3ZXQ : ZXQ0ZXQ, ZXQ2ZXQ et ZXQ1ZXQ."]

        result = translate({"example": plan}, translator)["example"]
        self.assertEqual(result, f"Avec {immutable[3]} : {immutable[0]}, {immutable[2]} et {immutable[1]}.")
        for value in immutable:
            self.assertNotIn(value, repr(calls))

    def test_damaged_markers_fall_back_to_deduplicated_prose_fragments(self):
        damaged = (
            "Découvrir ZXQ0ZXQ et ZXQ0ZXQ.",
            "Découvrir le site web.",
            "Découvrir ZXQ0ZXQ et ZXQ99ZXQ.",
            "Découvrir ZXQ0ZXQ et ZXQ 99 ZXQ.",
            "Découvrir zxq0zxq.",
            "Découvrir ZXQ0ZXQ et Z X Q 99 Z X Q.",
        )
        for output in damaged:
            with self.subTest(output=output):
                plans = {
                    "sdot": [(False, "Visit the "), (True, "SDot"), (False, " website")],
                    "geogram": [(False, "Visit the "), (True, "Geogram"), (False, " website")],
                }
                calls = []

                def translator(requests):
                    calls.append(requests)
                    if len(calls) == 1:
                        self.assertEqual(requests, ["Visit the ZXQ0ZXQ website"])
                        return [output]
                    self.assertEqual(requests, ["Visit the", "website"])
                    return ["Visiter le", "site web"]

                self.assertEqual(translate(plans, translator), {
                    "sdot": "Visiter le SDot site web",
                    "geogram": "Visiter le Geogram site web",
                })
                self.assertEqual(len(calls), 2)
                self.assertNotIn("SDot", repr(calls))
                self.assertNotIn("Geogram", repr(calls))

    def test_fallback_reuses_a_fragment_already_translated_in_context_batch(self):
        plans = {
            "plain": [(False, "website")],
            "named": [(False, "Visit the "), (True, "SDot"), (False, " website")],
        }
        calls = []

        def translator(requests):
            calls.append(requests)
            if len(calls) == 1:
                self.assertEqual(requests, ["website", "Visit the ZXQ0ZXQ website"])
                return ["site web", "Broken marker"]
            self.assertEqual(requests, ["Visit the"])
            return ["Visiter le"]

        self.assertEqual(translate(plans, translator), {
            "plain": "site web", "named": "Visiter le SDot site web",
        })
        submitted = [text for batch in calls for text in batch]
        self.assertEqual(len(submitted), len(set(submitted)))

    def test_unprotected_prose_is_translated_as_a_complete_text(self):
        def translator(requests):
            self.assertEqual(requests, ["A complete sentence. Another sentence."])
            return ["  Une phrase complète. Une autre phrase.  "]

        self.assertEqual(translate({"plain": [
            (False, "\n  A complete sentence. "), (False, "Another sentence.\t"),
        ]}, translator), {"plain": "\n  Une phrase complète. Une autre phrase.\t"})

    def test_wholly_protected_or_nonprose_plans_do_not_run_inference(self):
        def translator(_):
            self.fail("No model call should be made.")

        plans = {"name": [(True, "SDot")], "math": [(False, " "), (True, "$x$"), (False, ".")],
                 "number": [(False, " 123 ")], "empty": []}
        self.assertEqual(translate(plans, translator), {
            "name": "SDot", "math": " $x$.", "number": " 123 ", "empty": "",
        })

    def test_model_response_shape_and_blank_values_are_rejected(self):
        invalid = (None, "Bonjour", [], ["Bonjour", "Extra"], [None], [""], [" \n\t"])
        for response in invalid:
            with self.subTest(response=response), self.assertRaises(ValueError):
                translate({"hello": [(False, "Hello")]}, lambda _: response)

    def test_invalid_fallback_response_is_also_rejected(self):
        calls = []

        def translator(requests):
            calls.append(requests)
            return ["Missing marker"] if len(calls) == 1 else [""]

        with self.assertRaises(ValueError):
            translate({"named": [(False, "Hello "), (True, "SDot")]}, translator)

    def test_inputs_and_translator_outputs_are_not_mutated(self):
        plans = {"named": [[False, "Visit the "], [True, "SDot"], [False, " website"]]}
        before = copy.deepcopy(plans)
        response = ["Découvrir le site web de ZXQ0ZXQ"]
        original_response = response.copy()
        self.assertEqual(translate(plans, lambda _: response)["named"], "Découvrir le site web de SDot")
        self.assertEqual(plans, before)
        self.assertEqual(response, original_response)

    def test_namespace_cannot_collide_with_protected_source_text(self):
        def translator(requests):
            self.assertEqual(requests, ["Show ZZXQ0ZZXQ."])
            return ["Afficher ZZXQ0ZZXQ."]

        self.assertEqual(translate({"literal": [(False, "Show "), (True, "ZXQ0ZXQ"), (False, ".")]}, translator),
                         {"literal": "Afficher ZXQ0ZXQ."})

    def test_invalid_plan_shapes_are_rejected_before_inference(self):
        invalid = ([], {1: []}, {"a": "text"}, {"a": [("yes", "text")]}, {"a": [(False, None)]})
        for plans in invalid:
            with self.subTest(plans=plans), self.assertRaises(ValueError):
                translate(plans, lambda _: self.fail("Invalid input must not reach inference."))


if __name__ == "__main__":
    unittest.main()
