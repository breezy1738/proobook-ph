"""
auth_pages.py  —  PropBook PH
Login / Register UI — redesigned for visibility & modern aesthetics.
"""

import streamlit as st
from auth import (
    login, register,
    get_google_oauth_url,
    verify_supabase_token,
    login_or_create_google_user,
    SUPABASE_URL,
)

# ── Inject auth-page styles ───────────────────────────────────────────────────
def _inject_auth_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Manrope:wght@400;500;600;700&display=swap');

    /* ── Full-page background ── */
    html, body,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    .main {
        background: #f2f0eb !important;
        font-family: 'Manrope', sans-serif !important;
    }

    /* Hide Streamlit chrome */
    [data-testid="stSidebar"]  { display: none !important; }
    [data-testid="stHeader"]   { display: none !important; }
    footer, #MainMenu          { visibility: hidden !important; }

    /* ── Auth card ── */
    .auth-wrap {
        max-width: 420px;
        margin: 3rem auto 2rem;
        background: #ffffff;
        border-radius: 20px;
        padding: 2.5rem 2.5rem 2rem;
        box-shadow: 0 8px 40px rgba(15,42,74,0.13), 0 2px 8px rgba(15,42,74,0.07);
        border: 1px solid #d9d5cc;
        position: relative;
        overflow: hidden;
    }
    .auth-wrap::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 4px;
        background: linear-gradient(90deg, #0f2a4a, #d4960a);
    }

    /* ── Logo / brand ── */
    .auth-brand {
        text-align: center;
        margin-bottom: 1.6rem;
    }
    .auth-brand .brand-icon {
        font-size: 2.5rem;
        display: block;
        margin-bottom: 0.3rem;
    }
    .auth-brand h2 {
        font-family: 'Sora', sans-serif !important;
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        color: #0f2a4a !important;
        margin: 0 !important;
        letter-spacing: -0.01em;
    }
    .auth-brand p {
        font-size: 0.8rem !important;
        color: #9ca3af !important;
        margin: 0.2rem 0 0 !important;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        font-weight: 600;
    }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #e8e5de !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 2px !important;
        border: none !important;
        margin-bottom: 1.2rem !important;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 7px !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.88rem !important;
        color: #6b7280 !important;
        padding: 0.45rem 1.3rem !important;
        border: none !important;
        transition: all 0.15s !important;
        flex: 1 !important;
        justify-content: center !important;
    }
    .stTabs [aria-selected="true"] {
        background: #0f2a4a !important;
        color: white !important;
        box-shadow: 0 1px 4px rgba(15,42,74,0.22) !important;
    }

    /* ── Inputs ── */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border: 1.5px solid #d1d5db !important;
        border-radius: 8px !important;
        background: #fafaf9 !important;
        color: #111827 !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 0.9rem !important;
        padding: 0.55rem 0.8rem !important;
        transition: border-color 0.15s !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #2563a8 !important;
        box-shadow: 0 0 0 3px rgba(37,99,168,0.10) !important;
        outline: none !important;
        background: #fff !important;
    }
    .stSelectbox > div > div {
        border: 1.5px solid #d1d5db !important;
        border-radius: 8px !important;
        background: #fafaf9 !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 0.9rem !important;
        color: #111827 !important;
    }

    /* Labels */
    .stTextInput label,
    .stSelectbox label {
        color: #374151 !important;
        font-family: 'Manrope', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.83rem !important;
        letter-spacing: 0.01em !important;
    }

    /* ── Primary button ── */
    .stButton > button {
        width: 100% !important;
        background: #0f2a4a !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 700 !important;
        padding: 0.6rem 1rem !important;
        letter-spacing: 0.02em !important;
        transition: all 0.18s !important;
        box-shadow: 0 2px 6px rgba(15,42,74,0.22) !important;
    }
    .stButton > button:hover {
        background: #1a4070 !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(15,42,74,0.28) !important;
    }

    /* ── Forms ── */
    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
    }

    /* ── OR divider ── */
    .or-divider {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin: 1.2rem 0;
        color: #9ca3af;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .or-divider::before,
    .or-divider::after {
        content: '';
        flex: 1;
        height: 1px;
        background: #e5e7eb;
    }

    /* ── Google button ── */
    .google-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        padding: 0.6rem 1rem;
        background: white;
        color: #374151;
        border: 1.5px solid #d1d5db;
        border-radius: 8px;
        font-size: 0.88rem;
        font-weight: 700;
        font-family: 'Manrope', sans-serif;
        cursor: pointer;
        text-decoration: none !important;
        transition: all 0.15s;
        box-sizing: border-box;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .google-btn:hover {
        background: #f9fafb;
        border-color: #9ca3af;
        box-shadow: 0 2px 6px rgba(0,0,0,0.10);
        color: #374151 !important;
        text-decoration: none !important;
    }

    /* ── Message boxes ── */
    .msg-success {
        background: #dcfce7;
        color: #14532d;
        border: 1.5px solid #86efac;
        border-left: 4px solid #16a34a;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-size: 0.87rem;
        font-family: 'Manrope', sans-serif;
        font-weight: 500;
        margin-bottom: 1rem;
    }
    .msg-error {
        background: #fee2e2;
        color: #7f1d1d;
        border: 1.5px solid #fca5a5;
        border-left: 4px solid #dc2626;
        padding: 0.75rem 1rem;
        border-radius: 8px;
        font-size: 0.87rem;
        font-family: 'Manrope', sans-serif;
        font-weight: 500;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Handle Google OAuth callback ──────────────────────────────────────────────
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
            st.markdown(
                f'<div class="msg-error">Google sign-in failed: {e}</div>',
                unsafe_allow_html=True
            )
            st.query_params.clear()


# ── Main login page ───────────────────────────────────────────────────────────
def show_login_page():
    _inject_auth_css()
    _handle_google_callback()

    # Use columns to center — narrow middle column acts as the card container
    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        # Brand header
        st.markdown("""
        <div class="auth-brand">
            <span class="brand-icon">🏘️</span>
            <h2>PropBook PH</h2>
            <p>Philippines Property Booking</p>
        </div>
        """, unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Login", "Register"])

        # ── LOGIN TAB ────────────────────────────────────────────────────────
        with tab_login:
            msg = st.empty()

            with st.form("login_form"):
                email = st.text_input(
                    "Email address",
                    placeholder="you@example.com",
                )
                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="••••••••",
                )
                submitted = st.form_submit_button(
                    "Login", use_container_width=True
                )

            if submitted:
                if not email or not password:
                    msg.markdown(
                        '<div class="msg-error">Please fill in all fields.</div>',
                        unsafe_allow_html=True
                    )
                else:
                    user = login(email, password)
                    if user:
                        st.session_state["user"]      = user
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        msg.markdown(
                            '<div class="msg-error">Invalid email or password.</div>',
                            unsafe_allow_html=True
                        )

            # OR divider + Google button
            st.markdown('<div class="or-divider">or</div>', unsafe_allow_html=True)

            google_url = get_google_oauth_url()
            if google_url:
                st.markdown(f"""
                <a href="{google_url}" target="_self" class="google-btn">
                    <img src="https://www.svgrepo.com/show/475656/google-color.svg"
                         width="18" alt="Google logo">
                    Continue with Google
                </a>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="msg-error" style="font-size:0.82rem;text-align:center">
                    Google sign-in is not configured.
                </div>
                """, unsafe_allow_html=True)

        # ── REGISTER TAB ─────────────────────────────────────────────────────
        with tab_register:
            msg2 = st.empty()

            with st.form("register_form"):
                reg_email    = st.text_input("Email address", placeholder="you@example.com", key="r_email")
                reg_name     = st.text_input("Full name", placeholder="Juan dela Cruz", key="r_name")
                reg_phone    = st.text_input("Phone number", placeholder="+63 9XX XXX XXXX", key="r_phone")
                reg_role     = st.selectbox("Register as", ["guest", "owner"], key="r_role")
                reg_password = st.text_input("Password", type="password",
                                              placeholder="Minimum 6 characters", key="r_pass")
                reg_confirm  = st.text_input("Confirm password", type="password",
                                              placeholder="••••••••", key="r_confirm")
                reg_submitted = st.form_submit_button(
                    "Create Account", use_container_width=True
                )

            if reg_submitted:
                if not reg_name or not reg_email or not reg_password:
                    msg2.markdown(
                        '<div class="msg-error">Please fill in all required fields.</div>',
                        unsafe_allow_html=True
                    )
                elif reg_password != reg_confirm:
                    msg2.markdown(
                        '<div class="msg-error">Passwords do not match.</div>',
                        unsafe_allow_html=True
                    )
                elif len(reg_password) < 6:
                    msg2.markdown(
                        '<div class="msg-error">Password must be at least 6 characters.</div>',
                        unsafe_allow_html=True
                    )
                else:
                    success, msg_text = register(
                        reg_name, reg_email, reg_password, reg_role, reg_phone
                    )
                    if success:
                        msg2.markdown(
                            f'<div class="msg-success">✓ {msg_text} Please login.</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        msg2.markdown(
                            f'<div class="msg-error">{msg_text}</div>',
                            unsafe_allow_html=True
                        )
