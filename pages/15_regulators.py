"""
Regulatory Radar — monitor MHRA, DHSC, IBVTA and other UK regulators for
policy changes that affect Riot. First to comment wins.
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

from utils.styles import apply_global_styles, render_sidebar, get_page_icon
from services.regulator_monitor import (
    REGULATORS,
    REGULATOR_DESCRIPTIONS,
    get_all_regulator_news,
    get_news_for_body,
    get_latest_alerts,
    triage_article,
    is_configured,
)
from services.news_monitor import format_article
from services.ai_engine import is_configured as ai_configured

st.set_page_config(
    page_title="Regulatory Radar | Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
)
apply_global_styles()
render_sidebar()

st.title("Regulatory Radar")
st.markdown(
    "Monitor MHRA, DHSC, IBVTA and other regulators for policy changes that affect Riot. "
    "**First to comment wins.**"
)
st.divider()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_published(pub_str: str):
    """Parse ISO or RFC-2822 date string to a timezone-aware datetime, or None."""
    if not pub_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(pub_str, fmt)
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(pub_str)
    except ValueError:
        return None


def _is_recent(pub_str: str, hours: int = 24) -> bool:
    """Return True if the article was published within the last N hours."""
    dt = _parse_published(pub_str)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt) < timedelta(hours=hours)


def _most_recent_date(articles: list) -> str:
    """Return the formatted date of the most recent article, or 'unknown'."""
    dates = [
        _parse_published(a.get("publishedAt", ""))
        for a in articles
        if "error" not in a
    ]
    dates = [d for d in dates if d is not None]
    if not dates:
        return "unknown"
    latest = max(dates)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    return latest.strftime("%d %b %Y %H:%M")


def _score_colour(score: int) -> str:
    """Return a CSS colour class for a relevance score 1–5."""
    if score >= 5:
        return "red"
    if score >= 4:
        return "#fbbf24"   # amber / yellow
    if score >= 3:
        return "#60a5fa"   # blue
    return "#888"          # grey


def _render_body_articles(articles: list, body_name: str, key_prefix: str):
    """Render articles for one regulatory body with AI triage and Draft Response buttons."""
    if not articles:
        st.info("No recent stories found for this body.")
        return

    valid = [a for a in articles if "error" not in a]
    if not valid:
        st.warning(
            f"Could not fetch news: {articles[0].get('error', 'unknown error')}"
        )
        return

    for i, article in enumerate(valid):
        formatted = format_article(article)
        pub_str = article.get("publishedAt", "")
        is_new = _is_recent(pub_str, hours=24)

        # Build expander label — include a red ALERT badge for fresh articles
        alert_tag = " [NEW]" if is_new else ""
        label = f"**{formatted['title']}** — {formatted['source']}{alert_tag}"

        with st.expander(label, expanded=(i == 0 and is_new)):
            st.caption(f"Published: {formatted['published']}")
            if formatted["description"]:
                st.markdown(formatted["description"])
            if formatted["url"]:
                st.markdown(f"[Read full article →]({formatted['url']})")

            triage_key = f"{key_prefix}_triage_{i}"
            col1, col2 = st.columns(2)

            with col1:
                if ai_configured():
                    if st.button(
                        "Triage with AI",
                        key=f"{key_prefix}_triage_btn_{i}",
                        use_container_width=True,
                    ):
                        with st.spinner("Triaging article..."):
                            result = triage_article(article)
                            st.session_state[triage_key] = result
                else:
                    st.caption("Configure AI engine to enable triage.")

            with col2:
                if st.button(
                    "Draft Response →",
                    key=f"{key_prefix}_draft_{i}",
                    use_container_width=True,
                ):
                    st.session_state["pr_input"] = (
                        f"Regulatory development — {body_name}\n\n"
                        f"{formatted['title']}\n\n"
                        f"{formatted['description']}"
                    )
                    st.switch_page("pages/2_pr_generator.py")

            # Show triage result if available
            if triage_key in st.session_state:
                triage = st.session_state[triage_key]
                st.divider()
                if "error" in triage:
                    st.error(triage["error"])
                else:
                    score = triage.get("relevance_score", 1)
                    colour = _score_colour(score)
                    # Relevance score bar
                    st.markdown(
                        f"""
                        <div style="display:flex; align-items:center; gap:0.75rem; margin-bottom:0.5rem;">
                            <span style="
                                background: {colour}22;
                                border: 1px solid {colour}66;
                                color: {colour};
                                font-weight: 700;
                                font-size: 0.8rem;
                                padding: 2px 10px;
                                border-radius: 2px;
                                font-family: 'PPFormula', sans-serif;
                                text-transform: uppercase;
                                letter-spacing: 0.08em;
                            ">Relevance {score}/5</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if triage.get("why_it_matters"):
                        st.markdown(f"**Why it matters for Riot:** {triage['why_it_matters']}")
                    if triage.get("suggested_action"):
                        st.markdown(f"**Suggested action:** {triage['suggested_action']}")


# ---------------------------------------------------------------------------
# Top controls
# ---------------------------------------------------------------------------

ctrl_col, refresh_col = st.columns([3, 1])

with ctrl_col:
    selected_body = st.selectbox(
        "Filter to a specific body",
        options=["All bodies"] + list(REGULATORS.keys()),
        key="reg_body_select",
        label_visibility="collapsed",
        help="Choose a specific regulatory body or view all",
    )

with refresh_col:
    refresh_all = st.button(
        "Refresh All",
        key="reg_refresh_all",
        use_container_width=True,
        type="primary",
        help="Fetch the latest news for all regulatory bodies (~30s)",
    )

if refresh_all:
    with st.spinner("Fetching regulatory news..."):
        st.session_state["reg_radar_news"] = get_all_regulator_news(page_size=8)

# Auto-load on first visit
if "reg_radar_news" not in st.session_state:
    st.caption("Click **Refresh All** to load the latest regulatory news.")
    st.stop()

all_news: dict = st.session_state.get("reg_radar_news", {})

if not all_news:
    st.caption("Click **Refresh All** to load the latest regulatory news.")
    st.stop()


# ---------------------------------------------------------------------------
# Summary metrics + alert banner
# ---------------------------------------------------------------------------

all_articles_flat = [
    a for arts in all_news.values() for a in arts if "error" not in a
]
recent_articles = [
    a for a in all_articles_flat if _is_recent(a.get("publishedAt", ""), hours=24)
]

if recent_articles:
    st.markdown(
        """
        <div style="
            background: #3a1a1a;
            border: 1px solid #f87171;
            border-radius: 6px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
        ">
            <span style="color: #f87171; font-weight: 700; font-size: 0.9rem;">
                ALERT — {count} new regulatory story{plural} in the last 24 hours
            </span>
        </div>
        """.format(
            count=len(recent_articles),
            plural="s" if len(recent_articles) != 1 else "",
        ),
        unsafe_allow_html=True,
    )

m1, m2, m3, m4 = st.columns(4)
m1.metric("Bodies monitored", len(all_news))
m2.metric("Total stories", len(all_articles_flat))
m3.metric("New (24 h)", len(recent_articles))
m4.metric("Most recent", _most_recent_date(all_articles_flat))

st.divider()


# ---------------------------------------------------------------------------
# Body grid / detail
# ---------------------------------------------------------------------------

bodies_to_show = (
    list(REGULATORS.keys())
    if selected_body == "All bodies"
    else [selected_body]
)

if selected_body == "All bodies":
    # Grid layout: 2 columns of cards
    pairs = [bodies_to_show[i:i + 2] for i in range(0, len(bodies_to_show), 2)]

    for pair in pairs:
        cols = st.columns(len(pair))
        for col, body_name in zip(cols, pair):
            with col:
                articles = all_news.get(body_name, [])
                valid = [a for a in articles if "error" not in a]
                has_alert = any(
                    _is_recent(a.get("publishedAt", ""), hours=24) for a in valid
                )
                alert_indicator = " [NEW]" if has_alert else ""

                desc = REGULATOR_DESCRIPTIONS.get(body_name, "")
                st.markdown(
                    f"""
                    <div style="
                        background: #111;
                        border: 1px solid {'#f8717166' if has_alert else '#1A1A1A'};
                        border-top: 3px solid {'#f87171' if has_alert else '#E8192C'};
                        border-radius: 3px;
                        padding: 1rem 1.25rem 0.5rem 1.25rem;
                        margin-bottom: 0.25rem;
                    ">
                        <div style="font-family: 'PPFormula', sans-serif; font-weight: 900;
                                    font-size: 1.05rem; text-transform: uppercase;
                                    letter-spacing: 0.05em; color: #FFFFFF;">
                            {body_name}{alert_indicator}
                        </div>
                        <div style="font-size: 0.72rem; color: #888; margin-top: 2px;">
                            {desc}
                        </div>
                        <div style="font-size: 0.75rem; color: #666; margin-top: 0.4rem;">
                            {len(valid)} stories · latest {_most_recent_date(valid) if valid else 'none'}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                key_prefix = f"radar_{body_name.lower().replace(' ', '_').replace('/', '_')}"
                _render_body_articles(
                    articles,
                    body_name=body_name,
                    key_prefix=key_prefix,
                )
        st.divider()

else:
    # Single-body detail view
    body_name = selected_body
    articles = all_news.get(body_name, [])
    desc = REGULATOR_DESCRIPTIONS.get(body_name, "")

    st.subheader(f"{body_name}")
    if desc:
        st.caption(desc)

    key_prefix = f"radar_{body_name.lower().replace(' ', '_').replace('/', '_')}"
    _render_body_articles(articles, body_name=body_name, key_prefix=key_prefix)


# ---------------------------------------------------------------------------
# Footer status
# ---------------------------------------------------------------------------

st.divider()
if not ai_configured():
    st.info(
        "Configure your AI engine (ANTHROPIC_API_KEY or OPENAI_API_KEY) "
        "to enable AI triage and draft response features.",
    )
