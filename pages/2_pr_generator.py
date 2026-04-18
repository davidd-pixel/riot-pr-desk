import datetime
import streamlit as st
from services.ai_engine import is_configured as ai_configured, generate_stream, refine_text, refine_text_sync
from services.content_generator import generate_pr_pack, _build_pr_pack_prompt, _parse_pr_pack
from services.feedback import record_vote
from services.journalist_db import get_journalist_count
from services.pr_library import save_pack, get_recent_packs
from config.positions import get_position_names
from config.spokespeople import get_spokesperson_names
from config.settings import TONES, AUDIENCES
from utils.styles import apply_global_styles, render_sidebar

st.set_page_config(page_title="PR Generator | Riot PR Desk", page_icon="✍️", layout="wide")

apply_global_styles()
render_sidebar()

st.title("✍️ PR Pack Generator")
st.markdown("Generate an approval-ready PR response pack in minutes.")

st.divider()

# --- Check AI configuration ---
if not ai_configured():
    st.error(
        "**AI engine not configured.** Add your `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `.env` to get started. "
        "Then set `AI_PROVIDER` to `anthropic` or `openai`.",
        icon="🔑",
    )
    st.stop()

# --- Template library ---
with st.expander("📚 Template Library — start from a proven framework", expanded=False):
    st.caption("Click a template to load it into the input field. Edit freely from there.")

    templates = {
        "Vape Tax Response": {
            "description": "Regulatory announcement or tax policy update",
            "input": "The UK government has confirmed that Vaping Products Duty (VPD) will take effect from 1 October 2026 at £2.20 per 10ml, with full shelf compliance required by 1 April 2027. [Add specific details of the announcement here]"
        },
        "Product Launch": {
            "description": "New product or range launch announcement",
            "input": "Riot Labs is launching [PRODUCT NAME], a new [product description] designed for [target channel/audience]. [Add key product details: features, formats, RRP, availability date]"
        },
        "Non-Compliant Products Story": {
            "description": "Media story about illegal/non-compliant vaping products",
            "input": "A [publication] investigation has revealed [details about non-compliant products in the UK market]. [Add specific claims from the story and whether Riot is named]"
        },
        "Activist Campaign Launch": {
            "description": "Riot Activist campaign or stunt announcement",
            "input": "[Campaign name]: Riot Labs is launching [campaign description] in response to [trigger event]. [Add campaign details, what Riot is doing, what we're calling for]"
        },
        "Flavour Ban Threat": {
            "description": "Government consultation or proposal to restrict flavours",
            "input": "The [government body] has announced a consultation on restricting flavoured vaping products. [Add specific proposals and timeline]"
        },
        "Regulatory Win": {
            "description": "Positive regulatory news for the industry",
            "input": "[Regulatory body/government] has [announced/confirmed/published] [positive news for vaping]. [Add details and what it means for the industry]"
        },
        "Competitor News": {
            "description": "Respond to a competitor announcement",
            "input": "[Competitor name] has announced [what they've done/launched/said]. [Add context and why Riot has a relevant perspective]"
        },
        "Misinformation Response": {
            "description": "Counter a misleading media story about vaping",
            "input": "[Publication] has published a story claiming [false/misleading claim about vaping]. [Add specific claims from the story that are factually incorrect]"
        },
    }

    tmpl_cols = st.columns(4)
    for idx, (name, tmpl) in enumerate(templates.items()):
        with tmpl_cols[idx % 4]:
            if st.button(name, key=f"tmpl_{idx}", use_container_width=True, help=tmpl["description"]):
                st.session_state["input_content"] = tmpl["input"]
                st.rerun()

st.divider()

# --- Input section ---
st.markdown("### 1. What's the story?")

# Pre-fill from session state if arriving from news monitor or home page
if "pr_input" in st.session_state:
    st.session_state["input_content"] = st.session_state.pop("pr_input")

input_content = st.text_area(
    "Paste a news headline, article excerpt, product update or campaign idea:",
    key="input_content",
    height=150,
    placeholder="e.g. 'Government announces new vape tax starting January 2027, adding £1 per 10ml to all e-liquids...'",
)

# --- Example inputs via selectbox ---
example_options = {
    "Select an example...": "",
    "Vape tax announcement": "The UK government has confirmed that a new excise duty on vaping products will take effect from October 2026. The tax will add £1 per 10ml to e-liquid costs, with the stated aim of discouraging youth uptake while maintaining vaping as a cheaper alternative to smoking.",
    "Product launch": "Riot Labs is launching RIOT CONNEX, a new closed-pod system designed for the convenience retail channel. The device features pre-filled pods in 10 flavours, a 500mAh battery, and is fully TRPR compliant. RRP is £5.99 for the device and £3.99 for a 2-pack of pods.",
    "Regulatory news": "The MHRA has announced new enforcement powers to tackle non-compliant vaping products entering the UK market. From January 2027, importers will face fines of up to £10,000 per product line for failing to meet notification requirements.",
    "Industry controversy": "A major investigation by The Times has revealed that over 60% of disposable vapes sold in UK convenience stores fail basic safety tests, with many containing nicotine levels above the legal limit. The story names several Chinese manufacturers but does not mention Riot Labs.",
}

selected_example = st.selectbox("Or try an example:", list(example_options.keys()))
if selected_example != "Select an example..." and example_options[selected_example]:
    st.session_state["input_content"] = example_options[selected_example]
    st.rerun()

st.divider()

# --- Configuration ---
st.markdown("### 2. Configure your response")

col1, col2 = st.columns(2)
with col1:
    position_name = st.selectbox("Riot's stance:", get_position_names())
    spokesperson_key = st.selectbox("Spokesperson:", get_spokesperson_names())

with col2:
    audience_key = st.selectbox("Target audience:", list(AUDIENCES.keys()))
    tone_key = st.selectbox("Tone:", list(TONES.keys()))

# Show selected config summary inline
from config.positions import get_position
from config.spokespeople import get_spokesperson

pos = get_position(position_name)
spk = get_spokesperson(spokesperson_key)
st.info(
    f"**Position:** {position_name} — *{pos['headline']}*  \n"
    f"**Spokesperson:** {spk['name']}, {spk['title']} — Tone: *{spk['tone']}*  \n"
    f"**Audience:** {audience_key} — *{AUDIENCES[audience_key]}*  \n"
    f"**Tone:** {tone_key} — *{TONES[tone_key]}*",
    icon="📋",
)

st.divider()

# --- Fine-tune ---
st.markdown("### 3. Fine-tune the output")
dial_col1, dial_col2, dial_col3 = st.columns(3)
with dial_col1:
    tone_dial = st.select_slider(
        "Tone dial",
        options=["Very measured", "Measured", "Balanced", "Bold", "Very bold"],
        value="Balanced",
        help="Shift from cautious/corporate toward provocative/activist"
    )
with dial_col2:
    length_dial = st.select_slider(
        "Output length",
        options=["Concise", "Standard", "Detailed"],
        value="Standard",
        help="Concise = tight and punchy. Detailed = fully developed with more depth."
    )
with dial_col3:
    variations = st.selectbox(
        "Variations per section",
        options=[1, 2, 3],
        index=0,
        help="Generate multiple versions of each section to choose from"
    )

st.divider()

# --- Generate ---
st.markdown("### 4. Generate")

generate_clicked = st.button(
    "🚀 Generate PR Pack",
    type="primary",
    use_container_width=True,
    disabled=not input_content.strip(),
)

# --- PR Pack output ---
if generate_clicked and input_content.strip():
    try:
        prompt = _build_pr_pack_prompt(
            input_content=input_content.strip(),
            position_name=position_name,
            spokesperson_key=spokesperson_key,
            audience_key=audience_key,
            tone_key=tone_key,
            tone_dial=tone_dial,
            length_dial=length_dial,
        )

        try:
            with st.status("🚀 Generating your PR pack...", expanded=True) as status:
                st.write("Crafting 6 tailored outputs — press releases, pitch emails, LinkedIn, WhatsApp, social and internal briefing...")
                stream = generate_stream(prompt)
                raw_response = st.write_stream(stream)
                status.update(label="✅ PR Pack ready!", state="complete", expanded=False)
        except Exception:
            # Fallback to non-streaming if st.write_stream is unavailable
            with st.spinner("🚀 Generating your PR pack — this takes 30-60 seconds while we craft 6 tailored outputs..."):
                raw_response = generate_pr_pack(
                    input_content=input_content.strip(),
                    position_name=position_name,
                    spokesperson_key=spokesperson_key,
                    audience_key=audience_key,
                    tone_key=tone_key,
                    tone_dial=tone_dial,
                    length_dial=length_dial,
                )
                # generate_pr_pack returns parsed sections, not raw — handle that
                if isinstance(raw_response, dict):
                    sections = raw_response
                    raw_response = None

        if raw_response is not None:
            sections = _parse_pr_pack(raw_response)

        # Handle variations
        if variations > 1:
            st.session_state["variation_count"] = variations
            st.session_state["all_variations"] = [sections]

        st.session_state["last_pr_pack"] = sections
        st.session_state["last_pr_input"] = input_content.strip()
        st.session_state["last_tone_dial"] = tone_dial
        st.session_state["last_length_dial"] = length_dial

        # Auto-save to PR Library
        try:
            saved = save_pack(
                input_content=input_content.strip(),
                sections=sections,
                position_name=position_name,
                spokesperson_key=spokesperson_key,
                audience_key=audience_key,
                tone_key=tone_key,
            )
            st.session_state["last_saved_pack_id"] = saved["id"]
        except Exception:
            pass  # Silent fail — don't block UI

        st.rerun()

    except Exception as e:
        st.error(f"Generation failed: {e}")

# --- Display stored PR pack ---
CONDITIONAL_SECTIONS = {"Retailer WhatsApp Comms", "Consumer Social Media Comms", "Internal Briefing", "Creative Brief"}

if "last_pr_pack" in st.session_state:
    sections = st.session_state["last_pr_pack"]
    # Retrieve the original input used to generate this pack (for regeneration prompts)
    stored_input = st.session_state.get("last_pr_input", input_content.strip())

    st.divider()
    st.markdown("### 📦 Your PR Pack")
    st.caption("DRAFT — All outputs require approval before external use.")

    # --- Variations UI ---
    if st.session_state.get("variation_count", 1) > 1:
        all_vars = st.session_state.get("all_variations", [])

        if len(all_vars) < st.session_state["variation_count"]:
            if st.button(
                f"🔀 Generate Variation {len(all_vars) + 1} of {st.session_state['variation_count']}",
                use_container_width=True,
                type="secondary",
            ):
                try:
                    variation_prompt = _build_pr_pack_prompt(
                        input_content=st.session_state.get("last_pr_input", ""),
                        position_name=position_name,
                        spokesperson_key=spokesperson_key,
                        audience_key=audience_key,
                        tone_key=tone_key,
                        tone_dial=st.session_state.get("last_tone_dial", "Balanced"),
                        length_dial=st.session_state.get("last_length_dial", "Standard"),
                    ) + f"\n\nNote: This is variation {len(all_vars) + 1}. Use a DIFFERENT approach, angle, headline and structure than you would normally. Be creative and distinct."

                    with st.status(f"🔀 Generating variation {len(all_vars) + 1}...", expanded=True) as var_status:
                        stream = generate_stream(variation_prompt)
                        raw = st.write_stream(stream)
                        var_status.update(label=f"✅ Variation {len(all_vars) + 1} ready!", state="complete", expanded=False)

                    new_sections = _parse_pr_pack(raw)
                    all_vars.append(new_sections)
                    st.session_state["all_variations"] = all_vars
                    st.rerun()
                except Exception as e:
                    st.error(f"Variation generation failed: {e}")

        if len(all_vars) > 1:
            var_labels = [f"Variation {i+1}" for i in range(len(all_vars))]
            selected_var = st.radio(
                "Viewing:",
                var_labels,
                horizontal=True,
                key="selected_variation",
            )
            var_idx = var_labels.index(selected_var)
            sections = all_vars[var_idx]
            # Also update the main pack reference for download etc.
            st.session_state["last_pr_pack"] = sections

    # --- Publishing Readiness Check ---
    sections = st.session_state["last_pr_pack"]
    input_used = st.session_state.get("last_pr_input", "")
    all_content = " ".join(sections.values()).lower()
    pr_text = sections.get("Press Release", "").lower()

    checklist_items = []

    # Has spokesperson quote?
    has_quote = '"' in sections.get("Press Release", "") or "johnson" in pr_text or "donaghy" in pr_text
    checklist_items.append(("Spokesperson quote included", has_quote))

    # Has verified stat?
    has_stat = any(s in all_content for s in ["95%", "4 million", "£2.20", "75,000", "6.4 million", "%"])
    checklist_items.append(("Statistics referenced", has_stat))

    # Has boilerplate?
    has_boilerplate = "about riot" in all_content or "riot labs is" in all_content
    checklist_items.append(("About Riot boilerplate present", has_boilerplate))

    # Forbidden phrases check
    forbidden = ["delighted to announce", "pleased to confirm", "world-class", "best-in-class",
                 "industry-leading", "going forward", "leveraging", "synergies", "holistic approach"]
    forbidden_found = [f for f in forbidden if f in all_content]
    checklist_items.append(("No forbidden phrases", len(forbidden_found) == 0))

    # Has media contact?
    has_contact = "press@" in all_content or "media contact" in all_content or "placeholder" in all_content
    checklist_items.append(("Media contact included", has_contact))

    # Has call to action?
    has_cta = any(w in all_content for w in ["contact", "available for", "happy to", "reach out", "get in touch"])
    checklist_items.append(("Call to action present", has_cta))

    passed = sum(1 for _, v in checklist_items if v)
    total = len(checklist_items)
    score_pct = round(passed / total * 100)

    score_color = "🟢" if score_pct >= 80 else "🟡" if score_pct >= 60 else "🔴"
    with st.expander(f"{score_color} Publishing Readiness: {score_pct}% ({passed}/{total} checks passed)", expanded=score_pct < 80):
        for label, passed_check in checklist_items:
            icon = "✅" if passed_check else "⚠️"
            st.caption(f"{icon} {label}")
        if forbidden_found:
            st.warning(f"Forbidden phrases detected: {', '.join(forbidden_found)}")
        if score_pct == 100:
            st.success("All checks passed. This pack is ready for review.")

    for section_name, content in sections.items():
        is_not_applicable = content.strip().upper().startswith("NOT APPLICABLE")
        is_conditional = section_name in CONDITIONAL_SECTIONS

        if is_not_applicable and is_conditional:
            with st.expander(f"~~{section_name}~~ — *Not applicable*", expanded=False):
                st.caption(content)
        else:
            with st.expander(f"**{section_name}**", expanded=True):
                st.markdown(content)

                # --- Copy / Vote row ---
                safe_key = section_name.replace(" ", "_").replace("/", "_")
                vote_key = f"pr_voted_{safe_key}"

                st.divider()

                if vote_key in st.session_state:
                    col_copy, col_feedback = st.columns([1, 5])
                    with col_copy:
                        st.code(content, language=None)
                    with col_feedback:
                        st.caption(f"{'👍' if st.session_state[vote_key] == 'up' else '👎'} Feedback recorded")
                else:
                    col_copy, col_up, col_down, col_note = st.columns([1, 0.5, 0.5, 4])
                    with col_copy:
                        st.code(content, language=None)
                    with col_note:
                        pr_note = st.text_input(
                            "Feedback (optional):",
                            key=f"pr_note_{safe_key}",
                            placeholder="e.g. 'tone is off', 'great headline'",
                        )
                    with col_up:
                        if st.button("👍", key=f"pr_up_{safe_key}", help="Good output"):
                            record_vote(f"PR Pack: {section_name}", "up", "pr_pack_section", note=pr_note)
                            st.session_state[vote_key] = "up"
                            st.rerun()
                    with col_down:
                        if st.button("👎", key=f"pr_down_{safe_key}", help="Needs improvement"):
                            record_vote(f"PR Pack: {section_name}", "down", "pr_pack_section", note=pr_note)
                            st.session_state[vote_key] = "down"
                            st.rerun()

                # --- Action row: Regenerate + AI Edit ---
                action_col1, action_col2 = st.columns(2)

                with action_col1:
                    regen_key = f"pr_regen_{safe_key}"
                    if st.button("🔄 Regenerate section", key=regen_key, help="Rewrite this section from scratch with a fresh approach", use_container_width=True):
                        with st.spinner(f"Regenerating {section_name}..."):
                            try:
                                from services.ai_engine import generate
                                regen_prompt = (
                                    f"You previously generated a PR pack. Please regenerate ONLY the '{section_name}' section "
                                    f"with a fresh approach. Keep the same facts and key messages but use different wording, "
                                    f"structure or angle. Do not include any other sections.\n\n"
                                    f"Original input: {stored_input[:500]}\n\n"
                                    f"Current {section_name}:\n{content}\n\n"
                                    f"Generate an improved version of just the {section_name}:"
                                )
                                new_content = generate(regen_prompt)
                                # Auto-save version before regenerating section
                                if "last_saved_pack_id" in st.session_state:
                                    try:
                                        from services.pr_library import add_version
                                        add_version(
                                            st.session_state["last_saved_pack_id"],
                                            dict(st.session_state["last_pr_pack"]),
                                            note=f"Before regenerating {section_name}"
                                        )
                                    except Exception:
                                        pass
                                updated_sections = dict(st.session_state["last_pr_pack"])
                                updated_sections[section_name] = new_content
                                st.session_state["last_pr_pack"] = updated_sections
                                st.rerun()
                            except Exception as e:
                                st.error(f"Regeneration failed: {e}")

                with action_col2:
                    refine_toggle_key = f"pr_refine_active_{safe_key}"
                    if st.button(
                        "✏️ Refine with AI" if not st.session_state.get(refine_toggle_key) else "✕ Close editor",
                        key=f"pr_refine_toggle_{safe_key}",
                        help="Give the AI a specific instruction to improve this section",
                        use_container_width=True,
                    ):
                        st.session_state[refine_toggle_key] = not st.session_state.get(refine_toggle_key, False)
                        st.rerun()

                # --- Inline AI editing panel ---
                if st.session_state.get(f"pr_refine_active_{safe_key}"):
                    st.markdown("""<div style="background:#111;border:1px solid #E8192C33;border-radius:4px;padding:0.75rem 1rem 0.5rem 1rem;margin-top:0.5rem">""", unsafe_allow_html=True)

                    quick_prompts = [
                        "Make it shorter and punchier",
                        "Make the tone more provocative",
                        "Make the tone more measured",
                        "Add a stronger opening line",
                        "Make the quote more quotable",
                        "Remove any corporate clichés",
                        "Add a specific statistic",
                        "Strengthen the call to action",
                    ]
                    st.caption("✏️ **AI EDIT** — Tell the AI exactly what to change:")

                    qp_col1, qp_col2 = st.columns([3, 1])
                    with qp_col1:
                        refine_instruction = st.text_input(
                            "Instruction",
                            key=f"pr_refine_instruction_{safe_key}",
                            placeholder="e.g. 'Make it punchier', 'Add a stat', 'Shorten by half'...",
                            label_visibility="collapsed",
                        )
                    with qp_col2:
                        apply_refine = st.button(
                            "Apply →",
                            key=f"pr_refine_apply_{safe_key}",
                            type="primary",
                            use_container_width=True,
                            disabled=not refine_instruction.strip(),
                        )

                    # Quick-prompt chips
                    chip_cols = st.columns(4)
                    for ci, qp in enumerate(quick_prompts):
                        with chip_cols[ci % 4]:
                            if st.button(qp, key=f"pr_qp_{safe_key}_{ci}", use_container_width=True):
                                st.session_state[f"pr_refine_instruction_{safe_key}"] = qp
                                st.session_state[f"pr_qp_trigger_{safe_key}"] = True
                                st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)

                    # Apply via button or quick-prompt trigger
                    should_apply = apply_refine or st.session_state.pop(f"pr_qp_trigger_{safe_key}", False)
                    instruction_to_use = st.session_state.get(f"pr_refine_instruction_{safe_key}", "").strip()

                    if should_apply and instruction_to_use:
                        # Save version before editing
                        if "last_saved_pack_id" in st.session_state:
                            try:
                                from services.pr_library import add_version
                                add_version(
                                    st.session_state["last_saved_pack_id"],
                                    dict(st.session_state["last_pr_pack"]),
                                    note=f"Before AI edit: '{instruction_to_use}' on {section_name}"
                                )
                            except Exception:
                                pass

                        with st.spinner(f"Applying: \"{instruction_to_use}\"..."):
                            try:
                                new_content = refine_text_sync(content, instruction_to_use, context=section_name)
                                updated_sections = dict(st.session_state["last_pr_pack"])
                                updated_sections[section_name] = new_content
                                st.session_state["last_pr_pack"] = updated_sections
                                st.session_state[f"pr_refine_active_{safe_key}"] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"Refinement failed: {e}")

    # --- Find matching journalists ---
    st.divider()

    journalist_count = get_journalist_count()
    journalist_label = f"📇 Find matching journalists ({journalist_count} in database) →" if journalist_count else "📇 Find matching journalists →"

    if st.button(journalist_label, use_container_width=True):
        # Build a story context summary for the journalist matcher
        story_summary = stored_input[:500]
        st.session_state["journalist_story_context"] = story_summary
        st.switch_page("pages/6_journalists.py")

    # --- Export ---
    st.divider()
    # Only include applicable sections in export
    export_sections = {
        name: content for name, content in sections.items()
        if not (name in CONDITIONAL_SECTIONS and content.strip().upper().startswith("NOT APPLICABLE"))
    }

    full_pack = "\n\n".join(
        f"{'=' * 60}\n{name}\n{'=' * 60}\n\n{content}"
        for name, content in export_sections.items()
    )
    full_pack = (
        f"RIOT PR DESK — PR PACK (DRAFT)\n"
        f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"{'=' * 60}\n\n{full_pack}"
    )

    st.download_button(
        "📥 Download PR Pack",
        data=full_pack,
        file_name=f"riot_pr_pack_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        mime="text/plain",
        use_container_width=True,
    )
