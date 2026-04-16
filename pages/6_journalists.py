"""
Journalist Database -- lightweight CRM for managing press contacts.
Search, filter, add, import and get AI-powered match suggestions.
"""

import streamlit as st
import pandas as pd

from utils.styles import apply_global_styles, render_sidebar
from services.journalist_db import (
    get_all,
    add_journalist,
    update_journalist,
    delete_journalist,
    search,
    filter_by,
    import_csv,
    get_database_summary_for_ai,
    get_by_id,
    BEAT_OPTIONS,
    TYPE_OPTIONS,
)
from services.ai_engine import is_configured as ai_configured, generate
from services.journalist_history import log_contact, get_history, get_recent_contacts, get_contact_summary, get_pitch_analytics

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Journalist Database | Riot PR Desk", page_icon="📇", layout="wide")
apply_global_styles()
render_sidebar()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📇 Journalist Database")
st.caption("Manage your press contacts, import lists and find the best journalists for every story.")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_stars(score: int) -> str:
    score = max(1, min(5, int(score)))
    return "⭐" * score + "☆" * (5 - score)


def _render_beats(beats: list) -> str:
    if not beats:
        return ""
    return " ".join(f"`{b}`" for b in beats)


def _render_tags(tags: list) -> str:
    if not tags:
        return ""
    return " ".join(f"*{t}*" for t in tags)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_contacts, tab_add, tab_discover, tab_ai, tab_history = st.tabs(["All Contacts", "Add / Import", "🔍 AI Discover", "AI Match", "📞 Contact History"])

# ============================= TAB 1: ALL CONTACTS ========================
with tab_contacts:
    # -- Search & filter row --
    search_query = st.text_input("🔍 Search journalists", placeholder="Name, publication, beat, tag...", key="j_search")

    col_type, col_beat = st.columns(2)
    with col_type:
        type_filter = st.selectbox("Filter by type", ["All"] + TYPE_OPTIONS, key="j_type_filter")
    with col_beat:
        beat_filter = st.selectbox("Filter by beat", ["All"] + BEAT_OPTIONS, key="j_beat_filter")

    # -- Fetch & filter --
    if search_query:
        journalists = search(search_query)
    elif type_filter != "All" or beat_filter != "All":
        journalists = filter_by(
            type_filter=type_filter if type_filter != "All" else None,
            beat_filter=beat_filter if beat_filter != "All" else None,
        )
    else:
        journalists = get_all()

    # -- Display mode toggle --
    if not journalists:
        st.info("No journalists found. Head to the **Add / Import** tab to start building your database.")
    else:
        view_mode = st.radio("View:", ["All", "Grouped by type"], horizontal=True, key="j_view")

        st.markdown(f"**{len(journalists)}** contact{'s' if len(journalists) != 1 else ''} found")

        if view_mode == "Grouped by type":
            # Group journalists by type
            from collections import defaultdict
            grouped = defaultdict(list)
            for j in journalists:
                grouped[j.get("type", "Other")].append(j)

            type_icons = {"Trade": "📰", "National": "🗞️", "Regional": "📍", "Consumer": "🛍️",
                          "Broadcast": "📺", "Freelance": "✍️", "Online": "🌐", "Other": "📋"}

            for type_name in TYPE_OPTIONS + ["Other"]:
                if type_name in grouped:
                    icon = type_icons.get(type_name, "📋")
                    st.markdown(f"### {icon} {type_name} ({len(grouped[type_name])})")
                    for j in grouped[type_name]:
                        label_parts = [f"**{j.get('name', 'Unnamed')}**", j.get("publication", ""), j.get("job_title", "")]
                        label = " | ".join(p for p in label_parts if p)
                        stars = _render_stars(j.get("relationship_score", 3))
                        st.caption(f"{label} — {stars} — Beats: {_render_beats(j.get('beats', []))}")
                    st.divider()
        else:
            pass  # Fall through to expander view below

        # Expander detail view (for "All" mode)
        if view_mode != "Grouped by type":
            pass  # continue to for loop

        for j in journalists if view_mode == "All" else []:
            label_parts = [
                f"**{j.get('name', 'Unnamed')}**",
                j.get("publication", ""),
                j.get("job_title", ""),
            ]
            label = " | ".join(p for p in label_parts if p)
            stars = _render_stars(j.get("relationship_score", 3))

            with st.expander(f"{label}  --  {stars}"):
                detail_col1, detail_col2 = st.columns(2)

                with detail_col1:
                    st.markdown(f"**Email:** {j.get('email', '-')}")
                    st.markdown(f"**Phone:** {j.get('phone', '-')}")
                    st.markdown(f"**Location:** {j.get('location', '-')}")
                    st.markdown(f"**LinkedIn:** {j.get('linkedin', '-')}")
                    st.markdown(f"**Type:** {j.get('type', '-')}")

                with detail_col2:
                    st.markdown(f"**Beats:** {_render_beats(j.get('beats', []))}")
                    st.markdown(f"**Tags:** {_render_tags(j.get('tags', []))}")
                    st.markdown(f"**Relationship:** {stars}")
                    st.markdown(f"**Added:** {j.get('added_date', '-')}")
                    st.markdown(f"**Last contacted:** {j.get('last_contacted', '-') or '-'}")

                if j.get("notes"):
                    st.markdown(f"**Notes:** {j['notes']}")

                # -- Action buttons --
                btn_col1, btn_col2, _ = st.columns([1, 1, 4])
                jid = j["id"]

                with btn_col1:
                    if st.button("✏️ Edit", key=f"edit_{jid}"):
                        st.session_state[f"editing_{jid}"] = True

                with btn_col2:
                    if st.button("🗑️ Delete", key=f"del_{jid}", type="secondary"):
                        delete_journalist(jid)
                        st.success(f"Deleted {j.get('name', '')}.")
                        st.rerun()

                # --- Contact history quick view ---
                history = get_history(jid)
                summary = get_contact_summary(jid)
                if summary["total_contacts"] > 0:
                    st.caption(f"📞 {summary['total_contacts']} contacts logged | Last: {summary['last_contact_date'][:10] if summary['last_contact_date'] else 'never'} | Response rate: {summary['response_rate']}%")

                # --- Recent articles section ---
                art_key = f"j_articles_{jid}"
                if st.button("📰 Fetch recent articles", key=f"j_fetch_art_{jid}", help="Search Google News for recent bylines"):
                    with st.spinner(f"Searching for recent articles by {j.get('name', '')}..."):
                        try:
                            from services.news_monitor import _search_gnews
                            name = j.get("name", "")
                            pub = j.get("publication", "")
                            # Search for their name + publication
                            query = f'"{name}" {pub}' if pub else f'"{name}"'
                            articles = _search_gnews(query, max_items=5)
                            # Filter out errors
                            articles = [a for a in articles if "error" not in a]
                            st.session_state[art_key] = articles
                        except Exception as e:
                            st.error(f"Search failed: {e}")

                if art_key in st.session_state:
                    articles = st.session_state[art_key]
                    if not articles:
                        st.caption("No recent articles found.")
                    else:
                        for art in articles:
                            title = art.get("title", "No title")
                            url = art.get("url", "")
                            pub_date = art.get("publishedAt", "")[:10] if art.get("publishedAt") else ""
                            if url:
                                st.caption(f"• [{title}]({url}) — {pub_date}")
                            else:
                                st.caption(f"• {title} — {pub_date}")

                # Log contact button
                with st.expander("📞 Log a contact", expanded=False):
                    with st.form(key=f"log_contact_{jid}"):
                        lc_col1, lc_col2 = st.columns(2)
                        with lc_col1:
                            lc_type = st.selectbox("Contact type", ["pitch", "call", "meeting", "email", "coverage"], key=f"lct_{jid}")
                            lc_subject = st.text_input("Subject/story", key=f"lcs_{jid}", placeholder="e.g. 'Vape Tax press release'")
                        with lc_col2:
                            lc_outcome = st.selectbox("Outcome", ["", "responded", "no_response", "coverage_landed", "declined"], key=f"lco_{jid}")
                            lc_notes = st.text_area("Notes", height=68, key=f"lcn_{jid}", placeholder="Any details about this interaction...")
                        if st.form_submit_button("Log contact"):
                            log_contact(jid, lc_type, lc_subject, notes=lc_notes, outcome=lc_outcome)
                            st.success("Contact logged.")
                            st.rerun()

                # Show recent history
                if history:
                    outcome_icons = {"responded": "✅", "coverage_landed": "🏆", "declined": "❌", "no_response": "⏳", "": "📝"}
                    for h in history[:3]:  # Show last 3
                        icon = outcome_icons.get(h.get("outcome", ""), "📝")
                        st.caption(f"{icon} **{h['contact_type'].title()}** — {h.get('subject', '')} — {h['logged_at'][:10]}")
                    if len(history) > 3:
                        st.caption(f"...and {len(history)-3} more. See Contact History tab for full log.")

                # -- Inline edit form --
                if st.session_state.get(f"editing_{jid}", False):
                    st.divider()
                    st.markdown("##### Edit Contact")

                    with st.form(key=f"editform_{jid}"):
                        e_name = st.text_input("Name", value=j.get("name", ""), key=f"en_{jid}")
                        e_email = st.text_input("Email", value=j.get("email", ""), key=f"ee_{jid}")
                        e_phone = st.text_input("Phone", value=j.get("phone", ""), key=f"ep_{jid}")
                        e_pub = st.text_input("Publication", value=j.get("publication", ""), key=f"epub_{jid}")
                        e_title = st.text_input("Job title", value=j.get("job_title", ""), key=f"et_{jid}")
                        # Filter defaults to only values that exist in BEAT_OPTIONS (handles case mismatches from AI discovery)
                        _valid_beats = [b for b in j.get("beats", []) if b in BEAT_OPTIONS]
                        e_beats = st.multiselect("Beats", BEAT_OPTIONS, default=_valid_beats, key=f"eb_{jid}")
                        e_loc = st.text_input("Location", value=j.get("location", ""), key=f"el_{jid}")
                        e_type = st.selectbox("Type", TYPE_OPTIONS, index=TYPE_OPTIONS.index(j.get("type", "Trade")) if j.get("type") in TYPE_OPTIONS else 0, key=f"ety_{jid}")
                        e_notes = st.text_area("Notes", value=j.get("notes", ""), key=f"eno_{jid}")
                        e_linkedin = st.text_input("LinkedIn URL", value=j.get("linkedin", ""), key=f"eli_{jid}")
                        e_score = st.slider("Relationship score", 1, 5, value=j.get("relationship_score", 3), key=f"es_{jid}")
                        e_tags = st.text_input("Tags (comma-separated)", value=", ".join(j.get("tags", [])), key=f"etg_{jid}")

                        if st.form_submit_button("Save changes"):
                            update_journalist(jid, {
                                "name": e_name,
                                "email": e_email,
                                "phone": e_phone,
                                "publication": e_pub,
                                "job_title": e_title,
                                "beats": e_beats,
                                "location": e_loc,
                                "type": e_type,
                                "notes": e_notes,
                                "linkedin": e_linkedin,
                                "relationship_score": e_score,
                                "tags": [t.strip() for t in e_tags.split(",") if t.strip()],
                            })
                            st.session_state[f"editing_{jid}"] = False
                            st.success("Contact updated.")
                            st.rerun()


# ========================== TAB 2: ADD / IMPORT ===========================
with tab_add:
    st.subheader("Add a contact manually")

    with st.form("add_journalist_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)

        with col_a:
            a_name = st.text_input("Name *")
            a_email = st.text_input("Email")
            a_phone = st.text_input("Phone")
            a_pub = st.text_input("Publication *")
            a_title = st.text_input("Job title")
            a_beats = st.multiselect("Beats", BEAT_OPTIONS)

        with col_b:
            a_loc = st.text_input("Location")
            a_type = st.selectbox("Type", TYPE_OPTIONS)
            a_linkedin = st.text_input("LinkedIn URL")
            a_score = st.slider("Relationship score", 1, 5, value=3)
            a_tags = st.text_input("Tags (comma-separated)")
            a_notes = st.text_area("Notes")

        submitted = st.form_submit_button("Add journalist", type="primary")

        if submitted:
            if not a_name or not a_pub:
                st.error("Name and Publication are required.")
            else:
                record = add_journalist({
                    "name": a_name,
                    "email": a_email,
                    "phone": a_phone,
                    "publication": a_pub,
                    "job_title": a_title,
                    "beats": a_beats,
                    "location": a_loc,
                    "type": a_type,
                    "notes": a_notes,
                    "linkedin": a_linkedin,
                    "relationship_score": a_score,
                    "tags": [t.strip() for t in a_tags.split(",") if t.strip()],
                })
                st.success(f"Added **{record['name']}** ({record['publication']}).")

    st.divider()

    # -- CSV import --
    st.subheader("Import from CSV")
    st.caption(
        "CSV must include at least **name** and **publication** columns. "
        "Optional columns: email, phone, job_title, beats, location, type, notes, linkedin, relationship_score, tags."
    )

    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"], key="csv_upload")

    if uploaded_file is not None:
        csv_content = uploaded_file.getvalue().decode("utf-8")

        # Preview first 5 rows
        try:
            df_preview = pd.read_csv(uploaded_file)
            st.markdown("**Preview (first 5 rows):**")
            st.dataframe(df_preview.head(5), use_container_width=True)
        except Exception as e:
            st.error(f"Could not parse CSV for preview: {e}")

        if st.button("Import CSV", type="primary", key="import_csv_btn"):
            imported, skipped, errors = import_csv(csv_content)
            st.success(f"Imported **{imported}** contacts.")
            if skipped:
                st.warning(f"Skipped **{skipped}** rows.")
            if errors:
                with st.expander("Import errors"):
                    for err in errors:
                        st.text(err)


# ======================== TAB 3: AI DISCOVER ==============================
with tab_discover:
    st.subheader("🔍 AI Journalist Discovery")
    st.markdown(
        "Tell the AI what beat or topic you need journalists for and it will research and suggest "
        "real contacts you can add to your database. **Review each suggestion before accepting.**"
    )

    if not ai_configured():
        st.warning("AI engine is not configured. Add your API key in the .env file.")
    else:
        # Quick preset buttons — must be BEFORE the text_input to allow session_state pre-fill
        st.caption("Choose a preset or type your own:")
        preset_cols = st.columns(4)
        presets = ["UK vaping & e-cigarettes", "FMCG & retail trade", "Health & public health", "National news desks"]
        for idx, preset in enumerate(presets):
            with preset_cols[idx]:
                if st.button(preset, key=f"preset_{idx}", use_container_width=True):
                    st.session_state["_discover_preset"] = preset
                    st.rerun()

        # Apply preset before widget renders
        if "_discover_preset" in st.session_state:
            st.session_state["discover_topic"] = st.session_state.pop("_discover_preset")

        # Topic input
        discover_topic = st.text_input(
            "What topic or beat do you need journalists for?",
            placeholder="e.g. 'UK vaping regulation', 'FMCG retail trade press', 'health correspondents at national newspapers'",
            key="discover_topic",
        )

        def _run_discovery(topic_text):
            """Run journalist discovery and store results."""
            from utils.prompts import JOURNALIST_DISCOVER_PROMPT
            import json as _json

            # Build list of existing journalist names to avoid duplicates
            existing = get_all()
            existing_names = ", ".join(j.get("name", "") for j in existing) if existing else "None yet"

            prompt = JOURNALIST_DISCOVER_PROMPT.format(
                topic=topic_text,
                existing_journalists=existing_names,
            )

            with st.spinner(f"Deep-researching journalists who cover '{topic_text}'... this may take a minute."):
                try:
                    raw_result = generate(user_prompt=prompt)
                    st.session_state["discover_results_raw"] = raw_result
                    st.session_state["discover_results_topic"] = topic_text

                    # Parse JSON lines
                    suggestions = []
                    for line in raw_result.strip().split("\n"):
                        line = line.strip()
                        if line.startswith("{"):
                            try:
                                suggestions.append(_json.loads(line))
                            except _json.JSONDecodeError:
                                pass

                    # Append to existing suggestions if doing "Discover More"
                    if "discover_suggestions" in st.session_state and st.session_state.get("_append_mode"):
                        existing_sug = st.session_state["discover_suggestions"]
                        # Deduplicate by name
                        existing_names_set = {s.get("name", "").lower() for s in existing_sug}
                        new_only = [s for s in suggestions if s.get("name", "").lower() not in existing_names_set]
                        st.session_state["discover_suggestions"] = existing_sug + new_only
                        st.session_state.pop("_append_mode", None)
                    else:
                        st.session_state["discover_suggestions"] = suggestions

                    # Clear accept/skip states for new results
                    keys_to_clear = [k for k in st.session_state if k.startswith("disc_accepted_") or k.startswith("disc_skipped_")]
                    for k in keys_to_clear:
                        del st.session_state[k]

                except Exception as e:
                    st.error(f"Discovery failed: {e}")

        if st.button("🔍 Discover Journalists", type="primary", use_container_width=True, disabled=not discover_topic):
            _run_discovery(discover_topic)

        # Show results
        if "discover_suggestions" in st.session_state:
            suggestions = st.session_state["discover_suggestions"]
            topic = st.session_state.get("discover_results_topic", "")

            if not suggestions:
                st.warning("No structured suggestions returned. Here's the raw AI response:")
                st.markdown(st.session_state.get("discover_results_raw", ""))
            else:
                st.success(f"Found {len(suggestions)} journalist suggestions for '{topic}'.")
                st.caption("Review each suggestion and click **Accept** to add them to your database, or **Skip** to ignore.")

                for k, sug in enumerate(suggestions):
                    accept_key = f"disc_accepted_{k}"

                    if accept_key in st.session_state:
                        st.caption(f"✅ **{sug.get('name', '?')}** — Added to database")
                        continue

                    if f"disc_skipped_{k}" in st.session_state:
                        st.caption(f"⏭️ **{sug.get('name', '?')}** — Skipped")
                        continue

                    with st.expander(
                        f"**{sug.get('name', 'Unknown')}** — {sug.get('publication', '?')} | {sug.get('job_title', '')}",
                        expanded=True,
                    ):
                        dc1, dc2 = st.columns(2)
                        with dc1:
                            st.markdown(f"**Email:** {sug.get('email', '-')}")
                            st.markdown(f"**Type:** {sug.get('type', '-')}")
                            st.markdown(f"**Location:** {sug.get('location', '-')}")
                        with dc2:
                            beats = sug.get("beats", [])
                            st.markdown(f"**Beats:** {' '.join(f'`{b}`' for b in beats) if beats else '-'}")
                            st.markdown(f"**LinkedIn:** {sug.get('linkedin', '-') or '-'}")

                        if sug.get("notes"):
                            st.markdown(f"**AI notes:** {sug['notes']}")

                        bc1, bc2, bc3 = st.columns([1, 1, 4])
                        with bc1:
                            if st.button("✅ Accept", key=f"disc_add_{k}", use_container_width=True, type="primary"):
                                add_journalist({
                                    "name": sug.get("name", ""),
                                    "email": sug.get("email", ""),
                                    "phone": sug.get("phone", ""),
                                    "publication": sug.get("publication", ""),
                                    "job_title": sug.get("job_title", ""),
                                    "beats": sug.get("beats", []),
                                    "location": sug.get("location", ""),
                                    "type": sug.get("type", "Trade"),
                                    "notes": f"AI-discovered ({topic}). {sug.get('notes', '')}",
                                    "linkedin": sug.get("linkedin", ""),
                                    "relationship_score": 1,
                                    "tags": ["ai-discovered"],
                                })
                                st.session_state[accept_key] = True
                                st.rerun()
                        with bc2:
                            if st.button("⏭️ Skip", key=f"disc_skip_{k}", use_container_width=True):
                                st.session_state[f"disc_skipped_{k}"] = True
                                st.rerun()

                # Accept all button
                remaining = [k for k in range(len(suggestions))
                             if f"disc_accepted_{k}" not in st.session_state
                             and f"disc_skipped_{k}" not in st.session_state]
                if remaining:
                    st.divider()
                    if st.button(f"✅ Accept all remaining ({len(remaining)})", use_container_width=True):
                        for k in remaining:
                            sug = suggestions[k]
                            add_journalist({
                                "name": sug.get("name", ""),
                                "email": sug.get("email", ""),
                                "phone": sug.get("phone", ""),
                                "publication": sug.get("publication", ""),
                                "job_title": sug.get("job_title", ""),
                                "beats": sug.get("beats", []),
                                "location": sug.get("location", ""),
                                "type": sug.get("type", "Trade"),
                                "notes": f"AI-discovered ({topic}). {sug.get('notes', '')}",
                                "linkedin": sug.get("linkedin", ""),
                                "relationship_score": 1,
                                "tags": ["ai-discovered"],
                            })
                            st.session_state[f"disc_accepted_{k}"] = True
                        st.success(f"Added {len(remaining)} journalists to your database.")
                        st.rerun()

                # Discover More button — runs another round, skipping already-found contacts
                st.divider()
                st.markdown("**Want more?** Run another round to find journalists the AI missed.")
                dm_col1, dm_col2 = st.columns(2)
                with dm_col1:
                    if st.button("🔍 Discover More (same topic)", use_container_width=True):
                        st.session_state["_append_mode"] = True
                        _run_discovery(topic + " — find additional journalists NOT already listed. Go deeper into specialist, freelance and regional contacts.")
                        st.rerun()
                with dm_col2:
                    more_topic = st.text_input("Or refine the search:", key="discover_more_topic", placeholder="e.g. 'vaping trade press editors specifically'")
                    if more_topic and st.button("🔍 Discover", key="disc_more_btn"):
                        st.session_state["_append_mode"] = True
                        _run_discovery(more_topic)
                        st.rerun()


# ======================== TAB 4: AI MATCH =================================
with tab_ai:
    st.subheader("AI-powered journalist matching")

    if not ai_configured():
        st.warning("AI engine is not configured. Add your API key in the .env file to unlock AI suggestions.")
    else:
        # Check if story context was passed from PR Generator
        story_context = st.session_state.get("journalist_story_context", "")

        if story_context:
            st.info("Story context loaded from PR Generator.")
            st.text_area("Story / press release", value=story_context, height=200, key="ai_story_display", disabled=True)
        else:
            story_context = st.text_area(
                "Paste your press release or describe your story",
                height=200,
                placeholder="E.g.: We are launching a new nicotine pouch range targeted at adult consumers in the UK...",
                key="ai_story_input",
            )

        db_summary = get_database_summary_for_ai()

        if db_summary == "No journalists in the database yet.":
            st.warning("Your journalist database is empty. Add contacts first so the AI can suggest matches.")
        else:
            if st.button("Find matching journalists", type="primary", key="ai_match_btn"):
                if not story_context:
                    st.error("Please provide a story or press release to match against.")
                else:
                    with st.spinner("Analysing your database and finding the best matches..."):
                        prompt = (
                            "You are a senior PR professional. Given the story/press release below and "
                            "a database of journalist contacts, rank the TOP 10 best journalists to pitch "
                            "this story to. For each journalist explain briefly WHY they are a good match.\n\n"
                            "If fewer than 10 journalists are in the database, rank all of them.\n\n"
                            "FORMAT your response as a numbered list:\n"
                            "1. **Journalist Name** (Publication) -- Reason for match\n\n"
                            "---\n\n"
                            f"STORY / PRESS RELEASE:\n{story_context}\n\n"
                            "---\n\n"
                            f"JOURNALIST DATABASE:\n{db_summary}"
                        )

                        try:
                            result = generate(
                                user_prompt=prompt,
                                system_prompt=(
                                    "You are Riot PR Desk's journalist matching assistant. "
                                    "Rank journalists by relevance to the story based on their beats, "
                                    "publication type, relationship score and any other available signals. "
                                    "Be concise and actionable."
                                ),
                            )
                            st.markdown("### Recommended journalists")
                            st.markdown(result)
                        except Exception as e:
                            st.error(f"AI matching failed: {e}")


# ======================== TAB 5: CONTACT HISTORY ==========================
with tab_history:
    st.markdown("### 📞 Contact History & Pitch Analytics")
    st.caption("Track every interaction with journalists and measure what's working.")

    # --- Analytics section ---
    analytics = get_pitch_analytics()

    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.metric("Total contacts logged", analytics.get("total_contacts", 0))
    with col_b:
        st.metric("Overall response rate", f"{analytics.get('avg_response_rate', 0)}%")
    with col_c:
        st.metric("Coverage pieces landed", analytics.get("total_coverage", 0))
    with col_d:
        recent = get_recent_contacts(days=30)
        st.metric("Contacts this month", len(recent))

    st.divider()

    # --- Two sub-tabs ---
    sub_recent, sub_per_journalist, sub_analytics = st.tabs(["Recent Activity", "Per Journalist", "Analytics"])

    with sub_recent:
        recent_all = get_recent_contacts(days=60)
        if not recent_all:
            st.info("No contact history yet. Log interactions from the All Contacts tab.")
        else:
            st.caption(f"Showing {len(recent_all)} interactions in the last 60 days.")
            # Show as a table
            outcome_icons = {"responded": "✅", "coverage_landed": "🏆", "declined": "❌", "no_response": "⏳", "": "📝"}

            for h in recent_all[:50]:
                j = get_by_id(h.get("journalist_id", ""))
                j_name = j["name"] if j else "Unknown journalist"
                j_pub = j.get("publication", "") if j else ""
                icon = outcome_icons.get(h.get("outcome", ""), "📝")

                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.markdown(f"**{j_name}** ({j_pub}) — {h.get('subject', '-')}")
                with col2:
                    st.caption(f"{h['contact_type'].title()} · {h['logged_at'][:10]}")
                with col3:
                    st.caption(f"{icon} {h.get('outcome', '').replace('_', ' ').title() or 'Logged'}")

    with sub_per_journalist:
        all_journalists = get_all()
        if not all_journalists:
            st.info("No journalists in database yet.")
        else:
            # Filter to only journalists with history
            journalists_with_history = []
            for j in all_journalists:
                summary = get_contact_summary(j["id"])
                if summary["total_contacts"] > 0:
                    journalists_with_history.append((j, summary))

            if not journalists_with_history:
                st.info("No contact history yet. Start logging interactions from the All Contacts tab.")
            else:
                journalists_with_history.sort(key=lambda x: x[1]["total_contacts"], reverse=True)

                for j, summary in journalists_with_history:
                    with st.expander(
                        f"**{j['name']}** ({j.get('publication', '')}) — {summary['total_contacts']} contacts | {summary['response_rate']}% response rate",
                        expanded=False
                    ):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Total contacts", summary["total_contacts"])
                        with col2:
                            st.metric("Response rate", f"{summary['response_rate']}%")
                        with col3:
                            st.metric("Coverage landed", summary["coverage_count"])

                        history = get_history(j["id"])
                        outcome_icons = {"responded": "✅", "coverage_landed": "🏆", "declined": "❌", "no_response": "⏳", "": "📝"}
                        for h in history:
                            icon = outcome_icons.get(h.get("outcome", ""), "📝")
                            st.caption(f"{icon} **{h['contact_type'].title()}** — {h.get('subject', '-')} — {h['logged_at'][:10]} — {h.get('notes', '')}")

    with sub_analytics:
        if not analytics.get("total_contacts"):
            st.info("Start logging contacts to see analytics here.")
        else:
            st.markdown("### What's working")

            # Coverage by publication
            cov = analytics.get("coverage_by_publication", {})
            if cov:
                st.markdown("**Coverage by publication:**")
                for pub, count in sorted(cov.items(), key=lambda x: -x[1])[:10]:
                    st.caption(f"• {pub}: {count} piece{'s' if count != 1 else ''}")

            # Best performers
            best = analytics.get("top_journalists_by_response", [])
            if best:
                st.markdown("**Best-responding journalists:**")
                for j in best[:5]:
                    st.caption(f"• {j.get('name', '?')} ({j.get('publication', '')}) — {j.get('response_rate', 0)}% response rate")

            # Outcome breakdown
            breakdown = analytics.get("outcome_breakdown", {})
            if breakdown:
                st.markdown("**Outcome breakdown:**")
                for outcome, count in breakdown.items():
                    icon = {"responded": "✅", "coverage_landed": "🏆", "declined": "❌", "no_response": "⏳"}.get(outcome, "📝")
                    st.caption(f"{icon} {outcome.replace('_', ' ').title()}: {count}")
