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
# Morning briefing (cached 4 hours — runs fast if cache is fresh)
# ---------------------------------------------------------------------------
briefing_opps = []
briefing_meta = {}
briefing_error = None

try:
    from services.autonomous_engine import run_daily_briefing, get_briefing_meta
    briefing_opps = run_daily_briefing()
    briefing_meta = get_briefing_meta()
except Exception as e:
    briefing_error = str(e)

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
# Today's Opportunities — morning briefing strip
# ---------------------------------------------------------------------------

if briefing_opps or briefing_meta:
    opp_count = len(briefing_opps)
    gen_at = briefing_meta.get("generated_at", "")
    if gen_at:
        try:
            from datetime import datetime, timezone
            dt = datetime.fromisoformat(gen_at)
            # Convert to local time
            local_dt = dt.astimezone()
            time_str = local_dt.strftime("%H:%M")
        except Exception:
            time_str = gen_at[11:16]
    else:
        time_str = ""

    # Header row
    opp_hdr_left, opp_hdr_right = st.columns([6, 2])
    with opp_hdr_left:
        meta_suffix = f"&nbsp;&middot;&nbsp;analysed at {time_str}" if time_str else ""
        count_label = f"{opp_count} opportunit{'ies' if opp_count != 1 else 'y'} found{meta_suffix}"
        st.markdown(
            f'<div style="display:flex;align-items:baseline;gap:0.75rem;margin-bottom:0.5rem">'
            f'<span style="font-family:PPFormula,sans-serif;font-weight:900;font-size:1rem;'
            f'text-transform:uppercase;letter-spacing:0.04em;color:#FFFFFF">Today\'s Opportunities</span>'
            f'<span style="font-size:0.72rem;color:#666">{count_label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with opp_hdr_right:
        if st.button("Open Inbox →", key="dash_inbox_link", use_container_width=True, type="primary"):
            st.switch_page("pages/17_inbox.py")

    if not briefing_opps:
        st.markdown(
            '<p style="color:#555;font-size:0.85rem;margin-bottom:0.75rem">'
            'No high-relevance opportunities found in today\'s news. '
            'Check back later or <a href="/pages/17_inbox.py" style="color:#E8192C">open the Inbox</a>.</p>',
            unsafe_allow_html=True,
        )
    else:
        # Show up to 3 opportunities in a horizontal strip
        opp_cols = st.columns(min(len(briefing_opps), 3))
        for i, opp in enumerate(briefing_opps[:3]):
            with opp_cols[i]:
                score = opp.get("relevance_score", 0)
                if score >= 8:
                    score_colour = "#E8192C"
                elif score >= 6:
                    score_colour = "#fbbf24"
                else:
                    score_colour = "#60a5fa"

                opp_id = opp.get("id", "")
                title_text = opp.get("story_title", "")[:70]
                source_text = opp.get("story_source", "")
                angle_text = opp.get("riot_angle", "")[:120]

                # Pre-build all parts
                score_badge = (
                    f'<span style="background:{score_colour}22;border:1px solid {score_colour}55;'
                    f'color:{score_colour};font-size:0.62rem;font-weight:700;padding:1px 7px;'
                    f'border-radius:2px;text-transform:uppercase;letter-spacing:0.06em">'
                    f'{score}/10</span>'
                )
                card_html = (
                    f'<div style="background:#111;border:1px solid #1A1A1A;border-top:2px solid {score_colour};'
                    f'border-radius:3px;padding:0.75rem;height:100%">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.35rem">'
                    f'<span style="font-size:0.7rem;color:#555;text-transform:uppercase;letter-spacing:0.06em">{source_text}</span>'
                    f'{score_badge}'
                    f'</div>'
                    f'<div style="font-family:PPFormula,sans-serif;font-weight:700;font-size:0.82rem;'
                    f'color:#FFFFFF;margin-bottom:0.4rem;line-height:1.3">{title_text}</div>'
                    f'<div style="font-size:0.75rem;color:#999;line-height:1.4">{angle_text}</div>'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

                # Approve / Skip buttons
                btn_approve, btn_skip = st.columns(2)
                with btn_approve:
                    approve_key = f"dash_approve_{opp_id}"
                    if st.button("Approve", key=approve_key, use_container_width=True, type="primary"):
                        st.session_state[f"dash_approving_{opp_id}"] = True
                        st.rerun()
                with btn_skip:
                    skip_key = f"dash_skip_{opp_id}"
                    if st.button("Skip", key=skip_key, use_container_width=True):
                        try:
                            from services.opportunity_tracker import update_opportunity_status
                            update_opportunity_status(opp_id, "skipped")
                            st.rerun()
                        except Exception:
                            pass

                # Handle approve — trigger auto-generation
                if st.session_state.get(f"dash_approving_{opp_id}"):
                    with st.spinner("Generating PR pack…"):
                        try:
                            from services.autonomous_engine import auto_generate_pack
                            pack_id = auto_generate_pack(opp_id)
                            st.session_state.pop(f"dash_approving_{opp_id}", None)
                            st.success("Pack generated! Check your Inbox.")
                            st.rerun()
                        except Exception as ex:
                            st.error(f"Generation failed: {ex}")
                            st.session_state.pop(f"dash_approving_{opp_id}", None)

        if len(briefing_opps) > 3:
            extra = len(briefing_opps) - 3
            st.caption(f"+{extra} more in Inbox")

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
            "draft":        ("#888",    "Draft"),
            "under_review": ("#fbbf24", "Under Review"),
            "approved":     ("#4ade80", "Approved"),
            "pitched":      ("#60a5fa", "Pitched"),
            "covered":      ("#E8192C", "Covered"),
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
    if st.button("Open Inbox", use_container_width=True, type="primary", key="qa_inbox"):
        st.switch_page("pages/17_inbox.py")

    if st.button("Monitor Today's News", use_container_width=True, key="qa_news"):
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
