"""
auth.py  —  PropBook PH
Handles email/password login + Google OAuth (via Supabase) for Streamlit.

Google OAuth flow:
  1. User clicks "Continue with Google" → redirected to Supabase /auth/v1/authorize
  2. Supabase redirects to your APP_URL with ?code=... (PKCE flow) or #access_token=... (implicit)
  3. The JS bridge in auth_pages.py converts URL fragments → query params so Streamlit can read them
  4. We call verify_supabase_token() or exchange_code_for_token() to get the user profile
  5. We find-or-create the local DB user and set session state

Supabase Dashboard setup (required):
  - Authentication → Providers → Google → enable, add Client ID + Secret
  - Authentication → URL Configuration → Site URL: your app URL (e.g. https://yourapp.streamlit.app)
  - Authentication → URL Configuration → Redirect URLs: same app URL
  - For local dev add: http://localhost:8501

Environment variables (in .streamlit/secrets.toml or Streamlit Cloud secrets):
  SUPABASE_URL      = "https://xxxx.supabase.co"
  SUPABASE_ANON_KEY = "eyJ..."
  APP_URL           = "http://localhost:8501"   # or your deployed URL
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
import streamlit as st
from database import get_conn, hash_password, _p, adapt_sql, USE_POSTGRES, release_conn


# ── Supabase config ────────────────────────────────────────────────────────────
def _get_supabase_cfg():
    try:
        url = st.secrets.get("SUPABASE_URL", "") or os.environ.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_ANON_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    except Exception:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_ANON_KEY", "")
    return url.rstrip("/"), key


SUPABASE_URL, SUPABASE_KEY = _get_supabase_cfg()


def _get_app_url() -> str:
    """The URL Supabase should redirect back to after OAuth."""
    try:
        url = st.secrets.get("APP_URL", "") or os.environ.get("APP_URL", "")
    except Exception:
        url = os.environ.get("APP_URL", "")
    return url.rstrip("/") or "http://localhost:8501"


# ── Email / password auth ──────────────────────────────────────────────────────

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


# ── Google OAuth via Supabase ──────────────────────────────────────────────────

def get_google_oauth_url() -> str:
    """
    Build the Supabase Google OAuth URL.

    Uses the Authorization Code flow with PKCE when possible (more secure).
    The redirect_to must exactly match one of the URLs configured in:
      Supabase Dashboard → Authentication → URL Configuration → Redirect URLs

    For local dev:   http://localhost:8501
    For production:  https://yourapp.streamlit.app
    """
    if not SUPABASE_URL:
        return ""

    redirect_to = _get_app_url()

    params = urllib.parse.urlencode({
        "provider": "google",
        "redirect_to": redirect_to,
        # Request these scopes so we get the user's name and email
        "scopes": "email profile",
    })

    return f"{SUPABASE_URL}/auth/v1/authorize?{params}"


def exchange_code_for_session(code: str) -> dict:
    """
    Exchange a PKCE authorization code for a Supabase session.
    Returns the full session dict (contains access_token, refresh_token, user).
    Raises on failure.
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase not configured.")

    payload = json.dumps({
        "auth_code": code,
        "code_verifier": "",  # Supabase handles PKCE internally for browser flows
    }).encode()

    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/token?grant_type=pkce",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "apikey": SUPABASE_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Token exchange failed ({e.code}): {body}")


def verify_supabase_token(access_token: str) -> dict:
    """
    Fetch the Supabase user profile for a given access_token.
    Returns dict with: email, name, google_id
    """
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Supabase not configured.")

    req = urllib.request.Request(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "apikey": SUPABASE_KEY,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        raise RuntimeError(f"Token verification failed ({e.code}): {body}")

    email     = data.get("email", "")
    meta      = data.get("user_metadata", {})
    name      = meta.get("full_name") or meta.get("name") or email.split("@")[0]
    google_id = data.get("id", "")

    if not email:
        raise RuntimeError("Could not retrieve email from Google account.")

    return {"email": email, "name": name, "google_id": google_id}


def login_or_create_google_user(profile: dict):
    """
    Given a Google profile dict {email, name, google_id}, find-or-create the
    local DB user and return the user row dict.
    Raises ValueError if the account is deactivated.
    """
    email     = profile["email"]
    name      = profile["name"]

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


# ── Session helpers ────────────────────────────────────────────────────────────

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
