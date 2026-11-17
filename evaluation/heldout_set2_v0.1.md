# Held-out pilot essays — Set 2 (v0.1)

These essays were authored for *future* out-of-sample checks. They were not used to tune the v1.5.6 prompts or guards. Keep them outside model prompts. Scores are not yet available.

## Essay I — correct grammar, paragraph-level topic shift (approximately 125 words)

AI tools can help university students understand difficult concepts. For example, students may use an AI assistant to compare different explanations of the same topic. These tools are available outside class hours, which can make independent study more convenient.

However, AI-generated answers are not always reliable. Students may accept incorrect explanations without checking academic sources. Many universities are investing in digital classrooms and campus networks. Teachers should therefore show students how to verify information and explain why an answer is trustworthy.

I believe universities should allow AI tools with clear guidelines. Students should acknowledge when they use AI in assignments and remain responsible for their own work. With appropriate guidance, AI can support learning while preserving independent thinking.

### Provisional gold annotation
- **I-O1 (high priority, Organization)**: `Many universities are investing in digital classrooms and campus networks.` interrupts the second paragraph's discussion of AI reliability and verification. Relocate it or explicitly connect it to that topic.
- **Language high-priority errors**: none identified. Any `Language · Correction` should receive especially careful manual review.
- **Content**: no required addition of statistics or extra examples. Optional suggestions must identify a specific benefit and avoid repeating existing support.
- **Valid strength**: `With appropriate guidance, AI can support learning while preserving independent thinking.` is a defensible qualified conclusion.
- **Caution**: This is one synthetic essay, not a representative sample.

## Essay J — genuine grammar errors across paragraphs (approximately 121 words)

AI tools is becoming common in university classrooms. Many students use them to review lectures and find explanations of difficult ideas. An AI assistant can provides useful examples when a student needs extra practice.

However, these systems sometimes gives inaccurate information. Students should not accept every answer without checking it. Teachers can show students how to compare AI responses with reliable sources. This approach also encourage students to think critically.

I believe universities should allow students to use AI for learning. Clear rules can help students understand when AI assistance is appropriate. Students should explains their own reasoning in assignments and acknowledge the support they receive. In this way, AI can be a useful resource without replacing independent work.

### Provisional gold annotation
- **J-L1 (high, Language)**: `AI tools is` → `AI tools are`.
- **J-L2 (high, Language)**: `can provides` → `can provide`.
- **J-L3 (high, Language)**: `systems sometimes gives` → `systems sometimes give`.
- **J-L4 (high, Language)**: `This approach also encourage` → `This approach also encourages`.
- **J-L5 (high, Language)**: `Students should explains` → `Students should explain`.
- **Organization high-priority targets**: none preidentified. Avoid forced sentence merging.
- **Valid strength**: `In this way, AI can be a useful resource without replacing independent work.` (correct and appropriately qualified).
- **Language selection limit**: at most 3 corrections; score their validity, across-paragraph coverage, and raw recall against all five gold errors separately.

## Evaluation procedure
1. Verify the exact deployed app version, clear researcher test cache.
2. Run each essay at least 3 independent times, saving each Neutral/Supportive pair. This is a pilot only.
3. Blind-rate each suggestion: valid, borderline, invalid; false correction; matched priority target.
4. Record precision and recall separately, and confirm feedback content is identical across conditions.
5. Do not alter the gold annotations after seeing outputs without documenting the change and rationale.
