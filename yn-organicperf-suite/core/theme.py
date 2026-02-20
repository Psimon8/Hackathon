"""
YN Organic-Perf Suite — shared dark theme.
Import and call inject_theme() at the top of each page after st.set_page_config().
"""
import streamlit as st

_YN_THEME_CSS = """
<style>
/* ── Root variables ──────────────────────────────────────────────────── */
:root {
    --yn-bg-primary: #0E1117;
    --yn-bg-card: #161B22;
    --yn-bg-card-hover: #1C222D;
    --yn-border: #2D333B;
    --yn-accent-green: #22C55E;
    --yn-accent-green-dim: #16A34A;
    --yn-accent-purple: #7C3AED;
    --yn-accent-purple-light: #A855F7;
    --yn-text-primary: #FAFAFA;
    --yn-text-secondary: #9CA3AF;
    --yn-text-muted: #6B7280;
}

/* ── Main container gradient ─────────────────────────────────────────── */
.stApp {
    background: linear-gradient(165deg, #0E1117 0%, #13111C 40%, #1A1035 70%, #1E1145 100%) !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E1117 0%, #161125 100%) !important;
    border-right: 1px solid var(--yn-border) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown li,
section[data-testid="stSidebar"] label {
    color: var(--yn-text-secondary) !important;
}

/* ── Card-like containers (metric, expander) ─────────────────────────── */
div[data-testid="stMetric"],
div[data-testid="metric-container"] {
    background: var(--yn-bg-card) !important;
    border: 1px solid var(--yn-border) !important;
    border-radius: 12px !important;
    padding: 1rem 1.25rem !important;
    transition: border-color 0.2s ease;
}
div[data-testid="stMetric"]:hover,
div[data-testid="metric-container"]:hover {
    border-color: var(--yn-accent-purple) !important;
}
div[data-testid="stMetric"] label,
div[data-testid="metric-container"] label {
    color: var(--yn-text-secondary) !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
div[data-testid="stMetric"] div[data-testid="stMetricValue"],
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    color: var(--yn-accent-green) !important;
    font-weight: 700 !important;
    font-size: 2rem !important;
}

/* ── Expander ────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
    background: var(--yn-bg-card) !important;
    border: 1px solid var(--yn-border) !important;
    border-radius: 12px !important;
}

/* ── Tabs ────────────────────────────────────────────────────────────── */
button[data-baseweb="tab"] {
    color: var(--yn-text-secondary) !important;
    border-radius: 8px 8px 0 0 !important;
    font-weight: 500 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--yn-accent-green) !important;
    border-bottom-color: var(--yn-accent-green) !important;
}
div[data-baseweb="tab-highlight"] {
    background-color: var(--yn-accent-green) !important;
}

/* ── Buttons ─────────────────────────────────────────────────────────── */
button[kind="primary"],
button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, var(--yn-accent-green-dim), var(--yn-accent-green)) !important;
    color: #0E1117 !important;
    font-weight: 600 !important;
    border: none !important;
    border-radius: 8px !important;
    transition: all 0.2s ease;
}
button[kind="primary"]:hover,
button[data-testid="stBaseButton-primary"]:hover {
    filter: brightness(1.1);
    box-shadow: 0 4px 15px rgba(34, 197, 94, 0.3);
}
button[kind="secondary"],
button[data-testid="stBaseButton-secondary"] {
    background: var(--yn-bg-card) !important;
    color: var(--yn-text-primary) !important;
    border: 1px solid var(--yn-border) !important;
    border-radius: 8px !important;
}

/* ── Download button ─────────────────────────────────────────────────── */
button[data-testid="stDownloadButton"] > button,
div[data-testid="stDownloadButton"] button {
    background: linear-gradient(135deg, var(--yn-accent-purple), var(--yn-accent-purple-light)) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

/* ── Inputs ──────────────────────────────────────────────────────────── */
div[data-baseweb="input"],
div[data-baseweb="textarea"],
div[data-baseweb="select"],
div[data-baseweb="popover"] {
    border-radius: 8px !important;
}
input, textarea,
div[data-baseweb="input"] input,
div[data-baseweb="textarea"] textarea {
    background: var(--yn-bg-card) !important;
    color: var(--yn-text-primary) !important;
    border-color: var(--yn-border) !important;
}

/* ── Dataframe / table ───────────────────────────────────────────────── */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--yn-border) !important;
    border-radius: 12px !important;
    overflow: hidden;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
div[data-testid="stProgress"] > div > div > div {
    background: linear-gradient(90deg, var(--yn-accent-green-dim), var(--yn-accent-green)) !important;
}

/* ── Alert boxes ─────────────────────────────────────────────────────── */
div[data-testid="stAlert"] {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* ── Slider ──────────────────────────────────────────────────────────── */
div[data-testid="stSlider"] div[role="slider"] {
    background: var(--yn-accent-green) !important;
}
div[data-testid="stSlider"] div[data-testid="stThumbValue"] {
    color: var(--yn-accent-green) !important;
}

/* ── Checkbox ────────────────────────────────────────────────────────── */
span[data-testid="stCheckbox"] label span[role="checkbox"][aria-checked="true"] {
    background-color: var(--yn-accent-green) !important;
    border-color: var(--yn-accent-green) !important;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr {
    border-color: var(--yn-border) !important;
    opacity: 0.5;
}

/* ── Titles ──────────────────────────────────────────────────────────── */
h1 {
    background: linear-gradient(135deg, #FAFAFA 0%, #D4D4D8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 800 !important;
}
h2, h3 {
    color: var(--yn-text-primary) !important;
    font-weight: 700 !important;
}

/* ── Charts ──────────────────────────────────────────────────────────── */
div[data-testid="stArrowVegaLiteChart"],
div[data-testid="stVegaLiteChart"] {
    background: var(--yn-bg-card) !important;
    border: 1px solid var(--yn-border) !important;
    border-radius: 12px !important;
    padding: 0.5rem !important;
}

/* ── Dropdowns ───────────────────────────────────────────────────────── */
ul[data-testid="stSelectboxVirtualDropdown"],
div[data-baseweb="menu"] {
    background: var(--yn-bg-card) !important;
    border: 1px solid var(--yn-border) !important;
}

/* ── Radio ───────────────────────────────────────────────────────────── */
div[data-testid="stRadio"] label {
    color: var(--yn-text-secondary) !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: var(--yn-bg-primary); }
::-webkit-scrollbar-thumb { background: var(--yn-border); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: var(--yn-text-muted); }

/* ── Links ───────────────────────────────────────────────────────────── */
a { color: var(--yn-accent-purple-light) !important; }
a:hover { color: var(--yn-accent-green) !important; }

/* ── Multiselect tags ────────────────────────────────────────────────── */
span[data-baseweb="tag"] {
    background-color: var(--yn-accent-green-dim) !important;
    color: white !important;
    border-radius: 6px !important;
}
</style>
"""


def inject_theme():
    """Inject the YN dark theme CSS into the current Streamlit page."""
    st.markdown(_YN_THEME_CSS, unsafe_allow_html=True)
