import streamlit as st
from services.news_monitor import fetch_trending_news, fetch_social_viral_news, format_article, is_configured as news_configured
from services.ai_engine import is_configured as ai_configured, generate
from services.content_generator import suggest_newsjack
from services.feedback import record_vote
from services.cultural_calendar import (
    get_upcoming_events, add_event, delete_event, format_events_for_ai, CATEGORIES,
)
from utils.prompts import CULTURAL_CALENDAR_PROMPT, NEWSJACK_PROMPT
from utils.styles import apply_global_styles, render_sidebar

st.set_page_config(page_title="News-Jacking | Riot PR Desk", page_icon="⚡", layout="wide")
apply_global_styles()
render_sidebar()

st.title("⚡ News-Jacking")
st.markdown(
    "Spot trending stories and upcoming cultural moments to hijack for Riot PR coverage. "
    "Think Paddy Power meets Riot Activist."
)

st.divider()

if not ai_configured():
    st.error("**AI engine not configured.** Add your API key to `.env` to generate news-jack ideas.", icon="🔑")
    st.stop()

st.info("To analyse a specific story, paste it in the **News Desk** quick-analyse bar.")

# --- Two tabs: Trending Stories + Cultural Calendar ---
tab_trending, tab_calendar = st.tabs(["🔥 Trending Stories", "📅 Cultural Calendar"])

# ===================== TRENDING STORIES =====================
with tab_trending:
    def _load_newsjack_stories():
        trending = fetch_trending_news(page_size=20)
        social = fetch_social_viral_news(page_size=15)
        combined = trending + social
        seen = set()
        deduped = []
        for a in combined:
            title_key = a.get("title", "").lower()[:60]
            if title_key and title_key not in seen:
                seen.add(title_key)
                deduped.append(a)
        st.session_state["newsjack_trending"] = deduped

    # Auto-load on first visit
    if "newsjack_trending" not in st.session_state:
        with st.spinner("Loading trending stories..."):
            _load_newsjack_stories()

    nj_col_refresh, nj_col_ts = st.columns([1, 3])
    with nj_col_refresh:
        if st.button("🔄 Refresh Stories", use_container_width=True, type="secondary"):
            with st.spinner("Fetching latest trending & social stories..."):
                _load_newsjack_stories()
            st.rerun()
    with nj_col_ts:
        if "newsjack_trending" in st.session_state:
            st.caption("Stories loaded — click Refresh to check for newer ones.")

    stories = st.session_state.get("newsjack_trending", [])
    if not stories:
        st.info("No trending stories found. Try again later.")
    else:
        st.success(f"Found {len(stories)} trending stories.")

        for i, article in enumerate(stories):
            if "error" in article:
                continue

            formatted = format_article(article)
            cat_badge = f" `{formatted['category']}`" if formatted.get("category") else ""

            with st.expander(
                f"**{formatted['title']}** — {formatted['source']}{cat_badge}",
                expanded=i < 5,
            ):
                st.caption(f"Published: {formatted['published']}")
                st.markdown(formatted["description"])
                if formatted["url"]:
                    st.markdown(f"[Read full article →]({formatted['url']})")

                col_nj, col_pr = st.columns(2)
                with col_nj:
                    if st.button("💡 Suggest News-Jack", key=f"nj_{i}", use_container_width=True, type="primary"):
                        story_text = f"{formatted['title']}\n\n{formatted['description']}"
                        with st.spinner("Thinking of creative ways to hijack this story..."):
                            try:
                                ideas = suggest_newsjack(story_text)
                                st.session_state[f"nj_result_{i}"] = ideas
                            except Exception as e:
                                st.error(f"Failed: {e}")
                with col_pr:
                    if st.button("✍️ Create PR Pack →", key=f"nj_gen_{i}", use_container_width=True):
                        st.session_state["pr_input"] = f"{formatted['title']}\n\n{formatted['description']}"
                        st.switch_page("pages/2_pr_generator.py")

                # Show news-jack ideas (outside col_pr, inside expander)
                if f"nj_result_{i}" in st.session_state:
                    st.divider()
                    st.markdown("### 💡 News-Jacking Ideas")
                    st.markdown(st.session_state[f"nj_result_{i}"])

                    # Vote on ideas
                    idea_vote_key = f"nj_idea_voted_{i}"
                    if idea_vote_key in st.session_state:
                        st.caption(f"{'👍' if st.session_state[idea_vote_key] == 'up' else '👎'} Vote recorded")
                    else:
                        v1, v2, v3 = st.columns([1, 1, 3])
                        with v3:
                            note = st.text_input("Note (optional)", key=f"nj_note_{i}", placeholder="e.g. 'too safe', 'love the stunt idea'")
                        with v1:
                            if st.button("👍 Great", key=f"nj_up_{i}"):
                                record_vote(f"Newsjack ideas for: {formatted['title']}", "up", "newsjack_idea", note=note)
                                st.session_state[idea_vote_key] = "up"
                                st.rerun()
                        with v2:
                            if st.button("👎 Weak", key=f"nj_dn_{i}"):
                                record_vote(f"Newsjack ideas for: {formatted['title']}", "down", "newsjack_idea", note=note)
                                st.session_state[idea_vote_key] = "down"
                                st.rerun()

# ===================== CULTURAL CALENDAR =====================
with tab_calendar:
    st.markdown("**Forward-looking opportunities** — upcoming events, cultural moments and key dates that Riot could plan news-jacks around.")

    # Controls
    col_days, col_filter = st.columns(2)
    with col_days:
        days_ahead = st.selectbox("Look ahead:", [30, 60, 90, 180, 365], index=1, format_func=lambda x: f"Next {x} days")
    with col_filter:
        cat_filter = st.selectbox("Filter by category:", ["All"] + CATEGORIES)

    upcoming = get_upcoming_events(days_ahead=days_ahead)
    if cat_filter != "All":
        upcoming = [e for e in upcoming if e.get("category") == cat_filter]

    # AI opportunity scan button
    if upcoming and st.button("🤖 AI Opportunity Scan — rank all events", use_container_width=True, type="primary"):
        events_text = format_events_for_ai(upcoming)
        prompt = CULTURAL_CALENDAR_PROMPT.format(events_list=events_text)
        with st.spinner("Analysing upcoming events for news-jack potential..."):
            try:
                scan_result = generate(prompt)
                st.session_state["calendar_scan"] = scan_result
            except Exception as e:
                st.error(f"Scan failed: {e}")

    # Show AI scan results
    if "calendar_scan" in st.session_state:
        with st.expander("🤖 AI Opportunity Scan Results", expanded=True):
            st.markdown(st.session_state["calendar_scan"])
        st.divider()

    # Event list
    if not upcoming:
        st.info(f"No events in the next {days_ahead} days. Add a custom event below.")
    else:
        st.caption(f"Showing {len(upcoming)} events in the next {days_ahead} days.")

        for j, event in enumerate(upcoming):
            status = event.get("_status", "")
            is_custom = event.get("custom", False)
            custom_tag = " `custom`" if is_custom else ""
            status_tag = f" — **{status}**" if status else ""

            date_display = event.get("date", "?")
            if event.get("end_date"):
                date_display += f" → {event['end_date']}"

            with st.expander(
                f"**{event['name']}** ({date_display}) `{event.get('category', '')}`{custom_tag}{status_tag}",
                expanded=False,
            ):
                st.markdown(event.get("description", ""))
                if event.get("relevance_to_riot"):
                    st.markdown(f"**Riot relevance:** {event['relevance_to_riot']}")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("💡 Suggest News-Jack", key=f"cal_nj_{j}", use_container_width=True, type="primary"):
                        event_text = (
                            f"{event['name']} ({date_display})\n\n"
                            f"{event.get('description', '')}\n\n"
                            f"Riot relevance: {event.get('relevance_to_riot', 'Not assessed')}"
                        )
                        with st.spinner("Generating news-jack ideas for this event..."):
                            try:
                                ideas = suggest_newsjack(event_text)
                                st.session_state[f"cal_result_{j}"] = ideas
                            except Exception as e:
                                st.error(f"Failed: {e}")

                with col_b:
                    if is_custom:
                        if st.button("🗑️ Remove", key=f"cal_del_{j}", use_container_width=True):
                            delete_event(event["name"])
                            st.rerun()

                # Show ideas
                if f"cal_result_{j}" in st.session_state:
                    st.divider()
                    st.markdown("### 💡 News-Jacking Ideas")
                    st.markdown(st.session_state[f"cal_result_{j}"])

                    # Vote
                    cal_vote_key = f"cal_voted_{j}"
                    if cal_vote_key in st.session_state:
                        st.caption(f"{'👍' if st.session_state[cal_vote_key] == 'up' else '👎'} Vote recorded")
                    else:
                        cv1, cv2, cv3 = st.columns([1, 1, 3])
                        with cv3:
                            cal_note = st.text_input("Note (optional)", key=f"cal_note_{j}", placeholder="e.g. 'perfect timing', 'too forced'")
                        with cv1:
                            if st.button("👍 Great", key=f"cal_up_{j}"):
                                record_vote(f"Calendar newsjack: {event['name']}", "up", "newsjack_idea", note=cal_note)
                                st.session_state[cal_vote_key] = "up"
                                st.rerun()
                        with cv2:
                            if st.button("👎 Weak", key=f"cal_dn_{j}"):
                                record_vote(f"Calendar newsjack: {event['name']}", "down", "newsjack_idea", note=cal_note)
                                st.session_state[cal_vote_key] = "down"
                                st.rerun()

    # --- Add custom event ---
    st.divider()
    st.markdown("### ➕ Add a custom event")
    st.caption("Add upcoming events, cultural moments or deadlines that aren't in the calendar yet.")

    with st.form("add_event_form"):
        ae_col1, ae_col2 = st.columns(2)
        with ae_col1:
            ae_name = st.text_input("Event name", placeholder="e.g. 'Tottenham relegation battle'")
            ae_date = st.date_input("Start date")
            ae_end = st.date_input("End date (optional, leave same as start if single day)")
        with ae_col2:
            ae_category = st.selectbox("Category", CATEGORIES)
            ae_description = st.text_area("Description", height=68, placeholder="What is this event and why is it culturally significant?")
            ae_relevance = st.text_input("Riot relevance", placeholder="Why might this be a news-jack opportunity for Riot?")

        if st.form_submit_button("Add Event", use_container_width=True):
            if ae_name.strip():
                end_date_str = ae_end.strftime("%Y-%m-%d") if ae_end != ae_date else None
                add_event(
                    name=ae_name.strip(),
                    date=ae_date.strftime("%Y-%m-%d"),
                    category=ae_category,
                    description=ae_description.strip(),
                    relevance=ae_relevance.strip(),
                    end_date=end_date_str,
                )
                st.success(f"Added **{ae_name}** to the calendar.")
                st.rerun()
            else:
                st.warning("Please enter an event name.")
