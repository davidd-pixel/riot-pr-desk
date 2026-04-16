import streamlit as st
from utils.styles import apply_global_styles, render_sidebar
from services.news_monitor import (
    fetch_uk_vape_news, fetch_global_vape_news, fetch_trending_news, fetch_social_viral_news,
    format_article, is_configured as news_configured, is_url, fetch_article_text,
)
from services.ai_engine import is_configured as ai_configured
from services.content_generator import triage_news
from services.feedback import record_vote
from config.settings import TRIAGE_CATEGORIES

st.set_page_config(page_title="News Desk | Riot PR Desk", page_icon="📰", layout="wide")
apply_global_styles()
render_sidebar()

st.title("📰 News Desk")
st.markdown("Monitor industry news, analyse stories and spot PR opportunities.")

st.divider()

# --- Top input bar: always visible ---
with st.container():
    input_col, btn_col = st.columns([5, 1])
    with input_col:
        quick_input = st.text_input(
            "Quick analyse",
            key="news_desk_quick",
            placeholder="Paste a URL or article text to analyse instantly...",
            label_visibility="collapsed",
        )
    with btn_col:
        quick_go = st.button("Analyse →", use_container_width=True, type="primary")

    if quick_go and quick_input.strip():
        content = quick_input.strip()
        if is_url(content):
            with st.spinner("Fetching article..."):
                fetched = fetch_article_text(content)
            if fetched:
                content = fetched
            else:
                st.error("Couldn't fetch that URL. Try pasting the text directly.")
                content = ""
        if content:
            st.session_state["pr_input"] = content
            st.switch_page("pages/2_pr_generator.py")


def _render_articles(articles, key_prefix):
    """Render article list with analyse, PR pack and voting buttons."""
    if not articles:
        st.info("No articles found.")
        return

    for i, article in enumerate(articles):
        if "error" in article:
            st.error(f"API: {article['error']}")
            continue

        formatted = format_article(article)
        cat_badge = f" `{formatted['category']}`" if formatted.get("category") else ""

        with st.expander(
            f"**{formatted['title']}** — {formatted['source']}{cat_badge}",
            expanded=i < 3,
        ):
            st.caption(f"Published: {formatted['published']}")
            st.markdown(formatted["description"])
            if formatted["url"]:
                st.markdown(f"[Read full article →]({formatted['url']})")

            # Action buttons
            c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
            with c1:
                if ai_configured() and st.button("🔍 Analyse", key=f"{key_prefix}_tri_{i}", use_container_width=True):
                    with st.spinner("Analysing..."):
                        result = triage_news(f"{formatted['title']}\n\n{formatted['description']}")
                    st.session_state[f"{key_prefix}_result_{i}"] = result
            with c2:
                if st.button("✍️ Create PR Pack →", key=f"{key_prefix}_gen_{i}", use_container_width=True):
                    st.session_state["pr_input"] = f"{formatted['title']}\n\n{formatted['description']}"
                    st.switch_page("pages/2_pr_generator.py")

            # Voting
            vote_key = f"{key_prefix}_v_{i}"
            with c3:
                if vote_key not in st.session_state:
                    if st.button("👍", key=f"{key_prefix}_up_{i}", use_container_width=True):
                        record_vote(formatted["title"], "up", "news_story")
                        st.session_state[vote_key] = "up"
                        st.rerun()
            with c4:
                if vote_key not in st.session_state:
                    if st.button("👎", key=f"{key_prefix}_dn_{i}", use_container_width=True):
                        record_vote(formatted["title"], "down", "news_story")
                        st.session_state[vote_key] = "down"
                        st.rerun()

            if vote_key in st.session_state:
                v = st.session_state[vote_key]
                st.caption(f"{'👍 Relevant' if v == 'up' else '👎 Not relevant'}")

            # Show triage result if available
            if f"{key_prefix}_result_{i}" in st.session_state:
                result = st.session_state[f"{key_prefix}_result_{i}"]
                st.divider()
                if "raw_response" in result:
                    st.markdown(result["raw_response"])
                else:
                    cat = result.get("category", "unknown")
                    badge_styles = {
                        "respond": ("🔴", "#3a0a0a", "#ff6b6b", "RESPOND NOW"),
                        "campaign": ("🟢", "#0a2a0a", "#51cf66", "CAMPAIGN OPPORTUNITY"),
                        "monitor": ("🟡", "#2a2a0a", "#fcc419", "MONITOR"),
                        "ignore": ("⚪", "#1a1a1a", "#868e96", "NOT RELEVANT"),
                    }
                    icon, bg, fg, label = badge_styles.get(cat, ("❓", "#1a1a1a", "#aaa", cat.upper()))
                    relevance = result.get('relevance_score', '')
                    score_display = f" · Relevance: {relevance}/10" if relevance else ""

                    st.markdown(
                        f'<div style="background:{bg};border-left:4px solid {fg};padding:8px 12px;border-radius:4px;margin:4px 0">'
                        f'<span style="color:{fg};font-weight:700;font-size:0.9rem">{icon} {label}{score_display}</span><br>'
                        f'<span style="color:#ccc;font-size:0.85rem">{result.get("reasoning", "")}</span>'
                        f'</div>',
                        unsafe_allow_html=True
                    )
                    if result.get("suggested_angle"):
                        st.success(f"💡 **Angle:** {result['suggested_angle']}")
                    if result.get("urgency"):
                        urgency_map = {"immediate": "🔴 Respond immediately", "this_week": "🟡 Respond this week", "when_convenient": "🟢 When convenient"}
                        st.caption(urgency_map.get(result["urgency"], result["urgency"]))


# --- Auto-load on first visit, or force-reload on Refresh click ---
_news_loaded = all(k in st.session_state for k in ("news_uk", "news_global", "news_trending", "news_social"))

col_refresh, col_ts = st.columns([1, 3])
with col_refresh:
    refresh_clicked = st.button("🔄 Refresh News", use_container_width=True, type="secondary")
with col_ts:
    if _news_loaded:
        st.caption("Stories loaded — click Refresh to check for the latest.")

if not _news_loaded or refresh_clicked:
    with st.spinner("Loading latest news..."):
        st.session_state["news_uk"]      = fetch_uk_vape_news()
        st.session_state["news_global"]  = fetch_global_vape_news()
        st.session_state["news_trending"]= fetch_trending_news()
        st.session_state["news_social"]  = fetch_social_viral_news()
    if refresh_clicked:
        st.rerun()

# Category tabs
uk_count     = len([a for a in st.session_state.get("news_uk",      []) if "error" not in a])
global_count = len([a for a in st.session_state.get("news_global",  []) if "error" not in a])
trend_count  = len([a for a in st.session_state.get("news_trending",[]) if "error" not in a])
social_count = len([a for a in st.session_state.get("news_social",  []) if "error" not in a])

tab_uk, tab_global, tab_trending, tab_social = st.tabs([
    f"🇬🇧 UK Vape ({uk_count})",
    f"🌍 Global Vape ({global_count})",
    f"🔥 Trending ({trend_count})",
    f"🌐 Social & Viral ({social_count})",
])

with tab_uk:
    _render_articles(st.session_state["news_uk"], "uk")

with tab_global:
    _render_articles(st.session_state["news_global"], "gl")

with tab_trending:
    st.caption("Entertainment, sport, business, health, science, tech — the raw material for news-jacking.")
    _render_articles(st.session_state["news_trending"], "tr")

with tab_social:
    st.caption("Stories from Reddit, TikTok and social media that have crossed into mainstream news. Weird, viral and culturally relevant — prime news-jacking territory.")
    _render_articles(st.session_state["news_social"], "so")
