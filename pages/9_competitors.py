"""
Competitor Intelligence Dashboard — monitor competitor and regulator activity via Google News.
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

from utils.styles import apply_global_styles, render_sidebar, get_page_icon
from services.competitor_monitor import (
    COMPETITORS,
    REGULATORS,
    fetch_competitor_news,
    fetch_all_competitor_news,
    fetch_regulator_news,
    get_competitor_summary_for_ai,
)
from services.news_monitor import format_article
from services.ai_engine import generate, is_configured as ai_configured

st.set_page_config(
    page_title="Competitor Intelligence | Riot PR Desk",
    page_icon=get_page_icon(),
    layout="wide",
)
apply_global_styles()
render_sidebar()

st.title("Competitor Intelligence")
st.markdown(
    "Monitor competitor and industry body activity in the press. "
    "Spot threats early, find counter-positioning opportunities, and brief the team fast."
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
    # Try isoformat with +00:00
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


def _render_competitor_articles(articles: list, entity_name: str, key_prefix: str):
    """Render articles for one competitor/regulator with action buttons."""
    if not articles:
        st.info("No recent stories found for this competitor. They may have been quiet lately, or try refreshing.")
        return

    valid = [a for a in articles if "error" not in a]
    if not valid:
        st.warning(f"Could not fetch news: {articles[0].get('error', 'unknown error')}")
        return

    for i, article in enumerate(valid):
        formatted = format_article(article)
        label = f"**{formatted['title']}** — {formatted['source']}"

        with st.expander(label, expanded=i == 0):
            st.caption(f"Published: {formatted['published']}")
            if formatted["description"]:
                st.markdown(formatted["description"])
            if formatted["url"]:
                st.markdown(f"[Read full article →]({formatted['url']})")

            col1, col2 = st.columns(2)

            with col1:
                suggest_key = f"{key_prefix}_suggest_{i}"
                if ai_configured():
                    if st.button(
                        "Suggest Response",
                        key=f"{key_prefix}_sb_{i}",
                        use_container_width=True,
                    ):
                        prompt = (
                            f"Competitor news story about {entity_name}:\n\n"
                            f"Title: {formatted['title']}\n"
                            f"Summary: {formatted['description']}\n\n"
                            "As Riot's PR strategist, what PR opportunity does this create for Riot? "
                            "How can Riot counter-position or capitalise on this story? "
                            "Give 2-3 concrete, actionable suggestions in bullet points."
                        )
                        with st.spinner("Thinking..."):
                            try:
                                response = generate(prompt)
                                st.session_state[suggest_key] = response
                            except Exception as e:
                                st.error(f"AI error: {e}")
                else:
                    st.caption("Configure AI engine to unlock suggestions.")

            with col2:
                if st.button(
                    "Create PR Pack →",
                    key=f"{key_prefix}_pr_{i}",
                    use_container_width=True,
                ):
                    st.session_state["pr_input"] = (
                        f"{formatted['title']}\n\n{formatted['description']}"
                    )
                    st.switch_page("pages/2_pr_generator.py")

            if suggest_key in st.session_state:
                st.divider()
                st.markdown(st.session_state[suggest_key])


def _render_regulator_articles(articles: list, body_name: str, key_prefix: str):
    """Render articles for a regulator/industry body with AI triage button."""
    if not articles:
        st.info("No recent news found.")
        return

    valid = [a for a in articles if "error" not in a]
    if not valid:
        st.warning(f"Could not fetch news: {articles[0].get('error', 'unknown error')}")
        return

    for i, article in enumerate(valid):
        formatted = format_article(article)
        label = f"**{formatted['title']}** — {formatted['source']}"

        with st.expander(label, expanded=i == 0):
            st.caption(f"Published: {formatted['published']}")
            if formatted["description"]:
                st.markdown(formatted["description"])
            if formatted["url"]:
                st.markdown(f"[Read full article →]({formatted['url']})")

            analyse_key = f"{key_prefix}_analyse_{i}"

            if ai_configured():
                if st.button(
                    "Analyse for Riot",
                    key=f"{key_prefix}_ab_{i}",
                    use_container_width=True,
                ):
                    prompt = (
                        f"Regulatory / industry body news from {body_name}:\n\n"
                        f"Title: {formatted['title']}\n"
                        f"Summary: {formatted['description']}\n\n"
                        "As Riot's PR strategist, provide a triage of how this regulatory development "
                        "affects Riot directly. Cover: (1) Immediate risk or opportunity, "
                        "(2) Recommended Riot response or stance, (3) Key messages to prepare. "
                        "Be concise and specific to Riot as a UK vape brand."
                    )
                    with st.spinner("Analysing..."):
                        try:
                            response = generate(prompt)
                            st.session_state[analyse_key] = response
                        except Exception as e:
                            st.error(f"AI error: {e}")
            else:
                st.caption("Configure AI engine to unlock analysis.")

            if analyse_key in st.session_state:
                st.divider()
                st.markdown(st.session_state[analyse_key])


# ---------------------------------------------------------------------------
# Main tabs
# ---------------------------------------------------------------------------

tab_comp, tab_reg = st.tabs(["Competitors", "Regulators & Industry Bodies"])


# ============================================================
# COMPETITORS TAB
# ============================================================
with tab_comp:
    # Top controls
    ctrl_col, refresh_col = st.columns([3, 1])
    with ctrl_col:
        selected_competitor = st.selectbox(
            "Select competitor",
            options=list(COMPETITORS.keys()),
            key="comp_selected",
            label_visibility="collapsed",
        )
    with refresh_col:
        refresh_all = st.button(
            "Refresh All",
            key="comp_refresh_all",
            use_container_width=True,
            help="Load the latest news for every competitor at once (takes ~30s)",
        )

    if refresh_all:
        with st.spinner("Fetching news for all competitors..."):
            st.session_state["comp_all_news"] = fetch_all_competitor_news(page_size=5)

    # Load single competitor on selection (if full refresh not yet done)
    load_single = st.button(
        f"Load news for {selected_competitor}",
        key="comp_load_single",
        use_container_width=True,
        type="primary",
    )
    if load_single:
        with st.spinner(f"Fetching {selected_competitor} news..."):
            articles = fetch_competitor_news(selected_competitor, page_size=10)
            if "comp_all_news" not in st.session_state:
                st.session_state["comp_all_news"] = {}
            st.session_state["comp_all_news"][selected_competitor] = articles

    st.divider()

    all_news: dict = st.session_state.get("comp_all_news", {})

    if all_news:
        # Summary card
        total_stories = sum(
            len([a for a in arts if "error" not in a])
            for arts in all_news.values()
        )
        all_articles_flat = [
            a for arts in all_news.values() for a in arts if "error" not in a
        ]
        most_recent = _most_recent_date(all_articles_flat)

        m1, m2, m3 = st.columns(3)
        m1.metric("Competitors monitored", len(all_news))
        m2.metric("Total stories", total_stories)
        m3.metric("Most recent activity", most_recent)

        st.divider()

        # Show selected competitor's news
        if selected_competitor in all_news:
            st.subheader(f"{selected_competitor}")
            comp_articles = all_news[selected_competitor]
            _render_competitor_articles(
                comp_articles,
                entity_name=selected_competitor,
                key_prefix=f"comp_{selected_competitor.lower().replace(' ', '_')}",
            )
        elif all_news:
            st.caption("Select a competitor above and click **Load news** to view their stories.")
    else:
        st.caption(
            "Click **Load news** to fetch stories for the selected competitor, "
            "or **Refresh All** to load every competitor at once."
        )

    # --------------------------------------------------------
    # AI Competitive Briefing
    # --------------------------------------------------------
    st.divider()
    st.subheader("AI Competitive Briefing")
    st.caption(
        "Generates a single-page competitive intelligence briefing from the "
        "3 most recent stories per competitor. Requires news to be loaded first."
    )

    if st.button(
        "Generate Competitive Briefing",
        key="comp_briefing_btn",
        type="primary",
        disabled=not (all_news and ai_configured()),
    ):
        # Build context from top 3 articles per competitor
        context_blocks = []
        for name, articles in all_news.items():
            summary = get_competitor_summary_for_ai(name, articles[:3])
            context_blocks.append(summary)

        briefing_prompt = (
            "You are Riot's senior PR intelligence analyst. "
            "Based on the competitor news below, write a concise competitive intelligence briefing. "
            "Format as a structured document with these sections:\n"
            "- **Executive Summary** (2-3 sentences)\n"
            "- **Key Competitor Moves** (bullet points per competitor, only notable activity)\n"
            "- **Threats to Riot** (bullet points)\n"
            "- **Opportunities for Riot** (bullet points)\n"
            "- **Recommended Actions** (3-5 prioritised action items)\n\n"
            "Be direct, specific and actionable. Omit competitors with no notable activity.\n\n"
            "COMPETITOR NEWS:\n\n"
            + "\n\n---\n\n".join(context_blocks)
        )

        with st.spinner("Generating briefing — this takes ~20 seconds..."):
            try:
                briefing = generate(briefing_prompt)
                st.session_state["comp_briefing"] = briefing
            except Exception as e:
                st.error(f"AI error: {e}")

    if "comp_briefing" in st.session_state:
        st.markdown(st.session_state["comp_briefing"])
        if st.button("Turn Briefing into PR Pack →", key="comp_briefing_to_pr"):
            st.session_state["pr_input"] = st.session_state["comp_briefing"]
            st.switch_page("pages/2_pr_generator.py")

    if not ai_configured():
        st.info("Configure your AI engine (ANTHROPIC_API_KEY or OPENAI_API_KEY) to enable AI features.")


# ============================================================
# REGULATORS TAB
# ============================================================
with tab_reg:
    reg_refresh = st.button(
        "Refresh Regulator News",
        key="reg_refresh",
        use_container_width=True,
        type="primary",
    )

    if reg_refresh:
        with st.spinner("Fetching regulator and industry body news..."):
            st.session_state["reg_news"] = fetch_regulator_news(page_size=8)

    reg_news: dict = st.session_state.get("reg_news", {})

    if reg_news:
        # Check for recent alerts (< 24 hours)
        all_reg_articles = [
            a for arts in reg_news.values() for a in arts if "error" not in a
        ]
        recent_alerts = [a for a in all_reg_articles if _is_recent(a.get("publishedAt", ""), hours=24)]

        if recent_alerts:
            st.markdown(
                """
                <div style="
                    background: #3a1a1a;
                    border: 1px solid #f87171;
                    border-radius: 8px;
                    padding: 0.75rem 1rem;
                    margin-bottom: 1rem;
                ">
                    <span style="color: #f87171; font-weight: 700; font-size: 0.9rem;">
                        ALERT — {} new regulatory story{} in the last 24 hours
                    </span>
                </div>
                """.format(
                    len(recent_alerts),
                    "s" if len(recent_alerts) != 1 else "",
                ),
                unsafe_allow_html=True,
            )

        # Metrics row
        total_reg_stories = len([a for a in all_reg_articles])
        most_recent_reg = _most_recent_date(all_reg_articles)

        m1, m2, m3 = st.columns(3)
        m1.metric("Bodies monitored", len(reg_news))
        m2.metric("Total stories", total_reg_stories)
        m3.metric("Most recent", most_recent_reg)

        st.divider()

        # Render each regulatory body
        for body_name, articles in reg_news.items():
            valid = [a for a in articles if "error" not in a]
            st.subheader(body_name)
            _render_regulator_articles(
                articles,
                body_name=body_name,
                key_prefix=f"reg_{body_name.lower().replace(' ', '_').replace('/', '_')}",
            )
            st.divider()

    else:
        st.caption("Click **Refresh Regulator News** to fetch the latest from regulators and industry bodies.")
