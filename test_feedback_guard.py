"""Regression checks for the deterministic false-correction guard."""
import unittest
from feedback_guard import is_known_false_correction, filter_known_false_corrections


class GuardTests(unittest.TestCase):
    def test_optional_that(self):
        self.assertTrue(is_known_false_correction(
            "I believe students should be allowed",
            "I believe that students should be allowed"))

    def test_optional_context_not_grammar(self):
        self.assertTrue(is_known_false_correction(
            "Teachers should encourage independent thinking.",
            "Teachers should encourage independent thinking among students."))

    def test_ai_tools_expansion_is_not_grammar(self):
        self.assertTrue(is_known_false_correction(
            "AI can also help students save time when preparing assignments.",
            "AI tools can also help students save time when preparing assignments."))

    def test_real_ai_agreement_error_kept(self):
        self.assertFalse(is_known_false_correction(
            "AI have disadvantages.", "AI has disadvantages."))

    def test_real_modal_error_kept(self):
        self.assertFalse(is_known_false_correction(
            "universities should allows", "universities should allow"))

    def test_real_agreement_error_kept(self):
        self.assertFalse(is_known_false_correction(
            "AI tools becomes", "AI tools become"))

    def test_hedging_not_grammar(self):
        self.assertTrue(is_known_false_correction(
            "because they are useful", "because they can be useful"))

    def test_only_corrections_filtered(self):
        items = [
            {"dimension": "Language", "type": "Correction",
             "original": "I believe students learn",
             "replacement": "I believe that students learn"},
            {"dimension": "Language", "type": "Improvement",
             "original": "I believe students learn",
             "replacement": "I believe that students learn"},
        ]
        kept = filter_known_false_corrections(items)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["type"], "Improvement")


if __name__ == "__main__":
    unittest.main()
