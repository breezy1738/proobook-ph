"""
main.py  —  PropBook PH  |  Streamlit entry point
Run with:  streamlit run main.py
"""

import streamlit as st
from database import init_db
from ui_components import inject_css, sidebar_nav
from auth_pages import show_login_page

st.set_page_config(
    page_title="PropBook PH",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialise DB on first run
init_db()

# ── Route: not logged in ───────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    show_login_page()
    st.stop()

# ── Route: logged in ──────────────────────────────────────────────────────────
inject_css()
user   = st.session_state["user"]
role   = user["role"]
choice = sidebar_nav(user)

if role == "admin":
    from admin_pages import (
        admin_dashboard, admin_properties, admin_users,
        admin_bookings, admin_trends,
    )
    pages = {
        "Dashboard":        admin_dashboard,
        "Properties":       admin_properties,
        "Users":            admin_users,
        "Bookings":         admin_bookings,
        "Property Trends":  admin_trends,
    }

elif role == "owner":
    from owner_pages import (
        owner_dashboard, owner_properties, owner_bookings,
        owner_add_property, owner_trends,
    )
    pages = {
        "Dashboard":        owner_dashboard,
        "My Properties":    owner_properties,
        "My Bookings":      owner_bookings,
        "Add Property":     owner_add_property,
        "Property Trends":  owner_trends,
    }

else:  # guest
    from guest_pages import browse_properties, guest_bookings, guest_profile
    pages = {
        "Browse Properties": lambda: browse_properties(user),
        "My Bookings":       guest_bookings,
        "My Profile":        guest_profile,
    }

fn = pages.get(choice)
if fn:
    fn()
else:
    st.error(f"Page '{choice}' not found.")