import os
import streamlit as st
from dotenv import load_dotenv

# Load .env for local development
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# On Streamlit Cloud, secrets are in st.secrets — sync them to os.environ
# so all existing os.getenv() calls work without any other changes.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

# Handle Google service account JSON stored as a secret string on Streamlit Cloud
# (local dev uses a file path; Cloud uses the JSON content directly)
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

st.set_page_config(
    page_title="Riot PR Desk",
    page_icon="assets/logo_patch.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

from utils.styles import apply_global_styles, render_sidebar

apply_global_styles()
render_sidebar()

# --- Page header ---
st.title("**RIOT PR DESK**")
st.markdown("Live intelligence dashboard")

st.divider()

# --- First-run onboarding ---
try:
    from services.journalist_db import get_journalist_count
    from services.pr_library import get_all_packs
    j_count = get_journalist_count()
    pack_count = len(get_all_packs())
except Exception:
    j_count = 0
    pack_count = 0

if j_count == 0 and pack_count == 0 and not st.session_state.get("onboarding_dismissed"):
    with st.container():
        st.info("""
        👋 **Welcome to Riot PR Desk!** Here's how to get started:

        1. **📰 News Desk** → Monitor live vaping news and spot PR opportunities
        2. **⚡ News-Jacking** → Find trending stories and cultural moments to hijack
        3. **✍️ PR Generator** → Turn any story into a complete, approval-ready PR pack
        4. **📇 Journalist Database** → Build your press contact list with AI discovery
        5. **📂 PR Library** → All your generated packs saved and searchable
        """, icon="🚀")
        if st.button("Got it, let's go →", type="primary"):
            st.session_state["onboarding_dismissed"] = True
            st.rerun()
    st.divider()

# --- Headline metrics row ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    try:
        from services.pr_library import get_stats as lib_stats
        lib = lib_stats()
        st.metric(
            "PR Packs Generated",
            lib["total"],
            delta=f"+{lib['this_month']} this month" if lib["this_month"] else None,
        )
    except Exception:
        st.metric("PR Packs Generated", "—")

with col2:
    try:
        st.metric("Press Contacts", j_count)
    except Exception:
        st.metric("Press Contacts", "—")

with col3:
    try:
        from services.feedback import get_stats as fb_stats
        fb = fb_stats()
        pct = round(fb["up"] / fb["total"] * 100) if fb["total"] > 0 else 0
        st.metric("AI Approval Rate", f"{pct}%", help="% of AI outputs voted up")
    except Exception:
        st.metric("AI Approval Rate", "—")

with col4:
    try:
        st.metric("Coverage Logged", lib["total_coverage"])
    except Exception:
        st.metric("Coverage Logged", "—")

st.divider()

# --- Main content area ---
col_left, col_right = st.columns([3, 2])

with col_left:
    # Recent PR Packs
    st.markdown("### 📂 Recent PR Packs")
    try:
        from services.pr_library import get_recent_packs
        recent_packs = get_recent_packs(5)
    except Exception:
        recent_packs = []

    if not recent_packs:
        st.caption("No packs generated yet. Head to the PR Generator to create your first.")
        if st.button("✍️ Create PR Pack", use_container_width=True):
            st.switch_page("pages/2_pr_generator.py")
    else:
        for pack in recent_packs:
            status_icons = {"draft": "⚪", "approved": "🟢", "pitched": "🔵", "covered": "🏆"}
            icon = status_icons.get(pack.get("status", "draft"), "⚪")
            cols = st.columns([4, 1, 1])
            with cols[0]:
                st.markdown(f"{icon} **{pack['title']}**")
                st.caption(
                    f"{pack['created_at'][:10]} · {pack.get('position_name', '')} · {pack.get('spokesperson_key', '')}"
                )
            with cols[1]:
                if pack.get("coverage"):
                    st.caption(f"🏆 {len(pack['coverage'])} hits")
            with cols[2]:
                if st.button("Open →", key=f"home_pack_{pack['id']}", use_container_width=True):
                    st.switch_page("pages/7_pr_library.py")
        st.divider()
        if st.button("📂 View all PR packs →", use_container_width=True):
            st.switch_page("pages/7_pr_library.py")

with col_right:
    # Upcoming Cultural Moments
    st.markdown("### 📅 Coming Up")
    try:
        from services.cultural_calendar import get_upcoming_events
        upcoming = get_upcoming_events(days_ahead=14)
    except Exception:
        upcoming = []

    if not upcoming:
        st.caption("No events in the next 14 days.")
    else:
        for event in upcoming[:5]:
            st.markdown(f"**{event['name']}**")
            st.caption(f"{event.get('date', '?')} · `{event.get('category', '')}`")
        if len(upcoming) > 5:
            st.caption(f"+{len(upcoming)-5} more")
        if st.button("📅 View full calendar →", use_container_width=True):
            st.switch_page("pages/4_news_jacking.py")

    st.divider()

    # Quick Actions
    st.markdown("### ⚡ Quick Actions")
    if st.button("📰 Monitor Today's News", use_container_width=True, type="primary"):
        st.switch_page("pages/1_news_desk.py")
    if st.button("✍️ Generate PR Pack", use_container_width=True):
        st.switch_page("pages/2_pr_generator.py")
    if st.button("🔍 Competitor Intel", use_container_width=True):
        st.switch_page("pages/9_competitors.py")
    if st.button("📇 Journalist Database", use_container_width=True):
        st.switch_page("pages/6_journalists.py")

st.divider()

# --- Workflow reminder (collapsed) ---
with st.expander("ℹ️ How Riot PR Desk works", expanded=False):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        <div class="workflow-step">
            <div class="step-number">1</div>
            <h3>Spot</h3>
            <p style="color: #aaa; font-size: 0.9rem;">
                Monitor news, spot trending stories and identify PR opportunities.
            </p>
        </div>
        """, unsafe_allow_html=True)
        c1a, c1b = st.columns(2)
        with c1a:
            if st.button("📰 News Desk", use_container_width=True, key="workflow_news"):
                st.switch_page("pages/1_news_desk.py")
        with c1b:
            if st.button("⚡ News-Jack", use_container_width=True, key="workflow_newsjack"):
                st.switch_page("pages/4_news_jacking.py")

    with col2:
        st.markdown("""
        <div class="workflow-step">
            <div class="step-number">2</div>
            <h3>Shape</h3>
            <p style="color: #aaa; font-size: 0.9rem;">
                Generate press releases, pitch emails, social copy and internal briefings.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("✍️ PR Generator", use_container_width=True, key="workflow_prgenerator"):
            st.switch_page("pages/2_pr_generator.py")

    with col3:
        st.markdown("""
        <div class="workflow-step">
            <div class="step-number">3</div>
            <h3>Ship</h3>
            <p style="color: #aaa; font-size: 0.9rem;">
                Match with relevant journalists and prepare personalised pitches.
            </p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("📇 Journalist Database", use_container_width=True, key="workflow_journalists"):
            st.switch_page("pages/6_journalists.py")

    st.info(
        "Riot PR Desk **drafts and recommends** — it never sends anything automatically. "
        "Final approval always sits with the relevant Riot lead.",
        icon="🔒",
    )
