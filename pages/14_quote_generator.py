"""
Quote of the Week Generator — Riot PR Desk
Generates punchy, shareable LinkedIn quotes for Ben Johnson or David Donaghy.
"""

import json
import os
import re
import datetime

import streamlit as st

from services.ai_engine import generate_stream, is_configured as ai_configured
from utils.styles import apply_global_styles, render_sidebar, get_page_icon

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Quote Generator | Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
)

apply_global_styles()
render_sidebar()

# ── Additional page-level styles ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    .linkedin-card {
        background: #111;
        border: 1px solid #1A1A1A;
        border-radius: 6px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.5rem;
    }
    .linkedin-card .li-name {
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        color: #FFFFFF;
        margin-bottom: 0.1rem;
    }
    .linkedin-card .li-meta {
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        font-size: 0.72rem;
        color: #666;
        margin-bottom: 0.75rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .linkedin-card .li-body {
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #E0E0E0;
        white-space: pre-wrap;
    }
    .linkedin-card .li-footer {
        margin-top: 0.75rem;
        padding-top: 0.6rem;
        border-top: 1px solid #1A1A1A;
        font-family: 'PPFormulaUI', sans-serif !important;
        font-size: 0.7rem;
        color: #444;
        letter-spacing: 0.04em;
    }
    .quote-box {
        background: #0D0D0D;
        border: 1px solid #1A1A1A;
        border-left: 3px solid #E8192C;
        border-radius: 3px;
        padding: 1rem 1.25rem;
        margin-bottom: 0.25rem;
    }
    .quote-box p {
        font-family: 'PPFormulaUI', sans-serif !important;
        font-size: 0.95rem !important;
        line-height: 1.6 !important;
        color: #E0E0E0 !important;
        margin: 0 !important;
    }
    .quote-number {
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 900;
        font-size: 0.7rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #E8192C;
        margin-bottom: 0.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("Quote of the Week")
st.markdown(
    "Generate punchy, shareable quotes for Ben Johnson or David Donaghy to post on LinkedIn "
    "— keeping their thought leadership fresh without effort."
)

st.divider()

# ── AI gate ───────────────────────────────────────────────────────────────────
if not ai_configured():
    st.error(
        "**AI engine not configured.** Add your `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` "
        "to `.env` to get started.",
    )
    st.stop()

# ── Input form ────────────────────────────────────────────────────────────────
with st.form("quote_form"):
    topic_input = st.text_area(
        "What's happening this week?",
        placeholder=(
            "e.g. Government delays vape tax implementation again, citing industry concerns..."
        ),
        height=120,
    )

    col1, col2 = st.columns(2)
    with col1:
        spokesperson = st.selectbox(
            "Spokesperson",
            ["Ben Johnson (CEO)", "David Donaghy (Head of PR)"],
        )
    with col2:
        num_quotes = st.slider("Number of quotes", min_value=3, max_value=8, value=5)

    tone_options = st.multiselect(
        "Tone mix",
        options=["Provocative", "Measured", "Witty", "Authoritative", "Campaigning"],
        default=["Provocative", "Authoritative"],
    )

    generate_clicked = st.form_submit_button("Generate Quotes", type="primary", use_container_width=True)

st.divider()

# ── Generation ────────────────────────────────────────────────────────────────
if generate_clicked:
    if not topic_input.strip():
        st.warning("Please describe what's happening this week before generating quotes.")
        st.stop()

    if not tone_options:
        st.warning("Please select at least one tone.")
        st.stop()

    tone_str = ", ".join(tone_options)

    prompt = f"""Generate {num_quotes} short, punchy LinkedIn quotes for {spokesperson} about: {topic_input.strip()}

Tone mix requested: {tone_str}

Rules:
- Each quote should be 1-3 sentences max, under 150 characters ideally
- No corporate clichés or waffle
- Each quote should take a clear point of view — no sitting on the fence
- Mix the tones requested
- Draw on Riot's positioning as the rebel who grew up — anti-Big-Tobacco, pro harm reduction, British manufacturing
- Format as a numbered list: 1. [quote]
- No hashtags, no emojis, no "I believe" or "I think" openers
- Quotes should sound like things a real person would actually say on LinkedIn
"""

    full_text = ""
    with st.status("Generating quotes...", expanded=True) as status:
        try:
            stream = generate_stream(prompt)
            full_text = st.write_stream(stream)
            status.update(label="Quotes ready.", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Generation failed.", state="error", expanded=True)
            st.error(f"Could not generate quotes: {e}")
            st.stop()

    st.session_state["generated_quotes"] = {
        "text": full_text,
        "spokesperson": spokesperson,
        "topic": topic_input.strip(),
        "num_quotes": num_quotes,
        "tone_options": tone_options,
        "generated_at": datetime.datetime.now().isoformat(),
    }
    st.rerun()

# ── Display previously generated quotes ──────────────────────────────────────
def _parse_numbered_quotes(raw: str) -> list[str]:
    """Extract individual quotes from a numbered list (e.g. '1. ...', '2. ...')."""
    # Match lines that start with a number followed by a period/dot
    pattern = re.compile(r"^\s*\d+\.\s+(.+)", re.MULTILINE)
    matches = pattern.findall(raw)
    if matches:
        return [m.strip() for m in matches if m.strip()]
    # Fallback: split by double newline if no numbered list detected
    parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
    return parts


if "generated_quotes" in st.session_state:
    data = st.session_state["generated_quotes"]
    raw_text: str = data["text"]
    sp: str = data["spokesperson"]
    topic: str = data["topic"]
    tone_list: list = data.get("tone_options", [])
    generated_at: str = data.get("generated_at", "")

    # Format generated_at for display
    try:
        dt = datetime.datetime.fromisoformat(generated_at)
        generated_label = dt.strftime("%-d %b %Y, %H:%M")
    except Exception:
        generated_label = generated_at

    st.markdown(f"### Quotes for **{sp}**")
    st.caption(
        f"Topic: {topic[:120]}{'...' if len(topic) > 120 else ''} "
        f"· Tones: {', '.join(tone_list)} "
        f"· Generated: {generated_label}"
    )
    st.divider()

    quotes = _parse_numbered_quotes(raw_text)

    if not quotes:
        st.warning("Could not parse individual quotes. Raw output:")
        st.markdown(raw_text)
    else:
        # ── Tabs: Copy Boxes vs LinkedIn Preview ─────────────────────────────
        tab_copy, tab_preview = st.tabs(["Copy Quotes", "LinkedIn Preview"])

        with tab_copy:
            st.markdown(
                "Each quote below is in a copyable code block. "
                "Click the copy icon in the top-right corner of each box."
            )
            st.divider()
            for i, quote in enumerate(quotes, start=1):
                st.markdown(
                    f'<div class="quote-number">Quote {i} of {len(quotes)}</div>',
                    unsafe_allow_html=True,
                )
                st.code(quote, language=None)

        with tab_preview:
            st.markdown(
                "How these quotes could look as LinkedIn posts — for visual reference only."
            )
            st.divider()

            # Derive first name for the avatar-style header
            first_name = sp.split(" ")[0]
            role_label = sp.split("(")[-1].rstrip(")") if "(" in sp else "Riot Labs"

            for i, quote in enumerate(quotes, start=1):
                char_count = len(quote)
                char_colour = "#4ade80" if char_count <= 150 else "#fbbf24" if char_count <= 280 else "#f87171"
                st.markdown(
                    f"""
                    <div class="linkedin-card">
                        <div class="li-name">{sp.split(" (")[0]}</div>
                        <div class="li-meta">{role_label} · Riot Labs</div>
                        <div class="li-body">{quote}</div>
                        <div class="li-footer">
                            Quote {i} of {len(quotes)}
                            &nbsp;·&nbsp;
                            <span style="color:{char_colour};">{char_count} chars</span>
                            &nbsp;·&nbsp; LinkedIn &nbsp;·&nbsp; Just now
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.divider()

        # ── Save to JSON ──────────────────────────────────────────────────────
        st.markdown("#### Save quotes")
        save_col, dl_col = st.columns(2)

        with save_col:
            if st.button("Save to quotes library", use_container_width=True):
                data_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
                )
                os.makedirs(data_dir, exist_ok=True)
                save_path = os.path.join(data_dir, "saved_quotes.json")

                # Load existing records
                existing: list = []
                if os.path.exists(save_path):
                    try:
                        with open(save_path, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = []
                    except (json.JSONDecodeError, OSError):
                        existing = []

                # Append new record
                new_record = {
                    "saved_at": datetime.datetime.now().isoformat(),
                    "generated_at": generated_at,
                    "spokesperson": sp,
                    "topic": topic,
                    "tone_options": tone_list,
                    "quotes": quotes,
                    "raw_text": raw_text,
                }
                existing.append(new_record)

                try:
                    with open(save_path, "w", encoding="utf-8") as f:
                        json.dump(existing, f, indent=2, ensure_ascii=False)
                    st.success(
                        f"Saved {len(quotes)} quote(s) to `data/saved_quotes.json` "
                        f"({len(existing)} record(s) total)."
                    )
                except OSError as e:
                    st.error(f"Could not save file: {e}")

        with dl_col:
            if st.button("Send to Google Docs", use_container_width=True, key="qg_to_gdocs"):
                with st.spinner("Creating Google Doc…"):
                    try:
                        from services.google_docs_export import export_text_to_docs
                        body_lines = [
                            f"Spokesperson: {sp}",
                            f"Topic: {topic}",
                            f"Tones: {', '.join(tone_list)}",
                            "",
                        ]
                        for i, q in enumerate(quotes, start=1):
                            body_lines.append(f"{i}. {q}")
                            body_lines.append("")
                        gd = export_text_to_docs(
                            title=f"Quote of the Week — {topic}",
                            body="\n".join(body_lines),
                            label="QUOTES",
                        )
                        st.success(f"[Open in Google Docs →]({gd['doc_url']})")
                    except Exception as ex:
                        st.error(f"Google Docs export failed: {ex}")
