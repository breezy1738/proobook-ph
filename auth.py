"""
auth.py  —  PropBook PH
Handles email/password login + Google OAuth (via Supabase) for Streamlit.
"""

import os
import json
import urllib.request
import urllib.error
import streamlit as st
from database import get_conn, hash_password, _p, adapt_sql, USE_POSTGRES, release_conn

# ── Supabase config (read from environment / Streamlit secrets) ───────────────
def _get_supabase_cfg():
    """
    Read SUPABASE_URL and SUPABASE_ANON_KEY.
    Works with:
      • Streamlit Cloud  →  st.secrets["SUPABASE_URL"]
      • Local dev        →  .streamlit/con.env  (loaded via python-dotenv or
                            the SUPABASE_URL env var set in your shell / con.env)
    """
    try:
        url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
    return url.rstrip("/"), key


SUPABASE_URL, SUPABASE_KEY = _get_supabase_cfg()


# ── Email / password auth ─────────────────────────────────────────────────────

def login(email, password):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            adapt_sql("SELECT * FROM users WHERE email=%s AND password=%s AND is_active=1"),
            (email, hash_password(password))
        )
        user = c.fetchone()
        return dict(user) if user else None
    finally:
        release_conn(conn)


def register(name, email, password, role, phone=""):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            adapt_sql("INSERT INTO users (name, email, password, role, phone) VALUES (%s,%s,%s,%s,%s)"),
            (name, email, hash_password(password), role, phone)
        )
        conn.commit()
        return True, "Account created successfully!"
    except Exception as e:
        conn.rollback()
        err = str(e).lower()
        if "unique" in err or "duplicate" in err:
            return False, "Email already registered."
        return False, str(e)
    finally:
        release_conn(conn)


# ── Google OAuth (Supabase) ───────────────────────────────────────────────────

def get_google_oauth_url() -> str:
    """
    Build the Supabase Google OAuth URL.
    Supabase will redirect back to the Streamlit app URL after the user
    approves, appending  #access_token=...  to the fragment.

    Because Streamlit can't read URL fragments server-side, we handle
    the token client-side via st.query_params (Supabase also supports
    ?access_token= query-param mode — see note below).
    """
    if not SUPABASE_URL:
        return ""

    # The redirect_to must match exactly what is set in Supabase Dashboard →
    # Authentication → URL Configuration → Redirect URLs.
    # For local dev use: http://localhost:8501
    # For Streamlit Cloud use your app URL, e.g. https://yourapp.streamlit.app
    redirect_to = os.environ.get("APP_URL", "http://localhost:8501")

    return (
        f"{SUPABASE_URL}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={redirect_to}"
    )


def verify_supabase_token(access_token: str):
    """
    Exchange a Supabase access_token for the user's profile.
    Returns a dict with keys: email, name, google_id  — or raises on failure.
    """
    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": SUPABASE_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    email     = data.get("email", "")
    meta      = data.get("user_metadata", {})
    name      = meta.get("full_name") or meta.get("name") or email.split("@")[0]
    google_id = data.get("id", "")
    return {"email": email, "name": name, "google_id": google_id}


def login_or_create_google_user(profile: dict):
    """
    Given a Google profile dict, find-or-create the local DB user and
    return the user row dict. Raises ValueError if account is deactivated.
    """
    email     = profile["email"]
    name      = profile["name"]
    google_id = profile["google_id"]

    conn = get_conn()
    c    = conn.cursor()
    try:
        c.execute(adapt_sql("SELECT * FROM users WHERE email=%s"), (email,))
        user = c.fetchone()

        if not user:
            # Auto-register as guest
            c.execute(
                adapt_sql(
                    "INSERT INTO users (name, email, password, role, phone) "
                    "VALUES (%s, %s, %s, %s, %s)"
                ),
                (name, email, "", "guest", ""),
            )
            conn.commit()
            c.execute(adapt_sql("SELECT * FROM users WHERE email=%s"), (email,))
            user = c.fetchone()

        user = dict(user)

        if not user.get("is_active", 1):
            raise ValueError("Your account has been deactivated.")

        return user

    finally:
        release_conn(conn)


# ── Session helpers ───────────────────────────────────────────────────────────

def get_current_user():
    return st.session_state.get("user", None)


def require_login():
    if not get_current_user():
        st.error("Please log in to continue.")
        st.stop()
    return get_current_user()


def require_role(role):
    user = require_login()
    if isinstance(role, list):
        if user["role"] not in role:
            st.error("Access denied.")
            st.stop()
    else:
        if user["role"] != role:
            st.error("Access denied.")
            st.stop()
    return user