"""
auth_pages.py  —  PropBook PH
Login / Register UI matching the clean card + tab design from index.html
"""

import streamlit as st
from auth import (
    login, register,
    get_google_oauth_url,
    verify_supabase_token,
    login_or_create_google_user,
    SUPABASE_URL,
)

# ── Inject UI styles ──────────────────────────────────────────────────────────
def _inject_auth_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
        background-color: #f4f4f9 !important;
        font-family: 'Inter', Arial, sans-serif !important;
    }

    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="stHeader"]  { display: none !important; }
    footer                    { display: none !important; }
    #MainMenu                 { display: none !important; }

    .stButton > button {
        width: 100% !important;
        padding: 10px !important;
        background-color: #0066cc !important;
        color: white !important;
        border: none !important;
        border-radius: 4px !important;
        font-size: 15px !important;
        font-weight: bold !important;
        font-family: 'Inter', Arial, sans-serif !important;
        transition: background-color 0.2s !important;
    }

    .stButton > button:hover {
        background-color: #005bb5 !important;
    }

    .stTextInput > div > div > input,
    .stSelectbox > div > div {
        border: 1px solid #ccc !important;
        border-radius: 4px !important;
        font-family: 'Inter', Arial, sans-serif !important;
        font-size: 14px !important;
        background: #fff !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 2px solid #eee !important;
        border-radius: 0 !important;
        padding: 0 !important;
        gap: 0 !important;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 0 !important;
        font-family: 'Inter', Arial, sans-serif !important;
        font-weight: bold !important;
        font-size: 15px !important;
        color: #777 !important;
        padding: 10px 20px !important;
        flex: 1 !important;
        justify-content: center !important;
    }

    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #0066cc !important;
        border-bottom: 2px solid #0066cc !important;
    }

    div[data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
    }

    .field-label {
        display: block;
        margin-bottom: 4px;
        font-size: 14px;
        color: #333;
        font-weight: 500;
    }

    .or-divider {
        text-align: center;
        margin: 18px 0;
        color: #777;
        font-size: 14px;
        position: relative;
    }

    .or-divider::before, .or-divider::after {
        content: "";
        position: absolute;
        top: 50%;
        width: 40%;
        height: 1px;
        background-color: #ccc;
    }

    .or-divider::before { left: 0; }
    .or-divider::after  { right: 0; }

    .google-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        width: 100%;
        padding: 10px;
        background: white;
        color: #444;
        border: 1px solid #ccc;
        border-radius: 4px;
        font-size: 15px;
        font-weight: bold;
        font-family: 'Inter', Arial, sans-serif;
        cursor: pointer;
        text-decoration: none;
        transition: background 0.2s;
        box-sizing: border-box;
    }

    .google-btn:hover {
        background: #f9f9f9;
        color: #444;
        text-decoration: none;
    }

    .msg-success {
        background: #d4edda;
        color: #155724;
        border: 1px solid #c3e6cb;
        padding: 12px 15px;
        border-radius: 4px;
        font-size: 14px;
        margin-bottom: 15px;
        text-align: center;
    }

    .msg-error {
        background: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        padding: 12px 15px;
        border-radius: 4px;
        font-size: 14px;
        margin-bottom: 15px;
        text-align: center;
    }

    .auth-card {
        background: #ffffff;
        padding: 2rem 2rem 1.5rem;
        border-radius: 8px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)


# ── Handle Google OAuth callback ──────────────────────────────────────────────
def _handle_google_callback():
    params = st.query_params
    token  = params.get("access_token", "")
    if not token:
        return

    with st.spinner("Signing you in with Google, please wait..."):
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
            st.markdown(f'<div class="msg-error">Google sign-in failed: {e}</div>',
                        unsafe_allow_html=True)
            st.query_params.clear()


# ── Main login page ───────────────────────────────────────────────────────────
def show_login_page():
    _inject_auth_css()
    _handle_google_callback()

    # Center card using columns
    _, col, _ = st.columns([1, 1.5, 1])

    with col:
        st.markdown('<div class="auth-card">', unsafe_allow_html=True)

        tab_login, tab_register = st.tabs(["Login", "Register"])

        # ── LOGIN TAB ────────────────────────────────────────────────────────
        with tab_login:
            msg = st.empty()

            with st.form("login_form"):
                st.markdown('<span class="field-label">Email</span>', unsafe_allow_html=True)
                email = st.text_input("Email", placeholder="you@example.com",
                                      label_visibility="collapsed")

                st.markdown('<span class="field-label">Password</span>', unsafe_allow_html=True)
                password = st.text_input("Password", type="password",
                                         placeholder="••••••••",
                                         label_visibility="collapsed")

                submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if not email or not password:
                    msg.markdown('<div class="msg-error">Please fill in all fields.</div>',
                                 unsafe_allow_html=True)
                else:
                    user = login(email, password)
                    if user:
                        st.session_state["user"]      = user
                        st.session_state["logged_in"] = True
                        st.rerun()
                    else:
                        msg.markdown(
                            '<div class="msg-error">Invalid email or password.</div>',
                            unsafe_allow_html=True)

            # OR divider + Google button
            st.markdown('<div class="or-divider">OR</div>', unsafe_allow_html=True)

            google_url = get_google_oauth_url()
            if google_url:
                st.markdown(f"""
                <a href="{google_url}" target="_self" class="google-btn">
                    <img src="https://www.svgrepo.com/show/475656/google-color.svg"
                         width="20" alt="Google">
                    Continue with Google
                </a>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="msg-error" style="font-size:13px">
                    Google sign-in not configured.
                </div>
                """, unsafe_allow_html=True)

        # ── REGISTER TAB ─────────────────────────────────────────────────────
        with tab_register:
            msg2 = st.empty()

            with st.form("register_form"):
                st.markdown('<span class="field-label">Email</span>', unsafe_allow_html=True)
                reg_email = st.text_input("Reg Email", placeholder="you@example.com",
                                          label_visibility="collapsed")

                st.markdown('<span class="field-label">Full Name</span>', unsafe_allow_html=True)
                reg_name = st.text_input("Full Name", placeholder="Juan dela Cruz",
                                         label_visibility="collapsed")

                st.markdown('<span class="field-label">Phone</span>', unsafe_allow_html=True)
                reg_phone = st.text_input("Phone", placeholder="+63 9XX XXX XXXX",
                                          label_visibility="collapsed")

                st.markdown('<span class="field-label">Register as</span>', unsafe_allow_html=True)
                reg_role = st.selectbox("Role", ["guest", "owner"],
                                        label_visibility="collapsed")

                st.markdown('<span class="field-label">Password</span>', unsafe_allow_html=True)
                reg_password = st.text_input("Reg Password", type="password",
                                              placeholder="Min 6 characters",
                                              label_visibility="collapsed")

                st.markdown('<span class="field-label">Confirm Password</span>', unsafe_allow_html=True)
                reg_confirm = st.text_input("Confirm Password", type="password",
                                             placeholder="••••••••",
                                             label_visibility="collapsed")

                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)

            if reg_submitted:
                if not reg_name or not reg_email or not reg_password:
                    msg2.markdown(
                        '<div class="msg-error">Please fill in all required fields.</div>',
                        unsafe_allow_html=True)
                elif reg_password != reg_confirm:
                    msg2.markdown('<div class="msg-error">Passwords do not match.</div>',
                                  unsafe_allow_html=True)
                elif len(reg_password) < 6:
                    msg2.markdown(
                        '<div class="msg-error">Password must be at least 6 characters.</div>',
                        unsafe_allow_html=True)
                else:
                    success, msg_text = register(reg_name, reg_email, reg_password,
                                                 reg_role, reg_phone)
                    if success:
                        msg2.markdown(
                            f'<div class="msg-success">{msg_text} Please login.</div>',
                            unsafe_allow_html=True)
                    else:
                        msg2.markdown(f'<div class="msg-error">{msg_text}</div>',
                                      unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
