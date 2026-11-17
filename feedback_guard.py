"""Conservative deterministic checks for known false grammar corrections.

This is a high-precision safety filter, not a general grammar checker.
"""
import re

_BELIEVE_THAT = re.compile(r"\b(believe|think|feel|suppose)\s+that\b", re.I)


def is_known_false_correction(original, replacement):
    """Return True only for transformations that cannot justify a grammar Correction."""
    original, replacement = original.strip(), replacement.strip()
    if not original or not replacement:
        return False
    # Complementizer 'that' is optional in ordinary finite complements.
    if _BELIEVE_THAT.sub(lambda m: m.group(1), replacement).casefold() == original.casefold():
        return True
    # Appending a contextual prepositional phrase to an already complete
    # sentence does not by itself correct a grammatical error.
    if replacement.casefold().startswith(original.rstrip(".!?").casefold() + " "):
        suffix = replacement[len(original.rstrip(".!?")):].strip().rstrip(".!?")
        if re.match(r"^(among|for|in|at|with|to)\s+\w+", suffix, re.I):
            return True
    # AI is a grammatical noun phrase on its own. Expanding it to
    # "AI tools" does not repair a grammatical error.
    ai_expanded = re.sub(r"\\bAI\\b", "AI tools", original, count=1)
    if ai_expanded != original and ai_expanded.casefold() == replacement.casefold():
        return True
    # Changing certainty is not a grammatical repair.
    for source, target in (("are", "can be"), ("is", "can be"), ("may", "can")):
        changed = re.sub(r"\b" + source + r"\b", target, original, count=1, flags=re.I)
        if changed != original and changed.casefold() == replacement.casefold():
            return True
    return False


def filter_known_false_corrections(suggestions):
    """Discard only confidently identified invalid Language Corrections."""
    kept = []
    for item in suggestions:
        if (item.get("dimension") == "Language"
                and item.get("type") == "Correction"
                and is_known_false_correction(item.get("original", ""), item.get("replacement", ""))):
            continue
        kept.append(item)
    return kept
