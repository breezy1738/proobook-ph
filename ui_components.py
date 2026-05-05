import streamlit as st

# ── Design tokens ─────────────────────────────────────────────────────────────
# Palette: deep navy + warm gold + clean white surfaces
# Fonts: Sora (display) + Manrope (body) — distinctive, modern, legible

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Manrope:wght@300;400;500;600;700&display=swap');

/* ── CSS Variables ─────────────────────────────────────────────────────── */
:root {
    --primary:        #0f2a4a;
    --primary-mid:    #1a4070;
    --primary-light:  #2563a8;
    --accent:         #d4960a;
    --accent-light:   #f0b429;
    --accent-soft:    #fff3cd;
    --bg:             #f2f0eb;
    --surface:        #ffffff;
    --surface2:       #e8e5de;
    --surface3:       #f8f6f2;
    --text:           #111827;
    --text-muted:     #6b7280;
    --text-light:     #9ca3af;
    --success:        #15803d;
    --success-bg:     #dcfce7;
    --danger:         #b91c1c;
    --danger-bg:      #fee2e2;
    --warning:        #b45309;
    --warning-bg:     #fef3c7;
    --info:           #1d4ed8;
    --info-bg:        #dbeafe;
    --border:         #d9d5cc;
    --shadow-sm:      0 1px 3px rgba(15,42,74,0.08), 0 1px 2px rgba(15,42,74,0.05);
    --shadow:         0 4px 16px rgba(15,42,74,0.10), 0 2px 4px rgba(15,42,74,0.06);
    --shadow-lg:      0 8px 32px rgba(15,42,74,0.14), 0 4px 8px rgba(15,42,74,0.08);
    --radius-sm:      8px;
    --radius:         14px;
    --radius-lg:      20px;
}

/* ── Global reset ──────────────────────────────────────────────────────── */
html, body,
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main {
    background-color: var(--bg) !important;
    font-family: 'Manrope', sans-serif !important;
    color: var(--text) !important;
}

/* ── Sidebar ───────────────────────────────────────────────────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child {
    background: var(--primary) !important;
    border-right: none !important;
}

/* Sidebar text — force all text white with high specificity */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] div,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stRadio label,
[data-testid="stSidebar"] .stRadio span,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: rgba(232, 240, 252, 0.90) !important;
    font-family: 'Manrope', sans-serif !important;
}

[data-testid="stSidebar"] .stRadio [data-testid="stMarkdownContainer"] p {
    font-size: 0.93rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em !important;
}

/* Sidebar divider */
[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
}

/* Sidebar button */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.10) !important;
    color: white !important;
    border: 1.5px solid rgba(255,255,255,0.25) !important;
    font-weight: 600 !important;
    letter-spacing: 0.03em !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.20) !important;
    border-color: rgba(255,255,255,0.45) !important;
}

/* ── Header & footer strip ─────────────────────────────────────────────── */
[data-testid="stHeader"] {
    background: transparent !important;
}
footer, #MainMenu { visibility: hidden !important; }

/* ── Buttons ───────────────────────────────────────────────────────────── */
.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.02em !important;
    padding: 0.55rem 1.4rem !important;
    transition: all 0.18s ease !important;
    box-shadow: 0 2px 6px rgba(15,42,74,0.20) !important;
}
.stButton > button:hover {
    background: var(--primary-mid) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(15,42,74,0.28) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Form inputs ───────────────────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    border-radius: var(--radius-sm) !important;
    border: 1.5px solid var(--border) !important;
    background: var(--surface) !important;
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.5rem 0.75rem !important;
    transition: border-color 0.15s ease !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--primary-light) !important;
    box-shadow: 0 0 0 3px rgba(37,99,168,0.12) !important;
    outline: none !important;
}

/* Selectbox */
.stSelectbox > div > div {
    border-radius: var(--radius-sm) !important;
    border: 1.5px solid var(--border) !important;
    background: var(--surface) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem !important;
}

/* Input labels */
.stTextInput label,
.stTextArea label,
.stNumberInput label,
.stSelectbox label,
.stDateInput label,
.stMultiSelect label,
.stRadio label {
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.01em !important;
}

/* ── Tabs ──────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface2) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: 7px !important;
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    color: var(--text-muted) !important;
    padding: 0.4rem 1.2rem !important;
    transition: all 0.15s ease !important;
    border: none !important;
}
.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: white !important;
    box-shadow: var(--shadow-sm) !important;
}

/* ── Expander ──────────────────────────────────────────────────────────── */
div[data-testid="stExpander"] {
    background: var(--surface) !important;
    border-radius: var(--radius) !important;
    border: 1.5px solid var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
    margin-bottom: 0.6rem !important;
    overflow: hidden !important;
}
div[data-testid="stExpander"] summary {
    font-family: 'Manrope', sans-serif !important;
    font-weight: 600 !important;
    color: var(--text) !important;
    padding: 0.75rem 1rem !important;
}

/* ── Metric & dataframes ───────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: var(--surface) !important;
    border-radius: var(--radius) !important;
    padding: 1.1rem 1.25rem !important;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    color: var(--primary) !important;
    font-family: 'Sora', sans-serif !important;
    font-weight: 700 !important;
}

/* ── Alert/info boxes ──────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: var(--radius-sm) !important;
    font-family: 'Manrope', sans-serif !important;
    font-size: 0.9rem !important;
}

/* ── Markdown text override ────────────────────────────────────────────── */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: var(--text) !important;
    font-family: 'Manrope', sans-serif !important;
}

/* ──────────────────────────────────────────────────────────────────────── */
/*  CUSTOM COMPONENT CLASSES                                                */
/* ──────────────────────────────────────────────────────────────────────── */

/* Metric card */
.metric-card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.4rem 1.5rem;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
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
    background: linear-gradient(90deg, var(--primary), var(--accent));
}
.metric-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-lg);
}
.metric-icon {
    font-size: 1.6rem;
    margin-bottom: 0.4rem;
    display: block;
}
.metric-value {
    font-family: 'Sora', sans-serif;
    font-size: 1.9rem;
    font-weight: 800;
    color: var(--primary);
    line-height: 1.1;
    display: block;
}
.metric-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
    display: block;
}

/* Property card */
.property-card {
    background: var(--surface);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    margin-bottom: 1rem;
}
.property-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-lg);
}
.property-img {
    width: 100%;
    height: 190px;
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 55%, var(--accent) 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 3.5rem;
    position: relative;
}
.property-body { padding: 1.2rem 1.25rem 1rem; }
.property-title {
    font-family: 'Sora', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 0.35rem;
    line-height: 1.3;
}
.property-location {
    font-size: 0.82rem;
    color: var(--text-muted);
    margin-bottom: 0.7rem;
    font-weight: 500;
}
.price-tag {
    display: inline-block;
    background: var(--primary);
    color: white;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    margin-right: 0.4rem;
    font-family: 'Manrope', sans-serif;
    letter-spacing: 0.01em;
}
.price-tag.accent {
    background: var(--accent);
}

/* Status badges */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    padding: 0.22rem 0.7rem;
    border-radius: 20px;
    font-size: 0.73rem;
    font-weight: 700;
    font-family: 'Manrope', sans-serif;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.badge-approved  { background: var(--success-bg); color: var(--success); }
.badge-pending   { background: var(--warning-bg); color: var(--warning); }
.badge-rejected  { background: var(--danger-bg);  color: var(--danger); }
.badge-confirmed { background: var(--info-bg);    color: var(--info); }
.badge-cancelled { background: #f3f4f6; color: #6b7280; }
.badge-apartment { background: #ede9fe; color: #6d28d9; }
.badge-house     { background: var(--success-bg); color: #065f46; }
.badge-active    { background: var(--success-bg); color: var(--success); }
.badge-completed { background: var(--info-bg); color: var(--info); }

/* Section header */
.section-header {
    font-family: 'Sora', sans-serif;
    font-size: 1.35rem;
    font-weight: 800;
    color: var(--primary);
    margin-bottom: 1.1rem;
    padding-bottom: 0.55rem;
    border-bottom: 2.5px solid var(--accent);
    letter-spacing: -0.01em;
}

/* Trend card */
.trend-card {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 100%);
    border-radius: var(--radius);
    padding: 1.4rem;
    color: white;
    position: relative;
    overflow: hidden;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow);
    transition: transform 0.2s ease;
}
.trend-card:hover { transform: translateY(-3px); }
.trend-card::after {
    content: '🔥';
    position: absolute;
    right: 1rem;
    top: 0.9rem;
    font-size: 1.4rem;
}
.trend-card::before {
    content: '';
    position: absolute;
    bottom: -20px; right: -20px;
    width: 80px; height: 80px;
    border-radius: 50%;
    background: rgba(212,150,10,0.20);
}
.trend-score {
    font-family: 'Sora', sans-serif;
    font-size: 2.1rem;
    font-weight: 800;
    line-height: 1;
    color: var(--accent-light);
}
.trend-label {
    font-size: 0.68rem;
    opacity: 0.7;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    font-weight: 600;
    margin-bottom: 0.2rem;
}
.trend-name {
    font-weight: 700;
    font-size: 0.95rem;
    margin-top: 0.3rem;
    color: white;
}
.trend-meta {
    font-size: 0.8rem;
    opacity: 0.82;
    margin-top: 0.2rem;
}

/* Hero banner */
.hero-banner {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-mid) 45%, #0d3a6e 100%);
    border-radius: var(--radius-lg);
    padding: 2.8rem 2.5rem;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
}
.hero-banner::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: rgba(212,150,10,0.18);
}
.hero-banner::after {
    content: '';
    position: absolute;
    bottom: -50px; left: -30px;
    width: 160px; height: 160px;
    border-radius: 50%;
    background: rgba(255,255,255,0.05);
}
.hero-banner h1 {
    font-family: 'Sora', sans-serif !important;
    font-size: 2.3rem !important;
    font-weight: 800 !important;
    margin-bottom: 0.5rem !important;
    color: white !important;
    position: relative;
    z-index: 1;
}
.hero-banner p {
    color: rgba(255,255,255,0.88) !important;
    position: relative;
    z-index: 1;
}

/* Amenity tags */
.amenity-tag {
    display: inline-block;
    background: var(--surface3);
    color: var(--primary);
    padding: 0.18rem 0.6rem;
    border-radius: 6px;
    font-size: 0.75rem;
    margin: 0.15rem;
    border: 1px solid var(--border);
    font-weight: 500;
    font-family: 'Manrope', sans-serif;
}

/* Booking card */
.booking-card {
    background: var(--surface);
    border-radius: var(--radius-sm);
    padding: 1.2rem 1.4rem;
    border: 1.5px solid var(--border);
    margin-bottom: 0.8rem;
    box-shadow: var(--shadow-sm);
    transition: box-shadow 0.15s ease;
}
.booking-card:hover {
    box-shadow: var(--shadow);
}

/* Alert boxes (custom) */
.alert-box {
    padding: 1rem 1.25rem;
    border-radius: var(--radius-sm);
    margin-bottom: 1rem;
    font-size: 0.9rem;
    font-family: 'Manrope', sans-serif;
    font-weight: 500;
    line-height: 1.5;
}
.alert-success {
    background: var(--success-bg);
    border-left: 4px solid var(--success);
    color: #14532d;
}
.alert-warning {
    background: var(--warning-bg);
    border-left: 4px solid #d97706;
    color: #78350f;
}
.alert-info {
    background: var(--info-bg);
    border-left: 4px solid #2563eb;
    color: #1e3a8a;
}
.alert-danger {
    background: var(--danger-bg);
    border-left: 4px solid var(--danger);
    color: #7f1d1d;
}

/* Sidebar logo block */
.sidebar-logo {
    text-align: center;
    padding: 1.6rem 1rem 1.2rem;
    border-bottom: 1px solid rgba(255,255,255,0.13);
    margin-bottom: 1rem;
}
.sidebar-logo h1 {
    font-family: 'Sora', sans-serif !important;
    font-size: 1.45rem !important;
    color: white !important;
    margin: 0 !important;
    font-weight: 800 !important;
    letter-spacing: -0.01em !important;
}
.sidebar-logo p {
    font-size: 0.72rem !important;
    color: rgba(255,255,255,0.55) !important;
    margin: 0.3rem 0 0 !important;
    letter-spacing: 0.06em !important;
    text-transform: uppercase !important;
    font-weight: 500 !important;
}

/* Sidebar user info */
.sidebar-user {
    background: rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0.75rem;
    border: 1px solid rgba(255,255,255,0.12);
}
.sidebar-user .user-name {
    font-size: 0.9rem;
    font-weight: 700;
    color: white !important;
    display: block;
}
.sidebar-user .user-role {
    font-size: 0.72rem;
    color: rgba(255,255,255,0.60) !important;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 600;
}

/* Data table */
[data-testid="stDataFrame"] {
    border-radius: var(--radius-sm) !important;
    border: 1px solid var(--border) !important;
    overflow: hidden !important;
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
        "approved":  "✓",
        "pending":   "◷",
        "rejected":  "✕",
        "confirmed": "✓",
        "cancelled": "✕",
        "active":    "✓",
        "completed": "✓",
    }
    badges = {
        "approved":  "badge-approved",
        "pending":   "badge-pending",
        "rejected":  "badge-rejected",
        "confirmed": "badge-confirmed",
        "cancelled": "badge-cancelled",
        "apartment": "badge-apartment",
        "house":     "badge-house",
        "active":    "badge-active",
        "completed": "badge-completed",
    }
    cls  = badges.get(status, "badge-pending")
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
        unsafe_allow_html=True
    )

    role_emoji = {"admin": "🛡️", "owner": "🏠", "guest": "👤"}.get(role, "👤")
    st.sidebar.markdown(
        f'<div class="sidebar-user">'
        f'<span class="user-name">{role_emoji} {name}</span>'
        f'<span class="user-role">{role}</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    st.sidebar.markdown("")  # spacer

    if role == "admin":
        pages = [
            "📊 Dashboard",
            "🏘️ Properties",
            "👥 Users",
            "📋 Bookings",
            "📈 Property Trends",
        ]
    elif role == "owner":
        pages = [
            "📊 Dashboard",
            "🏠 My Properties",
            "📋 My Bookings",
            "➕ Add Property",
            "📈 Property Trends",
        ]
    else:
        pages = [
            "🔍 Browse Properties",
            "📋 My Bookings",
            "👤 My Profile",
        ]

    choice = st.sidebar.radio("Navigate", pages, label_visibility="collapsed")

    st.sidebar.divider()
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return choice.split(" ", 1)[1].strip()
