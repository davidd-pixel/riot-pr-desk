"""
Inbox — daily command centre for approving PR opportunities, reviewing
content and confirming media lists before pitching.

Three sections:
  A. Opportunities Awaiting Direction  (pending opps from autonomous engine)
  B. Content Awaiting Approval         (packs with status=under_review)
  C. Media Lists Awaiting Approval     (approved packs with suggested journalists)
"""

import streamlit as st
from utils.styles import apply_global_styles, render_sidebar, get_page_icon

st.set_page_config(
    page_title="Inbox | Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
)
apply_global_styles()
render_sidebar()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("Inbox")
st.divider()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

try:
    from services.opportunity_tracker import (
        get_pending_opportunities,
        update_opportunity_status,
    )
    pending_opps = get_pending_opportunities()
except Exception as e:
    pending_opps = []
    st.error(f"Could not load opportunities: {e}")

try:
    from services.pr_library import (
        get_all_packs,
        update_pack_status,
        add_version,
        add_comment,
    )
    all_packs = get_all_packs()
    under_review_packs = [p for p in all_packs if p.get("status") == "under_review"]
    media_pending_packs = [
        p for p in all_packs
        if p.get("status") == "approved"
        and p.get("suggested_journalists")
        and not p.get("pitches_sent")
    ]
except Exception as e:
    under_review_packs = []
    media_pending_packs = []
    all_packs = []
    st.error(f"Could not load packs: {e}")

total_items = len(pending_opps) + len(under_review_packs) + len(media_pending_packs)

if total_items == 0:
    st.markdown(
        '<div style="text-align:center;padding:3rem 0">'
        '<div style="font-size:2rem;margin-bottom:1rem">✓</div>'
        '<p style="font-size:1.1rem;color:#888">Your inbox is clear.</p>'
        '<p style="font-size:0.85rem;color:#555">New opportunities will appear here each morning.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ===========================================================================
# SECTION A — Opportunities Awaiting Direction
# ===========================================================================

if pending_opps:
    st.markdown("### Opportunities Awaiting Direction")
    st.write("")

    _type_labels = {
        "pr_commentary": ("PR / News Commentary", "#E8192C", "Approve & Generate Pack"),
        "newsjacking":   ("News-Jacking",         "#fbbf24", "Approve & Generate Pack"),
        "blog":          ("Blog Opportunities",   "#60a5fa", "Approve & Generate Blog"),
    }

    # Group opportunities by type — preserves relevance ordering within each group
    _groups = {t: [] for t in _type_labels}
    for opp in pending_opps:
        t = opp.get("opportunity_type", "pr_commentary")
        if t in _groups:
            _groups[t].append(opp)

    for opp_type, group_opps in _groups.items():
        if not group_opps:
            continue

        sec_label, sec_colour, approve_btn_label = _type_labels[opp_type]
        st.markdown(
            f'<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:{sec_colour};border-bottom:1px solid #1A1A1A;'
            f'padding-bottom:0.3rem;margin:1.25rem 0 0.75rem 0">'
            f'{sec_label} &nbsp;·&nbsp; {len(group_opps)}</div>',
            unsafe_allow_html=True,
        )

        _MAX_PER_SECTION = 5
        _shown = 0
        for opp in group_opps:
            if _shown >= _MAX_PER_SECTION:
                _remaining = len(group_opps) - _MAX_PER_SECTION
                st.caption(f"+{_remaining} more — skip some above to surface them")
                break
            _shown += 1

            opp_id = opp.get("id", "")
            score = opp.get("relevance_score", 0)
            title = opp.get("story_title", "Untitled")
            source = opp.get("story_source", "")
            angle = opp.get("riot_angle", "")
            position = opp.get("suggested_position", "")
            why = opp.get("why_it_matters", "")
            story_url = opp.get("story_url", "")
            nj_concept = opp.get("newsjacking_concept", "")
            nj_hook = opp.get("newsjacking_hook", "")
            nj_execution = opp.get("newsjacking_execution", "")
            nj_format = opp.get("newsjacking_format", "")
            nj_speed = opp.get("newsjacking_speed", "")

            if score >= 8:
                score_colour = "#E8192C"
            elif score >= 6:
                score_colour = "#fbbf24"
            else:
                score_colour = "#60a5fa"

            score_badge = (
                f'<span style="background:{score_colour}22;border:1px solid {score_colour}55;'
                f'color:{score_colour};font-size:0.65rem;font-weight:700;padding:2px 8px;'
                f'border-radius:2px;text-transform:uppercase;letter-spacing:0.06em">'
                f'Relevance {score}/10</span>'
            )
            position_badge = (
                f'<span style="background:#ffffff11;border:1px solid #333;color:#aaa;'
                f'font-size:0.65rem;padding:2px 8px;border-radius:2px">{position}</span>'
            ) if position else ""

            url_link = (
                f'<a href="{story_url}" target="_blank" style="color:#555;font-size:0.7rem;'
                f'text-decoration:none">Read story →</a>'
            ) if story_url else ""

            # Build the card body — newsjacking gets a full creative brief panel
            if opp_type == "newsjacking" and (nj_hook or nj_concept):
                # Format + Speed badges on the title row
                meta_badges = ""
                if nj_format:
                    meta_badges += (
                        f'<span style="background:#fbbf2422;border:1px solid #fbbf2466;color:#fbbf24;'
                        f'font-size:0.62rem;font-weight:700;padding:2px 8px;border-radius:2px;'
                        f'text-transform:uppercase;letter-spacing:0.06em;margin-right:4px">{nj_format}</span>'
                    )
                if nj_speed:
                    speed_colour = "#E8192C" if "Immediate" in nj_speed else "#fbbf24" if "This week" in nj_speed else "#60a5fa"
                    meta_badges += (
                        f'<span style="background:{speed_colour}22;border:1px solid {speed_colour}66;color:{speed_colour};'
                        f'font-size:0.62rem;font-weight:700;padding:2px 8px;border-radius:2px;'
                        f'text-transform:uppercase;letter-spacing:0.06em">{nj_speed}</span>'
                    )

                # Idea title — bold headline for the concept
                idea_title_html = (
                    f'<div style="font-family:PPFormula,sans-serif;font-weight:900;font-size:0.95rem;'
                    f'color:#fbbf24;margin-bottom:0.4rem">{nj_concept}</div>'
                ) if nj_concept else ""

                # Hook section
                hook_html = (
                    f'<div style="margin-bottom:0.5rem">'
                    f'<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:#fbbf24;margin-bottom:0.2rem">The Hook</div>'
                    f'<div style="font-size:0.82rem;color:#F0E0A0;line-height:1.5">{nj_hook}</div>'
                    f'</div>'
                ) if nj_hook else ""

                # Execution section
                execution_html = (
                    f'<div style="margin-bottom:0.2rem">'
                    f'<div style="font-size:0.62rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;'
                    f'color:#fbbf24;margin-bottom:0.2rem">The Execution</div>'
                    f'<div style="font-size:0.82rem;color:#F0E0A0;line-height:1.5">{nj_execution}</div>'
                    f'</div>'
                ) if nj_execution else ""

                card_body = (
                    f'<div style="font-size:0.72rem;color:#555;margin-bottom:0.6rem">{source} &nbsp;{url_link}</div>'
                    # Full creative brief panel
                    f'<div style="background:#1A1400;border:1px solid #fbbf2433;border-radius:3px;'
                    f'padding:0.75rem 0.9rem;margin-bottom:0.5rem">'
                    f'{idea_title_html}'
                    f'<div style="margin-bottom:0.5rem">{meta_badges}</div>'
                    f'{hook_html}'
                    f'{execution_html}'
                    f'</div>'
                    # Angle + why as small secondary context
                    f'<div style="font-size:0.78rem;color:#888;line-height:1.4;margin-bottom:0.2rem">'
                    f'<strong style="color:#555;font-size:0.65rem;text-transform:uppercase;letter-spacing:0.08em">Message</strong>'
                    f'&nbsp; {angle}</div>'
                    f'<div style="font-size:0.72rem;color:#555;font-style:italic">{why}</div>'
                )
            else:
                card_body = (
                    f'<div style="font-size:0.72rem;color:#555;margin-bottom:0.5rem">{source} &nbsp;{url_link}</div>'
                    f'<div style="font-size:0.82rem;color:#CCC;line-height:1.5;margin-bottom:0.3rem">'
                    f'<strong style="color:#888;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.08em">Riot angle</strong><br>'
                    f'{angle}</div>'
                    f'<div style="font-size:0.75rem;color:#666;font-style:italic">{why}</div>'
                )

            st.markdown(
                f'<div style="background:#111;border:1px solid #222;border-left:3px solid {score_colour};'
                f'border-radius:0 3px 3px 0;padding:1rem 1.25rem;margin-bottom:0.25rem">'
                f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.75rem;margin-bottom:0.4rem">'
                f'<span style="font-family:PPFormula,sans-serif;font-weight:700;font-size:0.92rem;'
                f'color:#FFFFFF;line-height:1.3">{title}</span>'
                f'<div style="display:flex;gap:0.4rem;flex-shrink:0">{score_badge}{position_badge}</div>'
                f'</div>'
                f'{card_body}'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Action row
            edit_key = f"inbox_edit_angle_{opp_id}"
            approving_key = f"inbox_approving_{opp_id}"

            btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 1])

            with btn_col1:
                if st.button(approve_btn_label, key=f"inbox_approve_{opp_id}", type="primary", use_container_width=True):
                    st.session_state[approving_key] = {"custom_angle": None}
                    st.rerun()

            with btn_col2:
                if st.button(
                    "Close editor" if st.session_state.get(edit_key) else "Edit angle first",
                    key=f"inbox_edit_toggle_{opp_id}",
                    use_container_width=True,
                ):
                    st.session_state[edit_key] = not st.session_state.get(edit_key, False)
                    st.rerun()

            with btn_col3:
                if st.button("Skip", key=f"inbox_skip_{opp_id}", use_container_width=True):
                    update_opportunity_status(opp_id, "skipped")
                    st.rerun()

            # Angle editor
            if st.session_state.get(edit_key):
                with st.container():
                    custom_angle = st.text_area(
                        "Edit Riot angle",
                        value=angle,
                        key=f"inbox_angle_text_{opp_id}",
                        height=80,
                        label_visibility="collapsed",
                    )
                    if st.button(
                        "Approve with this angle",
                        key=f"inbox_approve_custom_{opp_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state[approving_key] = {"custom_angle": custom_angle.strip()}
                        st.session_state.pop(edit_key, None)
                        st.rerun()

            # Trigger generation
            if st.session_state.get(approving_key):
                custom = st.session_state[approving_key].get("custom_angle")
                with st.spinner("Generating PR pack — this takes about 30 seconds…"):
                    try:
                        from services.autonomous_engine import auto_generate_pack
                        pack_id = auto_generate_pack(opp_id, custom_angle=custom)
                        st.session_state.pop(approving_key, None)
                        st.success("PR pack generated and saved to library. Scroll down to review it.")
                        st.rerun()
                    except Exception as ex:
                        st.session_state.pop(approving_key, None)
                        st.error(f"Generation failed: {ex}")

            st.write("")

    st.divider()


# ===========================================================================
# SECTION B — Content Awaiting Approval
# ===========================================================================

try:
    from services.blog_library import get_all_blogs
    auto_blogs = [
        b for b in get_all_blogs()
        if b.get("status") == "draft" and "auto-generated" in b.get("tags", [])
    ]
except Exception:
    auto_blogs = []

if under_review_packs or auto_blogs:
    st.markdown("### Content Awaiting Approval")
    st.write("")

    for pack in under_review_packs:
        pack_id = pack.get("id", "")
        title = pack.get("title", "Untitled")
        position = pack.get("position_name", "")
        created = pack.get("created_at", "")[:16].replace("T", " ")
        sections = pack.get("sections", {})

        st.markdown(
            f'<div style="background:#111;border:1px solid #fbbf2433;border-top:2px solid #fbbf24;'
            f'border-radius:3px;padding:0.75rem 1rem;margin-bottom:0.5rem">'
            f'<div style="font-family:PPFormula,sans-serif;font-weight:700;font-size:0.92rem;'
            f'color:#FFFFFF;margin-bottom:0.2rem">{title}</div>'
            f'<div style="font-size:0.72rem;color:#666">{position} &middot; Generated {created}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Full press release preview in expander
        with st.expander("Preview press release", expanded=False):
            pr_text = sections.get("Press Release", "")
            if pr_text:
                st.markdown(pr_text)
            else:
                st.caption("No press release section found.")

            # Show all sections
            if len(sections) > 1:
                st.divider()
                sec_tabs = st.tabs(list(sections.keys()))
                for sec_tab, (sec_name, sec_content) in zip(sec_tabs, sections.items()):
                    with sec_tab:
                        st.markdown(sec_content)

        # Revision feedback area (toggle)
        revision_key = f"inbox_revision_{pack_id}"
        approving_b_key = f"inbox_approving_b_{pack_id}"

        action_col1, action_col2, action_col3, action_col4 = st.columns([2, 2, 1, 1])

        with action_col1:
            if st.button("Approve Content", key=f"inbox_approve_b_{pack_id}", type="primary", use_container_width=True):
                st.session_state[approving_b_key] = True
                st.rerun()

        with action_col2:
            if st.button(
                "Close feedback" if st.session_state.get(revision_key) else "Request Changes",
                key=f"inbox_revision_toggle_{pack_id}",
                use_container_width=True,
            ):
                st.session_state[revision_key] = not st.session_state.get(revision_key, False)
                st.rerun()

        with action_col3:
            if st.button("Pass", key=f"inbox_decline_b_{pack_id}", use_container_width=True):
                update_pack_status(pack_id, "declined")
                add_comment(pack_id, "David", "Passed — not the right moment for this story.", "note")
                st.rerun()

        with action_col4:
            if st.button("Library", key=f"inbox_open_lib_{pack_id}", use_container_width=True):
                st.switch_page("pages/7_pr_library.py")

        # Handle approve
        if st.session_state.get(approving_b_key):
            with st.spinner("Approving and matching journalists…"):
                try:
                    update_pack_status(pack_id, "approved")
                    from services.autonomous_engine import auto_match_journalists
                    journalists = auto_match_journalists(pack_id)
                    st.session_state.pop(approving_b_key, None)
                    st.success(
                        f"Approved. {len(journalists)} journalist{'s' if len(journalists) != 1 else ''} matched — "
                        f"see Section C below."
                    )
                    st.rerun()
                except Exception as ex:
                    st.session_state.pop(approving_b_key, None)
                    st.error(f"Approval failed: {ex}")

        # Revision feedback panel
        if st.session_state.get(revision_key):
            st.markdown(
                '<div style="background:#0D0D0D;border:1px solid #E8192C33;border-radius:4px;'
                'padding:0.75rem 1rem;margin-top:0.5rem">',
                unsafe_allow_html=True,
            )
            st.caption("**Request changes** — describe what you want fixed:")

            quick_revision_prompts = [
                "Strengthen the Ben quote — make it more provocative",
                "Add a stat about 4m UK vapers",
                "Shorten the press release by 30%",
                "Make the headline more punchy",
                "Emphasise the British manufacturing angle",
                "Tone down corporate language",
                "Add a stronger call to action",
                "Make it more urgent / time-sensitive",
            ]

            rev_instr = st.text_area(
                "Revision instructions",
                key=f"inbox_rev_text_{pack_id}",
                height=80,
                placeholder="e.g. 'Strengthen the Ben quote, make it more provocative. Add a stat about 4m UK vapers.'",
                label_visibility="collapsed",
            )

            # Quick prompt chips
            chip_cols = st.columns(4)
            for ci, qp in enumerate(quick_revision_prompts):
                with chip_cols[ci % 4]:
                    if st.button(qp, key=f"inbox_rev_qp_{pack_id}_{ci}", use_container_width=True):
                        st.session_state[f"inbox_rev_text_{pack_id}"] = qp
                        st.rerun()

            rev_submit = st.button(
                "Send for revision",
                key=f"inbox_rev_submit_{pack_id}",
                type="primary",
                use_container_width=True,
                disabled=not st.session_state.get(f"inbox_rev_text_{pack_id}", "").strip(),
            )

            st.markdown("</div>", unsafe_allow_html=True)

            instr = st.session_state.get(f"inbox_rev_text_{pack_id}", "").strip()
            if rev_submit and instr:
                with st.spinner("Applying revisions…"):
                    try:
                        from services.ai_engine import refine_text_sync

                        # Save snapshot before modifying
                        add_version(pack_id, dict(sections), note=f"Before revision: {instr[:60]}")

                        # Apply revision to each section
                        import json, os as _os
                        lib_path = _os.path.join(
                            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                            "data", "pr_library.json"
                        )
                        with open(lib_path) as f:
                            all_recs = json.load(f)

                        revised_sections = {}
                        for sec_name, sec_content in sections.items():
                            if sec_content.strip():
                                revised = refine_text_sync(sec_content, instr, context=sec_name)
                                revised_sections[sec_name] = revised
                            else:
                                revised_sections[sec_name] = sec_content

                        for rec in all_recs:
                            if rec["id"] == pack_id:
                                rec["sections"] = revised_sections
                                break

                        with open(lib_path, "w") as f:
                            json.dump(all_recs, f, indent=2)

                        # Log as comment
                        add_comment(pack_id, "David", f"Revision requested: {instr}", "change_request")

                        st.session_state.pop(revision_key, None)
                        st.session_state.pop(f"inbox_rev_text_{pack_id}", None)
                        st.success("Revisions applied. Expand the preview above to review.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Revision failed: {ex}")

        st.write("")

    # --- Auto-generated blog drafts ---
    if auto_blogs:
        st.markdown(
            '<div style="font-size:0.68rem;font-weight:700;letter-spacing:0.12em;'
            'text-transform:uppercase;color:#60a5fa;border-bottom:1px solid #1A1A1A;'
            'padding-bottom:0.3rem;margin:1rem 0 0.75rem 0">Blog Drafts</div>',
            unsafe_allow_html=True,
        )
        for blog in auto_blogs:
            blog_id = blog.get("id", "")
            blog_title = blog.get("title", "Untitled")
            blog_created = blog.get("created_at", "")[:16].replace("T", " ")

            st.markdown(
                f'<div style="background:#111;border:1px solid #60a5fa33;border-top:2px solid #60a5fa;'
                f'border-radius:3px;padding:0.75rem 1rem;margin-bottom:0.5rem">'
                f'<div style="font-family:PPFormula,sans-serif;font-weight:700;font-size:0.92rem;'
                f'color:#FFFFFF;margin-bottom:0.2rem">{blog_title}</div>'
                f'<div style="font-size:0.72rem;color:#666">Blog draft · Generated {blog_created}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            blog_post = blog.get("sections", {}).get("Blog Post", "")
            with st.expander("Preview blog post", expanded=False):
                if blog_post:
                    st.markdown(blog_post)
                else:
                    st.caption("No blog post section found.")

            blog_col1, blog_col2, blog_col3 = st.columns([2, 2, 2])
            with blog_col1:
                if st.button("Approve Blog", key=f"inbox_approve_blog_{blog_id}", type="primary", use_container_width=True):
                    try:
                        from services.blog_library import update_blog_status
                        update_blog_status(blog_id, "ready")
                        st.success("Blog approved and marked as ready to publish.")
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error: {ex}")
            with blog_col2:
                if st.button("Pass", key=f"inbox_pass_blog_{blog_id}", use_container_width=True):
                    try:
                        from services.blog_library import update_blog_status
                        update_blog_status(blog_id, "draft")
                        # Remove auto-generated tag so it leaves the inbox
                        from services.blog_library import _load as _blog_load, _save as _blog_save
                        recs = _blog_load()
                        for r in recs:
                            if r["id"] == blog_id:
                                r["tags"] = [t for t in r.get("tags", []) if t != "auto-generated"]
                                break
                        _blog_save(recs)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Error: {ex}")
            with blog_col3:
                if st.button("Open in Blog Writer", key=f"inbox_open_blog_{blog_id}", use_container_width=True):
                    st.switch_page("pages/16_blog_writer.py")

            st.write("")

    st.divider()


# ===========================================================================
# SECTION C — Media Lists Awaiting Approval
# ===========================================================================

if media_pending_packs:
    st.markdown("### Media Lists Awaiting Approval")
    st.caption("AI-matched journalists for approved packs. Confirm the list, add notes, then send pitches.")
    st.write("")

    for pack in media_pending_packs:
        pack_id = pack.get("id", "")
        title = pack.get("title", "Untitled")
        journalists = pack.get("suggested_journalists", [])

        st.markdown(
            f'<div style="font-family:PPFormula,sans-serif;font-weight:700;font-size:0.92rem;'
            f'color:#FFFFFF;margin-bottom:0.25rem">{title}</div>',
            unsafe_allow_html=True,
        )

        if not journalists:
            st.caption("No journalists matched yet.")
            if st.button("Match journalists now", key=f"inbox_match_{pack_id}", use_container_width=True):
                with st.spinner("Matching journalists…"):
                    try:
                        from services.autonomous_engine import auto_match_journalists
                        journalists = auto_match_journalists(pack_id)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Matching failed: {ex}")
            continue

        # Per-journalist include toggles and note fields
        # Store include/note state in session_state
        include_key = f"inbox_include_{pack_id}"
        if include_key not in st.session_state:
            st.session_state[include_key] = {j["id"]: True for j in journalists}

        note_key_prefix = f"inbox_note_{pack_id}"

        for j in journalists:
            j_id = j.get("id", "")
            j_name = j.get("name", "")
            j_pub = j.get("publication", "")
            j_beats = ", ".join(j.get("beats", []))
            j_score = j.get("relationship_score", 3)
            j_reasoning = j.get("reasoning", "")
            j_email = j.get("email", "")

            # Score pips
            score_pips = ""
            for pip_i in range(5):
                pip_colour = "#E8192C" if pip_i < j_score else "#222"
                score_pips += f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:{pip_colour};margin-right:2px"></span>'

            included = st.session_state[include_key].get(j_id, True)
            border_col = "#222" if included else "#111"
            opacity = "1" if included else "0.4"

            st.markdown(
                f'<div style="background:#111;border:1px solid {border_col};border-radius:3px;'
                f'padding:0.75rem 1rem;margin-bottom:0.25rem;opacity:{opacity}">'
                f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:0.5rem">'
                f'<div>'
                f'<div style="font-weight:700;font-size:0.85rem;color:#FFFFFF">{j_name}</div>'
                f'<div style="font-size:0.72rem;color:#666;margin-top:2px">{j_pub}'
                f'{(" &middot; " + j_beats) if j_beats else ""}</div>'
                f'</div>'
                f'<div style="text-align:right;flex-shrink:0">'
                f'<div>{score_pips}</div>'
                f'<div style="font-size:0.62rem;color:#555;margin-top:2px">relationship</div>'
                f'</div>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#888;margin-top:0.4rem;font-style:italic">{j_reasoning}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            j_col1, j_col2 = st.columns([1, 3])
            with j_col1:
                inc_val = st.checkbox(
                    "Include",
                    value=st.session_state[include_key].get(j_id, True),
                    key=f"inbox_inc_{pack_id}_{j_id}",
                )
                st.session_state[include_key][j_id] = inc_val

            with j_col2:
                st.text_input(
                    "Pitch note (optional)",
                    key=f"{note_key_prefix}_{j_id}",
                    placeholder="e.g. Lead with British manufacturing angle for this journalist",
                    label_visibility="collapsed",
                )

        st.write("")

        # Confirm & generate pitches button
        included_journalists = [
            j for j in journalists
            if st.session_state[include_key].get(j.get("id", ""), True)
        ]

        confirm_key = f"inbox_confirm_pitches_{pack_id}"
        n_inc = len(included_journalists)
        confirm_btn_label = f"Confirm & Generate {n_inc} Pitch{'es' if n_inc != 1 else ''}"

        if st.button(confirm_btn_label, key=confirm_key, use_container_width=True, type="primary"):
            # Attach notes to each journalist
            for j in included_journalists:
                j_id = j.get("id", "")
                note = st.session_state.get(f"{note_key_prefix}_{j_id}", "").strip()
                if note:
                    j["pitch_note"] = note

            st.session_state[f"inbox_pitches_ready_{pack_id}"] = included_journalists
            st.rerun()

        # Render pitch mailto links
        pitches_ready = st.session_state.get(f"inbox_pitches_ready_{pack_id}", [])
        if pitches_ready:
            st.markdown("**Ready to send — click each journalist to open your email client:**")

            try:
                from services.autonomous_engine import build_mailto_link
                for j in pitches_ready:
                    j_name = j.get("name", "")
                    j_pub = j.get("publication", "")
                    j_email = j.get("email", "")
                    mailto = build_mailto_link(j, pack)

                    if mailto:
                        st.markdown(
                            f'<a href="{mailto}" style="display:inline-block;background:#E8192C;'
                            f'color:#FFF;font-family:PPFormula,sans-serif;font-weight:700;font-size:0.8rem;'
                            f'letter-spacing:0.06em;text-transform:uppercase;padding:8px 18px;'
                            f'border-radius:3px;text-decoration:none;margin:4px 4px 0 0">'
                            f'Send to {j_name} ({j_pub})</a>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption(f"{j_name} — no email address on file")

            except Exception as ex:
                st.error(f"Could not build pitch links: {ex}")

            st.write("")

            # Mark all as sent
            if st.button("Mark pitches as sent", key=f"inbox_mark_sent_{pack_id}", use_container_width=True):
                try:
                    from services.pr_library import mark_pitches_sent
                    from services.journalist_history import log_contact
                    mark_pitches_sent(pack_id)
                    for j in pitches_ready:
                        try:
                            log_contact(
                                journalist_id=j.get("id", ""),
                                contact_type="pitch",
                                subject=f"Pitch sent for: {title}",
                                pack_id=pack_id,
                            )
                        except Exception:
                            pass
                    st.session_state.pop(f"inbox_pitches_ready_{pack_id}", None)
                    st.success("Pitches marked as sent. Status updated to Pitched.")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Could not mark as sent: {ex}")

        st.write("")
        st.divider()
