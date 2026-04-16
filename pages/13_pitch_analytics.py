"""
Pitch Analytics — data-driven dashboard showing PR performance across the platform.
Covers funnel metrics, coverage by publication, position performance,
recent activity timeline and top journalist relationships.
"""

import streamlit as st
from datetime import datetime, timezone, timedelta

from utils.styles import apply_global_styles, render_sidebar

st.set_page_config(page_title="Pitch Analytics | Riot PR Desk", page_icon="📈", layout="wide")
apply_global_styles()
render_sidebar()

st.title("📈 Pitch Analytics")
st.caption("Track what you've pitched, who responded and what landed coverage.")

# ---------------------------------------------------------------------------
# Data loading — all wrapped in try/except with empty fallbacks
# ---------------------------------------------------------------------------

try:
    from services.pr_library import get_all_packs
    all_packs = get_all_packs()
except Exception:
    all_packs = []

try:
    from services.journalist_history import get_pitch_analytics, get_recent_contacts
    analytics = get_pitch_analytics()
    recent_contacts = get_recent_contacts(days=365)
except Exception:
    analytics = {
        "total_pitches": 0,
        "avg_response_rate": 0.0,
        "coverage_count": 0,
        "coverage_by_publication": {},
        "best_response_rate_journalist_ids": [],
        "outcome_breakdown": {},
        "top_journalists_by_response": [],
    }
    recent_contacts = []

try:
    from services.journalist_db import get_by_id, get_all
    all_journalists = get_all()
    total_journalists = len(all_journalists)
except Exception:
    all_journalists = []
    total_journalists = 0

# ---------------------------------------------------------------------------
# Section 1 — Headline metrics
# ---------------------------------------------------------------------------

st.markdown("### 📋 Headline Metrics")

n_generated = len(all_packs)
n_pitched = sum(1 for p in all_packs if p.get("status") in ["pitched", "covered"])
n_covered = sum(1 for p in all_packs if p.get("status") == "covered")
total_coverage_pieces = sum(len(p.get("coverage", [])) for p in all_packs)
response_rate_pct = round(analytics.get("avg_response_rate", 0.0) * 100)

# This month's activity — packs + contacts in last 30 days
now = datetime.now(timezone.utc)
thirty_days_ago = now - timedelta(days=30)

try:
    recent_30_contacts = get_recent_contacts(days=30)
    contacts_30 = len(recent_30_contacts)
except Exception:
    contacts_30 = 0

packs_30 = sum(
    1 for p in all_packs
    if p.get("created_at", "") >= thirty_days_ago.strftime("%Y-%m-%d")
)
this_month_activity = packs_30 + contacts_30

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total PR Packs Generated", n_generated)
with col2:
    st.metric("Packs Pitched", n_pitched)
with col3:
    st.metric("Coverage Pieces Logged", total_coverage_pieces)

col4, col5, col6 = st.columns(3)
with col4:
    st.metric("Total Journalist Contacts", total_journalists)
with col5:
    st.metric("Overall Response Rate", f"{response_rate_pct}%")
with col6:
    st.metric("This Month's Activity", this_month_activity, help="Packs created + contacts logged in last 30 days")

st.divider()

# ---------------------------------------------------------------------------
# Section 2 — Coverage funnel
# ---------------------------------------------------------------------------

st.markdown("### 📊 PR Funnel")

if n_generated > 0:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("Generated", n_generated)
        st.metric(
            "Pitched",
            n_pitched,
            delta=f"{round(n_pitched / n_generated * 100)}% of generated" if n_generated else None,
        )
        st.metric(
            "Covered",
            n_covered,
            delta=f"{round(n_covered / max(n_pitched, 1) * 100)}% of pitched" if n_pitched else None,
        )
    with col2:
        st.markdown("**Conversion rates**")
        pitch_rate = n_pitched / n_generated if n_generated else 0
        cover_rate = n_covered / max(n_pitched, 1) if n_pitched else 0
        st.caption(f"Generated → Pitched: {round(pitch_rate * 100)}%")
        st.progress(pitch_rate)
        st.caption(f"Pitched → Covered: {round(cover_rate * 100)}%")
        st.progress(cover_rate)
else:
    st.info("No PR packs generated yet. Head to the PR Generator to create your first.")

st.divider()

# ---------------------------------------------------------------------------
# Section 3 — Coverage by publication
# ---------------------------------------------------------------------------

st.markdown("### 🗞️ Coverage by Publication")

coverage_by_pub = {}
for pack in all_packs:
    for c in pack.get("coverage", []):
        pub = c.get("publication", "Unknown")
        coverage_by_pub[pub] = coverage_by_pub.get(pub, 0) + 1

if coverage_by_pub:
    sorted_pubs = sorted(coverage_by_pub.items(), key=lambda x: -x[1])[:10]
    for pub, count in sorted_pubs:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(pub)
            st.progress(count / sorted_pubs[0][1])
        with col2:
            st.caption(f"{count} piece{'s' if count != 1 else ''}")
else:
    st.info("No coverage logged yet. Log coverage from the PR Library.")

st.divider()

# ---------------------------------------------------------------------------
# Section 4 — Pitch performance by position
# ---------------------------------------------------------------------------

st.markdown("### 🏛️ Performance by Position")

position_stats = {}
for pack in all_packs:
    pos = pack.get("position_name", "Unknown")
    if pos not in position_stats:
        position_stats[pos] = {"total": 0, "pitched": 0, "covered": 0, "coverage_hits": 0}
    position_stats[pos]["total"] += 1
    if pack.get("status") in ["pitched", "covered"]:
        position_stats[pos]["pitched"] += 1
    if pack.get("status") == "covered":
        position_stats[pos]["covered"] += 1
    position_stats[pos]["coverage_hits"] += len(pack.get("coverage", []))

if position_stats:
    import pandas as pd
    df = pd.DataFrame([
        {
            "Position": pos,
            "Packs": s["total"],
            "Pitched": s["pitched"],
            "Covered": s["covered"],
            "Coverage Hits": s["coverage_hits"],
        }
        for pos, s in sorted(position_stats.items(), key=lambda x: -x[1]["total"])
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("Generate and track some PR packs to see position performance.")

st.divider()

# ---------------------------------------------------------------------------
# Section 5 — Recent activity timeline
# ---------------------------------------------------------------------------

st.markdown("### ⏱️ Recent Activity")

try:
    recent_contacts_60 = get_recent_contacts(days=60)
except Exception:
    recent_contacts_60 = []

recent_packs = sorted(all_packs, key=lambda p: p.get("created_at", ""), reverse=True)[:10]

# Merge into timeline
timeline = []
for c in recent_contacts_60[:20]:
    try:
        j = get_by_id(c.get("journalist_id", ""))
    except Exception:
        j = None
    timeline.append({
        "date": c.get("logged_at", "")[:10],
        "type": "contact",
        "description": f"📞 Pitched **{j['name'] if j else 'journalist'}** ({c.get('subject', '')})",
        "outcome": c.get("outcome", ""),
    })
for p in recent_packs:
    timeline.append({
        "date": p.get("created_at", "")[:10],
        "type": "pack",
        "description": f"✍️ Generated **{p.get('title', 'PR Pack')}**",
        "outcome": p.get("status", "draft"),
    })

timeline.sort(key=lambda x: x["date"], reverse=True)

if timeline:
    outcome_icons = {
        "responded": "✅",
        "coverage_landed": "🏆",
        "declined": "❌",
        "draft": "⚪",
        "approved": "🟢",
        "pitched": "🔵",
        "covered": "🏆",
        "no_response": "⏳",
        "": "",
    }
    for item in timeline[:20]:
        outcome = item.get("outcome", "")
        icon = outcome_icons.get(outcome, "")
        col1, col2 = st.columns([1, 5])
        with col1:
            st.caption(item["date"])
        with col2:
            st.markdown(f"{item['description']} {icon}")
else:
    st.info("Activity will appear here as you use the platform.")

st.divider()

# ---------------------------------------------------------------------------
# Section 6 — Top journalists by coverage
# ---------------------------------------------------------------------------

st.markdown("### 🏆 Best-Performing Journalist Relationships")

# Build top journalists list from analytics best_response_rate_journalist_ids
# and enrich with journalist data
top_journalist_ids = analytics.get("best_response_rate_journalist_ids", [])

top_journalists_enriched = []
for jid in top_journalist_ids:
    try:
        j = get_by_id(jid)
        if j:
            # Calculate response rate for this journalist
            from services.journalist_history import get_contact_summary
            summary = get_contact_summary(jid)
            top_journalists_enriched.append({
                "id": jid,
                "name": j.get("name", "?"),
                "publication": j.get("publication", ""),
                "response_rate": round(summary.get("response_rate", 0.0) * 100),
            })
    except Exception:
        pass

# Fall back to analytics.get("top_journalists_by_response") if present
if not top_journalists_enriched:
    top_journalists_enriched = analytics.get("top_journalists_by_response", [])

if top_journalists_enriched:
    for j_data in top_journalists_enriched[:10]:
        col1, col2, col3 = st.columns([3, 1, 1])
        with col1:
            st.markdown(f"**{j_data.get('name', '?')}** — {j_data.get('publication', '')}")
        with col2:
            st.caption(f"{j_data.get('response_rate', 0)}% response")
        with col3:
            if st.button("View →", key=f"pa_j_{j_data.get('id', '')}"):
                st.switch_page("pages/6_journalists.py")
else:
    st.info("Log journalist contacts to see relationship analytics.")
