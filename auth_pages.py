"""
auth_pages.py  —  PropBook PH
Login / Register UI — fully fixed button visibility & layout.
"""

import streamlit as st
from auth import (
    login, register,
    get_google_oauth_url,
    verify_supabase_token,
    login_or_create_google_user,
)


def _validate_ph_phone(phone: str) -> tuple:
    """
    Validate Philippine mobile numbers.
    Accepts: 09XXXXXXXXX, +639XXXXXXXXX, 639XXXXXXXXX (11 or 12/13 digits)
    Returns: (is_valid: bool, message: str)
    """
    import re
    p = phone.strip().replace(" ", "").replace("-", "")
    if not p:
        return False, "Phone number is required."
    pattern = r'^(\+63|63|0)9\d{9}$'
    if not re.match(pattern, p):
        return False, "Enter a valid PH mobile number (e.g. 09XX XXX XXXX or +639XX XXX XXXX)."
    return True, ""


def _inject_auth_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Manrope:wght@400;500;600;700&display=swap');

    /* Full-page background */
    html, body,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    section.main, .main { background: #f2f0eb !important; font-family: 'Manrope', sans-serif !important; }

    /* Hide chrome */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"]  { display: none !important; }
    footer, #MainMenu { visibility: hidden !important; }

    /* ── BUTTON BUG FIX — every possible selector ── */
    .stButton > button,
    button[data-testid="baseButton-secondary"],
    button[data-testid="baseButton-primary"],
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button,
    .stFormSubmitButton > button {
        background-color: #0f2a4a !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.2rem !important;
        width: 100% !important;
        box-shadow: 0 2px 6px rgba(15,42,74,0.22) !important;
        transition: all 0.18s ease !important;
        cursor: pointer !important;
    }
    .stButton > button:hover,
    button[data-testid="baseButton-secondary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    [data-testid="stFormSubmitButton"] > button:hover {
        background-color: #1a4070 !important;
        color: #ffffff !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15,42,74,0.30) !important;
    }
    .stButton > button p,
    .stButton > button span,
    button[data-testid="baseButton-secondary"] p,
    button[data-testid="baseButton-secondary"] span,
    button[data-testid="baseButton-primary"] p,
    button[data-testid="baseButton-primary"] span,
    [data-testid="stFormSubmitButton"] > button p,
    [data-testid="stFormSubmitButton"] > button span {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #e8e5de !important; border-radius: 10px !important;
        padding: 4px !important; gap: 2px !important; border: none !important; margin-bottom: 1rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important; border-radius: 7px !important;
        font-family: 'Manrope', sans-serif !important; font-weight: 700 !important;
        font-size: 0.88rem !important; color: #6b7280 !important;
        padding: 0.45rem 1.3rem !important; border: none !important;
        flex: 1 !important; justify-content: center !important; transition: all 0.15s !important;
    }
    .stTabs [aria-selected="true"] {
        background: #0f2a4a !important; color: #ffffff !important;
        box-shadow: 0 1px 4px rgba(15,42,74,0.22) !important;
    }

    /* ── Inputs ── */
    .stTextInput > div > div > input, .stTextArea > div > div > textarea {
        border: 1.5px solid #d1d5db !important; border-radius: 8px !important;
        background: #fafaf9 !important; color: #111827 !important;
        font-family: 'Manrope', sans-serif !important; font-size: 0.9rem !important;
        transition: border-color 0.15s, box-shadow 0.15s !important;
    }
    .stTextInput > div > div > input:focus, .stTextArea > div > div > textarea:focus {
        border-color: #2563a8 !important; box-shadow: 0 0 0 3px rgba(37,99,168,0.10) !important;
        outline: none !important; background: #ffffff !important;
    }
    .stSelectbox > div > div {
        border: 1.5px solid #d1d5db !important; border-radius: 8px !important;
        background: #fafaf9 !important; color: #111827 !important;
        font-family: 'Manrope', sans-serif !important;
    }
    .stTextInput label, .stSelectbox label,
    [data-testid="stWidgetLabel"] p {
        color: #374151 !important; font-family: 'Manrope', sans-serif !important;
        font-weight: 600 !important; font-size: 0.83rem !important;
    }

    /* ── Forms ── */
    div[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }

    /* ── OR divider ── */
    .or-divider {
        display: flex; align-items: center; gap: 0.75rem;
        margin: 1rem 0; color: #9ca3af; font-size: 0.78rem;
        font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em;
    }
    .or-divider::before, .or-divider::after { content: ''; flex: 1; height: 1px; background: #e5e7eb; }

    /* ── Google button ── */
    .google-btn {
        display: flex; align-items: center; justify-content: center; gap: 10px;
        width: 100%; padding: 0.6rem 1rem;
        background: white; color: #374151;
        border: 1.5px solid #d1d5db; border-radius: 8px;
        font-size: 0.88rem; font-weight: 700; font-family: 'Manrope', sans-serif;
        cursor: pointer; text-decoration: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        transition: all 0.15s; box-sizing: border-box;
    }
    .google-btn:hover {
        background: #f9fafb; border-color: #9ca3af;
        box-shadow: 0 2px 6px rgba(0,0,0,0.10);
        color: #374151 !important; text-decoration: none !important;
    }

    /* ── Messages ── */
    .msg-success {
        background: #dcfce7; color: #14532d;
        border: 1.5px solid #86efac; border-left: 4px solid #16a34a;
        padding: 0.75rem 1rem; border-radius: 8px;
        font-size: 0.87rem; font-family: 'Manrope', sans-serif;
        font-weight: 500; margin-bottom: 1rem;
    }
    .msg-error {
        background: #fee2e2; color: #7f1d1d;
        border: 1.5px solid #fca5a5; border-left: 4px solid #dc2626;
        padding: 0.75rem 1rem; border-radius: 8px;
        font-size: 0.87rem; font-family: 'Manrope', sans-serif;
        font-weight: 500; margin-bottom: 1rem;
    }

    /* ── Brand ── */
    .auth-brand { text-align: center; margin-bottom: 1.4rem; }
    .auth-brand .brand-icon { font-size: 2.4rem; display: block; margin-bottom: 0.3rem; }
    .auth-brand h2 {
        font-family: 'Sora', sans-serif !important; font-size: 1.5rem !important;
        font-weight: 800 !important; color: #0f2a4a !important;
        margin: 0 !important; letter-spacing: -0.01em;
    }
    .auth-brand p {
        font-size: 0.76rem !important; color: #9ca3af !important;
        margin: 0.2rem 0 0 !important; text-transform: uppercase;
        letter-spacing: 0.07em; font-weight: 600;
    }

    /* ── Auth card wrapper ── */
    .auth-card-outer {
        background: #ffffff;
        border-radius: 20px;
        padding: 2.4rem 2.4rem 2rem;
        box-shadow: 0 8px 40px rgba(15,42,74,0.12), 0 2px 8px rgba(15,42,74,0.06);
        border: 1px solid #d9d5cc;
        position: relative;
        overflow: hidden;
        margin-top: 2rem;
    }
    .auth-card-outer::before {
        content: '';
        position: absolute; top: 0; left: 0; right: 0; height: 4px;
        background: linear-gradient(90deg, #0f2a4a, #d4960a);
    }
    </style>
    """, unsafe_allow_html=True)


def _handle_google_callback():
    params = st.query_params
    token  = params.get("access_token", "")
    if not token:
        return
    with st.spinner("Signing you in with Google…"):
        try:
            profile = verify_supabase_token(token)
            user    = login_or_create_google_user(profile)
            st.session_state["user"]      = user
            st.session_state["logged_in"] = True
            st.query_params.clear()
            st.rerun()
        except ValueError as e:
            st.markdown(f'<div class="msg-error">{e}</div>', unsafe_allow_html=True)
            st.query_params.clear()
        except Exception as e:
            st.markdown(f'<div class="msg-error">Google sign-in failed: {e}</div>', unsafe_allow_html=True)
            st.query_params.clear()


def show_login_page():
    _inject_auth_css()
    _handle_google_callback()

    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        st.markdown('<div class="auth-card-outer">', unsafe_allow_html=True)

        st.markdown("""
        <div class="auth-brand">
            <span class="brand-icon">🏘️</span>
            <h2>PropBook PH</h2>
            <p>Philippines Property Booking</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Login", "Register"])

        # ── LOGIN TAB ────────────────────────────────────────────
        with tab_login:
            msg = st.empty()

            with st.form("login_form"):
                email    = st.text_input("Email address", placeholder="you@example.com")
                password = st.text_input("Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Login →", use_container_width=True)

            if submitted:
                if not email or not password:
                    msg.markdown('<div class="msg-error">Please fill in all fields.</div>', unsafe_allow_html=True)
                else:
                    user = login(email, password)
                    if user:
                        st.session_state["user"]      = user
                        st.session_state["logged_in"] = True
                        msg.markdown(
                            f'<div class="msg-success">✓ Welcome back, {user["name"].split()[0]}! Signing you in…</div>',
                            unsafe_allow_html=True
                        )
                        import time; time.sleep(1)
                        st.rerun()
                    else:
                        msg.markdown('<div class="msg-error">Invalid email or password.</div>', unsafe_allow_html=True)

            st.markdown('<div class="or-divider">or</div>', unsafe_allow_html=True)

            google_url = get_google_oauth_url()
            if google_url:
                st.markdown(f"""
                <a href="{google_url}" target="_self" class="google-btn">
                    <img src="https://www.svgrepo.com/show/475656/google-color.svg" width="18" alt="Google">
                    Continue with Google
                </a>
                """, unsafe_allow_html=True)
            else:
                st.markdown('<div class="msg-error" style="text-align:center;font-size:0.82rem">Google sign-in not configured.</div>', unsafe_allow_html=True)

        # ── REGISTER TAB ─────────────────────────────────────────
        with tab_register:
            msg2 = st.empty()

            with st.form("register_form"):
                reg_email    = st.text_input("Email address",   placeholder="you@example.com",     key="r_email")
                reg_name     = st.text_input("Full name",        placeholder="Juan dela Cruz",       key="r_name")
                reg_phone    = st.text_input("Phone number",     placeholder="+63 9XX XXX XXXX",     key="r_phone")
                reg_role     = st.selectbox("Register as",      ["guest", "owner"],                 key="r_role")
                reg_password = st.text_input("Password",         type="password", placeholder="Min 6 characters", key="r_pass")
                reg_confirm  = st.text_input("Confirm password", type="password", placeholder="••••••••",          key="r_confirm")
                reg_submitted = st.form_submit_button("Create Account →", use_container_width=True)

            if reg_submitted:
                _phone_ok, _phone_msg = _validate_ph_phone(reg_phone)
                if not reg_name or not reg_email or not reg_password:
                    msg2.markdown('<div class="msg-error">Please fill in all required fields.</div>', unsafe_allow_html=True)
                elif not _phone_ok:
                    msg2.markdown(f'<div class="msg-error">{_phone_msg}</div>', unsafe_allow_html=True)
                elif reg_password != reg_confirm:
                    msg2.markdown('<div class="msg-error">Passwords do not match.</div>', unsafe_allow_html=True)
                elif len(reg_password) < 6:
                    msg2.markdown('<div class="msg-error">Password must be at least 6 characters.</div>', unsafe_allow_html=True)
                else:
                    success, msg_text = register(reg_name, reg_email, reg_password, reg_role, reg_phone)
                    if success:
                        msg2.markdown(f'<div class="msg-success">✓ {msg_text} Please login.</div>', unsafe_allow_html=True)
                    else:
                        msg2.markdown(f'<div class="msg-error">{msg_text}</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
