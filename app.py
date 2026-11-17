
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
        "max_output_tokens": 1600,
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


def generate_feedback_core(essay):
    """Create structured, evidence-checked corrections before showing feedback."""
    import re

    instructions = (
        "You are an EFL writing tutor and grammar editor. Return ONLY a valid JSON "
        "object with keys 'strength_quote', 'strength_explanation', and 'suggestions'. "
        "The strength_quote must be an exact short substring of the essay and the "
        "explanation must identify one genuine writing strength without exaggeration. "
        "suggestions must be an array of exactly four objects, each with keys "
        "'category', 'original', 'replacement', 'explanation'. "
        "For each correction, original MUST be a verbatim substring of the essay, "
        "replacement must be correct in its original sentence context, and explanation "
        "must accurately name the grammatical rule. Use distinct, high-priority issues. "
        "Distinguish subject-verb agreement, modal + base verb, comparatives, articles, "
        "and other categories precisely. When an error follows can, should, must, "
        "may, might, will, would, could, or shall, label it modal + base verb, "
        "NOT subject-verb agreement. Praise ideas, examples, organization, or "
        "argumentation rather than grammatical accuracy when the cited passage "
        "contains an error. Prefer a grammatically correct quote when possible. "
        "No invented errors, no markdown."
    )
    draft = openai_response(instructions, essay)
    reviewed = openai_response(
        "You are an independent EFL feedback reviewer. Compare the original essay "
        "and JSON draft. Correct mislabeled categories, invalid replacements, "
         "overlapping points, and quotations not found verbatim in the essay. "
        "Do not praise grammatical accuracy or correct word choice in a quote "
        "that contains an error. A modal verb followed by an incorrect verb "
        "form is a modal + base verb error, not subject-verb agreement. "
        "Return ONLY a valid JSON object with the SAME schema: strength_quote, "
        "strength_explanation, suggestions (exactly four objects with category, "
        "original, replacement, explanation). Do not include markdown.",
        "ORIGINAL ESSAY:\n" + essay + "\n\nDRAFT JSON:\n" + draft,
    )
    try:
        data = json.loads(reviewed)
    except json.JSONDecodeError as exc:
        raise ValueError("Feedback is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("suggestions"), list):
        raise ValueError("Invalid feedback structure")
    suggestions = data["suggestions"]
    if len(suggestions) != 4:
        raise ValueError("Expected exactly four suggestions")
    quote = data.get("strength_quote")
    explanation = data.get("strength_explanation")
    if not isinstance(quote, str) or not quote.strip() or quote not in essay:
        raise ValueError("Strength evidence not found in essay")
    if not isinstance(explanation, str) or not explanation.strip():
        raise ValueError("Missing strength explanation")
    seen = set()
    for item in suggestions:
        if not isinstance(item, dict):
            raise ValueError("Invalid correction")
        for field in ("category", "original", "replacement", "explanation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("Incomplete correction")
        original = item["original"]
        if original not in essay or original == item["replacement"]:
            raise ValueError("Correction source missing or unchanged")
        if original in seen:
            raise ValueError("Duplicate correction")
        seen.add(original)
        # Deterministic category guard for modal + verb errors.
        # This does not certify that the proposed replacement is correct.
        modal_pattern = re.compile(
            r"\\b(can|could|should|would|will|shall|may|might|must)\\s+"
            r"([A-Za-z]+)\\b", re.IGNORECASE
        )
        for match in modal_pattern.finditer(original):
            modal = match.group(1)
            source_verb = match.group(2)
            corrected = re.search(
                r"\\b" + re.escape(modal) + r"\\s+([A-Za-z]+)\\b",
                item["replacement"], re.IGNORECASE
            )
            if (corrected and source_verb.lower() != corrected.group(1).lower()
                    and source_verb.lower().endswith("s")
                    and source_verb[:-1].lower() == corrected.group(1).lower()):
                item["category"] = "modal + base verb"
                item["explanation"] = (
                    f"After the modal verb '{modal.lower()}', use the base form "
                    f"'{corrected.group(1)}' rather than '{source_verb}'."
                )
                break
    return data


def format_feedback_core(data):
    """Render the same validated correction items for both conditions."""
    lines = [
        "Writing strength:",
        data["strength_explanation"] + ' Example: "' + data["strength_quote"] + '"',
        "",
        "Revision suggestions:",
        "",
    ]
    for i, item in enumerate(data["suggestions"], 1):
        lines.append(
            f'{i}. {item["category"]}: Replace "{item["original"]}" '
            f'with "{item["replacement"]}". {item["explanation"]}'
        )
    return "\n".join(lines)


def style_feedback(core, condition):
    """Only praise/closing vary; the four corrections are rendered identically."""
    factual = format_feedback_core(core)
    if condition == "neutral":
        return factual
    praise = openai_response(
        "Write TWO short paragraphs of encouraging, expressive EFL feedback. "
        "Return ONLY a JSON object with string fields 'opening' and 'closing'. "
        "In opening, praise only the documented writing strength and quote the "
        "provided exact evidence. In closing, encourage revision. Use 4-7 "
        "friendly emojis total, mostly in opening, including expressive faces. "
        "Do NOT include any correction suggestions or new factual claims. "
        "Do NOT use markdown.",
        json.dumps({
            "strength_quote": core["strength_quote"],
            "strength_explanation": core["strength_explanation"],
        }, ensure_ascii=False),
    )
    try:
        parts = json.loads(praise)
        opening, closing = parts["opening"], parts["closing"]
        if not all(isinstance(v, str) and v.strip() for v in (opening, closing)):
            raise ValueError("Empty supportive wording")
    except (ValueError, KeyError, TypeError):
        raise ValueError("Invalid supportive wording")
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
        st.query_params.clear()
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


if st.query_params.get("admin") == "1":
    st.title("Cogniva Write")
    admin_panel()
    st.stop()

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
st.caption("Version 0.9.1 · Structured Feedback Core · Secure Submission Storage")
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
        participant_id = st.text_input(
            "Participant ID",
            placeholder="e.g., TEST003"
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

        if not participant_id.strip():
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
                    except (ValueError, KeyError, TypeError):
                        st.error("AI response could not be processed. Please try again.")
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
                st.caption("Researcher preview only. Verify that all four correction points match before formal use.")

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
                "feedback_type": "ai_generated_v0_9_1_test" if test_mode else "ai_generated_v0_9_1",
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
