
import csv
import hashlib
import hmac
import io
import json
import random
import uuid
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st
from feedback_guard import filter_known_false_corrections

st.set_page_config(page_title="Cogniva Write", page_icon="📝")

def db_request(method, path, payload=None):
    """Supabase REST calls are server-side only; never expose the secret key."""
    # Accept either the Supabase project URL or the full Data API URL.
    base_url = str(st.secrets["SUPABASE_URL"]).strip().rstrip("/")
    if base_url.endswith("/rest/v1"):
        base_url = base_url[:-len("/rest/v1")]
    url = base_url + "/rest/v1/" + path
    key = st.secrets["SUPABASE_KEY"]
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Prefer"] = "return=minimal,resolution=ignore-duplicates"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=15) as response:
        body = response.read()
        return json.loads(body) if body else []



def openai_response(instructions, text):
    """Generate text server-side using the Responses API."""
    api_key = str(st.secrets["OPENAI_API_KEY"]).strip()
    if not api_key:
        raise ValueError("Missing API key")
    payload = {
        "model": "gpt-4.1-mini",
        "instructions": instructions,
        "input": text,
        "max_output_tokens": 2400,
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=90) as response:
        result = json.loads(response.read())
    if result.get("status") != "completed":
        raise ValueError("AI response incomplete")
    parts = [
        part.get("text", "")
        for item in result.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    ]
    answer = "\n".join(parts).strip()
    if not answer:
        raise ValueError("Empty AI response")
    return answer


def _generate_feedback_core_once(essay):
    """Create an evidence-grounded feedback core across three dimensions."""
    instructions = (
        "You are an EFL writing tutor. Return ONLY JSON with keys strength_quote, "
        "strength_explanation, suggestions. strength_quote is an exact substring "
        "of the essay. Praise a genuine strength without exaggeration. "
         "suggestions is an array of 0 to 11 candidate objects, each with keys dimension, "
         "category, type, original, replacement, explanation. Type must be exactly "
        "Correction or Improvement. Correction means a demonstrably incorrect "
        "form; Improvement means an acceptable passage with a specific, justified "
         "opportunity to improve it. A grammatical sentence is NEVER a Correction. "
        "Do not treat hedging (may/can), stylistic confidence, or equivalent "
        "prepositions as errors. If a Language Improvement is merely an "
        "alternative phrasing with no concrete gain in clarity or precision, "
        "omit it. Zero Language suggestions is acceptable. "
        "Dimension must be exactly "
        "Language, Content, or Organization. Identify up to 8 distinct Language candidates across the ENTIRE essay, "
        "including later paragraphs and different error categories; the app "
        "will select at most 3. Use at most 2 Content, "
        "and 1 Organization suggestions. Do not invent issues to fill quotas. "
        "Every original must be a verbatim, concise, nonempty substring of the essay. "
        "For Language, replacement must be a correct replacement for original in context. "
        "For Content and Organization, replacement must be a specific, actionable "
        "revision instruction, NOT a fabricated quote or a full rewritten essay. "
        "Explain the specific issue and what successful revision would achieve. "
          "Read the FULL essay before requesting supporting examples or details. "
        "Do not request evidence already present elsewhere in the essay. "
        "For 100-150 word essays, do not demand statistics for ordinary "
        "background claims. Organization feedback must identify an actual "
        "break in logic or misplaced idea; do not suggest adding a transition "
        "when the logical connection is already clear. "
        "Each suggestion must target one distinct issue and avoid overlap, even "
        "if two quotes differ. Do not give two suggestions that ask for the same "
        "examples or reasons. Organization suggestions must identify a genuine "
        "logical-order or cohesion issue; do not request a longer conclusion "
        "just because it is short, especially for a 100-150 word essay. "
        "If a text is grammatically correct but weakly argued, give specific "
        "Content suggestions rather than inventing grammar mistakes. "
        "Select a meaningful writing strength showing a balanced position, "
        "specific support, reasoning, or effective structure. Avoid trivial "
        "generic claims such as AI is convenient. "
        "Choose a strength_quote that is grammatically correct whenever "
        "possible. If no such quote exists, explicitly praise the IDEA rather "
        "than language correctness, and acknowledge that the wording needs "
        "editing. Never describe an erroneous sentence as well written. "
        "Modal verbs take the base verb form. Return no markdown."
    )
    draft = openai_response(instructions, essay)
    reviewed = openai_response(
        "Independently review this EFL essay and draft JSON. Return ONLY corrected "
        "JSON with EXACTLY the same schema: strength_quote, strength_explanation, "
         "suggestions (array of 0 to 11 candidates with dimension, category, original, "
         "replacement, explanation, type). type is Correction or Improvement. "
         "Act as a skeptical quality auditor: DELETE unnecessary changes even "
        "if this leaves zero suggestions. Confirm each Language Correction "
        "fixes an actual grammatical error, not merely a change in certainty, "
        "style, or phrasing. Reject changes from correct may to can or "
        "natural when preparing to on preparing without a specific error. "
        "Verify verbatim source quotes and correctness. Never treat an optional "
        "wording change as a Correction. Remove overlapping Content advice, "
         "and avoid generic requests to expand an adequate short conclusion. "
        "For Organization, describe the coherence problem and the desired "
        "relationship, not a mandatory technique such as combining sentences. "
         "Preserve up to 8 distinct Language candidates from throughout the essay; "
        "the application selects at most 3 across paragraphs and categories. "
        "Keep at most 2 Content and 1 Organization items. "
        "Do not select a trivial fact as the main writing strength. Prefer "
        "a meaningful claim, nuanced stance, reasoning, or concrete example. "
        "Choose a grammatically correct strength_quote if possible; otherwise "
        "praise only the idea and explicitly acknowledge language errors. "
         "Before suggesting Content evidence, search the entire essay for "
        "existing examples or explanations. Before suggesting Organization "
        "changes, verify there is an actual cohesion problem. "
        "Remove invented, redundant, vague, or unsupported items. For Content and "
        "Organization, replacement must be an actionable revision instruction, "
        "not a rewritten essay. Never force a quota.",
        "ORIGINAL ESSAY:\n" + essay + "\n\nDRAFT JSON:\n" + draft,
    )
    try:
        data = json.loads(reviewed)
    except json.JSONDecodeError as exc:
        raise ValueError("Feedback is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("suggestions"), list):
        raise ValueError("Invalid feedback structure")
    # A targeted second pass finds genuine language errors in paragraphs
    # missed by the full-essay reviewer. This is only needed when coverage
    # is concentrated in one paragraph.
    paragraph_texts = [p for p in essay.split("\n\n") if p.strip()]
    existing_language = [
        item for item in data["suggestions"]
        if isinstance(item, dict) and item.get("dimension") == "Language"
    ]
    covered = {
        next((i for i, paragraph in enumerate(paragraph_texts)
              if item.get("original", "") in paragraph), -1)
        for item in existing_language
    }
    if len(paragraph_texts) > 1 and len(covered - {-1}) < min(3, len(paragraph_texts)):
        missing = [
            {"paragraph": i + 1, "text": paragraph}
            for i, paragraph in enumerate(paragraph_texts)
            if i not in covered
        ]
        extra = openai_response(
            "Check ONLY the provided paragraphs for genuine grammatical errors. "
            "Return ONLY a JSON object with suggestions: a list of zero to six "
            "objects with exactly dimension ('Language'), type ('Correction'), "
            "category, original, replacement, explanation. Each original must "
            "be an exact substring of its paragraph, replacement must be "
            "grammatically correct in context. No optional style edits. "
            "Prefer different error categories. Do not invent errors.",
            json.dumps(missing, ensure_ascii=False),
        )
        try:
            extra_data = json.loads(extra)
            extras = extra_data.get("suggestions", [])
            if isinstance(extras, list):
                existing_quotes = {
                    item.get("original") for item in data["suggestions"]
                    if isinstance(item, dict)
                }
                for item in extras:
                    if (isinstance(item, dict)
                            and item.get("dimension") == "Language"
                            and item.get("type") == "Correction"
                            and isinstance(item.get("original"), str)
                            and item["original"] in essay
                            and all(isinstance(item.get(field), str)
                                    and item[field].strip()
                                    for field in ("category", "original",
                                                  "replacement", "explanation"))
                            and item["original"] != item["replacement"]
                            and item["original"] not in existing_quotes):
                        data["suggestions"].append(item)
                        existing_quotes.add(item["original"])
        except (ValueError, TypeError, AttributeError):
            pass  # Retain the independently reviewed core if supplement is invalid.
    # Select language targets from across the essay, not simply the first three.
    # Selection is deterministic for the same reviewed feedback core.
    limits = {"Language": 3, "Content": 2, "Organization": 1}
    paragraphs = [p for p in essay.split("\n\n") if p.strip()]
    def paragraph_index(evidence):
        position = essay.find(evidence)
        if position < 0:
            return len(paragraphs)
        return essay[:position].count("\n\n")

    # Incomplete optional AI suggestions must not abort a valid essay.
    # Discard them before selection, preserving the strict checks below.
    required = ("dimension", "category", "type", "original",
                "replacement", "explanation")
    candidates = [
        item for item in data["suggestions"]
        if isinstance(item, dict)
        and item.get("dimension") in limits
        and item.get("type") in ("Correction", "Improvement")
        and all(isinstance(item.get(field), str) and item[field].strip()
                for field in required)
        and item["original"] in essay
        and item["original"] != item["replacement"]
    ]
    candidates = filter_known_false_corrections(candidates)
    language = [item for item in candidates if item["dimension"] == "Language"]
    # Round-robin by paragraph, preferring different categories where available.
    buckets = {}
    for item in language:
        buckets.setdefault(paragraph_index(item.get("original", "")), []).append(item)
    chosen_language = []
    used_categories = set()
    while len(chosen_language) < limits["Language"] and any(buckets.values()):
        for paragraph in sorted(buckets):
            if len(chosen_language) >= limits["Language"]:
                break
            pool = buckets[paragraph]
            if not pool:
                continue
            index = next((i for i, candidate in enumerate(pool)
                          if candidate.get("category", "").lower() not in used_categories), 0)
            picked = pool.pop(index)
            chosen_language.append(picked)
            used_categories.add(picked.get("category", "").lower())
    chosen_ids = {id(item) for item in chosen_language}
    counts = {"Language": 0, "Content": 0, "Organization": 0}
    selected = []
    for item in candidates:
        dimension = item["dimension"]
        if dimension == "Language":
            if id(item) not in chosen_ids:
                continue
        elif counts[dimension] >= limits[dimension]:
            continue
        selected.append(item)
        counts[dimension] += 1
    suggestions = selected
    data["suggestions"] = suggestions
    quote = data.get("strength_quote")
    explanation = data.get("strength_explanation")
    if not isinstance(quote, str) or not quote.strip() or quote not in essay:
        raise ValueError("Strength evidence not found in essay")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Missing strength explanation")
    seen = set()
    import re
    for item in suggestions:
        if not isinstance(item, dict):
            raise ValueError("Invalid feedback item")
        for field in ("dimension", "category", "type", "original", "replacement", "explanation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("Incomplete feedback item")
        if item["type"] not in ("Correction", "Improvement"):
            raise ValueError("Unknown feedback type")
        dimension = item["dimension"]
        if dimension not in counts:
            raise ValueError("Unknown feedback dimension")
        original = item["original"]
        if original not in essay or original in seen:
            raise ValueError("Missing or duplicate feedback evidence")
        seen.add(original)
        if dimension == "Language":
            if original == item["replacement"]:
                raise ValueError("Unchanged language correction")
            pattern = re.compile(r"\\b(can|could|should|would|will|shall|may|might|must)\\s+([A-Za-z]+)\\b", re.I)
            for match in pattern.finditer(original):
                corrected = re.search(r"\\b" + re.escape(match.group(1)) + r"\\s+([A-Za-z]+)\\b", item["replacement"], re.I)
                source_verb = match.group(2)
                if (corrected and source_verb.lower().endswith("s")
                        and source_verb[:-1].lower() == corrected.group(1).lower()):
                    item["category"] = "modal + base verb"
                    item["explanation"] = (
                        f"After the modal verb '{match.group(1).lower()}', use the base "
                        f"form '{corrected.group(1)}' rather than '{source_verb}'."
                    )
                    break
    return data


def generate_feedback_core(essay):
    """Retry malformed or invalid feedback once."""
    last_error = None
    for _ in range(2):
        try:
            return _generate_feedback_core_once(essay)
        except (ValueError, KeyError, TypeError) as exc:
            last_error = exc
    raise ValueError(f"Feedback validation failed after two attempts: {last_error}") from last_error


def format_feedback_core(data):
    """Render identical substantive revision advice in both conditions."""
    lines = [
        "Writing strength:",
        data["strength_explanation"] + ' Example: "' + data["strength_quote"] + '"',
        "",
        "Revision suggestions:",
        "",
    ]
    if not data["suggestions"]:
        lines.append("No specific revision targets identified.")
    for i, item in enumerate(data["suggestions"], 1):
        if item["dimension"] == "Language":
            advice = f'Replace "{item["original"]}" with "{item["replacement"]}".'
        else:
            advice = f'Evidence: "{item["original"]}". Action: {item["replacement"]}'
        lines.append(
            f'{i}. [{item["dimension"]} · {item["type"]}] {item["category"]}: '
            f'{advice} {item["explanation"]}'
        )
    return "\n".join(lines)


def style_feedback(core, condition):
    """Only praise/closing vary; all corrections are rendered identically."""
    factual = format_feedback_core(core)
    if condition == "neutral":
        return factual
    import re
    # Retry only the supportive wrapper; never regenerate the shared feedback core.
    advice_pattern = re.compile(
        r"\\b(consider|try to|you (?:could|should|might)|add|expand|explain|"
        r"clarify|reorganize|include|provide|revise|focus on|work on|improve by)\\b",
        re.I,
    )
    last_error = None
    for _ in range(3):
        try:
            praise = openai_response(
                "Return ONLY a JSON object with two short string fields: opening "
                "and closing. Opening should warmly celebrate ONLY the documented "
                "writing strength using its exact quote. Closing should ONLY "
                "express emotional encouragement (e.g., 'You've got this!'). "
                "Use 4-7 friendly emojis across both fields. No additional "
                "revision advice, instructions, or factual claims. No markdown.",
                json.dumps({
                    "strength_quote": core["strength_quote"],
                    "strength_explanation": core["strength_explanation"],
                }, ensure_ascii=False),
            )
            parts = json.loads(praise)
            opening, closing = parts["opening"], parts["closing"]
            if not all(isinstance(v, str) and v.strip() for v in (opening, closing)):
                raise ValueError("Empty supportive wording")
            if advice_pattern.search(opening) or advice_pattern.search(closing):
                raise ValueError("Supportive wording contains additional revision advice")
            break
        except (ValueError, KeyError, TypeError) as exc:
            last_error = exc
    else:
        raise ValueError("Supportive wording validation failed") from last_error
    corrections = factual.split("Revision suggestions:", 1)[1]
    return "Writing strength:\n" + opening + "\n\nRevision suggestions:" + corrections + "\n\n" + closing


def generate_writing_feedback(essay, condition):
    return style_feedback(generate_feedback_core(essay), condition)


def admin_panel():
    st.subheader("Researcher Dashboard")
    if not all(k in st.secrets for k in ("SUPABASE_URL", "SUPABASE_KEY", "ADMIN_PASSWORD")):
        st.error("The researcher dashboard is not configured.")
        return
    if not st.session_state.get("admin_authenticated", False):
        with st.form("admin_login"):
            password = st.text_input("Administrator password", type="password")
            login = st.form_submit_button("Sign in")
        if login:
            if hmac.compare_digest(password.encode("utf-8"), str(st.secrets["ADMIN_PASSWORD"]).encode("utf-8")):
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
        return
    if st.button("Sign out"):
        st.session_state.admin_authenticated = False
        st.session_state.researcher_test_mode = False
        st.query_params["view"] = "researcher"
        st.rerun()
    st.divider()
    st.subheader("Researcher Test Mode")
    st.caption("Test mode is available only after administrator sign-in in this browser session.")
    if st.button("Start researcher test", type="primary"):
        st.session_state.researcher_test_mode = True
        st.session_state.stage = 1
        st.session_state.initial_data = {}
        st.session_state.feedback_condition = None
        st.session_state.feedback_text = ""
        st.session_state.pop("pending_record_id", None)
        st.query_params["view"] = "test"
        st.rerun()
    try:
        rows = db_request(
            "GET",
            "writing_submissions?select=*&order=created_at.desc&limit=1000",
        )
    except HTTPError as exc:
        # Display only allowlisted Supabase error fields, never raw responses or headers.
        error_code = "unknown"
        try:
            error_body = json.loads(exc.read().decode("utf-8"))
            if isinstance(error_body, dict):
                candidate = error_body.get("code")
                if isinstance(candidate, str) and len(candidate) <= 32 and candidate.replace("_", "").isalnum():
                    error_code = candidate
        except (ValueError, UnicodeError, OSError):
            pass
        st.error(f"Database request failed (HTTP {exc.code}; error code: {error_code}).")
        if error_code == "PGRST205":
            st.caption("Supabase cannot find writing_submissions in its API schema cache. Check table exposure and schema.")
        elif exc.code == 404:
            st.caption("The requested API endpoint or table was not found.")
        elif exc.code in (401, 403):
            st.caption("Check the server-side API key and database access permissions.")
        return
    except (URLError, TimeoutError):
        st.error("Database connection failed (network or timeout).")
        return
    except (KeyError, ValueError, TypeError):
        st.error("Database configuration or response format error.")
        return
    st.write(f"Showing {len(rows)} most recent submissions (maximum 1,000).")
    if not rows:
        st.info("No submissions yet.")
        return
    st.dataframe(
        [
            {
                "Participant ID": row.get("participant_id"),
                "Submitted": row.get("created_at"),
                "Condition": row.get("feedback_condition"),
                "Record type": "TEST" if str(row.get("feedback_type", "")).endswith("_test") else "Other",
            }
            for row in rows
        ],
        hide_index=True,
        use_container_width=True,
    )
    st.caption("Essay text is hidden in the overview. Downloads contain full responses.")
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    st.download_button(
        "Download submissions (CSV)",
        data=output.getvalue().encode("utf-8-sig"),
        file_name="cogniva_submissions.csv",
        mime="text/csv",
    )


# Stable researcher navigation: keep the view in the URL across refreshes.
view = st.query_params.get("view", "")
if st.query_params.get("admin") == "1":
    st.query_params["view"] = "researcher"
    del st.query_params["admin"]
    view = "researcher"

with st.sidebar:
    st.markdown("### Cogniva Write")
    if st.button("Participant writing", use_container_width=True):
        st.session_state.researcher_test_mode = False
        st.query_params["view"] = "participant"
        st.rerun()
    if st.button("Researcher Login / Dashboard", use_container_width=True):
        st.query_params["view"] = "researcher"
        st.rerun()
    if st.session_state.get("admin_authenticated", False):
        if st.button("Researcher Test Mode", use_container_width=True):
            st.session_state.researcher_test_mode = True
            st.query_params["view"] = "test"
            st.rerun()

if view == "researcher":
    st.title("Cogniva Write")
    admin_panel()
    st.stop()

if view == "test":
    if not st.session_state.get("admin_authenticated", False):
        st.title("Cogniva Write")
        st.info("Please sign in to access Researcher Test Mode.")
        admin_panel()
        st.stop()
    st.session_state.researcher_test_mode = True
else:
    st.session_state.researcher_test_mode = False

TOPIC = "Should university students use AI tools to support their learning?"

# Prototype feedback only. Not generated by AI.
SUPPORTIVE_FEEDBACK = (
    "You've made a great start by completing your argument about AI in "
    "education! It's encouraging to see you working on an important topic. "
    "Now, review whether your main opinion is clearly stated and whether "
    "each reason is supported by a specific example. Check the organization "
    "of your paragraph, and look carefully at grammar and word choice. "
    "These improvements can make your argument clearer and more convincing. "
    "Keep going! You have a valuable opportunity to strengthen your writing "
    "through this revision."
)

NEUTRAL_FEEDBACK = (
    "The paragraph addresses the topic of AI in education. The revision "
    "should focus on whether the main opinion is clearly stated and whether "
    "each reason is supported by a specific example. Review the organization "
    "of the paragraph and check grammar and word choice. These changes can "
    "improve the clarity of the argument and the accuracy of its expression. "
    "The revision should address the identified areas and maintain a "
    "consistent position throughout the paragraph."
)

FIELDS = [
    "record_id",
    "timestamp",
    "participant_id",
    "feedback_condition",
    "feedback_type",
    "feedback_text",
    "feedback_word_count",
    "initial_essay",
    "initial_word_count",
    "initial_score",
    "initial_confidence",
    "revised_essay",
    "revised_word_count",
    "revised_score",
    "revised_confidence",
]

if "stage" not in st.session_state:
    st.session_state.stage = 1

if "initial_data" not in st.session_state:
    st.session_state.initial_data = {}

if "feedback_condition" not in st.session_state:
    st.session_state.feedback_condition = None

if "feedback_text" not in st.session_state:
    st.session_state.feedback_text = ""

if "researcher_feedback_cache" not in st.session_state:
    st.session_state.researcher_feedback_cache = {}

st.title("Cogniva")
st.caption("Language · Cognition · AI")
st.header("Cogniva Write")
st.caption("Version 1.5.2 · Structured Feedback Core · Secure Submission Storage")
test_mode = bool(st.session_state.get("researcher_test_mode", False) and st.session_state.get("admin_authenticated", False))
if test_mode:
    st.warning("RESEARCHER TEST MODE — Responses will be marked as test data.")
    chosen_condition = st.radio(
        "Choose feedback condition for this test:",
        ["supportive", "neutral"],
        horizontal=True,
        key="researcher_condition",
        disabled=st.session_state.stage != 1,
    )
    st.caption("Identical essays in this researcher session reuse one factual feedback core.")
    if st.button("Clear test feedback cache"):
        st.session_state.researcher_feedback_cache = {}
        st.success("Researcher feedback cache cleared.")
    if st.button("Exit test mode"):
        st.session_state.researcher_test_mode = False
        st.query_params["view"] = "researcher"
        st.session_state.stage = 1
        st.session_state.initial_data = {}
        st.session_state.feedback_condition = None
        st.session_state.feedback_text = ""
        st.session_state.pop("pending_record_id", None)
        st.rerun()
st.divider()

if st.session_state.stage == 1:
    st.subheader("Step 1: Initial Writing")

    with st.form("initial_form"):
        if test_mode:
            participant_id = "AUTO_" + uuid.uuid4().hex[:10].upper()
            st.caption("Researcher test: Participant ID is generated automatically.")
        else:
            participant_id = st.text_input(
                "Participant ID",
                placeholder="e.g., P003"
            )

        st.info(f"Topic: {TOPIC}")

        initial_essay = st.text_area(
            "Write 100–150 words:",
            height=220
        )

        initial_score = st.slider(
            "Predicted writing score (0–100)",
            0, 100, 70
        )

        initial_confidence = st.slider(
            "Writing confidence (1–7)",
            1, 7, 4
        )

        continue_button = st.form_submit_button(
            "Continue to Feedback"
        )

    st.write(f"English word count: {len(initial_essay.split())} / 100–150")

    if continue_button:
        word_count = len(initial_essay.split())

        if not test_mode and not participant_id.strip():
            st.warning("Please enter a Participant ID.")
        elif any("\\u4e00" <= c <= "\\u9fff" for c in initial_essay):
            st.warning("This task requires an English essay. Please write in English.")
        elif not 100 <= word_count <= 150:
            st.warning("Please write between 100 and 150 words.")
        else:
            st.session_state.initial_data = {
                "participant_id": ("TEST_" + participant_id.strip()) if test_mode else participant_id.strip(),
                "initial_essay": initial_essay,
                "initial_word_count": word_count,
                "initial_score": initial_score,
                "initial_confidence": initial_confidence,
            }

            # Only authenticated researchers can override random assignment.
            condition = chosen_condition if test_mode else random.choice(["supportive", "neutral"])
            st.session_state.feedback_condition = condition

            if "OPENAI_API_KEY" not in st.secrets:
                st.error("AI feedback is not configured. Please contact the researcher.")
            else:
                with st.spinner("Generating writing feedback..."):
                    try:
                        if test_mode:
                            essay_hash = hashlib.sha256(initial_essay.encode("utf-8")).hexdigest()
                            cached = st.session_state.researcher_feedback_cache.get(essay_hash)
                            if cached is None:
                                cached = {"core": generate_feedback_core(initial_essay)}
                                st.session_state.researcher_feedback_cache[essay_hash] = cached
                            if condition not in cached:
                                cached[condition] = style_feedback(cached["core"], condition)
                            st.session_state.feedback_text = cached[condition]
                            st.session_state.active_test_essay_hash = essay_hash
                        else:
                            st.session_state.feedback_text = generate_writing_feedback(
                                initial_essay, condition
                            )
                    except HTTPError as exc:
                        # Only show status and allowlisted error code; never expose credentials.
                        api_error_code = "unknown"
                        try:
                            error_payload = json.loads(exc.read().decode("utf-8"))
                            candidate = error_payload.get("error", {}).get("code")
                            if isinstance(candidate, str) and len(candidate) <= 48 and all(c.isalnum() or c == "_" for c in candidate):
                                api_error_code = candidate
                        except (ValueError, UnicodeError, AttributeError, TypeError):
                            pass
                        st.error(f"AI request failed (HTTP {exc.code}; code: {api_error_code}).")
                    except (URLError, TimeoutError):
                        st.error("AI request failed (network connection or timeout).")
                    except (ValueError, KeyError, TypeError) as exc:
                        st.error("AI response could not be processed. Please try again.")
                        if test_mode:
                            st.caption(f"Researcher diagnostic: {type(exc).__name__}: {exc}")
                    else:
                        st.session_state.stage = 2
                        st.rerun()

elif st.session_state.stage == 2:
    st.subheader("Step 2: Writing Feedback")

    st.info(st.session_state.feedback_text)

    if test_mode:
        with st.expander("Researcher comparison: same feedback core", expanded=False):
            essay_hash = st.session_state.get("active_test_essay_hash")
            cached = st.session_state.researcher_feedback_cache.get(essay_hash, {})
            if cached:
                st.caption("The neutral version is the original factual core. The supportive version rewrites its tone.")
                st.markdown("**Neutral feedback**")
                st.info(format_feedback_core(cached["core"]))
                if "supportive" not in cached:
                    if st.button("Generate supportive comparison", key="generate_comparison"):
                        with st.spinner("Generating supportive wording..."):
                            try:
                                cached["supportive"] = style_feedback(cached["core"], "supportive")
                            except (HTTPError, URLError, TimeoutError, ValueError, KeyError, TypeError):
                                st.error("Could not generate the comparison. Please try again.")
                            else:
                                st.rerun()
                if "supportive" in cached:
                    st.markdown("**Supportive feedback**")
                    st.info(cached["supportive"])
                st.caption("Researcher preview only. Verify that the correction points match before formal use.")

    st.caption(
        "Please read the feedback carefully before revising."
    )

    if st.button("Continue to Revision"):
        st.session_state.stage = 3
        st.rerun()

elif st.session_state.stage == 3:
    st.subheader("Step 3: Writing Revision")

    st.text_area(
        "Original Writing",
        value=st.session_state.initial_data["initial_essay"],
        height=180,
        disabled=True
    )

    st.info(st.session_state.feedback_text)

    with st.form("revision_form"):
        revised_essay = st.text_area(
            "Revise your paragraph:",
            value=st.session_state.initial_data["initial_essay"],
            height=220
        )

        revised_score = st.slider(
            "Predicted score after revision (0–100)",
            0, 100, 70
        )

        revised_confidence = st.slider(
            "Writing confidence after revision (1–7)",
            1, 7, 4
        )

        submit_button = st.form_submit_button(
            "Submit Final Responses"
        )

    if submit_button:
        revised_word_count = len(revised_essay.split())

        if any("\\u4e00" <= c <= "\\u9fff" for c in revised_essay):
            st.warning("Please revise your essay in English.")
        elif not 100 <= revised_word_count <= 150:
            st.warning(
                "Please keep your revision between 100 and 150 words."
            )
        else:
            record = {
                "record_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),
                **st.session_state.initial_data,
                "feedback_condition":
                    st.session_state.feedback_condition,
                "feedback_type": "ai_generated_v1_5_2_test" if test_mode else "ai_generated_v1_5_2",
                "feedback_text": st.session_state.feedback_text,
                "feedback_word_count": len(
                    st.session_state.feedback_text.split()
                ),
                "revised_essay": revised_essay,
                "revised_word_count": revised_word_count,
                "revised_score": revised_score,
                "revised_confidence": revised_confidence,
            }

            if not all(k in st.secrets for k in ("SUPABASE_URL", "SUPABASE_KEY")):
                st.error("Submission storage is not configured. Please contact the researcher.")
            else:
                # Keep one stable ID across retries to avoid duplicate submissions.
                if "pending_record_id" not in st.session_state:
                    st.session_state.pending_record_id = record["record_id"]
                record["record_id"] = st.session_state.pending_record_id
                record.pop("timestamp", None)  # Supabase supplies created_at.
                try:
                    db_request("POST", "writing_submissions?on_conflict=record_id", [record])
                except (HTTPError, URLError, TimeoutError, KeyError, ValueError):
                    st.error("Submission could not be confirmed. Please retry; your text is still here.")
                else:
                    st.session_state.stage = 4
                    st.session_state.pop("pending_record_id", None)
                    st.rerun()

elif st.session_state.stage == 4:
    st.success("Your responses have been saved!")

    st.subheader("Submission Summary")
    st.write(
        "Participant ID:",
        st.session_state.initial_data["participant_id"]
    )
    st.write(
        "Feedback condition:",
        st.session_state.feedback_condition
    )

    if st.button("Start New Test"):
        st.session_state.stage = 1
        st.session_state.initial_data = {}
        st.session_state.feedback_condition = None
        st.session_state.feedback_text = ""
        st.session_state.pop("pending_record_id", None)
        st.rerun()
