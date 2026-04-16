import datetime
import streamlit as st
from services.ai_engine import generate, is_configured as ai_configured
from services.feedback import record_vote
from config.spokespeople import SPOKESPEOPLE, get_spokesperson_names
from utils.prompts import STORY_LADDER_PROMPT, QUOTE_OF_WEEK_PROMPT
from utils.styles import apply_global_styles, render_sidebar

st.set_page_config(page_title="Story Ladder | Riot PR Desk", page_icon="🪜", layout="wide")

apply_global_styles()
render_sidebar()

st.title("🪜 Story Ladder")
st.markdown("Plan multi-week PR campaigns with a phased sequence of actions that build momentum and maximise coverage.")

st.divider()

if not ai_configured():
    st.error(
        "**AI engine not configured.** Add your `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `.env` to get started.",
        icon="🔑",
    )
    st.stop()

tab_ladder, tab_quote = st.tabs(["🪜 Story Ladder", "💬 Quote of the Week"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: STORY LADDER
# ─────────────────────────────────────────────────────────────────────────────
with tab_ladder:

    # --- Preset example buttons ---
    st.markdown("#### Quick-start examples")
    preset_col1, preset_col2, preset_col3 = st.columns(3)

    PRESET_CAMPAIGNS = {
        "VPD Go-Live Campaign": "Vape Product Directive (VPD) go-live October 2026 — new compliance rules take effect, illegal products swept from shelves. Riot is fully compliant and positioned as the responsible manufacturer.",
        "Product Launch (RIOT CONNEX)": "Launch of RIOT CONNEX, Riot's new closed-pod system for the convenience retail channel. Pre-filled pods, 10 flavours, TRPR compliant, RRP £5.99 device / £3.99 pod 2-pack.",
        "Chief Misinformation Officer style stunt": "A major national newspaper runs a junk-science scare story about vaping health risks, citing a discredited study. Riot responds with a bold activist stunt to counter the misinformation.",
    }

    if "sl_campaign_input" not in st.session_state:
        st.session_state["sl_campaign_input"] = ""

    with preset_col1:
        if st.button("VPD Go-Live Campaign", use_container_width=True):
            st.session_state["sl_campaign_input"] = PRESET_CAMPAIGNS["VPD Go-Live Campaign"]
            st.rerun()

    with preset_col2:
        if st.button("Product Launch (RIOT CONNEX)", use_container_width=True):
            st.session_state["sl_campaign_input"] = PRESET_CAMPAIGNS["Product Launch (RIOT CONNEX)"]
            st.rerun()

    with preset_col3:
        if st.button("Chief Misinformation Officer style stunt", use_container_width=True):
            st.session_state["sl_campaign_input"] = PRESET_CAMPAIGNS["Chief Misinformation Officer style stunt"]
            st.rerun()

    st.divider()

    # --- Form inputs ---
    campaign_input = st.text_area(
        "Campaign moment / news hook",
        value=st.session_state.get("sl_campaign_input", ""),
        height=130,
        placeholder="e.g. 'Vape Tax Go-Live October 2026 — new excise duty takes effect, adding £1 per 10ml to e-liquids. Riot is ready and wants to own the narrative.'",
        help="What event or story is this campaign built around?",
        key="sl_campaign_input_area",
    )

    col1, col2 = st.columns(2)
    with col1:
        duration = st.selectbox(
            "Campaign duration",
            ["1 week", "2 weeks", "4 weeks", "6 weeks", "8 weeks", "12 weeks"],
        )
    with col2:
        objective = st.text_input(
            "Primary objective",
            placeholder="e.g. 'Establish Riot as the authority on VPD compliance'",
        )

    spokespeople = st.multiselect(
        "Spokespeople available",
        options=get_spokesperson_names(),
        default=get_spokesperson_names(),
    )

    generate_ladder_clicked = st.button(
        "🪜 Build Story Ladder",
        type="primary",
        use_container_width=True,
        disabled=not campaign_input.strip(),
    )

    # --- Generate ---
    if generate_ladder_clicked and campaign_input.strip():
        spokespeople_str = ", ".join(spokespeople) if spokespeople else "Ben Johnson (CEO), David Donaghy (Head of Brand & Marketing)"
        prompt = STORY_LADDER_PROMPT.format(
            campaign_input=campaign_input.strip(),
            duration=duration,
            objective=objective.strip() if objective.strip() else "Maximise PR coverage and establish Riot as the leading voice",
            spokespeople=spokespeople_str,
        )
        with st.spinner("🪜 Building your Story Ladder — planning the campaign rungs..."):
            try:
                result = generate(prompt)
                st.session_state["sl_last_result"] = result
                st.session_state["sl_last_campaign"] = campaign_input.strip()
                st.success("Story Ladder built! Review the campaign plan below.")
            except Exception as e:
                st.error(f"Generation failed: {e}")

    # --- Display result ---
    if "sl_last_result" in st.session_state:
        result = st.session_state["sl_last_result"]
        campaign_ref = st.session_state.get("sl_last_campaign", campaign_input.strip())

        st.divider()
        st.markdown("### 📋 Your Story Ladder")
        st.caption("DRAFT — Review and adapt before sharing with your team.")

        st.markdown(result)

        st.divider()

        # Save as note
        st.markdown("#### 💾 Save as note")
        note_content = st.text_area(
            "Edit before saving:",
            value=result,
            height=200,
            key="sl_note_content",
        )
        if st.button("💾 Save note", key="sl_save_note"):
            st.session_state["sl_saved_note"] = note_content
            st.success("Note saved to session.")

        col_dl, col_pr = st.columns(2)

        with col_dl:
            download_text = (
                f"RIOT PR DESK — STORY LADDER (DRAFT)\n"
                f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
                f"Campaign: {campaign_ref}\n"
                f"{'=' * 60}\n\n{result}"
            )
            st.download_button(
                "📥 Download as .txt",
                data=download_text,
                file_name=f"riot_story_ladder_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with col_pr:
            if st.button("✍️ Create PR Pack from this", use_container_width=True):
                # Extract first rung action (heuristic: find first "Action:" line)
                first_action = ""
                for line in result.splitlines():
                    if line.strip().lower().startswith("- **action:**") or line.strip().lower().startswith("**action:**"):
                        first_action = line.split(":", 1)[-1].strip().lstrip("*").strip()
                        break
                pr_seed = f"{campaign_ref}"
                if first_action:
                    pr_seed += f"\n\nFirst campaign action: {first_action}"
                st.session_state["pr_input"] = pr_seed
                st.switch_page("pages/2_pr_generator.py")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: QUOTE OF THE WEEK
# ─────────────────────────────────────────────────────────────────────────────
with tab_quote:

    # --- Preset context buttons ---
    st.markdown("#### Quick-start contexts")
    qp_col1, qp_col2, qp_col3, qp_col4 = st.columns(4)

    PRESET_CONTEXTS = {
        "Vape Tax reaction": "The UK government has confirmed the vape excise duty will go live October 2026, adding £1 per 10ml to e-liquids. Industry reaction has been mixed — some welcome the regulatory clarity, others warn it will push vapers back to cigarettes.",
        "Anti-vaping media story": "A national newspaper has run a front-page story claiming vaping is 'just as harmful as smoking', citing a single US study. The story has been widely shared on social media and is causing concern among Riot's customer base.",
        "British manufacturing pride": "New data shows UK vape manufacturing has grown 40% in two years, with British brands now exporting to 25 countries. The sector is positioning itself as a post-Brexit industrial success story.",
        "Retailer support": "New IBVTA data shows compliance-focused retailers are seeing 20% higher basket values as the illegal vape market shrinks. The compliance dividend is real — honest retailers are being rewarded.",
    }

    if "qw_context" not in st.session_state:
        st.session_state["qw_context"] = ""

    with qp_col1:
        if st.button("Vape Tax reaction", use_container_width=True, key="qp_btn1"):
            st.session_state["qw_context"] = PRESET_CONTEXTS["Vape Tax reaction"]
            st.rerun()
    with qp_col2:
        if st.button("Anti-vaping media story", use_container_width=True, key="qp_btn2"):
            st.session_state["qw_context"] = PRESET_CONTEXTS["Anti-vaping media story"]
            st.rerun()
    with qp_col3:
        if st.button("British manufacturing pride", use_container_width=True, key="qp_btn3"):
            st.session_state["qw_context"] = PRESET_CONTEXTS["British manufacturing pride"]
            st.rerun()
    with qp_col4:
        if st.button("Retailer support", use_container_width=True, key="qp_btn4"):
            st.session_state["qw_context"] = PRESET_CONTEXTS["Retailer support"]
            st.rerun()

    st.divider()

    # --- Inputs ---
    qw_context = st.text_area(
        "What's happening in the industry right now?",
        value=st.session_state.get("qw_context", ""),
        height=130,
        placeholder="e.g. paste a headline, describe a trend, or leave guidance for the AI — 'Focus on the vape tax being an opportunity for compliant brands'",
        key="qw_context_area",
    )

    spokesperson_key = st.selectbox(
        "Spokesperson voice",
        options=get_spokesperson_names(),
        key="qw_spokesperson",
    )
    spokesperson = SPOKESPEOPLE[spokesperson_key]

    generate_quotes_clicked = st.button(
        "💬 Generate 5 LinkedIn Posts",
        type="primary",
        use_container_width=True,
        disabled=not qw_context.strip(),
    )

    # --- Generate ---
    if generate_quotes_clicked and qw_context.strip():
        prompt = QUOTE_OF_WEEK_PROMPT.format(
            context=qw_context.strip(),
            spokesperson_name=spokesperson["name"],
            spokesperson_title=spokesperson["title"],
            spokesperson_tone=spokesperson["tone"],
        )
        with st.spinner("💬 Writing LinkedIn posts — finding the sharpest angles..."):
            try:
                result = generate(prompt)
                st.session_state["qw_last_result"] = result
                st.session_state["qw_last_spokesperson"] = spokesperson_key
                st.success(f"5 posts generated for {spokesperson['name']}. Review below.")
            except Exception as e:
                st.error(f"Generation failed: {e}")

    # --- Display result: parse and render each post ---
    if "qw_last_result" in st.session_state:
        raw = st.session_state["qw_last_result"]
        sp_key_used = st.session_state.get("qw_last_spokesperson", spokesperson_key)
        sp_used = SPOKESPEOPLE.get(sp_key_used, spokesperson)

        st.divider()
        st.markdown(f"### 💬 Posts for {sp_used['name']}, {sp_used['title']}")
        st.caption("DRAFT — Review before posting. These are suggestions, not final copy.")

        # Split on "---" separators (the prompt uses --- between posts)
        segments = [s.strip() for s in raw.split("---") if s.strip()]

        for i, segment in enumerate(segments):
            if not segment:
                continue
            post_num = i + 1
            with st.container():
                st.markdown(f"**Post {post_num}**")
                st.markdown(segment)

                col_copy, col_up, col_down = st.columns([6, 0.7, 0.7])
                with col_copy:
                    st.code(segment, language=None)

                vote_key = f"qw_voted_{post_num}"
                with col_up:
                    if vote_key not in st.session_state:
                        if st.button("👍", key=f"qw_up_{post_num}", help="Good post"):
                            record_vote(
                                f"Quote of Week post {post_num}: {segment[:100]}",
                                "up",
                                "quote_of_week",
                            )
                            st.session_state[vote_key] = "up"
                            st.rerun()
                    else:
                        st.caption("👍" if st.session_state[vote_key] == "up" else "👎")

                with col_down:
                    if vote_key not in st.session_state:
                        if st.button("👎", key=f"qw_down_{post_num}", help="Needs improvement"):
                            record_vote(
                                f"Quote of Week post {post_num}: {segment[:100]}",
                                "down",
                                "quote_of_week",
                            )
                            st.session_state[vote_key] = "down"
                            st.rerun()

                st.divider()
