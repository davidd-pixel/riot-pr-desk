import streamlit as st
from utils.styles import apply_global_styles, render_sidebar, get_page_icon
from config.positions import POSITIONS
from config.spokespeople import SPOKESPEOPLE

st.set_page_config(page_title="Position Bank | Riot PR Desk", page_icon=get_page_icon(), layout="wide")
apply_global_styles()
render_sidebar()

st.title("Position Bank")
st.markdown("Riot's key positions and spokesperson profiles. Edit in-session to test different messaging.")

st.warning(
    "Edits here are **session-only** — they'll feed into PR pack generation for this session but won't persist. "
    "To make permanent changes, edit `config/positions.py` and `config/spokespeople.py`.",
)

st.divider()

# --- Initialise session state copies for editing ---
if "positions" not in st.session_state:
    import copy
    st.session_state["positions"] = copy.deepcopy(POSITIONS)

if "spokespeople" not in st.session_state:
    import copy
    st.session_state["spokespeople"] = copy.deepcopy(SPOKESPEOPLE)

# --- Tabs ---
tab_positions, tab_spokespeople = st.tabs(["Positions", "Spokespeople"])

# ===================== POSITIONS =====================
with tab_positions:
    st.markdown("### Riot's positions on key industry topics")
    st.caption("These positions feed into all PR pack generation. Edits persist for this session only.")

    for name, pos in st.session_state["positions"].items():
        with st.expander(f"**{name}** — {pos['headline']}"):
            st.markdown(f"**Stance:**\n{pos['stance']}")

            st.markdown("**Key messages:**")
            for msg in pos["key_messages"]:
                st.markdown(f"- {msg}")

            st.markdown(f"**Keywords:** {', '.join(pos['keywords'])}")

            # Edit form
            with st.form(key=f"edit_pos_{name}"):
                new_headline = st.text_input("Headline:", value=pos["headline"])
                new_stance = st.text_area("Stance:", value=pos["stance"], height=100)
                new_messages = st.text_area(
                    "Key messages (one per line):",
                    value="\n".join(pos["key_messages"]),
                    height=100,
                )

                if st.form_submit_button("Save changes"):
                    st.session_state["positions"][name]["headline"] = new_headline
                    st.session_state["positions"][name]["stance"] = new_stance
                    st.session_state["positions"][name]["key_messages"] = [
                        m.strip() for m in new_messages.strip().split("\n") if m.strip()
                    ]
                    st.success(f"Updated {name} position.")
                    st.rerun()

# ===================== SPOKESPEOPLE =====================
with tab_spokespeople:
    st.markdown("### Riot spokesperson profiles")
    st.caption("These profiles shape how quotes and comments are drafted. Edits persist for this session only.")

    for role, spk in st.session_state["spokespeople"].items():
        with st.expander(f"**{spk['name']}** — {spk['title']}"):
            st.markdown(f"**Bio:** {spk['bio']}")
            st.markdown(f"**Tone:** {spk['tone']}")
            st.markdown(f"**Topics:** {', '.join(spk['topics'])}")

            with st.form(key=f"edit_spk_{role}"):
                new_name = st.text_input("Name:", value=spk["name"])
                new_title = st.text_input("Title:", value=spk["title"])
                new_bio = st.text_area("Bio:", value=spk["bio"], height=100)
                new_tone = st.text_input("Tone:", value=spk["tone"])
                new_topics = st.text_input("Topics (comma-separated):", value=", ".join(spk["topics"]))

                if st.form_submit_button("Save changes"):
                    st.session_state["spokespeople"][role]["name"] = new_name
                    st.session_state["spokespeople"][role]["title"] = new_title
                    st.session_state["spokespeople"][role]["bio"] = new_bio
                    st.session_state["spokespeople"][role]["tone"] = new_tone
                    st.session_state["spokespeople"][role]["topics"] = [
                        t.strip() for t in new_topics.split(",") if t.strip()
                    ]
                    st.success(f"Updated {new_name}.")
                    st.rerun()

st.divider()
st.info(
    "**Note:** Edits on this page are session-only and feed into PR pack generation. "
    "To make permanent changes, edit `config/positions.py` and `config/spokespeople.py`.",
)
