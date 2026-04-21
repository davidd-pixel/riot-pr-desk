"""
PR Library — browse, search, manage and track coverage for saved PR packs.
"""

import datetime

import streamlit as st

from utils.styles import apply_global_styles, render_sidebar, get_page_icon
from services.ai_engine import refine_text_sync
from services.google_docs_export import export_pr_pack_to_docs, is_configured as gdocs_configured
from services.pr_library import (
    get_all_packs,
    get_pack,
    delete_pack,
    duplicate_pack,
    search_packs,
    update_pack_title,
    update_pack_status,
    add_coverage,
    get_stats,
    STATUS_OPTIONS,
    add_version,
    get_versions,
    restore_version,
    add_comment,
    update_pack_tags,
    get_all_tags,
)
from config.positions import get_position_names
from config.spokespeople import get_spokesperson_names

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="PR Library | Riot PR Desk", page_icon=get_page_icon(), layout="wide")
apply_global_styles()
render_sidebar()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STATUS_BADGES = {
    "draft": "Draft",
    "under_review": "Under Review",
    "approved": "Approved",
    "declined": "Passed",
    "pitched": "Pitched",
    "covered": "Covered",
}


def _format_date(iso_str):
    """Return a human-readable date from an ISO timestamp string."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.datetime.fromisoformat(iso_str)
        return dt.strftime("%-d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return iso_str[:10]


def _pack_download_text(pack):
    """Render the full pack as plain text for download."""
    sections = pack.get("sections", {})
    lines = [
        f"RIOT PR DESK — PR PACK",
        f"Title: {pack.get('title', '—')}",
        f"Created: {_format_date(pack.get('created_at', ''))}",
        f"Position: {pack.get('position_name', '—')}",
        f"Spokesperson: {pack.get('spokesperson_key', '—')}",
        f"Audience: {pack.get('audience_key', '—')}",
        f"Tone: {pack.get('tone_key', '—')}",
        f"Status: {pack.get('status', 'draft').title()}",
        "=" * 60,
        "",
    ]
    for section_name, content in sections.items():
        lines.append(f"{'=' * 60}")
        lines.append(section_name)
        lines.append(f"{'=' * 60}")
        lines.append("")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("PR Library")
st.markdown("Browse, search and manage your saved PR packs. Log coverage and track pack performance over time.")
st.divider()

# ---------------------------------------------------------------------------
# Stats row
# ---------------------------------------------------------------------------
stats = get_stats()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total PR Packs", stats["total"])
m2.metric("Created This Month", stats["this_month"])
m3.metric("Coverage Hits Logged", stats["total_coverage"])
m4.metric(
    "Avg Feedback Score",
    f"{stats['avg_vote_pct']}%" if stats["avg_vote_pct"] is not None else "—",
)

st.divider()

# ---------------------------------------------------------------------------
# Search + Filters
# ---------------------------------------------------------------------------
search_col, status_col, position_col, spk_col = st.columns([3, 1.5, 1.5, 1.5])

with search_col:
    lib_query = st.text_input(
        "Search packs",
        placeholder="Title, content, section text…",
        key="lib_search_query",
        label_visibility="collapsed",
    )

with status_col:
    lib_status_filter = st.selectbox(
        "Status",
        ["All"] + STATUS_OPTIONS,
        key="lib_status_filter",
    )

with position_col:
    lib_position_filter = st.selectbox(
        "Position",
        ["All"] + get_position_names(),
        key="lib_position_filter",
    )

with spk_col:
    lib_spk_filter = st.selectbox(
        "Spokesperson",
        ["All"] + get_spokesperson_names(),
        key="lib_spk_filter",
    )

# Sort option
sort_col, _ = st.columns([2, 5])
with sort_col:
    lib_sort = st.selectbox(
        "Sort by",
        ["Newest first", "Status", "Coverage count"],
        key="lib_sort",
        label_visibility="collapsed",
    )

# Tag filter
all_tags = get_all_tags()
if all_tags:
    tag_filter = st.multiselect(
        "Filter by tags",
        options=all_tags,
        key="lib_tag_filter",
        placeholder="Select tags to filter...",
    )
else:
    tag_filter = []

# ---------------------------------------------------------------------------
# Fetch + filter packs
# ---------------------------------------------------------------------------
if lib_query:
    packs = search_packs(lib_query)
else:
    packs = get_all_packs()

if lib_status_filter != "All":
    packs = [p for p in packs if p.get("status") == lib_status_filter]

if lib_position_filter != "All":
    packs = [p for p in packs if p.get("position_name") == lib_position_filter]

if lib_spk_filter != "All":
    packs = [p for p in packs if p.get("spokesperson_key") == lib_spk_filter]

if tag_filter:
    packs = [p for p in packs if any(t in p.get("tags", []) for t in tag_filter)]

# Apply sort
if lib_sort == "Status":
    _status_order = {s: i for i, s in enumerate(STATUS_OPTIONS)}
    packs = sorted(packs, key=lambda p: _status_order.get(p.get("status", "draft"), 99))
elif lib_sort == "Coverage count":
    packs = sorted(packs, key=lambda p: len(p.get("coverage", [])), reverse=True)
# "Newest first" is already the default from get_all_packs / search_packs

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
if not packs:
    st.markdown("")
    empty_col1, empty_col2, empty_col3 = st.columns([1, 2, 1])
    with empty_col2:
        st.markdown(
            """
            <div style="text-align:center; padding: 3rem 0;">
                <div style="font-size: 3rem;">📭</div>
                <h3 style="margin-top: 1rem;">No PR packs saved yet</h3>
                <p style="color: #888;">Generate your first PR pack and save it to the library to track and manage it here.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Create your first PR pack →", type="primary", use_container_width=True):
            st.switch_page("pages/2_pr_generator.py")
    st.stop()

st.caption(f"**{len(packs)}** pack{'s' if len(packs) != 1 else ''} found")

# ---------------------------------------------------------------------------
# Pack cards
# ---------------------------------------------------------------------------
for pack in packs:
    pack_id = pack["id"]
    status = pack.get("status", "draft")
    badge = STATUS_BADGES.get(status, "Draft")
    title = pack.get("title", "Untitled Pack")
    created = _format_date(pack.get("created_at", ""))
    position = pack.get("position_name", "—")
    spokesperson = pack.get("spokesperson_key", "—")
    coverage_count = len(pack.get("coverage", []))

    expander_label = f"{badge}  |  {title}  —  {created}"

    with st.expander(expander_label, expanded=False):

        # --- Title editing ---
        title_col, save_title_col = st.columns([5, 1])
        with title_col:
            new_title = st.text_input(
                "Pack title",
                value=title,
                key=f"lib_title_{pack_id}",
                label_visibility="collapsed",
            )
        with save_title_col:
            if st.button("Save title", key=f"lib_save_title_{pack_id}", use_container_width=True):
                if new_title.strip() and new_title.strip() != title:
                    update_pack_title(pack_id, new_title.strip())
                    st.success("Title updated.")
                    st.rerun()

        # --- Meta row ---
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        meta_col1.caption(f"{created}")
        meta_col2.caption(f"{position}")
        meta_col3.caption(f"{spokesperson}")
        meta_col4.caption(f"{coverage_count} coverage hit{'s' if coverage_count != 1 else ''}")

        st.divider()

        # --- Tabs ---
        tab_content, tab_coverage, tab_actions, tab_history = st.tabs(
            ["Content", "Coverage", "Actions", "History"]
        )

        # =========================================================
        # TAB: CONTENT
        # =========================================================
        with tab_content:
            sections = pack.get("sections", {})

            if not sections:
                st.info("No sections found in this pack.")
            else:
                # Track any live edits in session state (not persisted until Save is clicked)
                edits_key = f"lib_edits_{pack_id}"
                if edits_key not in st.session_state:
                    st.session_state[edits_key] = {}

                has_unsaved = bool(st.session_state[edits_key])

                if has_unsaved:
                    save_col, discard_col = st.columns(2)
                    with save_col:
                        if st.button("Save all edits...", key=f"lib_save_edits_{pack_id}", type="primary", use_container_width=True):
                            from services.pr_library import get_pack as _get_pack
                            live = _get_pack(pack_id)
                            if live:
                                updated_secs = dict(live.get("sections", {}))
                                updated_secs.update(st.session_state[edits_key])
                                # Save a version snapshot then persist
                                add_version(pack_id, dict(live.get("sections", {})), note="Manual AI edits via library")
                                import json, os
                                lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "pr_library.json")
                                with open(lib_path) as f:
                                    all_packs = json.load(f)
                                for p in all_packs:
                                    if p["id"] == pack_id:
                                        p["sections"] = updated_secs
                                        break
                                with open(lib_path, "w") as f:
                                    json.dump(all_packs, f, indent=2)
                                st.session_state.pop(edits_key, None)
                                st.success("Edits saved to library.")
                                st.rerun()
                    with discard_col:
                        if st.button("Discard edits", key=f"lib_discard_edits_{pack_id}", use_container_width=True):
                            st.session_state.pop(edits_key, None)
                            st.rerun()
                    st.divider()

                quick_prompts = [
                    "Make it shorter and punchier",
                    "Make the tone more provocative",
                    "Make the tone more measured",
                    "Add a stronger opening line",
                    "Remove any corporate clichés",
                    "Add a specific statistic",
                    "Strengthen the call to action",
                    "Make the quote more quotable",
                ]

                for section_name, content in sections.items():
                    # Show edited version if available
                    display_content = st.session_state[edits_key].get(section_name, content)
                    edited_flag = "  (edited)" if section_name in st.session_state[edits_key] else ""

                    with st.expander(f"**{section_name}**{edited_flag}", expanded=False):
                        st.markdown(display_content)
                        st.code(display_content, language=None)

                        st.divider()
                        safe_key = f"{pack_id}_{section_name.replace(' ', '_').replace('/', '_')}"
                        refine_toggle_key = f"lib_refine_active_{safe_key}"

                        ref_col, _ = st.columns([1, 2])
                        with ref_col:
                            if st.button(
                                "Refine with AI" if not st.session_state.get(refine_toggle_key) else "Close editor",
                                key=f"lib_refine_toggle_{safe_key}",
                                use_container_width=True,
                            ):
                                st.session_state[refine_toggle_key] = not st.session_state.get(refine_toggle_key, False)
                                st.rerun()

                        if st.session_state.get(refine_toggle_key):
                            st.markdown("""<div style="background:#111;border:1px solid #E8192C33;border-radius:4px;padding:0.75rem 1rem 0.5rem 1rem;margin-top:0.5rem">""", unsafe_allow_html=True)
                            st.caption("**AI EDIT** — Give an instruction:")

                            qp_col1, qp_col2 = st.columns([3, 1])
                            with qp_col1:
                                refine_instr = st.text_input(
                                    "Instruction",
                                    key=f"lib_refine_instr_{safe_key}",
                                    placeholder="e.g. 'Make it punchier', 'Add a stat', 'Shorten by half'...",
                                    label_visibility="collapsed",
                                )
                            with qp_col2:
                                apply_btn = st.button(
                                    "Apply →",
                                    key=f"lib_refine_apply_{safe_key}",
                                    type="primary",
                                    use_container_width=True,
                                    disabled=not refine_instr.strip(),
                                )

                            chip_cols = st.columns(4)
                            for ci, qp in enumerate(quick_prompts):
                                with chip_cols[ci % 4]:
                                    if st.button(qp, key=f"lib_qp_{safe_key}_{ci}", use_container_width=True):
                                        st.session_state[f"lib_refine_instr_{safe_key}"] = qp
                                        st.session_state[f"lib_qp_trigger_{safe_key}"] = True
                                        st.rerun()

                            st.markdown("</div>", unsafe_allow_html=True)

                            should_apply = apply_btn or st.session_state.pop(f"lib_qp_trigger_{safe_key}", False)
                            instr = st.session_state.get(f"lib_refine_instr_{safe_key}", "").strip()

                            if should_apply and instr:
                                with st.spinner(f"Applying: \"{instr}\"..."):
                                    try:
                                        refined = refine_text_sync(display_content, instr, context=section_name)
                                        st.session_state[edits_key][section_name] = refined
                                        st.session_state[refine_toggle_key] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Refinement failed: {e}")

            st.divider()
            if st.button(
                "Re-edit in Generator →",
                key=f"lib_regen_{pack_id}",
                use_container_width=True,
            ):
                # Pre-fill the generator with this pack's input content and settings
                st.session_state["input_content"] = pack.get("input_content", "")
                st.session_state["lib_reload_position"] = pack.get("position_name")
                st.session_state["lib_reload_spokesperson"] = pack.get("spokesperson_key")
                st.session_state["lib_reload_audience"] = pack.get("audience_key")
                st.session_state["lib_reload_tone"] = pack.get("tone_key")
                st.switch_page("pages/2_pr_generator.py")

        # =========================================================
        # TAB: COVERAGE
        # =========================================================
        with tab_coverage:
            coverage_list = pack.get("coverage", [])

            if coverage_list:
                # Summary stats
                sentiments = [c.get("sentiment", "neutral") for c in coverage_list]
                total_reach = sum(c.get("reach", 0) or 0 for c in coverage_list)
                pos_count = sentiments.count("positive")
                neu_count = sentiments.count("neutral")
                neg_count = sentiments.count("negative")

                cs1, cs2, cs3, cs4 = st.columns(4)
                cs1.metric("Pieces logged", len(coverage_list))
                cs2.metric("Est. total reach", f"{total_reach:,}" if total_reach else "—")
                cs3.metric("Positive / Neutral", f"{pos_count} / {neu_count}")
                cs4.metric("Negative", neg_count)

                st.divider()

                for idx, cov in enumerate(coverage_list):
                    logged = _format_date(cov.get("logged_at", ""))
                    st.markdown(
                        f"**{cov.get('publication', '—')}** — {cov.get('journalist', '—')}  "
                        f"| {cov.get('sentiment', '—').title()}  "
                        f"| Reach: {cov.get('reach', '—'):,}  "
                        f"| Logged: {logged}"
                    )
                    if cov.get("notes"):
                        st.caption(f"Notes: {cov['notes']}")
                    if idx < len(coverage_list) - 1:
                        st.divider()

                st.divider()

            # --- Log new coverage form ---
            st.markdown("##### Log new coverage")
            with st.form(key=f"lib_coverage_form_{pack_id}", clear_on_submit=True):
                cov_col1, cov_col2 = st.columns(2)
                with cov_col1:
                    cov_pub = st.text_input("Publication *", placeholder="e.g. The Grocer")
                    cov_journalist = st.text_input("Journalist", placeholder="e.g. Jane Smith")
                with cov_col2:
                    cov_reach = st.number_input(
                        "Est. reach (readers/viewers)",
                        min_value=0,
                        step=1000,
                        value=0,
                        key=f"lib_cov_reach_{pack_id}",
                    )
                    cov_sentiment = st.radio(
                        "Sentiment",
                        ["positive", "neutral", "negative"],
                        horizontal=True,
                        key=f"lib_cov_sentiment_{pack_id}",
                    )
                cov_notes = st.text_area(
                    "Notes",
                    placeholder="Angle, key quote, online or print, etc.",
                    key=f"lib_cov_notes_{pack_id}",
                    height=80,
                )

                submitted_cov = st.form_submit_button("Log Coverage", type="primary")

                if submitted_cov:
                    if not cov_pub.strip():
                        st.error("Publication name is required.")
                    else:
                        add_coverage(
                            pack_id=pack_id,
                            publication=cov_pub,
                            journalist=cov_journalist,
                            reach_estimate=int(cov_reach),
                            sentiment=cov_sentiment,
                            notes=cov_notes,
                        )
                        st.success(f"Coverage logged for **{cov_pub.strip()}**.")
                        st.rerun()

        # =========================================================
        # TAB: ACTIONS
        # =========================================================
        with tab_actions:
            act_col1, act_col2 = st.columns(2)

            # --- Status update ---
            with act_col1:
                st.markdown("**Update status**")
                current_status_idx = STATUS_OPTIONS.index(status) if status in STATUS_OPTIONS else 0
                new_status = st.selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    index=current_status_idx,
                    key=f"lib_status_sel_{pack_id}",
                    label_visibility="collapsed",
                )
                if st.button("Update status", key=f"lib_status_btn_{pack_id}", use_container_width=True):
                    if new_status != status:
                        update_pack_status(pack_id, new_status)
                        st.success(f"Status updated to **{new_status}**.")
                        st.rerun()

            # --- Send to Google Docs (moved up from its own section) ---
            gdocs_key = f"lib_gdocs_url_{pack_id}"
            gdocs_err_key = f"lib_gdocs_err_{pack_id}"

            with act_col2:
                st.markdown("**Send to Google Docs**")
                if gdocs_configured():
                    if st.button(
                        "Send to Google Docs",
                        key=f"lib_send_gdocs_top_{pack_id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        with st.spinner("Creating Google Doc…"):
                            try:
                                result = export_pr_pack_to_docs(pack)
                                st.session_state[gdocs_key] = result["doc_url"]
                                st.session_state.pop(gdocs_err_key, None)
                            except Exception as e:
                                st.session_state[gdocs_err_key] = str(e)

                    if gdocs_key in st.session_state:
                        st.markdown(f"[Open in Google Docs →]({st.session_state[gdocs_key]})")
                    elif gdocs_err_key in st.session_state:
                        st.error(f"Export failed: {st.session_state[gdocs_err_key]}")
                else:
                    st.caption("Google Docs export not configured.")

            st.divider()

            # --- Tags section ---
            st.markdown("**Tags**")
            current_tags = pack.get("tags", [])
            all_pack_tags = get_all_tags()
            tag_input = st.text_input(
                "Add tags (comma-separated)",
                value=", ".join(current_tags),
                key=f"lib_tags_{pack_id}",
                placeholder="e.g. vape-tax, product-launch, activist",
            )
            if st.button("Save tags", key=f"lib_tags_btn_{pack_id}", use_container_width=True):
                new_tags = [t.strip() for t in tag_input.split(",") if t.strip()]
                update_pack_tags(pack_id, new_tags)
                st.success("Tags updated.")
                st.rerun()
            if all_pack_tags:
                st.caption("Existing tags: " + " ".join(f"`{t}`" for t in all_pack_tags))

            st.divider()

            # --- Approval & Comments section ---
            st.markdown("**Approval & Comments**")

            reviewer_input = st.text_input(
                "Reviewer",
                value=pack.get("reviewer", ""),
                key=f"lib_reviewer_{pack_id}",
                placeholder="e.g. Ben Johnson",
            )
            comment_type = st.selectbox(
                "Comment type",
                ["note", "approval", "change_request"],
                format_func=lambda x: {"note": "Note", "approval": "Approval", "change_request": "Change request"}[x],
                key=f"lib_comment_type_{pack_id}",
            )
            comment_text = st.text_area(
                "Add comment",
                height=80,
                key=f"lib_comment_{pack_id}",
                placeholder="e.g. 'Approved — send to The Grocer' or 'Change the headline — too corporate'",
            )
            if st.button("Add comment", key=f"lib_comment_btn_{pack_id}", use_container_width=True):
                if comment_text.strip():
                    author = reviewer_input.strip() or "Team"
                    add_comment(pack_id, author, comment_text.strip(), comment_type)
                    if reviewer_input.strip():
                        from services.pr_library import _load, _save
                        recs = _load()
                        for idx, rec in enumerate(recs):
                            if rec["id"] == pack_id:
                                recs[idx]["reviewer"] = reviewer_input.strip()
                                _save(recs)
                                break
                    # Auto-update status on approval
                    if comment_type == "approval" and status != "approved":
                        update_pack_status(pack_id, "approved")
                    st.success("Comment added.")
                    st.rerun()

            # Show existing comments
            existing_comments = pack.get("comments", [])
            if existing_comments:
                st.caption(f"{len(existing_comments)} comment(s):")
                for c in existing_comments[:5]:
                    ts = c.get("created_at", "")[:16].replace("T", " ")
                    st.markdown(f"**{c.get('author', '?')}** — {c.get('text', '')}")
                    st.caption(ts)

            st.divider()

            # --- Pitch sending (approved packs with suggested journalists) ---
            if status == "approved" and pack.get("suggested_journalists"):
                journalists = pack.get("suggested_journalists", [])
                pitches_sent = pack.get("pitches_sent", False)

                st.markdown("**Send Pitches**")

                if pitches_sent:
                    st.success("Pitches already sent for this pack.")
                elif journalists:
                    st.caption(f"{len(journalists)} journalists matched by AI. Click to open pre-filled email:")
                    st.write("")

                    try:
                        from services.autonomous_engine import build_mailto_link
                        for j in journalists:
                            j_name = j.get("name", "")
                            j_pub = j.get("publication", "")
                            j_email = j.get("email", "")
                            j_reasoning = j.get("reasoning", "")
                            mailto = build_mailto_link(j, pack)

                            mailto_html = (
                                f'<a href="{mailto}" style="display:inline-block;background:#E8192C;'
                                f'color:#FFF;font-family:PPFormula,sans-serif;font-weight:700;'
                                f'font-size:0.78rem;letter-spacing:0.06em;text-transform:uppercase;'
                                f'padding:7px 16px;border-radius:3px;text-decoration:none;margin:3px 4px 3px 0">'
                                f'Send to {j_name} ({j_pub})</a>'
                            ) if mailto else ""

                            no_email_note = (
                                f'<span style="font-size:0.72rem;color:#555">No email on file for {j_name}</span>'
                            ) if not mailto else ""

                            st.markdown(
                                f'<div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.5rem">'
                                f'<div style="flex:1">'
                                f'<span style="font-size:0.82rem;color:#CCC">{j_name}</span>'
                                f'<span style="font-size:0.72rem;color:#555"> &middot; {j_pub}</span>'
                                f'</div>'
                                f'{mailto_html}{no_email_note}'
                                f'</div>'
                                f'<div style="font-size:0.72rem;color:#555;font-style:italic;'
                                f'margin-bottom:0.4rem;margin-left:0.25rem">{j_reasoning}</div>',
                                unsafe_allow_html=True,
                            )
                    except Exception as _pe:
                        st.caption(f"Pitch links unavailable: {_pe}")

                    st.write("")
                    if st.button("Mark pitches as sent", key=f"lib_mark_sent_{pack_id}", use_container_width=True):
                        try:
                            from services.pr_library import mark_pitches_sent
                            from services.journalist_history import log_contact
                            mark_pitches_sent(pack_id)
                            for j in journalists:
                                try:
                                    log_contact(
                                        journalist_id=j.get("id", ""),
                                        contact_type="pitch",
                                        subject=f"Pitch sent for: {title}",
                                        pack_id=pack_id,
                                    )
                                except Exception:
                                    pass
                            st.success("Marked as pitched.")
                            st.rerun()
                        except Exception as _me:
                            st.error(f"Error: {_me}")
                else:
                    if st.button("Match journalists with AI", key=f"lib_match_j_{pack_id}", use_container_width=True):
                        with st.spinner("Matching journalists…"):
                            try:
                                from services.autonomous_engine import auto_match_journalists
                                auto_match_journalists(pack_id)
                                st.success("Journalists matched.")
                                st.rerun()
                            except Exception as _mex:
                                st.error(f"Matching failed: {_mex}")

                st.divider()

            # --- Duplicate ---
            dup_col, del_col = st.columns(2)

            with dup_col:
                if st.button(
                    "Duplicate pack",
                    key=f"lib_dup_{pack_id}",
                    use_container_width=True,
                ):
                    new_pack = duplicate_pack(pack_id)
                    st.success(f"Duplicated as **{new_pack['title']}**.")
                    st.rerun()

            # --- Delete (with confirmation) ---
            with del_col:
                confirm_key = f"lib_confirm_delete_{pack_id}"

                if st.session_state.get(confirm_key):
                    st.warning("Are you sure? This cannot be undone.")
                    confirm_col1, confirm_col2 = st.columns(2)
                    with confirm_col1:
                        if st.button(
                            "Yes, delete",
                            key=f"lib_del_confirm_{pack_id}",
                            type="primary",
                            use_container_width=True,
                        ):
                            delete_pack(pack_id)
                            st.session_state.pop(confirm_key, None)
                            st.success("Pack deleted.")
                            st.rerun()
                    with confirm_col2:
                        if st.button(
                            "Cancel",
                            key=f"lib_del_cancel_{pack_id}",
                            use_container_width=True,
                        ):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                else:
                    if st.button(
                        "Delete pack",
                        key=f"lib_del_{pack_id}",
                        use_container_width=True,
                    ):
                        st.session_state[confirm_key] = True
                        st.rerun()

        # =========================================================
        # TAB: HISTORY
        # =========================================================
        with tab_history:
            versions = get_versions(pack_id)

            if not versions:
                st.info("No version history yet. Version snapshots are saved automatically when you regenerate sections.")
            else:
                st.caption(f"{len(versions)} version snapshot(s) saved.")

                for v in versions:
                    v_id = v["version_id"]
                    saved_at = v.get("saved_at", "")[:16].replace("T", " ")
                    note = v.get("note", "")
                    v_sections = v.get("sections", {})

                    with st.expander(
                        f"Version {v_id[:6]} — {saved_at}" + (f" — *{note}*" if note else ""),
                        expanded=False
                    ):
                        st.caption(f"Contains {len(v_sections)} sections: {', '.join(v_sections.keys())}")

                        # Show a preview of the press release
                        if "Press Release" in v_sections:
                            st.caption("**Press Release preview:**")
                            st.caption(v_sections["Press Release"][:300] + "...")

                        v_col1, v_col2 = st.columns(2)
                        with v_col1:
                            if st.button(
                                "Restore this version",
                                key=f"lib_restore_{pack_id}_{v_id}",
                                use_container_width=True,
                                help="Replace current pack content with this version"
                            ):
                                restore_version(pack_id, v_id)
                                st.success("Version restored.")
                                st.rerun()
                        with v_col2:
                            # Send this version to Google Docs
                            if st.button(
                                "Send version to Google Docs",
                                key=f"lib_gdocs_ver_{pack_id}_{v_id}",
                                use_container_width=True,
                            ):
                                with st.spinner("Creating Google Doc…"):
                                    try:
                                        from services.google_docs_export import export_pr_pack_to_docs
                                        version_pack = {
                                            **pack,
                                            "title": f"{pack.get('title','Pack')} (v{v_id[:6]})",
                                            "sections": v_sections,
                                        }
                                        gd = export_pr_pack_to_docs(version_pack)
                                        st.markdown(f"[Open in Google Docs →]({gd['doc_url']})")
                                    except Exception as ex:
                                        st.error(f"Export failed: {ex}")
