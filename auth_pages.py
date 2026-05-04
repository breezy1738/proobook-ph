"""
auth_pages.py  —  PropBook PH
Login / Register UI, including Google OAuth Sign-In.
"""

import streamlit as st
from auth import (
    login, register,
    get_google_oauth_url,
    verify_supabase_token,
    login_or_create_google_user,
    SUPABASE_URL,
)
from ui_components import inject_css


# ── Handle Google OAuth callback token ───────────────────────────────────────
# Supabase appends ?access_token=... to the redirect URL (when using
# the query-param flow).  We check for it on every page load.

def _handle_google_callback():
    """
    If the URL contains ?access_token=..., it means Supabase just
    redirected back after a successful Google login.
    We verify the token, log the user in, and clear the param from the URL.
    """
    params = st.query_params
    token  = params.get("access_token", "")

    if not token:
        return  # nothing to handle

    with st.spinner("Completing Google sign-in…"):
        try:
            profile = verify_supabase_token(token)
            user    = login_or_create_google_user(profile)
            st.session_state["user"]      = user
            st.session_state["logged_in"] = True
            # Clear the token from the URL
            st.query_params.clear()
            st.success(f"Welcome, {user['name']}! 👋")
            st.rerun()
        except ValueError as e:
            st.error(str(e))
            st.query_params.clear()
        except Exception as e:
            st.error(f"Google sign-in failed: {e}")
            st.query_params.clear()


# ── Main login page ───────────────────────────────────────────────────────────

def show_login_page():
    inject_css()

    # Always check for OAuth callback first
    _handle_google_callback()

    st.markdown("""
    <div style="text-align:center;margin-bottom:2rem">
        <h1 style="font-family:'Playfair Display',serif;color:#1a3c5e;font-size:3rem">🏘️ PropBook</h1>
        <p style="color:#6b7280;font-size:1.1rem">Philippines Property Booking Platform</p>
    </div>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 1.2, 1])
    with col_center:
        tab_login, tab_register = st.tabs(["🔐 Login", "✍️ Register"])

        # ── LOGIN TAB ────────────────────────────────────────────────────────
        with tab_login:
            st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

            # ── Google Sign-In button ────────────────────────────────────────
            google_url = get_google_oauth_url()
            if google_url:
                st.markdown(
                    f"""
                    <div style="margin-bottom:1rem">
                      <a href="{google_url}" target="_self" style="
                        display:flex; align-items:center; justify-content:center; gap:0.65rem;
                        width:100%; padding:0.65rem 1.25rem;
                        background:#fff; color:#374151;
                        border:1.5px solid #e5e1d8; border-radius:10px;
                        font-family:'DM Sans',sans-serif; font-size:0.95rem; font-weight:500;
                        text-decoration:none; box-shadow:0 1px 4px rgba(0,0,0,0.08);
                        transition:box-shadow 0.2s;">
                        <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
                          <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4"/>
                          <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853"/>
                          <path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332Z" fill="#FBBC05"/>
                          <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335"/>
                        </svg>
                        Sign in with Google
                      </a>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Divider
                st.markdown("""
                <div style="display:flex;align-items:center;gap:0.75rem;
                            margin:0.75rem 0;color:#9ca3af;font-size:0.85rem">
                  <hr style="flex:1;border:none;border-top:1px solid #e5e1d8">
                  or sign in with email
                  <hr style="flex:1;border:none;border-top:1px solid #e5e1d8">
                </div>
                """, unsafe_allow_html=True)
            else:
                # Supabase not configured — show a subtle notice
                st.info("💡 Google sign-in is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY to enable it.", icon="ℹ️")

            # ── Email / password form ────────────────────────────────────────
            with st.form("login_form"):
                email    = st.text_input("📧 Email", placeholder="your@email.com")
                password = st.text_input("🔒 Password", type="password", placeholder="••••••••")
                submitted = st.form_submit_button("Sign In →", use_container_width=True)

                if submitted:
                    user = login(email, password)
                    if user:
                        st.session_state["user"]      = user
                        st.session_state["logged_in"] = True
                        st.success(f"Welcome back, {user['name']}! 👋")
                        st.rerun()
                    else:
                        st.error("Invalid credentials. Please try again.")

        # ── REGISTER TAB ─────────────────────────────────────────────────────
        with tab_register:
            st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)

            # Google sign-up shortcut (same URL)
            if google_url:
                st.markdown(
                    f"""
                    <div style="margin-bottom:1rem">
                      <a href="{google_url}" target="_self" style="
                        display:flex; align-items:center; justify-content:center; gap:0.65rem;
                        width:100%; padding:0.65rem 1.25rem;
                        background:#fff; color:#374151;
                        border:1.5px solid #e5e1d8; border-radius:10px;
                        font-family:'DM Sans',sans-serif; font-size:0.95rem; font-weight:500;
                        text-decoration:none; box-shadow:0 1px 4px rgba(0,0,0,0.08);">
                        <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
                          <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z" fill="#4285F4"/>
                          <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z" fill="#34A853"/>
                          <path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332Z" fill="#FBBC05"/>
                          <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58Z" fill="#EA4335"/>
                        </svg>
                        Sign up with Google
                      </a>
                    </div>
                    <div style="display:flex;align-items:center;gap:0.75rem;
                                margin:0.75rem 0;color:#9ca3af;font-size:0.85rem">
                      <hr style="flex:1;border:none;border-top:1px solid #e5e1d8">
                      or register with email
                      <hr style="flex:1;border:none;border-top:1px solid #e5e1d8">
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.form("register_form"):
                name     = st.text_input("👤 Full Name", placeholder="Juan dela Cruz")
                email    = st.text_input("📧 Email",     placeholder="your@email.com")
                phone    = st.text_input("📱 Phone",     placeholder="+63 9XX XXX XXXX")
                role     = st.selectbox("Register as",   ["guest", "owner"])
                password = st.text_input("🔒 Password",  type="password", placeholder="Min 6 characters")
                confirm  = st.text_input("🔒 Confirm Password", type="password")
                submitted = st.form_submit_button("Create Account →", use_container_width=True)

                if submitted:
                    if not name or not email or not password:
                        st.error("Please fill in all required fields.")
                    elif password != confirm:
                        st.error("Passwords do not match.")
                    elif len(password) < 6:
                        st.error("Password must be at least 6 characters.")
                    else:
                        success, msg = register(name, email, password, role, phone)
                        if success:
                            st.success(msg + " Please login.")
                        else:
                            st.error(msg)