"""Paragraph-level organization feedback validation.

An independent review is useful because content expansion and sentence
rewriting can mask a genuinely misplaced sentence. No hard-coded essay text.
"""

import re


def organization_audit_prompt():
    return (
        "You are a skeptical EFL writing ORGANIZATION auditor. Read the entire "
        "essay paragraph by paragraph. Identify the central topic of each "
        "paragraph, then inspect whether any sentence interrupts its topic or "
        "appears better suited to another paragraph. Return ONLY JSON: "
        '{"issue": null} if there is no meaningful coherence issue, or '
        '{"issue": {"dimension":"Organization","type":"Improvement",'
        '"category":"Paragraph coherence","original":"EXACT ESSAY QUOTE",'
        '"replacement":"ACTIONABLE REVISION INSTRUCTION",'
        '"explanation":"WHY THIS SENTENCE DISRUPTS THE PARAGRAPH"}}. '
        "Prefer a genuine misplaced sentence over a minor optional transition. "
        "Do not recommend merging two sentences merely because a combined "
        "sentence would also be grammatical. Do not mistake lack of supporting "
        "examples for a paragraph-placement issue. Never invent a problem. "
        "Check the actual sentence position before suggesting relocation. "
        "Never ask to move the opening sentence to the beginning of the essay. "
        "The original MUST be an exact nonempty substring of the essay."
    )


def validate_organization_issue(essay, issue):
    """Reject malformed/unsupported candidates; semantic validity needs review."""
    if not isinstance(issue, dict):
        return None
    fields = ("dimension", "type", "category", "original", "replacement", "explanation")
    if any(not isinstance(issue.get(k), str) or not issue[k].strip() for k in fields):
        return None
    if issue["dimension"] != "Organization" or issue["type"] != "Improvement":
        return None
    if issue["original"] not in essay:
        return None
    if issue["original"] == issue["replacement"]:
        return None
    # Prevent an objectively impossible relocation. An opening sentence
    # cannot be moved to the beginning of the essay: it is already there.
    source_position = essay.find(issue["original"])
    action = issue["replacement"].lower()
    if (not essay[:source_position].strip()
            and re.search(
                r"\b(move|relocate|place|put|shift)\b", action
            )
            and re.search(
                r"\b(beginning|start|opening|first sentence)\b"
                r".{0,30}\b(essay|text|introduction)\b"
                r"|\b(essay|text|introduction)\b"
                r".{0,30}\b(beginning|start|opening)\b",
                action
            )):
        return None
    return issue
