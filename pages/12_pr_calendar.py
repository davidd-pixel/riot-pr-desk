"""
PR Calendar — visual planning view combining cultural events and PR packs.
"""

import calendar
import streamlit as st
from datetime import date, datetime, timedelta
from itertools import groupby

from utils.styles import apply_global_styles, render_sidebar, get_page_icon

st.set_page_config(
    page_title="PR Calendar | Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
)

apply_global_styles()
render_sidebar()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

try:
    from services.cultural_calendar import CATEGORIES
except Exception:
    CATEGORIES = ["Sport", "Music & Festivals", "Entertainment", "UK Calendar", "Awareness Days", "Riot-Specific"]

HORIZON_MAP = {
    "Next 30 days": 30,
    "Next 60 days": 60,
    "Next 90 days": 90,
    "Next 6 months": 180,
    "Full year": 365,
}

CATEGORY_ICONS = {
    "Sport": "",
    "Music & Festivals": "",
    "Entertainment": "",
    "UK Calendar": "",
    "Awareness Days": "",
    "Riot-Specific": "",
}

STATUS_ICONS = {
    "draft": "",
    "approved": "",
    "pitched": "",
    "covered": "",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_timeline(days_ahead: int, category_filter: list, show_packs: bool) -> list:
    """Merge cultural events and PR packs into a single sorted timeline."""
    items = []

    # Cultural calendar events
    try:
        from services.cultural_calendar import get_upcoming_events
        events = get_upcoming_events(days_ahead=days_ahead)
        for e in events:
            cat = e.get("category", "")
            if cat in category_filter:
                items.append({
                    "date": e.get("date", ""),
                    "type": "event",
                    "title": e.get("name", ""),
                    "category": cat,
                    "description": e.get("description", ""),
                    "relevance": e.get("relevance_to_riot", ""),
                    "status": e.get("_status", ""),
                    "custom": e.get("custom", False),
                    "_raw": e,
                })
    except Exception:
        pass

    # PR packs (past activity)
    if show_packs:
        try:
            from services.pr_library import get_all_packs
            packs = get_all_packs()
            for p in packs:
                created = p.get("created_at", "")[:10]
                items.append({
                    "date": created,
                    "type": "pack",
                    "title": p.get("title", "PR Pack"),
                    "category": "PR Pack",
                    "description": f"Position: {p.get('position_name', '')} · {p.get('spokesperson_key', '')}",
                    "relevance": "",
                    "status": p.get("status", "draft"),
                    "_raw": p,
                })
        except Exception:
            pass

    items.sort(key=lambda x: x.get("date", "9999"))
    return items


def _month_label(date_str: str) -> str:
    try:
        return datetime.strptime(date_str[:7], "%Y-%m").strftime("%B %Y")
    except Exception:
        return date_str[:7] if date_str else "Unknown"


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("PR Calendar")
st.caption("Your complete view of past activity, upcoming events and planning horizon")

st.divider()

# ---------------------------------------------------------------------------
# Controls row
# ---------------------------------------------------------------------------

ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([2, 4, 1])

with ctrl_col1:
    horizon_label = st.selectbox(
        "View horizon",
        options=list(HORIZON_MAP.keys()),
        index=1,
        key="pcal_horizon",
    )

with ctrl_col2:
    selected_categories = st.multiselect(
        "Show categories",
        options=CATEGORIES + ["PR Packs"],
        default=CATEGORIES + ["PR Packs"],
        key="pcal_categories",
    )

with ctrl_col3:
    st.write("")  # vertical alignment nudge
    refresh = st.button("Refresh", use_container_width=True, key="pcal_refresh")
    if refresh:
        st.cache_data.clear()
        st.rerun()

# Derive filter parameters from controls
days_ahead = HORIZON_MAP[horizon_label]
show_packs = "PR Packs" in selected_categories
active_categories = [c for c in selected_categories if c != "PR Packs"]

# Load all timeline data once, shared across both tabs
all_items = _build_timeline(days_ahead, active_categories, show_packs)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_timeline, tab_grid = st.tabs(["Timeline View", "Month Grid"])


# ===========================================================================
# TAB 1 — Timeline View
# ===========================================================================

with tab_timeline:
    if not all_items:
        st.info("No events or PR packs found for the selected filters and horizon.")
    else:
        current_month = None
        for item in all_items:
            month = _month_label(item["date"])

            # Month header
            if month != current_month:
                if current_month is not None:
                    st.write("")  # breathing room between months
                st.markdown(f"### {month}")
                current_month = month

            if item["type"] == "event":
                cat = item.get("category", "")
                icon = CATEGORY_ICONS.get(cat, "")
                status = item.get("status", "")
                status_label = f" — **{status}**" if status else ""
                custom_badge = " `custom`" if item.get("custom") else ""

                col1, col2, col3 = st.columns([1, 5, 2])
                with col1:
                    date_part = item["date"][5:] if item["date"] else "?"
                    st.caption(date_part)
                with col2:
                    icon_prefix = f"{icon} " if icon else ""
                    st.markdown(
                        f"{icon_prefix}**{item['title']}** `{cat}`{custom_badge}{status_label}"
                    )
                    if item.get("description"):
                        st.caption(item["description"][:120])
                with col3:
                    btn_key = f"cal_{item['date']}_{item['title'][:20].replace(' ', '_')}"
                    if st.button(
                        "News-Jack",
                        key=btn_key,
                        use_container_width=True,
                    ):
                        st.session_state["pr_input"] = (
                            f"{item['title']}\n\n{item.get('description', '')}"
                        )
                        st.switch_page("pages/2_pr_generator.py")

            elif item["type"] == "pack":
                status = item.get("status", "draft")
                icon = STATUS_ICONS.get(status, "")

                col1, col2, col3 = st.columns([1, 5, 2])
                with col1:
                    date_part = item["date"][5:] if item["date"] else "?"
                    st.caption(date_part)
                with col2:
                    pack_icon_prefix = f"{icon} " if icon else ""
                    st.markdown(f"{pack_icon_prefix}**{item['title']}** `PR Pack`")
                    st.caption(item.get("description", ""))
                with col3:
                    btn_key = f"pack_{item['date']}_{item['title'][:20].replace(' ', '_')}"
                    if st.button(
                        "Open →",
                        key=btn_key,
                        use_container_width=True,
                    ):
                        st.switch_page("pages/7_pr_library.py")


# ===========================================================================
# TAB 2 — Month Grid
# ===========================================================================

with tab_grid:
    today = date.today()

    # Month selector — last month through 6 months ahead
    month_options = []
    for i in range(-1, 8):
        # Advance by roughly 31 days then snap to 1st
        candidate = (today.replace(day=1) + timedelta(days=31 * i)).replace(day=1)
        if candidate not in month_options:
            month_options.append(candidate)

    # Default to current month (index 1, since -1 offset is index 0)
    selected_month = st.selectbox(
        "Select month",
        options=month_options,
        format_func=lambda d: d.strftime("%B %Y"),
        index=1,
        key="pcal_grid_month",
    )

    year, month = selected_month.year, selected_month.month
    cal = calendar.monthcalendar(year, month)

    # Filter all_items (uses the full library regardless of horizon for packs)
    # For the grid we want ALL items for the selected month, not just the horizon window
    # so we fetch separately
    try:
        from services.cultural_calendar import get_all_events
        grid_events_raw = get_all_events()
    except Exception:
        grid_events_raw = []

    try:
        from services.pr_library import get_all_packs
        grid_packs_raw = get_all_packs()
    except Exception:
        grid_packs_raw = []

    month_str = selected_month.strftime("%Y-%m")

    grid_items = []

    for e in grid_events_raw:
        cat = e.get("category", "")
        if active_categories and cat not in active_categories:
            continue
        # Include if event date OR end_date falls within the selected month
        e_start = e.get("date", "")
        e_end = e.get("end_date") or e_start
        # Check overlap: event spans the month if start <= month-end AND end >= month-start
        month_start_str = selected_month.strftime("%Y-%m-01")
        # last day of month
        last_day = calendar.monthrange(year, month)[1]
        month_end_str = selected_month.strftime(f"%Y-%m-{last_day:02d}")

        if e_start <= month_end_str and e_end >= month_start_str:
            # Enumerate each day of the event that falls in this month
            try:
                ev_start_d = datetime.strptime(e_start, "%Y-%m-%d").date()
                ev_end_d = datetime.strptime(e_end, "%Y-%m-%d").date()
            except Exception:
                continue
            m_start_d = date(year, month, 1)
            m_end_d = date(year, month, last_day)
            span_start = max(ev_start_d, m_start_d)
            span_end = min(ev_end_d, m_end_d)
            cur = span_start
            while cur <= span_end:
                grid_items.append({
                    "date": cur.strftime("%Y-%m-%d"),
                    "type": "event",
                    "title": e.get("name", ""),
                    "category": cat,
                    "description": e.get("description", ""),
                    "status": "",
                    "custom": e.get("custom", False),
                })
                cur += timedelta(days=1)

    if show_packs:
        for p in grid_packs_raw:
            created = p.get("created_at", "")[:10]
            if created.startswith(month_str):
                grid_items.append({
                    "date": created,
                    "type": "pack",
                    "title": p.get("title", "PR Pack"),
                    "category": "PR Pack",
                    "description": f"Position: {p.get('position_name', '')} · {p.get('spokesperson_key', '')}",
                    "status": p.get("status", "draft"),
                    "custom": False,
                })

    # Index by date
    items_by_date: dict = {}
    for item in grid_items:
        d = item["date"]
        items_by_date.setdefault(d, []).append(item)

    # Render day-name headers
    st.write("")
    day_headers = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    header_cols = st.columns(7)
    for i, h in enumerate(day_headers):
        with header_cols[i]:
            st.markdown(f"**{h}**")

    # Initialise selected date in session state
    if "pcal_selected_date" not in st.session_state:
        st.session_state["pcal_selected_date"] = None

    for week in cal:
        week_cols = st.columns(7)
        for i, day_num in enumerate(week):
            with week_cols[i]:
                if day_num == 0:
                    st.write("")
                else:
                    day_date = date(year, month, day_num)
                    date_str = day_date.strftime("%Y-%m-%d")
                    day_items = items_by_date.get(date_str, [])
                    is_today = day_date == today
                    label = f"**{day_num}**" if is_today else str(day_num)

                    if day_items:
                        dots = "".join(
                            "●" if it["type"] == "pack" else "●"
                            for it in day_items[:3]
                        )
                        extra = f"+{len(day_items)-3}" if len(day_items) > 3 else ""
                        if st.button(
                            f"{label}\n{dots}{extra}",
                            key=f"pcal_grid_{date_str}",
                            use_container_width=True,
                        ):
                            st.session_state["pcal_selected_date"] = date_str
                            st.rerun()
                    else:
                        st.caption(f"{label}")

    # Selected-date detail panel
    selected_date = st.session_state.get("pcal_selected_date")
    if selected_date:
        sel_items = items_by_date.get(selected_date, [])
        if sel_items:
            st.divider()
            st.markdown(f"### Items for {selected_date}")
            for item in sel_items:
                if item["type"] == "event":
                    cat = item.get("category", "")
                    icon = CATEGORY_ICONS.get(cat, "")
                    custom_tag = " _(custom)_" if item.get("custom") else ""
                    icon_prefix = f"{icon} " if icon else ""
                    st.markdown(
                        f"{icon_prefix}**{item['title']}**{custom_tag} `{cat}`"
                    )
                    if item.get("description"):
                        st.caption(item["description"][:200])
                    news_jack_key = f"pcal_nj_{selected_date}_{item['title'][:20].replace(' ', '_')}"
                    if st.button(
                        "News-Jack this",
                        key=news_jack_key,
                    ):
                        st.session_state["pr_input"] = (
                            f"{item['title']}\n\n{item.get('description', '')}"
                        )
                        st.switch_page("pages/2_pr_generator.py")
                elif item["type"] == "pack":
                    status = item.get("status", "draft")
                    icon = STATUS_ICONS.get(status, "")
                    icon_prefix = f"{icon} " if icon else ""
                    st.markdown(
                        f"{icon_prefix}**{item['title']}** `PR Pack` — _{status.title()}_"
                    )
                    if item.get("description"):
                        st.caption(item["description"])
                    if st.button(
                        "Open in PR Library →",
                        key=f"pcal_open_pack_{selected_date}_{item['title'][:20].replace(' ', '_')}",
                    ):
                        st.switch_page("pages/7_pr_library.py")
        else:
            st.info(f"No items found for {selected_date}.")
        if st.button("Clear selection", key="pcal_clear_sel"):
            st.session_state["pcal_selected_date"] = None
            st.rerun()
