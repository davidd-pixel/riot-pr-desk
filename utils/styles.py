"""
Shared UI styles and helpers — Riot brand design system.
Brand: Riot red #E8192C · Black #0A0A0A · White #FFFFFF
Fonts: PP Formula Condensed (headlines) + PP Formula SemiCondensed (body/UI)
"""

import base64
import os
import streamlit as st

# ---------------------------------------------------------------------------
# Secrets bootstrap — runs on every page since every page imports this module.
# On Streamlit Cloud, API keys live in st.secrets (not os.environ).
# Sync them once so all os.getenv() calls work everywhere.
# ---------------------------------------------------------------------------
def _sync_secrets():
    try:
        for _k, _v in st.secrets.items():
            if isinstance(_v, str) and _k not in os.environ:
                os.environ[_k] = _v
    except Exception:
        pass

    # Handle Google service account JSON stored as a secret string
    _sa_content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
    if _sa_content and not os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"):
        import tempfile, json as _json
        try:
            _tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
            _json.dump(_json.loads(_sa_content), _tmp)
            _tmp.close()
            os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"] = _tmp.name
        except Exception:
            pass

_sync_secrets()

_ASSET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_FONT_DIR = os.path.join(_ASSET_DIR, "fonts")

# ---------------------------------------------------------------------------
# Font loading (cached so we only read files once per process)
# ---------------------------------------------------------------------------

@st.cache_resource
def _load_fonts() -> str:
    """Load all PP Formula fonts and return a CSS @font-face block."""
    fonts = [
        ("PPFormula", "900", "normal", "PPFormula-CondensedBlack"),
        ("PPFormula", "700", "normal", "PPFormula-CondensedBold"),
        ("PPFormula", "400", "normal", "PPFormula-CondensedRegular"),
        ("PPFormula", "300", "normal", "PPFormula-CondensedLight"),
        ("PPFormulaUI", "400", "normal", "PPFormula-SemiCondensedRegular"),
        ("PPFormulaUI", "300", "normal", "PPFormula-SemiCondensedLight"),
    ]
    css_parts = []
    for family, weight, style, filename in fonts:
        woff2_path = os.path.join(_FONT_DIR, f"{filename}.woff2")
        woff_path = os.path.join(_FONT_DIR, f"{filename}.woff")
        if os.path.exists(woff2_path):
            with open(woff2_path, "rb") as f:
                woff2_b64 = base64.b64encode(f.read()).decode()
            woff_src = ""
            if os.path.exists(woff_path):
                with open(woff_path, "rb") as f:
                    woff_b64 = base64.b64encode(f.read()).decode()
                woff_src = f",\n             url('data:font/woff;base64,{woff_b64}') format('woff')"
            css_parts.append(f"""
@font-face {{
    font-family: '{family}';
    font-weight: {weight};
    font-style: {style};
    font-display: swap;
    src: url('data:font/woff2;base64,{woff2_b64}') format('woff2'){woff_src};
}}""")
    return "\n".join(css_parts)


@st.cache_resource
def _load_logo_b64() -> str:
    """Load the Riot logo as base64 — prefer logo_patch.png (black on transparent)."""
    for name in ("logo_patch.png", "logo_white.png"):
        logo_path = os.path.join(_ASSET_DIR, name)
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""


def get_page_icon() -> str:
    """Consistent branded favicon for all pages — avoids 16 different emoji."""
    return "🔴"


def _status_dot(ok: bool) -> str:
    """Return an HTML inline dot indicator for service status."""
    colour = "#4ade80" if ok else "#888"
    label = "Online" if ok else "Not configured"
    return (
        f'<span style="display:inline-block;width:6px;height:6px;border-radius:50%;'
        f'background:{colour};margin-right:6px;vertical-align:middle;"></span>{label}'
    )


# ---------------------------------------------------------------------------
# Main style injection
# ---------------------------------------------------------------------------

def apply_global_styles():
    """Inject Riot brand CSS across every page."""
    font_css = _load_fonts()

    st.markdown(f"""
    <style>
    {font_css}

    /* ── Global resets ── */
    html, body, [class*="css"] {{
        font-family: 'PPFormulaUI', 'PPFormula', -apple-system, sans-serif;
        font-weight: 400;
        background-color: #0A0A0A;
        color: #FFFFFF;
    }}

    /* ── Page container ── */
    .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }}

    /* ── Headings ── */
    h1, h2, h3, h4, h5, h6,
    [data-testid="stHeading"],
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3 {{
        font-family: 'PPFormula', sans-serif !important;
        letter-spacing: -0.01em;
    }}
    h1, .stMarkdown h1 {{
        font-weight: 900 !important;
        font-size: 2.4rem !important;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }}
    h2, .stMarkdown h2 {{
        font-weight: 700 !important;
        font-size: 1.6rem !important;
        text-transform: uppercase;
        letter-spacing: 0.02em;
    }}
    h3, .stMarkdown h3 {{
        font-weight: 700 !important;
        font-size: 1.2rem !important;
    }}

    /* ── Body text ── */
    p, li, .stMarkdown p, .stMarkdown li,
    [data-testid="stMarkdownContainer"] p {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        font-size: 0.95rem;
        line-height: 1.6;
        color: #E0E0E0;
    }}

    /* ── Captions / small text ── */
    .stCaption, small, caption,
    [data-testid="stCaptionContainer"] {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        font-size: 0.78rem;
        color: #888;
    }}

    /* ── Streamlit title widget ── */
    [data-testid="stTitle"] {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: #FFFFFF;
    }}

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {{
        background-color: #0A0A0A !important;
        border-right: 1px solid #1A1A1A;
    }}
    [data-testid="stSidebar"] > div:first-child {{
        padding-top: 0;
    }}
    /* Sidebar logo container */
    .riot-logo-block {{
        background: #E8192C;
        padding: 0.85rem 1.1rem;
        margin: 0;
    }}
    .riot-logo-block img {{
        width: 100%;
        display: block;
        filter: invert(1);
        mix-blend-mode: screen;
    }}
    .riot-tagline {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 900;
        font-size: 0.72rem;
        letter-spacing: 0.22em;
        text-transform: uppercase;
        color: #FFFFFF;
        text-align: left;
        padding: 0.45rem 1.1rem 0.4rem 1.1rem;
    }}
    /* Sidebar nav links */
    [data-testid="stSidebar"] .stPageLink a,
    [data-testid="stSidebarNav"] a {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 400;
        font-size: 0.88rem;
        color: #CCCCCC !important;
        text-decoration: none;
        transition: color 0.15s;
    }}
    [data-testid="stSidebar"] .stPageLink a:hover {{
        color: #FFFFFF !important;
    }}
    [data-testid="stSidebar"] .stPageLink a[aria-current="page"] {{
        color: #E8192C !important;
        font-weight: 700;
        border-left: 2px solid #E8192C;
        padding-left: 6px;
        background: rgba(232, 25, 44, 0.06);
        border-radius: 0 2px 2px 0;
    }}
    /* Sidebar dividers */
    [data-testid="stSidebar"] hr {{
        border-color: #1A1A1A;
    }}

    /* ── Section headers (nav labels) ── */
    .section-header {{
        font-family: 'PPFormula', sans-serif !important;
        font-size: 0.65rem;
        font-weight: 900;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: #E8192C;
        margin-top: 1.25rem;
        margin-bottom: 0.25rem;
    }}

    /* ── Dividers ── */
    hr, [data-testid="stDivider"] {{
        border-color: #1A1A1A !important;
    }}

    /* ── Buttons ── */
    .stButton > button {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        border-radius: 3px;
        transition: all 0.15s;
    }}
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {{
        background-color: #E8192C !important;
        border-color: #E8192C !important;
        color: #FFFFFF !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: #CC1525 !important;
        border-color: #CC1525 !important;
    }}
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="baseButton-secondary"] {{
        background-color: transparent !important;
        border: 1px solid #333 !important;
        color: #CCCCCC !important;
    }}
    .stButton > button[kind="secondary"]:hover {{
        border-color: #E8192C !important;
        color: #FFFFFF !important;
    }}

    /* ── Download button ── */
    .stDownloadButton > button {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border-radius: 3px;
        background-color: transparent !important;
        border: 1px solid #333 !important;
        color: #CCCCCC !important;
    }}
    .stDownloadButton > button:hover {{
        border-color: #E8192C !important;
        color: #FFFFFF !important;
    }}

    /* ── Text inputs ── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        background-color: #111 !important;
        border: 1px solid #222 !important;
        color: #FFFFFF !important;
        border-radius: 3px;
    }}
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: #E8192C !important;
        box-shadow: 0 0 0 2px rgba(232, 25, 44, 0.15) !important;
    }}
    /* Input labels */
    .stTextInput label,
    .stTextArea label,
    .stSelectbox label,
    .stMultiSelect label,
    .stSlider label,
    .stRadio label,
    .stCheckbox label {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 400;
        font-size: 0.82rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #888 !important;
    }}

    /* ── Selectbox / dropdown ── */
    .stSelectbox [data-testid="stSelectbox"],
    div[data-baseweb="select"] {{
        background-color: #111 !important;
    }}
    div[data-baseweb="select"] > div {{
        background-color: #111 !important;
        border: 1px solid #222 !important;
        color: #FFFFFF !important;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: transparent;
        border-bottom: 1px solid #1A1A1A;
        gap: 0;
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #666;
        background-color: transparent;
        border-bottom: 2px solid transparent;
        padding: 0.6rem 1.2rem;
    }}
    .stTabs [aria-selected="true"] {{
        color: #FFFFFF !important;
        border-bottom-color: #E8192C !important;
        background-color: transparent !important;
    }}

    /* ── Expanders ── */
    .streamlit-expanderHeader,
    [data-testid="stExpanderToggleIcon"] + div {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        font-size: 0.9rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }}
    [data-testid="stExpander"] {{
        border: 1px solid #1A1A1A !important;
        border-radius: 3px;
        background: #0D0D0D;
    }}

    /* ── Metric cards ── */
    [data-testid="stMetric"] {{
        background: #111 !important;
        border: 1px solid #1A1A1A !important;
        border-top: 2px solid #E8192C !important;
        border-radius: 3px;
        padding: 1rem 1.25rem !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 400;
        font-size: 0.72rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: #888 !important;
    }}
    [data-testid="stMetricValue"] {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 900;
        font-size: 2rem !important;
        color: #FFFFFF !important;
    }}

    /* ── Info / warning / success / error boxes ── */
    .stAlert {{
        border-radius: 3px;
        font-family: 'PPFormulaUI', sans-serif !important;
    }}
    [data-testid="stAlertContainer"][data-type="info"] {{
        background: rgba(148, 163, 184, 0.08) !important;
        border-left: 3px solid #64748b !important;
        color: #E0E0E0 !important;
    }}
    [data-testid="stAlertContainer"][data-type="success"] {{
        background: rgba(74, 222, 128, 0.08) !important;
        border-left: 3px solid #4ade80 !important;
    }}
    [data-testid="stAlertContainer"][data-type="warning"] {{
        background: rgba(251, 191, 36, 0.08) !important;
        border-left: 3px solid #fbbf24 !important;
    }}
    [data-testid="stAlertContainer"][data-type="error"] {{
        background: rgba(248, 113, 113, 0.08) !important;
        border-left: 3px solid #f87171 !important;
    }}

    /* ── Progress bars ── */
    [data-testid="stProgressBar"] > div > div {{
        background: #E8192C !important;
    }}
    [data-testid="stProgressBar"] > div {{
        background: #1A1A1A !important;
    }}

    /* ── Sliders ── */
    [data-testid="stSlider"] [data-testid="stThumbValue"] {{
        background: #E8192C !important;
    }}
    .stSlider [data-baseweb="slider"] [role="slider"] {{
        background: #E8192C !important;
        border-color: #E8192C !important;
    }}

    /* ── Code blocks ── */
    .stCodeBlock,
    code, pre {{
        font-family: 'SF Mono', 'Fira Code', monospace !important;
        font-size: 0.82rem;
        background: #111 !important;
        border: 1px solid #1A1A1A;
        border-radius: 3px;
    }}

    /* ── Status badge ── */
    .status-badge {{
        display: inline-block;
        padding: 2px 10px;
        border-radius: 2px;
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        font-size: 0.7rem;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }}
    .status-badge.green  {{ background: rgba(74,222,128,0.12);  color: #4ade80; border: 1px solid rgba(74,222,128,0.3); }}
    .status-badge.red    {{ background: rgba(232,25,44,0.12);   color: #E8192C; border: 1px solid rgba(232,25,44,0.3); }}
    .status-badge.yellow {{ background: rgba(251,191,36,0.12);  color: #fbbf24; border: 1px solid rgba(251,191,36,0.3); }}
    .status-badge.grey   {{ background: rgba(255,255,255,0.06); color: #888;    border: 1px solid rgba(255,255,255,0.1); }}
    .status-badge.blue   {{ background: rgba(96,165,250,0.12);  color: #60a5fa; border: 1px solid rgba(96,165,250,0.3); }}

    /* ── Workflow step cards ── */
    .workflow-step {{
        background: #111;
        border: 1px solid #1A1A1A;
        border-top: 3px solid #E8192C;
        border-radius: 3px;
        padding: 1.5rem;
        text-align: center;
        height: 100%;
    }}
    .workflow-step h3 {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        margin-top: 0.5rem;
        font-size: 1rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }}
    .workflow-step .step-number {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 900;
        font-size: 2.5rem;
        color: #E8192C;
        line-height: 1;
    }}
    .workflow-arrow {{
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        color: #333;
    }}

    /* ── Journalist / PR pack cards ── */
    .pr-card {{
        background: #111;
        border: 1px solid #1A1A1A;
        border-radius: 3px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        transition: border-color 0.15s;
    }}
    .pr-card:hover {{
        border-color: #333;
    }}
    .pr-card h4 {{
        font-family: 'PPFormula', sans-serif !important;
        font-weight: 700;
        text-transform: uppercase;
        font-size: 0.9rem;
        letter-spacing: 0.04em;
        margin: 0 0 0.5rem 0;
        color: #FFFFFF;
    }}

    /* ── Spinner ── */
    .stSpinner > div {{
        border-top-color: #E8192C !important;
    }}

    /* ── Multiselect tags ── */
    [data-baseweb="tag"] {{
        background: rgba(232,25,44,0.15) !important;
        border: 1px solid rgba(232,25,44,0.3) !important;
        color: #E8192C !important;
        font-family: 'PPFormulaUI', sans-serif !important;
        font-size: 0.75rem;
        border-radius: 2px;
    }}

    /* ── Scrollbar ── */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #0A0A0A; }}
    ::-webkit-scrollbar-thumb {{ background: #222; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #333; }}

    /* ── Page title bottom separator ── */
    [data-testid="stTitle"] {{
        border-bottom: 1px solid #1A1A1A;
        padding-bottom: 0.5rem;
        margin-bottom: 0.25rem;
    }}

    /* ── Status line (sidebar bottom indicators) ── */
    .status-line {{
        font-family: 'PPFormulaUI', sans-serif !important;
        font-weight: 300;
        font-size: 0.75rem;
        color: #666;
        margin: 0.15rem 0;
        letter-spacing: 0.04em;
    }}

    /* ── Streamlit default overrides ── */
    .stDeployButton {{ display: none; }}
    #MainMenu {{ display: none; }}
    footer {{ display: none; }}

    /* ── Hide Streamlit's auto-generated page nav (we use our own) ── */
    [data-testid="stSidebarNav"] {{ display: none !important; }}

    /* ── Always-visible sidebar — hide the collapse/expand toggle ── */
    [data-testid="collapsedControl"] {{ display: none !important; }}
    button[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
    section[data-testid="stSidebar"] {{ min-width: 260px !important; }}
    </style>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar():
    """Render the standardised Riot-branded sidebar navigation."""
    logo_b64 = _load_logo_b64()

    with st.sidebar:
        # Logo block — white RIOT wordmark on brand red background
        if logo_b64:
            st.markdown(
                f"""<a href="/" target="_self" style="text-decoration:none">
                    <div class="riot-logo-block">
                        <img src="data:image/png;base64,{logo_b64}" alt="RIOT">
                    </div>
                </a>
                <p class="riot-tagline">PR DESK</p>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown("# RIOT PR DESK")

        st.divider()

        st.markdown('<p class="section-header">Workflow</p>', unsafe_allow_html=True)
        st.page_link("pages/1_news_desk.py",        label="News Desk",        icon=":material/newspaper:")
        st.page_link("pages/4_news_jacking.py",     label="News-Jacking",     icon=":material/bolt:")
        st.page_link("pages/2_pr_generator.py",     label="PR Generator",     icon=":material/edit_note:")
        st.page_link("pages/7_pr_library.py",       label="PR Library",       icon=":material/folder_open:")
        st.page_link("pages/12_pr_calendar.py",     label="PR Calendar",      icon=":material/calendar_month:")
        st.page_link("pages/10_story_ladder.py",    label="Story Ladder",     icon=":material/trending_up:")
        st.page_link("pages/14_quote_generator.py", label="Quote Generator",  icon=":material/format_quote:")
        st.page_link("pages/11_crisis_comms.py",    label="Crisis Comms",     icon=":material/crisis_alert:")

        st.markdown('<p class="section-header">Intelligence</p>', unsafe_allow_html=True)
        st.page_link("pages/9_competitors.py",      label="Competitor Monitor", icon=":material/manage_search:")
        st.page_link("pages/15_regulators.py",      label="Regulatory Radar",   icon=":material/balance:")

        st.markdown('<p class="section-header">Content</p>', unsafe_allow_html=True)
        st.page_link("pages/16_blog_writer.py",     label="Blog Writer",      icon=":material/article:")

        st.markdown('<p class="section-header">Tools</p>', unsafe_allow_html=True)
        st.page_link("pages/6_journalists.py",      label="Journalist Database", icon=":material/contacts:")
        st.page_link("pages/8_media_lists.py",      label="Media Lists",         icon=":material/list:")
        st.page_link("pages/3_position_bank.py",    label="Position Bank",       icon=":material/account_balance:")
        st.page_link("pages/5_feedback.py",         label="Feedback & Learning", icon=":material/thumb_up:")
        st.page_link("pages/13_pitch_analytics.py", label="Pitch Analytics",     icon=":material/analytics:")

        st.divider()

        # Status indicators — CSS dots, no emoji
        from services.ai_engine import is_configured as ai_ok
        from services.news_monitor import is_configured as news_ok
        st.markdown(
            f'<p class="status-line">AI Engine&nbsp;&nbsp;{_status_dot(ai_ok())}</p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="status-line">News API&nbsp;&nbsp;&nbsp;{_status_dot(news_ok())}</p>',
            unsafe_allow_html=True,
        )
