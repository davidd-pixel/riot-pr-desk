"""
Media Lists — group journalists into named lists for campaigns, pitches and outreach.
"""

import streamlit as st

from utils.styles import apply_global_styles, render_sidebar
import services.media_lists as media_lists
import services.journalist_db as journalist_db
from services.journalist_db import BEAT_OPTIONS, TYPE_OPTIONS

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Media Lists | Riot PR Desk", page_icon="📋", layout="wide")
apply_global_styles()
render_sidebar()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_stars(score: int) -> str:
    score = max(1, min(5, int(score or 3)))
    return "⭐" * score + "☆" * (5 - score)


def _render_beats_inline(beats: list) -> str:
    return " ".join(f"`{b}`" for b in beats) if beats else "—"


def _short_date(iso: str) -> str:
    """Turn an ISO timestamp into a short readable date."""
    if not iso:
        return "—"
    try:
        return iso[:10]
    except Exception:
        return iso


def _most_recently_updated(lists: list) -> str:
    if not lists:
        return "—"
    latest = max(lists, key=lambda l: l.get("updated_at", ""))
    return latest.get("name", "—")


def _total_contacts(lists: list) -> int:
    """Unique journalist IDs across all lists."""
    all_ids = set()
    for lst in lists:
        all_ids.update(lst.get("journalist_ids", []))
    return len(all_ids)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📋 Media Lists")
st.caption("Group journalists into targeted lists for campaigns, pitches and outreach.")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
all_lists = media_lists.get_all_lists()

# ---------------------------------------------------------------------------
# Stats row
# ---------------------------------------------------------------------------
if all_lists:
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total lists", len(all_lists))
    with m2:
        st.metric("Total unique contacts", _total_contacts(all_lists))
    with m3:
        st.metric("Recently updated", _most_recently_updated(all_lists))

st.divider()

# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------
if not all_lists and not st.session_state.get("ml_show_create_form", False):
    st.markdown(
        """
<div style="text-align:center;padding:3rem 2rem;color:#888">
    <div style="font-size:3rem">📋</div>
    <h3 style="color:#ccc">No media lists yet</h3>
    <p>Media lists let you group journalists for specific campaigns.<br>
    Build one for your next vape tax response, product launch or activist campaign.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("➕ Create your first media list", type="primary", key="ml_create_first"):
        st.session_state["ml_show_create_form"] = True
        st.rerun()

# ---------------------------------------------------------------------------
# Create-list form (inline, shown above the two-column layout when active)
# ---------------------------------------------------------------------------
if st.session_state.get("ml_show_create_form", False):
    st.subheader("New media list")
    with st.form("ml_create_form", clear_on_submit=True):
        cf_name = st.text_input("List name *", placeholder="e.g. Vape Tax comment piece contacts")
        cf_desc = st.text_area("Description", placeholder="What is this list for?", height=80)
        cf_tags = st.text_input("Tags (comma-separated)", placeholder="e.g. vaping, regulation, trade")
        c1, c2 = st.columns([1, 1])
        with c1:
            submitted = st.form_submit_button("Create list", type="primary", use_container_width=True)
        with c2:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    if submitted:
        if not cf_name.strip():
            st.error("List name is required.")
        else:
            tags = [t.strip() for t in cf_tags.split(",") if t.strip()]
            new_lst = media_lists.create_list(cf_name, cf_desc, tags)
            st.session_state["ml_show_create_form"] = False
            st.session_state["ml_active_list_id"] = new_lst["id"]
            st.success(f"Created **{new_lst['name']}**.")
            st.rerun()
    elif cancelled:
        st.session_state["ml_show_create_form"] = False
        st.rerun()

    st.divider()

# ---------------------------------------------------------------------------
# Two-column layout (only when there are lists)
# ---------------------------------------------------------------------------
all_lists = media_lists.get_all_lists()   # refresh after possible creation
if all_lists:
    left_col, right_col = st.columns([1, 2])

    # -----------------------------------------------------------------------
    # Left column — list of all media lists
    # -----------------------------------------------------------------------
    with left_col:
        st.markdown("#### Your lists")

        if st.button("➕ New List", key="ml_new_btn", use_container_width=True):
            st.session_state["ml_show_create_form"] = True
            st.rerun()

        st.markdown("")

        active_id = st.session_state.get("ml_active_list_id")

        for lst in sorted(all_lists, key=lambda l: l.get("updated_at", ""), reverse=True):
            lid = lst["id"]
            journalist_count = len(lst.get("journalist_ids", []))
            tags = lst.get("tags", [])
            tag_str = " · ".join(tags) if tags else ""

            is_active = lid == active_id
            btn_label = f"{'▶ ' if is_active else ''}{lst['name']}"

            if st.button(
                btn_label,
                key=f"ml_list_btn_{lid}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["ml_active_list_id"] = lid
                # Reset per-list UI state
                st.session_state.pop("ml_search_query", None)
                st.session_state.pop("ml_bulk_selection", None)
                st.session_state.pop("ml_confirm_delete", None)
                st.session_state.pop("ml_copy_name", None)
                st.rerun()

            caption_parts = [f"{journalist_count} contact{'s' if journalist_count != 1 else ''}"]
            if tag_str:
                caption_parts.append(tag_str)
            st.caption(" · ".join(caption_parts))

    # -----------------------------------------------------------------------
    # Right column — selected list detail
    # -----------------------------------------------------------------------
    with right_col:
        active_id = st.session_state.get("ml_active_list_id")

        if not active_id:
            st.markdown(
                """
                <div style="text-align:center; padding: 3rem 1rem; color:#888;">
                    <div style="font-size:2rem;">👈</div>
                    <p>Select a list from the left to view and manage it.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            lst = media_lists.get_list(active_id)

            if not lst:
                st.warning("List not found. It may have been deleted.")
                st.session_state.pop("ml_active_list_id", None)
            else:
                # ---- List metadata edit form --------------------------------
                st.subheader("List details")

                with st.form(f"ml_edit_meta_{active_id}"):
                    new_name = st.text_input("Name", value=lst["name"])
                    new_desc = st.text_area("Description", value=lst.get("description", ""), height=80)
                    new_tags_raw = st.text_input(
                        "Tags (comma-separated)",
                        value=", ".join(lst.get("tags", [])),
                    )
                    if st.form_submit_button("Save changes", type="primary"):
                        new_tags = [t.strip() for t in new_tags_raw.split(",") if t.strip()]
                        media_lists.update_list(active_id, {
                            "name": new_name,
                            "description": new_desc,
                            "tags": new_tags,
                        })
                        st.success("List updated.")
                        st.rerun()

                st.markdown(
                    f"<span style='background:#1A1D24;border:1px solid #2A2D35;"
                    f"border-radius:12px;padding:4px 12px;font-size:0.85rem;'>"
                    f"👥 {len(lst.get('journalist_ids', []))} contact"
                    f"{'s' if len(lst.get('journalist_ids', [])) != 1 else ''}"
                    f"</span>&nbsp;&nbsp;"
                    f"<span style='color:#888;font-size:0.8rem;'>Updated {_short_date(lst.get('updated_at'))}</span>",
                    unsafe_allow_html=True,
                )

                st.divider()

                # ---- Add journalists section --------------------------------
                st.markdown("#### Add journalists")

                search_tab, filter_tab = st.tabs(["Search by name / publication", "Filter by type or beat"])

                with search_tab:
                    search_query = st.text_input(
                        "Search",
                        placeholder="Name, publication, beat…",
                        key="ml_search_query",
                    )

                    if search_query:
                        results = journalist_db.search(search_query)
                        # Exclude already-in-list
                        already_in = set(lst.get("journalist_ids", []))
                        results = [j for j in results if j["id"] not in already_in]

                        if not results:
                            st.caption("No matching journalists not already in this list.")
                        else:
                            # Bulk select controls
                            if "ml_bulk_selection" not in st.session_state:
                                st.session_state["ml_bulk_selection"] = set()

                            select_all = st.checkbox(
                                f"Select all ({len(results)})",
                                key="ml_select_all_cb",
                            )
                            if select_all:
                                st.session_state["ml_bulk_selection"] = {j["id"] for j in results}
                            else:
                                # If unchecked, clear only if it was fully selected before
                                if st.session_state["ml_bulk_selection"] == {j["id"] for j in results}:
                                    st.session_state["ml_bulk_selection"] = set()

                            bulk_sel = st.session_state["ml_bulk_selection"]

                            for j in results:
                                jid = j["id"]
                                row_cols = st.columns([0.5, 3, 1])
                                with row_cols[0]:
                                    checked = st.checkbox(
                                        "",
                                        value=jid in bulk_sel,
                                        key=f"ml_cb_{active_id}_{jid}",
                                        label_visibility="collapsed",
                                    )
                                    if checked:
                                        bulk_sel.add(jid)
                                    else:
                                        bulk_sel.discard(jid)
                                with row_cols[1]:
                                    beats_str = _render_beats_inline(j.get("beats", []))
                                    st.markdown(
                                        f"**{j.get('name', '?')}** · {j.get('publication', '—')}  \n"
                                        f"{beats_str}  {_render_stars(j.get('relationship_score', 3))}"
                                    )
                                with row_cols[2]:
                                    if st.button("➕ Add", key=f"ml_add_{active_id}_{jid}", use_container_width=True):
                                        media_lists.add_journalist_to_list(active_id, jid)
                                        st.session_state["ml_bulk_selection"] = set()
                                        st.rerun()

                            st.session_state["ml_bulk_selection"] = bulk_sel
                            n_sel = len(bulk_sel)
                            if n_sel > 0:
                                if st.button(
                                    f"Add selected ({n_sel})",
                                    type="primary",
                                    use_container_width=True,
                                    key="ml_add_bulk_btn",
                                ):
                                    for jid in bulk_sel:
                                        media_lists.add_journalist_to_list(active_id, jid)
                                    st.session_state["ml_bulk_selection"] = set()
                                    st.session_state.pop("ml_search_query", None)
                                    st.success(f"Added {n_sel} journalists to the list.")
                                    st.rerun()

                with filter_tab:
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        ft_type = st.selectbox("Type", ["All"] + TYPE_OPTIONS, key="ml_ft_type")
                    with fc2:
                        ft_beat = st.selectbox("Beat", ["All"] + BEAT_OPTIONS, key="ml_ft_beat")

                    if ft_type != "All" or ft_beat != "All":
                        filter_results = journalist_db.filter_by(
                            type_filter=ft_type if ft_type != "All" else None,
                            beat_filter=ft_beat if ft_beat != "All" else None,
                        )
                        already_in = set(lst.get("journalist_ids", []))
                        filter_results = [j for j in filter_results if j["id"] not in already_in]

                        if not filter_results:
                            st.caption("No matching journalists not already in this list.")
                        else:
                            st.caption(f"{len(filter_results)} matching journalist{'s' if len(filter_results) != 1 else ''} not in this list.")
                            if st.button(
                                f"Add all matching ({len(filter_results)})",
                                type="primary",
                                use_container_width=True,
                                key="ml_filter_add_all",
                            ):
                                for j in filter_results:
                                    media_lists.add_journalist_to_list(active_id, j["id"])
                                st.success(f"Added {len(filter_results)} journalists.")
                                st.rerun()
                    else:
                        st.caption("Select a type or beat to filter journalists.")

                st.divider()

                # ---- Journalists in this list ------------------------------
                in_list = media_lists.get_journalists_in_list(active_id)
                st.markdown(f"#### Journalists in this list ({len(in_list)})")

                if not in_list:
                    st.caption("No journalists in this list yet. Use the section above to add some.")
                else:
                    for j in in_list:
                        jid = j["id"]
                        beats_str = _render_beats_inline(j.get("beats", []))
                        stars = _render_stars(j.get("relationship_score", 3))
                        email = j.get("email", "") or "—"

                        row = st.columns([3, 2, 1, 1])
                        with row[0]:
                            st.markdown(
                                f"**{j.get('name', '?')}**  \n"
                                f"{j.get('job_title', '')} · {j.get('publication', '—')}"
                            )
                        with row[1]:
                            st.markdown(f"{beats_str}  \n{stars}")
                        with row[2]:
                            st.caption(email)
                        with row[3]:
                            if st.button("✕", key=f"ml_remove_{active_id}_{jid}", help="Remove from list"):
                                media_lists.remove_journalist_from_list(active_id, jid)
                                st.rerun()

                st.divider()

                # ---- Use this list section ----------------------------------
                st.markdown("#### Use this list")
                use_c1, use_c2 = st.columns(2)

                with use_c1:
                    if st.button("📤 Export emails", use_container_width=True, key="ml_export_emails"):
                        media_lists.mark_list_used(active_id)
                        st.session_state["ml_show_emails"] = True

                with use_c2:
                    if st.button("✍️ Match to PR pack", use_container_width=True, key="ml_match_pr"):
                        media_lists.mark_list_used(active_id)
                        st.session_state["journalist_story_context"] = lst["name"]
                        st.switch_page("pages/6_journalists.py")

                if st.session_state.get("ml_show_emails"):
                    emails = [j.get("email", "") for j in in_list if j.get("email")]
                    if emails:
                        email_str = ", ".join(emails)
                        st.text_area(
                            "Email addresses (copy below)",
                            value=email_str,
                            height=100,
                            key="ml_email_export_area",
                        )
                        st.caption(f"{len(emails)} email address{'es' if len(emails) != 1 else ''}")
                    else:
                        st.warning("No email addresses found for journalists in this list.")

                st.divider()

                # ---- Copy list / Delete ------------------------------------
                action_c1, action_c2 = st.columns(2)

                with action_c1:
                    copy_name_default = f"{lst['name']} (copy)"
                    copy_name = st.text_input(
                        "Copy list as",
                        value=st.session_state.get("ml_copy_name", copy_name_default),
                        key="ml_copy_name_input",
                    )
                    if st.button("📋 Copy list", use_container_width=True, key="ml_copy_btn"):
                        if copy_name.strip():
                            new_lst = media_lists.copy_list(active_id, copy_name.strip())
                            st.session_state["ml_active_list_id"] = new_lst["id"]
                            st.success(f"Copied to **{new_lst['name']}**.")
                            st.rerun()
                        else:
                            st.error("Please enter a name for the copied list.")

                with action_c2:
                    st.markdown("&nbsp;", unsafe_allow_html=True)  # vertical spacer
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    if not st.session_state.get("ml_confirm_delete"):
                        if st.button(
                            "🗑️ Delete list",
                            use_container_width=True,
                            key="ml_delete_btn",
                            type="secondary",
                        ):
                            st.session_state["ml_confirm_delete"] = True
                            st.rerun()
                    else:
                        st.warning(f"Delete **{lst['name']}**? This cannot be undone.")
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            if st.button("Yes, delete", type="primary", use_container_width=True, key="ml_confirm_delete_yes"):
                                media_lists.delete_list(active_id)
                                st.session_state.pop("ml_active_list_id", None)
                                st.session_state.pop("ml_confirm_delete", None)
                                st.success("List deleted.")
                                st.rerun()
                        with dc2:
                            if st.button("Cancel", use_container_width=True, key="ml_confirm_delete_no"):
                                st.session_state.pop("ml_confirm_delete", None)
                                st.rerun()
