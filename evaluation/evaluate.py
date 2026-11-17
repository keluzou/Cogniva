#!/usr/bin/env python3
"""Cogniva pilot evaluation: aggregate *human-coded* feedback annotations.

Usage: python evaluation/evaluate.py evaluation/sample_annotations.json
No API calls. This tool does NOT decide semantic validity or automatically grade AI.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

GOLD = {
    "E": {"Language": {"E-L1", "E-L2", "E-L3", "E-L4", "E-L5", "E-L6"},
          "Content": set(), "Organization": set()},
    "F": {"Language": set(), "Content": {"F-C1", "F-C2"}, "Organization": set()},
    "G": {"Language": set(), "Content": set(), "Organization": set()},
    "H": {"Language": set(), "Content": set(), "Organization": {"H-O1"}},
}
LIMITS = {"Language": 3, "Content": 2, "Organization": 1}
VALIDITY = {"valid", "borderline", "invalid"}
DIMENSIONS = set(LIMITS)


def evaluate(records):
    """Each record is one essay generation, with human labels per suggestion."""
    results = []
    for run in records:
        essay = run["essay"]
        if essay not in GOLD:
            raise ValueError(f"Unknown essay: {essay}")
        suggestions = run["suggestions"]
        seen = defaultdict(set)
        counts = defaultdict(int)
        valid = borderline = false_corrections = 0
        for item in suggestions:
            dim = item["dimension"]
            if dim not in DIMENSIONS:
                raise ValueError(f"Unknown dimension: {dim}")
            counts[dim] += 1
            label = item["validity"]
            if label not in VALIDITY:
                raise ValueError(f"Invalid human label: {label}")
            if item["type"] not in ("Correction", "Improvement"):
                raise ValueError("Invalid suggestion type")
            if not isinstance(item["false_correction"], bool):
                raise ValueError("false_correction must be boolean")
            if item["false_correction"] and item["type"] != "Correction":
                raise ValueError("False Correction flag requires Correction type")
            false_corrections += int(item["false_correction"])
            valid += label == "valid"
            borderline += label == "borderline"
            match = item.get("gold_match")
            if match:
                if label != "valid" or match not in GOLD[essay][dim]:
                    raise ValueError(f"Invalid gold match {match!r} for {essay}/{dim}")
                seen[dim].add(match)
        if any(counts[d] > LIMITS[d] for d in LIMITS):
            raise ValueError(f"Feedback exceeds 3/2/1 cap: {essay}")
        recall = {}
        for dim in LIMITS:
            gold = GOLD[essay][dim]
            # The app cannot present >3 Language targets: report raw coverage,
            # not an artificially inflated capped denominator.
            recall[dim] = None if not gold else {
                "matched": len(seen[dim]), "total": len(gold),
                "fraction": round(len(seen[dim]) / len(gold), 3)
            }
        results.append({
            "essay": essay, "version": run["version"], "run_id": run["run_id"],
            "suggestions": len(suggestions), "valid": valid,
            "borderline": borderline, "invalid": len(suggestions)-valid-borderline,
            "precision_strict": round(valid/len(suggestions), 3) if suggestions else None,
            "false_corrections": false_corrections, "priority_recall": recall,
            "same_substantive_feedback": run.get("same_substantive_feedback")
        })
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("annotations", type=Path)
    args = parser.parse_args()
    records = json.loads(args.annotations.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        parser.error("Expected a JSON array of human-annotated runs")
    print(json.dumps(evaluate(records), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
