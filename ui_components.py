import streamlit as st

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

:root {
    --primary: #1a3c5e;
    --primary-light: #2563a8;
    --accent: #e8a020;
    --accent-light: #f5c842;
    --bg: #f8f6f1;
    --surface: #ffffff;
    --surface2: #f0ede6;
    --text: #1a1a2e;
    --text-muted: #6b7280;
    --success: #16a34a;
    --danger: #dc2626;
    --warning: #d97706;
    --border: #e5e1d8;
    --shadow: 0 4px 24px rgba(26,60,94,0.10);
    --radius: 16px;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    font-family: 'DM Sans', sans-serif;
    color: var(--text);
}

[data-testid="stSidebar"] {
    background: var(--primary) !important;
    border-right: none !important;
}

[data-testid="stSidebar"] * {
    color: #e8edf5 !important;
}

[data-testid="stSidebar"] .stRadio label {
    color: #e8edf5 !important;
    font-size: 0.95rem;
    padding: 6px 0;
}

.stButton > button {
    background: var(--primary) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    padding: 0.5rem 1.5rem !important;
    transition: all 0.2s ease !important;
}

.stButton > button:hover {
    background: var(--primary-light) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(37,99,168,0.3) !important;
}

.stTextInput > div > div > input,
.stSelectbox > div > div,
.stTextArea > div > div > textarea,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    border-radius: 10px !important;
    border: 1.5px solid var(--border) !important;
    background: var(--surface) !important;
    font-family: 'DM Sans', sans-serif !important;
}

.metric-card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 1.5rem;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    text-align: center;
    transition: transform 0.2s;
}

.metric-card:hover { transform: translateY(-2px); }

.metric-value {
    font-family: 'Playfair Display', serif;
    font-size: 2rem;
    font-weight: 700;
    color: var(--primary);
}

.metric-label {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-top: 0.25rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.property-card {
    background: var(--surface);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
    border: 1px solid var(--border);
    transition: all 0.3s ease;
    margin-bottom: 1rem;
}

.property-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(26,60,94,0.18);
}

.property-img {
    width: 100%;
    height: 200px;
    object-fit: cover;
    background: linear-gradient(135deg, #1a3c5e 0%, #2563a8 50%, #e8a020 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 4rem;
}

.property-body { padding: 1.25rem; }

.property-title {
    font-family: 'Playfair Display', serif;
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text);
    margin-bottom: 0.4rem;
}

.property-location {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 0.75rem;
}

.price-tag {
    display: inline-block;
    background: var(--primary);
    color: white;
    padding: 0.25rem 0.75rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-right: 0.5rem;
}

.badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
}

.badge-approved { background: #dcfce7; color: #16a34a; }
.badge-pending { background: #fef9c3; color: #92400e; }
.badge-rejected { background: #fee2e2; color: #dc2626; }
.badge-confirmed { background: #dbeafe; color: #1d4ed8; }
.badge-cancelled { background: #f3f4f6; color: #6b7280; }
.badge-apartment { background: #ede9fe; color: #6d28d9; }
.badge-house { background: #d1fae5; color: #065f46; }

.section-header {
    font-family: 'Playfair Display', serif;
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--primary);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--accent);
}

.trend-card {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
    border-radius: var(--radius);
    padding: 1.5rem;
    color: white;
    position: relative;
    overflow: hidden;
    margin-bottom: 0.75rem;
}

.trend-card::after {
    content: '🔥';
    position: absolute;
    right: 1rem;
    top: 1rem;
    font-size: 1.5rem;
}

.trend-score {
    font-size: 2rem;
    font-weight: 700;
    font-family: 'Playfair Display', serif;
}

.sidebar-logo {
    text-align: center;
    padding: 1.5rem 1rem;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    margin-bottom: 1rem;
}

.sidebar-logo h1 {
    font-family: 'Playfair Display', serif;
    font-size: 1.5rem;
    color: white !important;
    margin: 0;
}

.sidebar-logo p {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.6) !important;
    margin: 0;
}

.login-container {
    max-width: 440px;
    margin: 2rem auto;
    background: var(--surface);
    border-radius: 24px;
    padding: 2.5rem;
    box-shadow: 0 8px 40px rgba(26,60,94,0.15);
}

.hero-banner {
    background: linear-gradient(135deg, #1a3c5e 0%, #0f2645 40%, #e8a020 100%);
    border-radius: 20px;
    padding: 3rem 2rem;
    color: white;
    text-align: center;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}

.hero-banner h1 {
    font-family: 'Playfair Display', serif;
    font-size: 2.5rem;
    margin-bottom: 0.5rem;
}

.amenity-tag {
    display: inline-block;
    background: var(--surface2);
    color: var(--primary);
    padding: 0.2rem 0.6rem;
    border-radius: 6px;
    font-size: 0.78rem;
    margin: 0.15rem;
    border: 1px solid var(--border);
}

.booking-card {
    background: var(--surface);
    border-radius: 12px;
    padding: 1.25rem;
    border: 1px solid var(--border);
    margin-bottom: 0.75rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

div[data-testid="stExpander"] {
    background: var(--surface) !important;
    border-radius: 12px !important;
    border: 1px solid var(--border) !important;
    margin-bottom: 0.5rem;
}

.stTabs [data-baseweb="tab-list"] {
    background: var(--surface2) !important;
    border-radius: 12px !important;
    padding: 4px !important;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
}

.stTabs [aria-selected="true"] {
    background: var(--primary) !important;
    color: white !important;
}

.alert-box {
    padding: 1rem 1.25rem;
    border-radius: 12px;
    margin-bottom: 1rem;
    font-size: 0.9rem;
}

.alert-success { background: #dcfce7; border-left: 4px solid #16a34a; color: #14532d; }
.alert-warning { background: #fef9c3; border-left: 4px solid #d97706; color: #78350f; }
.alert-info { background: #dbeafe; border-left: 4px solid #2563eb; color: #1e3a8a; }

footer { visibility: hidden; }
#MainMenu { visibility: hidden; }
</style>
"""

def inject_css():
    st.markdown(THEME_CSS, unsafe_allow_html=True)

def metric_card(value, label, icon=""):
    return f"""
    <div class="metric-card">
        <div style="font-size:1.8rem">{icon}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-label">{label}</div>
    </div>
    """

def property_emoji(ptype):
    return "🏢" if ptype == "apartment" else "🏠"

def status_badge(status):
    badges = {
        "approved": "badge-approved", "pending": "badge-pending",
        "rejected": "badge-rejected", "confirmed": "badge-confirmed",
        "cancelled": "badge-cancelled", "apartment": "badge-apartment",
        "house": "badge-house", "active": "badge-approved",
        "completed": "badge-confirmed",
    }
    cls = badges.get(status, "badge-pending")
    return f'<span class="badge {cls}">{status.title()}</span>'

def sidebar_nav(user):
    st.sidebar.markdown("""
    <div class="sidebar-logo">
        <h1>🏘️ PropBook</h1>
        <p>Philippines Property Booking</p>
    </div>
    """, unsafe_allow_html=True)

    role = user['role']
    name = user['name']

    st.sidebar.markdown(f"**👤 {name}**")
    st.sidebar.markdown(f"*{role.title()}*")
    st.sidebar.divider()

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