import datetime
import streamlit as st
from services.ai_engine import generate, is_configured as ai_configured
from utils.prompts import CRISIS_COMMS_PROMPT
from utils.styles import apply_global_styles, render_sidebar, get_page_icon

st.set_page_config(page_title="Crisis Comms | Riot PR Desk", page_icon=get_page_icon(), layout="wide")

apply_global_styles()
render_sidebar()

st.title("Crisis Comms")
st.markdown(
    '<p style="color: #f87171; font-size: 1.05rem; font-weight: 600;">Rapid response toolkit for breaking stories</p>',
    unsafe_allow_html=True,
)

st.warning(
    "This tool is for rapid response to breaking stories. All outputs are DRAFT — require immediate human review before publication.",
)

st.divider()

if not ai_configured():
    st.error(
        "**AI engine not configured.** Add your `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `.env` to get started.",
    )
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# INPUTS
# ─────────────────────────────────────────────────────────────────────────────
crisis_situation = st.text_area(
    "Describe the situation",
    height=150,
    placeholder=(
        "e.g. 'A national newspaper is running a story tomorrow claiming Riot products contain "
        "illegal levels of nicotine. We have been asked to comment by 5pm today.'"
    ),
    key="crisis_situation",
)

crisis_urgency = st.selectbox(
    "Urgency level",
    [
        "Breaking — respond within 1 hour",
        "Urgent — respond within 4 hours",
        "Monitor — respond within 24 hours",
    ],
    key="crisis_urgency",
)

generate_crisis_clicked = st.button(
    "Generate Crisis Response Pack",
    type="primary",
    use_container_width=True,
    disabled=not crisis_situation.strip(),
)

# ─────────────────────────────────────────────────────────────────────────────
# GENERATE
# ─────────────────────────────────────────────────────────────────────────────
if generate_crisis_clicked and crisis_situation.strip():
    prompt = CRISIS_COMMS_PROMPT.format(
        situation=crisis_situation.strip(),
        urgency=crisis_urgency,
    )
    with st.spinner("Generating crisis response pack — stand by..."):
        try:
            result = generate(prompt)
            st.session_state["crisis_last_result"] = result
            st.session_state["crisis_last_situation"] = crisis_situation.strip()
            st.session_state["crisis_last_urgency"] = crisis_urgency
            st.success("Crisis response pack ready. Review each section below.")
        except Exception as e:
            st.error(f"Generation failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY RESULT
# ─────────────────────────────────────────────────────────────────────────────
if "crisis_last_result" in st.session_state:
    result = st.session_state["crisis_last_result"]
    situation_ref = st.session_state.get("crisis_last_situation", crisis_situation.strip())
    urgency_ref = st.session_state.get("crisis_last_urgency", crisis_urgency)

    st.divider()

    st.info(
        "All outputs are DRAFT. Do not publish without senior approval.",
    )

    st.markdown(f"**Urgency:** {urgency_ref}")

    # ── Parse sections from the AI response ──
    # Sections are headed ### 1. SITUATION ASSESSMENT, ### 2. HOLDING STATEMENT, etc.
    SECTION_LABELS = [
        ("1. SITUATION ASSESSMENT", "1. Situation Assessment", ""),
        ("2. HOLDING STATEMENT", "2. Holding Statement", ""),
        ("3. FULL RESPONSE", "3. Full Response", ""),
        ("4. INTERNAL BRIEFING", "4. Internal Briefing", ""),
        ("5. MEDIA MONITORING", "5. Media Monitoring", ""),
        ("6. RECOVERY PLAN", "6. Recovery Plan", ""),
    ]

    def _extract_section(text, heading_marker):
        """Extract content for a section identified by heading_marker."""
        # Try ### heading match (case-insensitive)
        import re
        pattern = rf"###\s*{re.escape(heading_marker)}.*?\n(.*?)(?=###|\Z)"
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    parsed_any = False
    for marker, label, icon in SECTION_LABELS:
        content = _extract_section(result, marker)
        if content:
            parsed_any = True
            with st.expander(label, expanded=True):
                st.markdown(content)

    # Fallback: if parsing failed, show raw output in expanders by splitting on ###
    if not parsed_any:
        import re
        chunks = re.split(r"(?=###\s)", result)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            # Extract heading
            lines = chunk.splitlines()
            heading = lines[0].lstrip("#").strip() if lines else "Section"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else chunk
            with st.expander(heading, expanded=True):
                st.markdown(body)

    # ── Send to Google Docs ──
    st.divider()
    if st.button("Send to Google Docs", use_container_width=True, key="cc_to_gdocs"):
        with st.spinner("Creating Google Doc…"):
            try:
                from services.google_docs_export import export_text_to_docs
                body = (
                    f"Urgency: {urgency_ref}\n"
                    f"Situation: {situation_ref}\n\n"
                    f"{result}"
                )
                gd = export_text_to_docs(
                    title=f"Crisis Comms Pack — {urgency_ref or 'Urgent'}",
                    body=body,
                    label="CRISIS COMMS",
                )
                st.success(f"[Open in Google Docs →]({gd['doc_url']})")
            except Exception as ex:
                st.error(f"Google Docs export failed: {ex}")
