import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

_sa_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
if _sa_content and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
    import tempfile, json as _json
    try:
        _sa_data = _json.loads(_sa_content)
        _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        _json.dump(_sa_data, _tmp)
        _tmp.close()
        os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = _tmp.name
    except Exception:
        pass

from utils.styles import apply_global_styles, render_sidebar, get_page_icon

st.set_page_config(
    page_title="Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
render_sidebar()

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

try:
    from services.pr_library import get_stats as lib_stats, get_recent_packs
    lib = lib_stats()
    recent_packs = get_recent_packs(5)
except Exception:
    lib = {"total": 0, "this_month": 0, "total_coverage": 0}
    recent_packs = []

try:
    from services.journalist_db import get_journalist_count
    j_count = get_journalist_count()
except Exception:
    j_count = 0

try:
    from services.feedback import get_stats as fb_stats
    fb = fb_stats()
    approval_pct = round(fb["up"] / fb["total"] * 100) if fb.get("total", 0) > 0 else 0
except Exception:
    approval_pct = 0

try:
    from services.cultural_calendar import get_upcoming_events
    upcoming = get_upcoming_events(days_ahead=30)
except Exception:
    upcoming = []

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("PR Desk")
st.caption("Live intelligence dashboard")

st.divider()

# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.metric(
        "PR Packs Generated",
        lib["total"],
        delta=f"+{lib['this_month']} this month" if lib.get("this_month") else None,
    )
with m2:
    st.metric("Press Contacts", j_count)
with m3:
    st.metric("AI Approval Rate", f"{approval_pct}%", help="% of AI outputs voted up")
with m4:
    st.metric("Coverage Logged", lib.get("total_coverage", 0))

st.divider()

# ---------------------------------------------------------------------------
# Main grid — Recent activity (left) | Upcoming + Actions (right)
# ---------------------------------------------------------------------------

col_left, spacer, col_right = st.columns([5, 1, 3])

# ── LEFT: Recent PR Packs ─────────────────────────────────────────────────

with col_left:
    st.markdown("#### Recent PR Packs")

    if not recent_packs:
        st.markdown(
            '<p style="color:#666;font-size:0.9rem;margin-bottom:1rem">'
            'No packs generated yet.</p>',
            unsafe_allow_html=True,
        )
        if st.button("Create your first PR Pack →", type="primary"):
            st.switch_page("pages/2_pr_generator.py")
    else:
        STATUS_COLOURS = {
            "draft":    ("#888",    "Draft"),
            "approved": ("#4ade80", "Approved"),
            "pitched":  ("#60a5fa", "Pitched"),
            "covered":  ("#E8192C", "Covered"),
        }

        for pack in recent_packs:
            status = pack.get("status", "draft")
            colour, label = STATUS_COLOURS.get(status, ("#888", "Draft"))

            # Format date DD/MM/YYYY
            raw_date = pack.get("created_at", "")[:10]
            try:
                y, m, d = raw_date.split("-")
                date_display = f"{d}/{m}/{y}"
            except Exception:
                date_display = raw_date

            title = pack.get("title", "Untitled")
            position = pack.get("position_name", "")
            coverage_hits = len(pack.get("coverage", []))

            # Pre-build meta line to avoid inline conditionals inside HTML f-string
            meta_parts = [date_display]
            if position:
                meta_parts.append(position)
            if coverage_hits:
                s = "s" if coverage_hits != 1 else ""
                meta_parts.append(
                    f'<span style="color:#E8192C">{coverage_hits} coverage hit{s}</span>'
                )
            meta_line = "&nbsp;&middot;&nbsp;".join(meta_parts)

            st.markdown(
                f'<div style="border-left:3px solid {colour};padding:0.55rem 0.75rem;'
                f'margin-bottom:0.4rem;background:#111;border-radius:0 3px 3px 0">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;gap:0.5rem">'
                f'<span style="font-family:PPFormula,sans-serif;font-weight:900;font-size:0.88rem;'
                f'color:#FFFFFF;letter-spacing:0.02em">{title}</span>'
                f'<span style="background:{colour}22;border:1px solid {colour}66;color:{colour};'
                f'font-size:0.65rem;font-weight:700;padding:1px 8px;border-radius:2px;'
                f'white-space:nowrap;text-transform:uppercase">{label}</span>'
                f'</div>'
                f'<div style="font-size:0.75rem;color:#666;margin-top:3px">{meta_line}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        st.write("")
        if st.button("View all PR packs →", use_container_width=True):
            st.switch_page("pages/7_pr_library.py")

# ── RIGHT: Coming Up + Quick Actions ─────────────────────────────────────

with col_right:

    st.markdown("#### Coming Up")

    if not upcoming:
        st.markdown(
            '<p style="color:#666;font-size:0.85rem">Nothing in the next 30 days.</p>',
            unsafe_allow_html=True,
        )
    else:
        for event in upcoming[:4]:
            raw = event.get("date", "")
            try:
                ey, em, ed = raw.split("-")
                date_fmt = f"{ed}/{em}/{ey}"
            except Exception:
                date_fmt = raw
            cat = event.get("category", "")
            meta = date_fmt + ("&nbsp;&middot;&nbsp;" + cat if cat else "")
            name = event.get("name", "")
            st.markdown(
                f'<div style="padding:0.4rem 0;border-bottom:1px solid #1A1A1A">'
                f'<div style="font-size:0.85rem;color:#E0E0E0;font-weight:600">{name}</div>'
                f'<div style="font-size:0.72rem;color:#666;margin-top:2px">{meta}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if len(upcoming) > 4:
            st.caption(f"+{len(upcoming)-4} more events")
        st.write("")
        if st.button("Full calendar →", use_container_width=True):
            st.switch_page("pages/12_pr_calendar.py")

    st.write("")
    st.markdown("#### Quick Actions")

    # Primary action — full width
    if st.button("Monitor Today's News", use_container_width=True, type="primary"):
        st.switch_page("pages/1_news_desk.py")

    # Secondary actions — 2-column grid
    qa1, qa2 = st.columns(2)
    with qa1:
        if st.button("PR Generator", use_container_width=True, key="qa_pr"):
            st.switch_page("pages/2_pr_generator.py")
    with qa2:
        if st.button("News-Jacking", use_container_width=True, key="qa_nj"):
            st.switch_page("pages/4_news_jacking.py")

    qa3, qa4 = st.columns(2)
    with qa3:
        if st.button("Competitors", use_container_width=True, key="qa_comp"):
            st.switch_page("pages/9_competitors.py")
    with qa4:
        if st.button("Journalists", use_container_width=True, key="qa_j"):
            st.switch_page("pages/6_journalists.py")
