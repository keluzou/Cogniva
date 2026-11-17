# Cogniva Write — Feedback Gold Standard (pilot v0.1)

Status: provisional, single-annotator reference. NOT validated ground truth or a formal reliability study.
Purpose: separate feedback **precision** (validity of generated suggestions) from **recall** (coverage of priority issues). Do not treat optional improvements as mandatory errors. Evaluation unit = distinct revision target, not sentence count.

## Annotation rules
- **Correction**: demonstrably ungrammatical or otherwise incorrect form in context. A correct alternative does not make the original wrong. Omissible complementizer *that* after *believe*, hedging changes (*are*→*can be*), and equivalent natural prepositions are NOT corrections.
- **Improvement**: text is acceptable, but a specific revision has a defensible benefit for meaning, argument, or coherence. Label priority `high` or `optional`; do not count every conceivable stylistic rewrite as a gold target.
- **Language**: grammatical correctness/lexical precision. **Content**: reasoning, support, examples, counterargument. **Organization**: placement, sequencing, connections among ideas.
- **Precision**: valid generated targets / all generated targets; report False Correction separately. A suggestion is valid only if its evidence and claimed defect are grounded in the essay, and its proposed action helps. Rate borderline cases separately.
- **Recall@3/2/1**: number of high-priority gold targets addressed / number of high-priority gold targets, by dimension, accounting for limits of 3 Language, 2 Content, 1 Organization. For Language with more than 3 gold errors, additionally report raw coverage and whether selected items span paragraphs; do NOT demand all errors under a 3-item cap.
- A generated target matches a gold target by the **underlying issue**, not exact replacement wording. Equivalent valid revisions count.
- If no high-priority gold targets exist in a dimension, report recall as N/A, not 100%.
- Blind independent second annotation and adjudication required before using these labels in research claims.

## Essay E — deliberate grammatical errors (three paragraphs)
**High-priority Language Corrections**:
1. P1: `AI tools becomes` → `AI tools become` (plural subject).
2. P1: `Many students uses` → `Many students use` (plural subject).
3. P1: `These tools can provides` → `These tools can provide` (modal + base form).
4. P2: `AI also have` → `AI also has` (singular subject).
5. P2: `This can causes` → `This can cause` (modal + base form).
6. P3: `universities should allows` → `universities should allow` (modal + base form).

**Optional**: P2 `AI is convenient.` may interrupt the risk discussion; connecting or repositioning it is a defensible Organization improvement, not a required correction.
**Valid strength**: `AI can support university learning, but students must also develop their own knowledge and skills.`
**Check**: 3/3 selected Language corrections accurate and drawn from P1/P2/P3. Do not claim all six errors were detected.

## Essay F — grammatically acceptable, underdeveloped argument
**High-priority Content Improvements**:
1. `AI can help students in many ways.` — add concrete, nonredundant example of learning benefit; existing `completing assignments` is too general to establish mechanism.
2. `Some people argue that AI may have negative effects on learning. However, I think its advantages are greater than its disadvantages.` — name a specific counterargument and explain the rebuttal, rather than asserting a balance without support.

**Organization**: the counterargument/rebuttal sequence is weak, but overlaps Content target 2; do not count the same issue twice without a distinct organization-specific action.
**Not an error**: `I believe students should be allowed to use these tools because they are useful.` (omitted *that* is grammatical). Adding *that* is at most optional style and must NEVER be `Language · Correction`.
**Not an error**: `because they are useful` → `because they can be useful` changes modality, not grammar.
**Optional Language Improvement**: `this makes university life easier` → a more precise description of assignment-related benefit; optional, not mandatory.
**Strength caution**: `AI can help students in many ways. It is also an important part of modern technology.` is NOT itself a balanced viewpoint.

## Essay G — strong, adequately supported essay
**High-priority targets**: none preidentified in Language, Content, or Organization. The example of explaining unfamiliar concepts, risks of inaccurate information, verification against academic sources, and responsible-use guidelines are already present.
**Not an error**: `If students accept every response without checking it, they may develop misunderstandings or become overly dependent on technology.`
**Unnecessary as a standalone suggestion**: `may help them understand difficult course materials` → `can help them better understand difficult course materials`.
**Valid strength**: `For example, students can ask an AI assistant to explain an unfamiliar concept in different ways.`
**Check**: zero suggestions is a valid and potentially optimal outcome. Do not calculate recall when gold target count is zero.

## Essay H — coherence / organization stress test
**High-priority Organization Improvement**:
1. P2 `Many universities are introducing new technologies into their classrooms.` disrupts a paragraph otherwise discussing dependence, independent thinking, and AI misinformation. Move it to a technology-adoption context or explicitly explain its relevance to risks. Count as one organization target.

**Optional Organization Improvement**:
2. P1 `Universities should establish clear rules for AI use.` interrupts a sequence of AI learning benefits; a more logical placement or explicit connection may improve flow. This is distinct from adding examples of rules.

**Optional Content Improvement**:
3. `Universities should establish clear rules for AI use.` — specify one or two rules. Legitimate but not the primary test target.
**Not an error**: `save time when preparing assignments` is natural. Do not change to `save time on preparing assignments` as a correction or necessary improvement.
**Valid strength**: `With appropriate guidance, AI can support learning without replacing students' own efforts.`
**Check**: omission of target 1 is a missed priority Organization issue, even if an optional Content suggestion is valid.

## Existing single-run observations (not a comparative experiment)
- v1.4.1: E 7.75/8 (4 items), F 6.25/8 (4), G 5.67/8 (3), H 6/8 (3).
- v1.5/v1.5.1: E 8/8 (3), F 6/8 (4; FALSE Correction on optional *that*), G 5/8 (1; unnecessary paraphrase), H 7/8 (1; missed priority Organization issue).
- Per-item quality averages are **not** precision/recall and are not comparable without repeated generations, stable annotation, and uncertainty estimates.

## Next evaluation protocol
1. Freeze exact essay texts, model settings, prompts, and app commit SHA for each run.
2. Sample repeated independent generations per essay/version (at least 3 as an initial pilot, not a statistical guarantee).
3. Blind-label each suggestion: valid / borderline / invalid, Correction vs Improvement, target dimension, and match to gold issue.
4. Report precision, false-correction count, priority recall by dimension, paragraph spread, and supportive/neutral substantive identity.
5. Adjudicate disagreements with a second annotator before making formal research claims.
