import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
#  PropBook PH — ui_components.py
#  Complete CSS rewrite that fixes:
#  1. Black / invisible buttons (especially inside expanders, tabs, columns)
#  2. Invisible text in dark-background custom HTML cards
#  3. Sidebar text/icon color issues
#  4. Input label visibility
#  5. All Streamlit version-specific selector issues
# ─────────────────────────────────────────────────────────────────────────────

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Manrope:wght@300;400;500;600;700&display=swap');

/* ═══════════════════════════════════════════════════════════════════════════
   CSS VARIABLES
═══════════════════════════════════════════════════════════════════════════ */
:root {
    --primary:       #0f2a4a;
    --primary-mid:   #1a4070;
    --primary-light: #2563a8;
    --accent:        #d4960a;
    --accent-light:  #f0b429;
    --bg:            #f2f0eb;
    --surface:       #ffffff;
    --surface2:      #e8e5de;
    --surface3:      #f8f6f2;
    --text:          #111827;
    --text-muted:    #6b7280;
    --border:        #d9d5cc;
    --success:       #15803d;
    --success-bg:    #dcfce7;
    --danger:        #b91c1c;
    --danger-bg:     #fee2e2;
    --warning:       #b45309;
    --warning-bg:    #fef3c7;
    --info:          #1d4ed8;
    --info-bg:       #dbeafe;
    --shadow-sm:     0 1px 3px rgba(15,42,74,0.08);
    --shadow:        0 4px 16px rgba(15,42,74,0.10);
    --shadow-lg:     0 8px 32px rgba(15,42,74,0.14);
    --radius:        14px;
    --radius-sm:     8px;
}

/* ═══════════════════════════════════════════════════════════════════════════
   GLOBAL BACKGROUND & FONT
═══════════════════════════════════════════════════════════════════════════ */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section.main,
.main .block-container {
    background-color: var(--bg) !important;
    font-family: 'Manrope', sans-serif !important;
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   HIDE STREAMLIT CHROME
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stHeader"] { background: transparent !important; }
footer { visibility: hidden !important; }
#MainMenu { visibility: hidden !important; }

/* ═══════════════════════════════════════════════════════════════════════════
   BUTTONS — THE BLACK BUTTON BUG FIX
   Root cause: Streamlit injects a [data-testid="baseButton-secondary"] style
   that sets color: inherit, which inside dark containers renders as white-on-
   white or black-on-dark. We must target EVERY possible button selector.
═══════════════════════════════════════════════════════════════════════════ */

/* Target every Streamlit button variant with maximum specificity */
.stButton > button,
.stButton > button:link,
.stButton > button:visited,
button[data-testid="baseButton-secondary"],
button[data-testid="baseButton-primary"],
button[kind="secondary"],
button[kind="primary"],
[data-testid="stBaseButton-secondary"],
[data-testid="stBaseButton-primary"],
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"] {
    background-color: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.87rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.5rem 1.2rem !important;
    transition: background-color 0.18s ease, transform 0.15s ease, box-shadow 0.18s ease !important;
    box-shadow: 0 2px 6px rgba(15,42,74,0.22) !important;
    cursor: pointer !important;
    line-height: 1.4 !important;
}

/* Hover states — also needs full coverage */
.stButton > button:hover,
button[data-testid="baseButton-secondary"]:hover,
button[data-testid="baseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="baseButton-secondary"]:hover,
[data-testid="baseButton-primary"]:hover {
    background-color: var(--primary-mid) !important;
    color: #ffffff !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(15,42,74,0.30) !important;
    border: none !important;
}

/* Active / focus */
.stButton > button:active,
.stButton > button:focus,
button[data-testid="baseButton-secondary"]:active,
button[data-testid="baseButton-primary"]:active {
    background-color: var(--primary) !important;
    color: #ffffff !important;
    transform: translateY(0) !important;
    outline: 2px solid rgba(37,99,168,0.35) !important;
    outline-offset: 2px !important;
}

/* Ensure p / span inside buttons are also white */
.stButton > button p,
.stButton > button span,
button[data-testid="baseButton-secondary"] p,
button[data-testid="baseButton-secondary"] span,
button[data-testid="baseButton-primary"] p,
button[data-testid="baseButton-primary"] span {
    color: #ffffff !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
}

/* Fix buttons inside expanders specifically */
div[data-testid="stExpander"] .stButton > button,
div[data-testid="stExpander"] button[data-testid="baseButton-secondary"],
div[data-testid="stExpander"] button[data-testid="baseButton-primary"] {
    background-color: var(--primary) !important;
    color: #ffffff !important;
}

/* Fix buttons inside tabs */
.stTabs .stButton > button,
.stTabs button[data-testid="baseButton-secondary"],
.stTabs button[data-testid="baseButton-primary"] {
    background-color: var(--primary) !important;
    color: #ffffff !important;
}

/* Fix buttons inside columns */
[data-testid="column"] .stButton > button,
[data-testid="stColumns"] .stButton > button {
    background-color: var(--primary) !important;
    color: #ffffff !important;
}

/* Sidebar buttons — distinct style */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"] {
    background-color: rgba(255,255,255,0.12) !important;
    color: #ffffff !important;
    border: 1.5px solid rgba(255,255,255,0.28) !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button:hover,
[data-testid="stSidebar"] button[data-testid="baseButton-secondary"]:hover {
    background-color: rgba(255,255,255,0.22) !important;
    color: #ffffff !important;
    border-color: rgba(255,255,255,0.50) !important;
}
[data-testid="stSidebar"] .stButton > button p,
[data-testid="stSidebar"] .stButton > button span {
    color: #ffffff !important;
}

/* Form submit buttons */
[data-testid="stFormSubmitButton"] > button,
.stFormSubmitButton > button {
    background-color: var(--primary) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.9rem !important;
    padding: 0.55rem 1.4rem !important;
    box-shadow: 0 2px 8px rgba(15,42,74,0.22) !important;
    width: 100% !important;
}
[data-testid="stFormSubmitButton"] > button:hover,
.stFormSubmitButton > button:hover {
    background-color: var(--primary-mid) !important;
    color: #ffffff !important;
    transform: translateY(-1px) !important;
}
[data-testid="stFormSubmitButton"] > button p,
[data-testid="stFormSubmitButton"] > button span {
    color: #ffffff !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   SIDEBAR
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebar"] > div > div {
    background-color: var(--primary) !important;
    border-right: none !important;
}

/* Force ALL sidebar text to be light */
[data-testid="stSidebar"] *:not(button):not(button *) {
    color: rgba(232,240,252,0.90) !important;
}

[data-testid="stSidebar"] strong,
[data-testid="stSidebar"] b {
    color: #ffffff !important;
}

[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
}

/* Radio nav items */
[data-testid="stSidebar"] .stRadio > div {
    background: transparent !important;
}
[data-testid="stSidebar"] .stRadio label {
    padding: 0.35rem 0.5rem !important;
    border-radius: 6px !important;
    transition: background 0.15s !important;
    color: rgba(232,240,252,0.88) !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,255,255,0.08) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   FORM INPUTS
═══════════════════════════════════════════════════════════════════════════ */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    background-color: #ffffff !important;
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem !important;
    transition: border-color 0.15s ease, box-shadow 0.15s ease !important;
}

.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus,
.stNumberInput > div > div > input:focus {
    border-color: var(--primary-light) !important;
    box-shadow: 0 0 0 3px rgba(37,99,168,0.12) !important;
    outline: none !important;
    background-color: #ffffff !important;
    color: var(--text) !important;
}

/* Selectbox */
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border: 1.5px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    background-color: #ffffff !important;
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
}

/* ALL input labels — force dark text so they're always visible */
.stTextInput label,
.stTextArea label,
.stNumberInput label,
.stSelectbox label,
.stDateInput label,
.stMultiSelect label,
.stRadio > label,
.stCheckbox > label,
[data-testid="stWidgetLabel"],
[data-testid="stWidgetLabel"] p {
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.01em !important;
}

/* Number input +/- buttons */
.stNumberInput button {
    background-color: var(--surface2) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
    box-shadow: none !important;
}
.stNumberInput button:hover {
    background-color: var(--border) !important;
    color: var(--text) !important;
    transform: none !important;
}
.stNumberInput button p,
.stNumberInput button span {
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════════════════════════════════ */
.stTabs [data-baseweb="tab-list"] {
    background-color: var(--surface2) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    background-color: transparent !important;
    border-radius: 7px !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.87rem !important;
    color: var(--text-muted) !important;
    border: none !important;
    padding: 0.4rem 1.1rem !important;
    transition: all 0.15s !important;
}
.stTabs [aria-selected="true"] {
    background-color: var(--primary) !important;
    color: #ffffff !important;
    box-shadow: var(--shadow-sm) !important;
}
/* Tab panel text fix */
.stTabs [data-baseweb="tab-panel"] {
    background-color: transparent !important;
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   EXPANDERS
═══════════════════════════════════════════════════════════════════════════ */
div[data-testid="stExpander"] {
    background-color: var(--surface) !important;
    border-radius: var(--radius) !important;
    border: 1.5px solid var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
    margin-bottom: 0.6rem !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] > details > summary {
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    background-color: var(--surface) !important;
    padding: 0.8rem 1rem !important;
}
div[data-testid="stExpander"] > details > summary:hover {
    background-color: var(--surface3) !important;
}
/* Text inside expander */
div[data-testid="stExpander"] p,
div[data-testid="stExpander"] span,
div[data-testid="stExpander"] label,
div[data-testid="stExpander"] [data-testid="stMarkdownContainer"] p {
    color: var(--text) !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   MARKDOWN & GENERAL TEXT
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
}
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    font-family: 'Sora', sans-serif !important;
    color: var(--primary) !important;
}

/* st.caption */
.stCaptionContainer,
[data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
    font-size: 0.8rem !important;
    font-family: 'Manrope', sans-serif !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   METRICS
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stMetric"] {
    background-color: var(--surface) !important;
    border-radius: var(--radius) !important;
    padding: 1.1rem 1.25rem !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stMetricLabel"] p {
    color: var(--text-muted) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.78rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    color: var(--primary) !important;
    font-family: 'Sora', sans-serif !important;
    font-weight: 800 !important;
}
[data-testid="stMetricDelta"] {
    font-family: 'Manrope', sans-serif !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   DATAFRAME / TABLE
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stDataFrame"] {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    overflow: hidden !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   ALERTS
═══════════════════════════════════════════════════════════════════════════ */
[data-testid="stAlert"],
div[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   DIVIDERS
═══════════════════════════════════════════════════════════════════════════ */
hr {
    border-color: var(--border) !important;
    margin: 1.2rem 0 !important;
}

/* ═══════════════════════════════════════════════════════════════════════════
   CUSTOM HTML COMPONENT CLASSES
═══════════════════════════════════════════════════════════════════════════ */

/* ── Metric card ── */
.metric-card {
    background: #ffffff;
    border-radius: 14px;
    padding: 1.4rem 1.5rem;
    box-shadow: 0 4px 16px rgba(15,42,74,0.10);
    border: 1px solid #d9d5cc;
    text-align: center;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #0f2a4a, #d4960a);
}
.metric-card:hover { transform: translateY(-3px); box-shadow: 0 8px 32px rgba(15,42,74,0.14); }
.metric-icon { font-size: 1.6rem; margin-bottom: 0.35rem; display: block; }
.metric-value {
    font-family: 'Sora', sans-serif;
    font-size: 1.85rem;
    font-weight: 800;
    color: #0f2a4a;
    line-height: 1.1;
    display: block;
}
.metric-label {
    font-size: 0.73rem;
    color: #6b7280;
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
    display: block;
    font-family: 'Manrope', sans-serif;
}

/* ── Section header ── */
.section-header {
    font-family: 'Sora', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    color: #0f2a4a;
    margin-bottom: 1.1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2.5px solid #d4960a;
    letter-spacing: -0.01em;
}

/* ── Property card ── */
.property-card {
    background: #ffffff;
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 4px 16px rgba(15,42,74,0.10);
    border: 1px solid #d9d5cc;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    margin-bottom: 1rem;
}
.property-card:hover { transform: translateY(-5px); box-shadow: 0 8px 32px rgba(15,42,74,0.14); }
.property-img {
    width: 100%;
    height: 190px;
    background: linear-gradient(135deg, #0f2a4a 0%, #1a4070 55%, #d4960a 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 3.5rem;
}
.property-body { padding: 1.2rem 1.25rem 1rem; }
.property-title {
    font-family: 'Sora', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: #111827;
    margin-bottom: 0.35rem;
    line-height: 1.3;
}
.property-location {
    font-size: 0.82rem;
    color: #6b7280;
    margin-bottom: 0.7rem;
    font-weight: 500;
}
.price-tag {
    display: inline-block;
    background: #0f2a4a;
    color: #ffffff;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    margin-right: 0.4rem;
    font-family: 'Manrope', sans-serif;
}
.price-tag.accent { background: #d4960a; }

/* ── Status badges ── */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.22rem 0.7rem;
    border-radius: 20px;
    font-size: 0.73rem;
    font-weight: 700;
    font-family: 'Manrope', sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-approved  { background: #dcfce7; color: #15803d; }
.badge-pending   { background: #fef3c7; color: #b45309; }
.badge-rejected  { background: #fee2e2; color: #b91c1c; }
.badge-confirmed { background: #dbeafe; color: #1d4ed8; }
.badge-cancelled { background: #f3f4f6; color: #6b7280; }
.badge-apartment { background: #ede9fe; color: #6d28d9; }
.badge-house     { background: #dcfce7; color: #065f46; }
.badge-active    { background: #dcfce7; color: #15803d; }
.badge-completed { background: #dbeafe; color: #1d4ed8; }

/* ── Trend card ── */
.trend-card {
    background: linear-gradient(135deg, #0f2a4a 0%, #1a4070 100%);
    border-radius: 14px;
    padding: 1.4rem;
    color: #ffffff;
    position: relative;
    overflow: hidden;
    margin-bottom: 0.75rem;
    box-shadow: 0 4px 16px rgba(15,42,74,0.20);
    transition: transform 0.2s ease;
}
.trend-card:hover { transform: translateY(-3px); }
.trend-card::after { content: '🔥'; position: absolute; right: 1rem; top: 0.9rem; font-size: 1.4rem; }
.trend-score {
    font-family: 'Sora', sans-serif;
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1;
    color: #f0b429;
}
.trend-label { font-size: 0.68rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.09em; font-weight: 600; margin-bottom: 0.2rem; }
.trend-name { font-weight: 700; font-size: 0.95rem; margin-top: 0.3rem; color: #ffffff; }
.trend-meta { font-size: 0.8rem; opacity: 0.82; margin-top: 0.2rem; }

/* ── Hero banner ── */
.hero-banner {
    background: linear-gradient(135deg, #0f2a4a 0%, #1a4070 50%, #0d3a6e 100%);
    border-radius: 20px;
    padding: 2.8rem 2.5rem;
    color: #ffffff;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(15,42,74,0.18);
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: rgba(212,150,10,0.15);
}
.hero-banner h1 {
    font-family: 'Sora', sans-serif !important;
    font-size: 2.2rem !important;
    font-weight: 800 !important;
    margin-bottom: 0.5rem !important;
    color: #ffffff !important;
}
.hero-banner p { color: rgba(255,255,255,0.88) !important; }

/* ── Amenity tags ── */
.amenity-tag {
    display: inline-block;
    background: #f8f6f2;
    color: #0f2a4a;
    padding: 0.18rem 0.6rem;
    border-radius: 6px;
    font-size: 0.75rem;
    margin: 0.15rem;
    border: 1px solid #d9d5cc;
    font-weight: 500;
    font-family: 'Manrope', sans-serif;
}

/* ── Booking card ── */
.booking-card {
    background: #ffffff;
    border-radius: 8px;
    padding: 1.2rem 1.4rem;
    border: 1.5px solid #d9d5cc;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 3px rgba(15,42,74,0.08);
    transition: box-shadow 0.15s ease;
}
.booking-card:hover { box-shadow: 0 4px 16px rgba(15,42,74,0.10); }
.booking-card b { color: #111827; }

/* ── Custom alert boxes ── */
.alert-box { padding: 1rem 1.25rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem; font-family: 'Manrope', sans-serif; font-weight: 500; }
.alert-success { background: #dcfce7; border-left: 4px solid #15803d; color: #14532d; }
.alert-warning { background: #fef3c7; border-left: 4px solid #d97706; color: #78350f; }
.alert-info    { background: #dbeafe; border-left: 4px solid #2563eb; color: #1e3a8a; }
.alert-danger  { background: #fee2e2; border-left: 4px solid #dc2626; color: #7f1d1d; }

/* ── Sidebar logo ── */
.sidebar-logo {
    text-align: center;
    padding: 1.6rem 1rem 1.2rem;
    border-bottom: 1px solid rgba(255,255,255,0.13);
    margin-bottom: 1rem;
}
.sidebar-logo h1 {
    font-family: 'Sora', sans-serif !important;
    font-size: 1.45rem !important;
    color: #ffffff !important;
    margin: 0 !important;
    font-weight: 800 !important;
}
.sidebar-logo p {
    font-size: 0.72rem !important;
    color: rgba(255,255,255,0.55) !important;
    margin: 0.3rem 0 0 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}

/* ── Sidebar user chip ── */
.sidebar-user {
    background: rgba(255,255,255,0.09);
    border-radius: 10px;
    padding: 0.7rem 0.9rem;
    margin: 0 0.5rem 0.75rem;
    border: 1px solid rgba(255,255,255,0.12);
}
.sidebar-user .user-name {
    font-size: 0.9rem;
    font-weight: 700;
    color: #ffffff !important;
    display: block;
    font-family: 'Manrope', sans-serif;
}
.sidebar-user .user-role {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.55) !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
    font-family: 'Manrope', sans-serif;
}
</style>
"""


def inject_css():
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def metric_card(value, label, icon=""):
    return f"""
    <div class="metric-card">
        <span class="metric-icon">{icon}</span>
        <span class="metric-value">{value}</span>
        <span class="metric-label">{label}</span>
    </div>
    """


def property_emoji(ptype):
    return "🏢" if ptype == "apartment" else "🏠"


def status_badge(status):
    icons = {
        "approved":  "✓", "pending":   "◷", "rejected":  "✕",
        "confirmed": "✓", "cancelled": "✕", "active":    "✓", "completed": "✓",
    }
    classes = {
        "approved":  "badge-approved",  "pending":   "badge-pending",
        "rejected":  "badge-rejected",  "confirmed": "badge-confirmed",
        "cancelled": "badge-cancelled", "apartment": "badge-apartment",
        "house":     "badge-house",     "active":    "badge-active",
        "completed": "badge-completed",
    }
    cls  = classes.get(status, "badge-pending")
    icon = icons.get(status, "")
    return f'<span class="badge {cls}">{icon} {status.title()}</span>'


def sidebar_nav(user):
    role = user["role"]
    name = user["name"]

    st.sidebar.markdown(
        '<div class="sidebar-logo">'
        '<h1>🏘️ PropBook</h1>'
        '<p>Philippines Property Booking</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    role_emoji = {"admin": "🛡️", "owner": "🏠", "guest": "👤"}.get(role, "👤")
    st.sidebar.markdown(
        f'<div class="sidebar-user">'
        f'<span class="user-name">{role_emoji} {name}</span>'
        f'<span class="user-role">{role}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if role == "admin":
        pages = ["📊 Dashboard", "🏘️ Properties", "👥 Users", "📋 Bookings", "📈 Property Trends"]
    elif role == "owner":
        pages = ["📊 Dashboard", "🏠 My Properties", "📋 My Bookings", "➕ Add Property", "📈 Property Trends"]
    else:
        pages = ["🔍 Browse Properties", "📋 My Bookings", "👤 My Profile"]

    choice = st.sidebar.radio("Navigate", pages, label_visibility="collapsed")

    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return choice.split(" ", 1)[1].strip()
