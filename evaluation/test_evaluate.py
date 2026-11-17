"""Minimal regression tests for evaluation/evaluate.py (stdlib only)."""
import unittest

from evaluate import evaluate


class EvaluationTests(unittest.TestCase):
    def test_zero_suggestions_is_not_perfect_precision(self):
        result = evaluate([{
            "essay": "G", "version": "test", "run_id": "zero",
            "suggestions": []
        }])[0]
        self.assertIsNone(result["precision_strict"])
        self.assertIsNone(result["priority_recall"]["Language"])

    def test_false_correction_and_gold_match(self):
        result = evaluate([{
            "essay": "F", "version": "test", "run_id": "one",
            "suggestions": [
                {"dimension": "Content", "type": "Improvement",
                 "validity": "valid", "false_correction": False,
                 "gold_match": "F-C1"},
                {"dimension": "Language", "type": "Correction",
                 "validity": "invalid", "false_correction": True,
                 "gold_match": None},
            ],
        }])[0]
        self.assertEqual(result["precision_strict"], 0.5)
        self.assertEqual(result["false_corrections"], 1)
        self.assertEqual(result["priority_recall"]["Content"]["fraction"], 0.5)

    def test_reject_invalid_gold_match(self):
        with self.assertRaises(ValueError):
            evaluate([{
                "essay": "H", "version": "test", "run_id": "bad",
                "suggestions": [
                    {"dimension": "Content", "type": "Improvement",
                     "validity": "valid", "false_correction": False,
                     "gold_match": "H-O1"}
                ],
            }])

    def test_reject_excess_suggestions(self):
        with self.assertRaises(ValueError):
            evaluate([{
                "essay": "G", "version": "test", "run_id": "bad-cap",
                "suggestions": [
                    {"dimension": "Language", "type": "Improvement",
                     "validity": "valid", "false_correction": False,
                     "gold_match": None}
                    for _ in range(4)
                ],
            }])


if __name__ == "__main__":
    unittest.main()
