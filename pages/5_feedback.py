import streamlit as st
from utils.styles import apply_global_styles, render_sidebar
from services.feedback import get_all_feedback, get_stats, get_feedback_by_context, clear_all
from services.error_logger import get_recent_errors, get_error_summary, clear_errors

st.set_page_config(page_title="Feedback & Learning | Riot PR Desk", page_icon="📊", layout="wide")
apply_global_styles()
render_sidebar()

st.title("📊 Feedback & Learning")
st.markdown("Your votes teach the AI what works for Riot. The more you vote, the better it gets.")

st.divider()

# --- Stats overview ---
stats = get_stats()

if stats["total"] == 0:
    st.markdown("### How it works")
    st.markdown("""
    1. **Vote** — Use the 👍 👎 buttons on news stories, news-jack ideas and PR pack sections
    2. **Add notes** — Tell the AI *why* you liked or disliked something (optional but powerful)
    3. **AI adapts** — Your feedback is injected into the AI's instructions so future outputs improve

    Start using the tool and voting — this page will fill up with insights.
    """)
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Votes", stats["total"])
with col2:
    st.metric("👍 Liked", stats["up"])
with col3:
    st.metric("👎 Disliked", stats["down"])

st.divider()

# --- By category ---
st.markdown("### Votes by Category")

context_labels = {
    "news_story": "📰 News Stories",
    "newsjack_story": "⚡ News-Jack Stories",
    "newsjack_idea": "💡 News-Jack Ideas",
    "pr_pack_section": "✍️ PR Pack Sections",
}

for ctx, label in context_labels.items():
    ctx_stats = stats["by_context"].get(ctx)
    if ctx_stats:
        up = ctx_stats["up"]
        down = ctx_stats["down"]
        total = up + down
        pct = round(up / total * 100) if total > 0 else 0
        st.markdown(f"**{label}** — {total} votes ({up} 👍 / {down} 👎) — {pct}% approval")
        st.progress(pct / 100)

st.divider()

# --- Recent feedback ---
st.markdown("### Recent Feedback")

filter_ctx = st.selectbox(
    "Filter by:",
    ["All"] + list(context_labels.values()),
)

all_feedback = get_all_feedback()

# Apply filter
if filter_ctx != "All":
    ctx_key = [k for k, v in context_labels.items() if v == filter_ctx]
    if ctx_key:
        all_feedback = [e for e in all_feedback if e.get("context") == ctx_key[0]]

# Show most recent first
all_feedback.reverse()

for entry in all_feedback[:50]:
    vote_icon = "👍" if entry["vote"] == "up" else "👎"
    ctx_label = context_labels.get(entry.get("context", ""), entry.get("context", ""))
    note_part = f" — *\"{entry['note']}\"*" if entry.get("note") else ""
    ts = entry.get("timestamp", "")[:16].replace("T", " ")

    st.markdown(f"{vote_icon} **{entry['content']}**{note_part}")
    st.caption(f"{ctx_label} · {ts}")

if len(all_feedback) > 50:
    st.caption(f"Showing 50 of {len(all_feedback)} entries.")

st.divider()

# --- What the AI is learning ---
st.markdown("### What the AI Is Learning")
st.markdown(
    "The feedback summary below is injected into the AI's system prompt. "
    "It tells the AI what you've liked and disliked so it can adapt."
)

from services.feedback import get_feedback_summary
summary = get_feedback_summary()
if summary:
    with st.expander("Current feedback prompt injection", expanded=True):
        st.code(summary, language="markdown")
else:
    st.info("Not enough feedback yet. The AI will start learning after a few votes.")

st.divider()

# --- Clear ---
st.markdown("### Manage Data")
if st.button("🗑️ Clear All Feedback", type="secondary"):
    st.session_state["confirm_clear"] = True

if st.session_state.get("confirm_clear"):
    st.warning("This will permanently delete all feedback. Are you sure?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, clear everything", type="primary"):
            clear_all()
            st.session_state.pop("confirm_clear", None)
            st.success("All feedback cleared.")
            st.rerun()
    with c2:
        if st.button("Cancel"):
            st.session_state.pop("confirm_clear", None)
            st.rerun()

st.divider()

# --- Error log ---
st.markdown("### 🔧 System Health & Error Log")
st.caption("Automatically captures AI failures, news fetch errors and API issues for debugging.")

err_summary = get_error_summary()
ec1, ec2, ec3 = st.columns(3)
with ec1:
    st.metric("Errors logged", err_summary.get("total", 0))
with ec2:
    by_type = err_summary.get("by_type", {})
    most_common = max(by_type, key=by_type.get) if by_type else "—"
    st.metric("Most common type", most_common)
with ec3:
    last = err_summary.get("last_error", "—") or "None"
    st.metric("Last error", last)

if err_summary.get("total", 0) > 0:
    with st.expander("📋 View recent errors", expanded=False):
        errors = get_recent_errors(50)
        for err in errors:
            ts = err.get("timestamp", "")[:19].replace("T", " ")
            etype = err.get("type", "unknown")
            msg = err.get("message", "")
            ctx = err.get("context", "")
            tb = err.get("traceback", "")

            err_icon = {"ai_generation": "🤖", "news_fetch": "📰"}.get(etype, "⚠️")
            st.markdown(f"{err_icon} **{etype}** — `{ts}`")
            st.caption(f"Message: {msg}")
            if ctx:
                st.caption(f"Context: {ctx}")
            if tb and tb != "NoneType: None\n":
                with st.expander("Traceback", expanded=False):
                    st.code(tb, language="python")
            st.divider()

    if st.button("🗑️ Clear error log", type="secondary", key="clear_errors_btn"):
        clear_errors()
        st.success("Error log cleared.")
        st.rerun()
else:
    st.success("No errors logged. All systems running cleanly.", icon="✅")
