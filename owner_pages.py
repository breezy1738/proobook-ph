import streamlit as st
import pandas as pd
import base64, json
from database import get_conn, adapt_sql, df_query, USE_POSTGRES, release_conn
from ui_components import metric_card, status_badge, property_emoji
from ml_model import get_monthly_forecast, predict_trending_properties, predict_trending_by_month, run_backtest, get_data_quality_report, process_new_booking
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# FIX #6: safe int coercion — psycopg2 returns Decimal for NUMERIC/REAL cols
# ─────────────────────────────────────────────────────────────────────────────
def _int(val):
    """Convert any numeric-like value (int, float, Decimal, str) to Python int."""
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0



def _encode_images(uploaded_files):
    """Convert uploaded files to base64 JSON list for DB storage."""
    imgs = []
    for f in uploaded_files:
        b64 = base64.b64encode(f.read()).decode('utf-8')
        imgs.append(f"data:{f.type};base64,{b64}")
    return json.dumps(imgs) if imgs else None


def _show_property_photos(images_json, max_cols=3):
    """Display property photos from JSON base64 string."""
    if not images_json:
        return
    try:
        imgs = json.loads(images_json)
        if not imgs:
            return
        cols = st.columns(min(len(imgs), max_cols))
        for i, img_data in enumerate(imgs):
            with cols[i % max_cols]:
                st.image(img_data, use_container_width=True)
    except Exception:
        pass


def owner_dashboard(user):
    owner_id = _int(user['id'])
    conn = get_conn()
    c = conn.cursor()

    c.execute(adapt_sql("SELECT COUNT(*) as n FROM properties WHERE owner_id=%s AND status='approved'"), (owner_id,))
    row = c.fetchone(); active = _int(row['n']) if row else 0
    c.execute(adapt_sql("SELECT COUNT(*) as n FROM properties WHERE owner_id=%s AND status='pending'"), (owner_id,))
    row = c.fetchone(); pending = _int(row['n']) if row else 0
    c.execute(adapt_sql("""
        SELECT COUNT(*) as n FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE p.owner_id=%s
    """), (owner_id,))
    row = c.fetchone(); total_bookings = _int(row['n']) if row else 0
    c.execute(adapt_sql("""
        SELECT COALESCE(SUM(b.total_price), 0) as rev FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE p.owner_id=%s AND b.status='confirmed'
    """), (owner_id,))
    row = c.fetchone(); revenue = float(row['rev']) if row else 0.0
    conn.close()

    st.markdown(f'<div class="section-header">📊 Owner Dashboard — {user["name"]}</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(metric_card(active, "Active Properties", "🏠"), unsafe_allow_html=True)
    with col2: st.markdown(metric_card(pending, "Pending Approval", "⏳"), unsafe_allow_html=True)
    with col3: st.markdown(metric_card(total_bookings, "Total Bookings", "📋"), unsafe_allow_html=True)
    with col4: st.markdown(metric_card(f"₱{revenue:,.0f}", "Revenue Earned", "💰"), unsafe_allow_html=True)

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown('<div class="section-header">📈 6-Month Booking Forecast</div>', unsafe_allow_html=True)
        # FIX #1: use df_query instead of pd.read_sql_query with raw psycopg2 conn
        props = df_query(
            "SELECT id, title FROM properties WHERE owner_id=%s AND status='approved'",
            params=[owner_id]
        )
        if not props.empty:
            props['id'] = pd.to_numeric(props['id'], errors='coerce').fillna(0).astype(int)
            selected = st.selectbox("Select property", props['title'].tolist())
            match = props[props['title'] == selected]
            if match.empty:
                match = props.iloc[[0]]
            pid = _int(match['id'].iloc[0])
            forecast = get_monthly_forecast(pid)
            if forecast:
                df_f = pd.DataFrame(forecast)
                st.bar_chart(df_f.set_index('month')['predicted_bookings'])
                st.caption("🤖 ML forecast based on seasonal patterns & historical data")
        else:
            st.info("No approved properties yet.")

    with col_r:
        st.markdown('<div class="section-header">🔔 Recent Booking Requests</div>', unsafe_allow_html=True)
        # FIX #1: use df_query
        recent = df_query("""
            SELECT b.id, u.name as guest, b.check_in, b.check_out, b.total_price, b.status, p.title,
                   COALESCE(b.is_open_ended, 0) as is_open_ended
            FROM bookings b
            JOIN properties p ON b.property_id = p.id
            JOIN users u ON b.guest_id = u.id
            WHERE p.owner_id=%s AND b.status='pending'
            ORDER BY b.created_at DESC LIMIT 5
        """, params=[owner_id])

        if recent.empty:
            st.info("No pending booking requests.")
        else:
            for _, row in recent.iterrows():
                checkout_display = "Open-ended" if row.get('is_open_ended') else row['check_out']
                st.markdown(f"""
                <div class="booking-card">
                    <b>{row['guest']}</b> wants to book <b>{row['title']}</b><br>
                    <small>📅 {row['check_in']} → {checkout_display} | ₱{float(row['total_price'] or 0):,.0f}</small>
                </div>
                """, unsafe_allow_html=True)


def owner_properties(user):
    owner_id = _int(user['id'])
    st.markdown('<div class="section-header">🏠 My Properties</div>', unsafe_allow_html=True)
    # FIX #1: use df_query
    df = df_query(
        "SELECT * FROM properties WHERE owner_id=%s ORDER BY created_at DESC",
        params=[owner_id]
    )

    # Normalize is_active
    if "is_active" in df.columns:
        df["is_active"] = pd.to_numeric(df["is_active"], errors="coerce").fillna(1).astype(int)

    if df.empty:
        st.info("You haven't added any properties yet. Go to 'Add Property' to get started!")
        return

    # Cast numeric columns (psycopg2 may return them as strings or Decimal)
    for col in ['id', 'nightly_price', 'monthly_price', 'max_guests', 'bedrooms', 'bathrooms', 'latitude', 'longitude']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    for idx, (_, row) in enumerate(df.iterrows()):
        _status_icons = {
            'approved': '✅', 'pending': '⏳', 'rejected': '❌'
        }
        _sicon = _status_icons.get(row['status'], '•')
        _is_blocked = int(row.get('is_active', 1)) == 0
        _is_maintenance = int(row.get('is_maintenance', 0)) == 1
        _maint_label = " | 🔧 MAINTENANCE" if _is_maintenance else ""
        _blocked_label = " | 🚫 BLOCKED" if _is_blocked else ""
        with st.expander(f"{property_emoji(row['type'])} {row['title']} | {_sicon} {row['status'].title()}{_blocked_label}{_maint_label}", expanded=False):
            if _is_blocked and row.get('status') == 'approved':
                st.error("🚫 This property has been **blocked by the admin**. Guests cannot view or book it until the admin unblocks it. Contact support if you believe this is a mistake.")
            if row['status'] == 'approved':
                # ── Under Maintenance toggle (owner-controlled) ────────────────
                prop_id_m = _int(row['id'])
                if not _is_maintenance:
                    if st.button("🔧 Put Under Maintenance", key=f"maint_on_{prop_id_m}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET is_maintenance=1 WHERE id=%s"), (prop_id_m,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.warning("Property is now under maintenance — guests cannot book it."); st.rerun()
                else:
                    st.warning("🔧 This property is currently **under maintenance**. Guests cannot view or book it.")
                    if st.button("✅ Mark as Available", key=f"maint_off_{prop_id_m}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET is_maintenance=0 WHERE id=%s"), (prop_id_m,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.success("Property is now available for booking!"); st.rerun()

            tabs = st.tabs(["📋 Details", "🛏️ Rooms", "✏️ Edit"])

            with tabs[0]:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**City:** {row['city']}")
                    st.markdown(f"**Address:** {row['address']}, {row['barangay']}")
                    st.markdown(f"**Type:** {row['type'].title()}")
                    st.markdown(f"**Max Guests:** {row['max_guests']}")
                    st.markdown(f"**Bedrooms:** {row['bedrooms']} | **Bathrooms:** {row['bathrooms']}")
                with col2:
                    st.markdown(f"**Nightly:** ₱{row['nightly_price']:,.0f}")
                    st.markdown(f"**Monthly:** ₱{row['monthly_price']:,.0f}")
                    st.markdown(f"**Status:** {status_badge(row['status'])}", unsafe_allow_html=True)
                    if row['amenities']:
                        st.markdown("**Amenities:**")
                        ams = row['amenities'].split(',')
                        st.markdown(" ".join([f'<span class="amenity-tag">{a.strip()}</span>' for a in ams]), unsafe_allow_html=True)
                if row['description']:
                    st.markdown(f"**Description:** {row['description']}")

                # Show photos in details tab
                images_json = row.get('images') or ''
                if images_json:
                    try:
                        imgs = json.loads(images_json)
                        if imgs:
                            st.markdown("**📸 Photos:**")
                            pcols = st.columns(min(len(imgs), 3))
                            for pi, img_data in enumerate(imgs[:3]):
                                with pcols[pi % 3]:
                                    st.image(img_data, use_container_width=True)
                    except Exception:
                        pass

            with tabs[1]:
                if row['type'] == 'apartment':
                    _manage_rooms(_int(row['id']))
                else:
                    st.info("Room management is for apartment-type properties only.")

            with tabs[2]:
                _edit_property(row, idx)


def _manage_rooms(property_id):
    # FIX #1: use df_query
    rooms = df_query(
        "SELECT * FROM rooms WHERE property_id=%s",
        params=[property_id]
    )

    st.markdown("**Existing Rooms:**")
    st.caption("💡 Rooms are automatically blocked for booked dates. Use the toggle only to close a room for maintenance.")
    if rooms.empty:
        st.info("No rooms added yet.")
    else:
        from datetime import date as _date
        today = _date.today().isoformat()
        # FIX #1: use df_query
        active_bookings = df_query("""
            SELECT room_id FROM bookings
            WHERE property_id=%s AND status IN ('confirmed','pending')
            AND room_id IS NOT NULL AND check_out > %s
        """, params=[property_id, today])
        booked_room_ids = set(active_bookings['room_id'].tolist()) if not active_bookings.empty else set()

        # Ensure id column is numeric
        rooms['id'] = pd.to_numeric(rooms['id'], errors='coerce').fillna(0).astype(int)
        # FIX #4: safe boolean for is_available — cast to int first to avoid "0" string pitfall
        rooms['is_available'] = pd.to_numeric(rooms['is_available'], errors='coerce').fillna(0).astype(int)

        for _, rm in rooms.iterrows():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.markdown(f"🛏️ Room {rm['room_number']} — Floor {rm['floor']} — {rm['room_type'].title()} (Cap: {rm['capacity']})")
            with col2:
                # FIX #4: compare to integer 0, not bool() of possibly-string value
                if rm['is_available'] == 0:
                    st.markdown("🔧 Closed (maintenance)")
                elif _int(rm['id']) in booked_room_ids:
                    st.markdown("📅 Booked")
                else:
                    st.markdown("✅ Available")
            with col3:
                toggle_label = "🔓 Reopen" if rm['is_available'] == 0 else "🔧 Close"
                if st.button(toggle_label, key=f"tog_{rm['id']}"):
                    room_id = _int(rm['id'])
                    # FIX #3: use CASE WHEN instead of arithmetic to toggle — safe in both Postgres & SQLite
                    c = get_conn()
                    cur = c.cursor()
                    cur.execute(
                        adapt_sql("UPDATE rooms SET is_available = CASE WHEN is_available = 1 THEN 0 ELSE 1 END WHERE id=%s"),
                        (room_id,)
                    )
                    c.commit(); c.close(); st.rerun()

    st.markdown("---")
    st.markdown("**Add New Room:**")
    with st.form(f"add_room_{property_id}"):
        col1, col2 = st.columns(2)
        with col1:
            rnum = st.text_input("Room Number", placeholder="e.g. 101")
            floor = st.number_input("Floor", min_value=1, max_value=50, value=1)
        with col2:
            rtype = st.selectbox("Room Type", ["standard", "deluxe", "suite", "penthouse"])
            capacity = st.number_input("Capacity", min_value=1, max_value=10, value=2)
        desc = st.text_input("Description (optional)")
        if st.form_submit_button("➕ Add Room"):
            if rnum:
                c = get_conn()
                cur = c.cursor()
                cur.execute(adapt_sql("INSERT INTO rooms (property_id, room_number, floor, room_type, capacity, description) VALUES (%s,%s,%s,%s,%s,%s)"),
                          (property_id, rnum, floor, rtype, capacity, desc))
                c.commit(); c.close()
                st.success(f"Room {rnum} added!"); st.rerun()
            else:
                st.error("Room number is required.")


def _edit_property(row, idx=0):
    prop_id = _int(row['id'])
    sk = f"ep_{prop_id}_{idx}"  # unique session-state key prefix

    st.markdown("**Edit Property Details**")
    st.text_input("Title",                       value=row['title'],              key=f"{sk}_title")
    st.text_area("Description",                  value=row['description'] or "",  key=f"{sk}_desc")
    col1, col2 = st.columns(2)
    with col1:
        st.number_input("Nightly Price (₱)", value=max(0.0, float(row['nightly_price'])), min_value=0.0, key=f"{sk}_nightly")
        st.number_input("Max Guests",        value=max(1,   _int(row['max_guests'])),       min_value=1,   key=f"{sk}_guests")
        st.number_input("Bedrooms",          value=max(0,   _int(row['bedrooms'])),          min_value=0,   key=f"{sk}_beds")
    with col2:
        st.number_input("Monthly Price (₱)", value=max(0.0, float(row['monthly_price'])),  min_value=0.0, key=f"{sk}_monthly")
        st.number_input("Bathrooms",         value=max(1,   _int(row['bathrooms'])),         min_value=1,   key=f"{sk}_baths")
    st.text_input("Amenities (comma-separated)", value=row['amenities'] or "", key=f"{sk}_amenities")

    st.markdown("---")
    st.markdown("**📸 Property Photos**")

    # Load existing photos into session state for per-photo deletion
    existing_images = row.get('images') or ''
    try:
        current_imgs = json.loads(existing_images) if existing_images else []
    except Exception:
        current_imgs = []

    # Per-photo delete buttons
    if current_imgs:
        st.caption("Current photos (click ✕ to remove):")
        keep_imgs = list(current_imgs)
        pcols = st.columns(min(len(current_imgs), 3))
        for pi, img_data in enumerate(current_imgs):
            with pcols[pi % 3]:
                st.image(img_data, use_container_width=True)
                if st.button("✕ Remove", key=f"{sk}_del_photo_{pi}"):
                    keep_imgs.remove(img_data)
                    # Save immediately
                    c2 = get_conn()
                    cur2 = c2.cursor()
                    new_val = json.dumps(keep_imgs) if keep_imgs else None
                    cur2.execute(adapt_sql("UPDATE properties SET images=%s WHERE id=%s"), (new_val, prop_id))
                    c2.commit(); cur2.close(); c2.close()
                    st.success("Photo removed."); st.rerun()
        existing_images = json.dumps(keep_imgs) if keep_imgs else ''
    else:
        st.caption("No photos yet.")

    new_photos = st.file_uploader(
        "Upload new photos (JPG, PNG — max 5 total)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"{sk}_photos"
    )
    if new_photos:
        st.caption(f"{len(new_photos)} new photo(s) selected")
        preview_cols = st.columns(min(len(new_photos), 3))
        for pi, pf in enumerate(new_photos):
            with preview_cols[pi % 3]:
                st.image(pf, use_container_width=True)

    if st.button("💾 Save Changes", key=f"{sk}_save"):
        title       = st.session_state[f"{sk}_title"]
        description = st.session_state[f"{sk}_desc"]
        nightly     = st.session_state[f"{sk}_nightly"]
        monthly     = st.session_state[f"{sk}_monthly"]
        max_guests  = st.session_state[f"{sk}_guests"]
        bedrooms    = st.session_state[f"{sk}_beds"]
        bathrooms   = st.session_state[f"{sk}_baths"]
        amenities   = st.session_state[f"{sk}_amenities"]

        # Merge existing + new photos
        try:
            existing_list = json.loads(existing_images) if existing_images else []
        except Exception:
            existing_list = []
        if new_photos:
            for pf in new_photos[:5]:
                pf.seek(0)
                b64 = base64.b64encode(pf.read()).decode('utf-8')
                existing_list.append(f"data:{pf.type};base64,{b64}")
        final_images = json.dumps(existing_list) if existing_list else None

        try:
            c = get_conn()
            cur = c.cursor()
            cur.execute(adapt_sql(
                "UPDATE properties SET title=%s, description=%s, nightly_price=%s, monthly_price=%s, "
                "max_guests=%s, bedrooms=%s, bathrooms=%s, amenities=%s, images=%s WHERE id=%s"
            ), (str(title), str(description), float(nightly), float(monthly),
                _int(max_guests), _int(bedrooms), _int(bathrooms), str(amenities),
                final_images, prop_id))
            c.commit()
            cur.close()
            c.close()
            st.success("✅ Property updated successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to save: {e}")


def owner_add_property(user):
    owner_id = _int(user['id'])
    st.markdown('<div class="section-header">➕ Add New Property</div>', unsafe_allow_html=True)

    prop_type = st.selectbox("Property Type *", ["apartment", "house"],
                             format_func=lambda x: "🏢 Apartment" if x == "apartment" else "🏠 House")

    st.markdown("**📸 Property Photos**")
    st.caption("Upload up to 5 photos (JPG, PNG). Photos help guests choose your property!")
    uploaded_photos = st.file_uploader(
        "Choose photos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key="add_prop_photos"
    )
    if uploaded_photos:
        prev_cols = st.columns(min(len(uploaded_photos), 3))
        for pi, pf in enumerate(uploaded_photos[:5]):
            with prev_cols[pi % 3]:
                st.image(pf, use_container_width=True)
        st.caption(f"✅ {min(len(uploaded_photos), 5)} photo(s) ready to upload")

    with st.form("add_property_form"):
        col1, col2 = st.columns(2)
        with col1:
            title = st.text_input("Property Title *", placeholder="e.g. Cozy Studio in BGC")
            city = st.text_input("City *", placeholder="e.g. Makati")
            barangay = st.text_input("Barangay", placeholder="e.g. Poblacion")
            province = st.text_input("Province", placeholder="e.g. Metro Manila")
        with col2:
            address = st.text_input("Street Address *", placeholder="e.g. 123 Ayala Ave")
            nightly_price = st.number_input("Nightly Price (₱) *", min_value=0.0, step=100.0)
            monthly_price = st.number_input("Monthly Price (₱) *", min_value=0.0, step=500.0)
            max_guests = st.number_input("Max Guests", min_value=1, value=2)

        col3, col4 = st.columns(2)
        with col3:
            bedrooms = st.number_input("Bedrooms", min_value=0, value=1)
            bathrooms = st.number_input("Bathrooms", min_value=1, value=1)
        with col4:
            amenities = st.multiselect("Amenities", [
                "WiFi", "AC", "Parking", "Pool", "Gym", "Kitchen", "Balcony",
                "Security", "CCTV", "Laundry", "Garden", "Pet-Friendly", "Beach Access"
            ])

        description = st.text_area("Description", placeholder="Describe your property...")

        st.markdown("---")
        num_rooms = 0
        if prop_type == 'apartment':
            st.markdown("**Initial Rooms** (apartments only)")
            st.caption("🏢 Guests will select a specific room when booking.")
            num_rooms = st.number_input("Number of Rooms to Add Initially", min_value=0, max_value=20, value=0)
        else:
            st.info("🏠 House properties are booked as a whole — no room setup needed.")

        submitted = st.form_submit_button("🏠 List Property", use_container_width=True)

        if submitted:
            if not title or not city or not address or nightly_price <= 0 or monthly_price <= 0:
                st.error("Please fill in all required fields with valid prices.")
            else:
                # Check for duplicate title under same owner
                _chk = get_conn()
                _cur = _chk.cursor()
                _cur.execute(adapt_sql(
                    "SELECT id FROM properties WHERE owner_id=%s AND LOWER(title)=LOWER(%s)"
                ), (owner_id, title.strip()))
                _dup = _cur.fetchone()
                if USE_POSTGRES:
                    release_conn(_chk)
                else:
                    _chk.close()

                if _dup:
                    st.error(f'❌ You already have a property named "{title.strip()}". Please use a different title.')
                else:
                    conn = get_conn()
                    cur = conn.cursor()

                    # Encode uploaded photos
                    photos_json = None
                    if uploaded_photos:
                        imgs = []
                        for pf in uploaded_photos[:5]:
                            pf.seek(0)
                            b64 = base64.b64encode(pf.read()).decode('utf-8')
                            imgs.append(f"data:{pf.type};base64,{b64}")
                        photos_json = json.dumps(imgs) if imgs else None

                    if USE_POSTGRES:
                        cur.execute(adapt_sql("""
                            INSERT INTO properties (owner_id, title, description, type, address, city, barangay, province,
                            nightly_price, monthly_price, max_guests, bedrooms, bathrooms, amenities, images, status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending') RETURNING id
                        """), (owner_id, title, description, prop_type, address, city, barangay, province,
                              nightly_price, monthly_price, max_guests, bedrooms, bathrooms, ",".join(amenities), photos_json))
                        conn.commit()
                        returned = cur.fetchone()
                        prop_id = _int(returned['id']) if returned else None
                    else:
                        cur.execute(adapt_sql("""
                            INSERT INTO properties (owner_id, title, description, type, address, city, barangay, province,
                            nightly_price, monthly_price, max_guests, bedrooms, bathrooms, amenities, images, status)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
                        """), (owner_id, title, description, prop_type, address, city, barangay, province,
                              nightly_price, monthly_price, max_guests, bedrooms, bathrooms, ",".join(amenities), photos_json))
                        conn.commit()
                        prop_id = cur.lastrowid

                    if prop_id is None:
                        st.error("Failed to retrieve new property ID. Please try again.")
                        conn.close()
                    else:
                        # Auto-add rooms for apartments
                        if prop_type == 'apartment' and num_rooms > 0:
                            for i in range(1, num_rooms + 1):
                                cur.execute(adapt_sql("""
                                    INSERT INTO rooms (property_id, room_number, floor, room_type, capacity)
                                    VALUES (%s,%s,%s,%s,%s)
                                """), (prop_id, f"R{i:02d}", 1, "standard", 2))

                        conn.commit()
                        conn.close()
                        st.success("✅ Property submitted for admin approval!")
                        if prop_type == 'apartment' and num_rooms > 0:
                            st.info(f"🛏️ {num_rooms} rooms added. You can manage them from 'My Properties'.")


def owner_bookings(user):
    owner_id = _int(user['id'])
    st.markdown('<div class="section-header">📋 Booking Requests</div>', unsafe_allow_html=True)

    # FIX #1: use df_query
    df = df_query("""
        SELECT b.id, u.name as guest_name, u.phone as guest_phone, u.email as guest_email,
               p.title as property, p.is_active as prop_is_active,
               r.room_number, b.check_in, b.check_out,
               b.booking_type, b.total_price, b.down_payment, b.balance_due,
               b.status, b.payment_method, b.payment_status, b.special_requests, b.created_at,
               COALESCE(b.is_open_ended, 0) as is_open_ended
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.guest_id = u.id
        LEFT JOIN rooms r ON b.room_id = r.id
        WHERE p.owner_id=%s
        ORDER BY b.created_at DESC
    """, params=[owner_id])

    if df.empty:
        st.info("No bookings for your properties yet.")
        return

    # FIX #6: Normalize numeric columns — psycopg2 may return Decimal types
    for col in ['id', 'total_price', 'down_payment', 'balance_due']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    tab_all, tab_pending, tab_confirmed = st.tabs(["All", "Pending", "Confirmed"])

    def render_bookings(bdf, tab_key="all"):
        for _, row in bdf.iterrows():
            status_label = {
                'confirmed': '✅ Confirmed',
                'pending':   '⏳ Pending',
                'cancelled': '❌ Cancelled',
            }.get(row['status'], row['status'].title())
            with st.expander(f"📅 {row['guest_name']} → {row['property']} | {status_label}", expanded=False):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**Guest:** {row['guest_name']}")
                    st.markdown(f"**Contact:** {row['guest_email']} | {row['guest_phone']}")
                    st.markdown(f"**Property:** {row['property']}")
                    if row['room_number']:
                        st.markdown(f"**Room:** {row['room_number']}")
                    checkout_label = "Open-ended (monthly boarder)" if row.get('is_open_ended') else row['check_out']
                    st.markdown(f"**Check-in:** {row['check_in']} | **Check-out:** {checkout_label}")
                    st.markdown(f"**Type:** {row['booking_type'].title()}")
                    st.markdown(f"**Total:** ₱{float(row['total_price'] or 0):,.0f}")

                    # Down payment breakdown
                    down = row.get('down_payment') or 0
                    balance = row.get('balance_due') or 0
                    if down > 0:
                        pay_icon = "🌐" if row['payment_method'] == 'online' else "🏦"
                        status_map = {
                            'down_paid': ('✅ Down paid', '#dcfce7', '#16a34a'),
                            'walk_in_pending': ('⏳ Walk-in pending', '#fef3c7', '#92400e'),
                            'paid': ('✅ Fully paid', '#dcfce7', '#16a34a'),
                            'unpaid': ('❌ Unpaid', '#fee2e2', '#991b1b'),
                        }
                        lbl, bg, fg = status_map.get(row['payment_status'], ('—', '#f3f4f6', '#374151'))
                        st.markdown(f"""
                        <div style="background:#f0f4ff;border-radius:10px;padding:0.75rem 1rem;margin-top:0.4rem;font-size:0.88rem;">
                            <b style="color:#1a3c5e;">💳 Down Payment (30%)</b><br>
                            <span style="color:#6b7280;">Down:</span>
                            <b style="color:#2563a8;"> ₱{float(down):,.0f}</b>
                            &nbsp;<span style="background:{bg};color:{fg};padding:0.1rem 0.5rem;border-radius:999px;font-size:0.75rem;font-weight:700;">
                                {pay_icon} {lbl}
                            </span><br>
                            <span style="color:#6b7280;">Balance at check-in:</span>
                            <b> ₱{float(balance):,.0f}</b>
                        </div>
                        """, unsafe_allow_html=True)

                    if row['special_requests']:
                        st.markdown(f"**Notes:** {row['special_requests']}")

                with col2:
                    _prop_blocked = int(row.get('prop_is_active', 1)) == 0
                    if row['status'] == 'pending':
                        # FIX #6: _int() ensures booking_id is Python int, not Decimal
                        booking_id = _int(row['id'])
                        if _prop_blocked:
                            st.markdown(
                                "<div style='background:#fee2e2;border:1.5px solid #dc2626;border-radius:8px;"
                                "padding:0.5rem 0.75rem;font-size:0.82rem;color:#991b1b;font-weight:600;'>"
                                "🚫 Blocked by admin — cannot accept bookings</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            if st.button("✅ Accept", key=f"acc_{tab_key}_{booking_id}"):
                                c = get_conn()
                                cur = c.cursor()
                                cur.execute(adapt_sql("UPDATE bookings SET status='confirmed' WHERE id=%s"), (booking_id,))
                                c.commit(); c.close()
                                process_new_booking(booking_id)
                                st.success("Booking confirmed! ML trends updated."); st.rerun()
                        if st.button("❌ Reject", key=f"rj_{tab_key}_{booking_id}"):
                            c = get_conn()
                            cur = c.cursor()
                            cur.execute(adapt_sql("UPDATE bookings SET status='cancelled' WHERE id=%s"), (booking_id,))
                            c.commit(); c.close(); st.warning("Booking rejected."); st.rerun()

                    # Mark walk-in down payment as received
                    if row['payment_status'] == 'walk_in_pending':
                        if st.button("💰 Mark Down Payment Received", key=f"dpaid_{tab_key}_{_int(row['id'])}"):
                            c = get_conn()
                            cur = c.cursor()
                            cur.execute(adapt_sql("UPDATE bookings SET payment_status='down_paid' WHERE id=%s"), (_int(row['id']),))
                            c.commit(); c.close(); st.success("Down payment marked as received!"); st.rerun()

                    # Mark full balance paid at check-in
                    if row['status'] == 'confirmed' and row['payment_status'] == 'down_paid':
                        if st.button("💵 Mark Balance Paid", key=f"balpaid_{tab_key}_{_int(row['id'])}"):
                            c = get_conn()
                            cur = c.cursor()
                            cur.execute(adapt_sql("UPDATE bookings SET payment_status='paid' WHERE id=%s"), (_int(row['id']),))
                            c.commit(); c.close(); st.success("Marked as fully paid!"); st.rerun()

    with tab_all: render_bookings(df, 'all')
    with tab_pending: render_bookings(df[df['status'] == 'pending'], 'pending')
    with tab_confirmed: render_bookings(df[df['status'] == 'confirmed'], 'confirmed')


def owner_trends(user):
    owner_id = _int(user['id'])
    st.markdown('<div class="section-header">📈 Property Trends & ML Insights</div>', unsafe_allow_html=True)
    st.caption("AI-powered trend analysis based on historical booking data and Philippine seasonal patterns.")

    # FIX #7: Only rebuild if not already done this session — avoids hammering Supabase on every page visit
    if not st.session_state.get('_ml_rebuilt'):
        from ml_model import rebuild_booking_history_from_real_data
        rebuild_booking_history_from_real_data()
        st.session_state['_ml_rebuilt'] = True

    # FIX #1: use df_query
    props = df_query(
        "SELECT id, title, city, type FROM properties WHERE owner_id=%s AND status='approved'",
        params=[owner_id]
    )
    props['id'] = pd.to_numeric(props['id'], errors='coerce').fillna(0).astype(int)

    if props.empty:
        st.info("You have no approved properties yet. Once approved, trend data will appear here.")
        return

    # ── Data quality + accuracy panel ──────────────────────────────────────────
    dq = get_data_quality_report()
    bt = run_backtest()

    col_dq1, col_dq2, col_dq3, col_dq4 = st.columns(4)
    with col_dq1:
        label = "Real bookings" if not dq['is_synthetic'] else "Synthetic only"
        st.markdown(metric_card(dq['real_confirmed_bookings'], label, "📦"), unsafe_allow_html=True)
    with col_dq2:
        st.markdown(metric_card(dq['history_rows'], "History rows", "📂"), unsafe_allow_html=True)
    with col_dq3:
        if bt and bt.get('accuracy_pct') is not None:
            st.markdown(metric_card(f"{bt['accuracy_pct']}%", "Model accuracy", "🎯"), unsafe_allow_html=True)
        else:
            st.markdown(metric_card("N/A", "Model accuracy", "🎯"), unsafe_allow_html=True)
    with col_dq4:
        if bt:
            st.markdown(metric_card(f"{bt['mape']}%", "Avg forecast error (MAPE)", "📉"), unsafe_allow_html=True)
        else:
            st.markdown(metric_card("N/A", "Avg forecast error", "📉"), unsafe_allow_html=True)

    if dq['is_synthetic']:
        st.warning(
            "⚠️ **Running on synthetic data.** The model is trained on demo seed data, not real bookings. "
            "Accuracy improves automatically as guests make confirmed bookings — "
            "the model retrains itself every app restart."
        )
    else:
        st.success(
            f"✅ **Trained on real data** — {dq['real_confirmed_bookings']} confirmed bookings "
            f"from {dq['earliest_booking']} to {dq['latest_booking']}. "
            f"Model retrains automatically on each app restart."
        )

    if bt:
        with st.expander("🔬 Backtest details — predicted vs actual (last 3 months hold-out)"):
            st.caption(
                f"MAE: {bt['mae']} bookings | RMSE: {bt['rmse']} | MAPE: {bt['mape']}% | "
                f"Samples: {bt['n_samples']}"
            )
            bt_df = pd.DataFrame(bt['results'])
            if not bt_df.empty:
                bt_df['month_label'] = bt_df.apply(
                    lambda r: datetime(_int(r['year']), _int(r['month']), 1).strftime("%b %Y"), axis=1
                )
                st.dataframe(
                    bt_df[['property','month_label','actual','predicted','error']].rename(columns={
                        'property': 'Property', 'month_label': 'Month',
                        'actual': 'Actual', 'predicted': 'Predicted', 'error': 'Error'
                    }),
                    use_container_width=True, hide_index=True
                )

    st.markdown("---")
    # ── Month-aware trend comparison for owner's properties ───────────────────
    MONTH_NAMES = ['January','February','March','April','May','June',
                   'July','August','September','October','November','December']
    current_month = datetime.now().month

    st.markdown("### 🔥 Your Properties — Month-by-Month Trend Analysis")
    selected_month_name = st.selectbox(
        "📅 Select a month to see which of your properties is trending",
        MONTH_NAMES,
        index=current_month - 1,
        key="owner_month_picker"
    )
    selected_month_num = MONTH_NAMES.index(selected_month_name) + 1
    st.caption(f"🤖 ML scores learned from 3 years of historical data — showing predictions for **{selected_month_name}**")

    all_scores = predict_trending_by_month(selected_month_num)
    owner_prop_ids = set(int(float(i)) for i in props['id'].tolist())
    my_trends = [t for t in all_scores if _int(t['property_id']) in owner_prop_ids]

    if not my_trends:
        st.info("No data available for your properties yet.")
    else:
        df_my = pd.DataFrame(my_trends)
        df_my['short_title'] = df_my['title'].apply(
            lambda t: t[:22] + '…' if len(t) > 22 else t
        )

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**📊 Trend Score by Property**")
            st.bar_chart(
                df_my.set_index('short_title')['trend_score'],
                height=260,
                color="#1a3c5e"
            )
            st.caption("Higher = AI expects more demand this month")
        with col_c2:
            st.markdown("**🏠 Predicted Bookings**")
            st.bar_chart(
                df_my.set_index('short_title')['predicted_bookings'],
                height=260,
                color="#e8a020"
            )
            st.caption("Based on historical same-month avg × seasonal weight × growth trend")

        # Ranked cards
        st.markdown(f"**🏆 Ranking for {selected_month_name}**")
        cols = st.columns(min(len(my_trends), 3))
        for i, t in enumerate(my_trends):
            medal = ["🥇","🥈","🥉"][i] if i < 3 else f"#{i+1}"
            no_data = t.get('years_of_data', 0) == 0 and t['trend_score'] == 0.0
            bg = "linear-gradient(135deg,#6b7280,#9ca3af)" if no_data else "linear-gradient(135deg,#1a3c5e,#2563a8)"
            icon = "🆕" if no_data else "🔥"
            with cols[i % len(cols)]:
                if no_data:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;
                                padding:1.25rem;color:white;margin-bottom:1rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2.2rem;font-weight:700;font-family:'Playfair Display',serif">—</div>
                        <div style="font-weight:600;font-size:0.95rem;margin:0.2rem 0">{t['title']}</div>
                        <div style="font-size:0.8rem;opacity:0.85">
                            📍 {t['city']}<br>
                            📭 No bookings yet — score will appear after first confirmed booking
                        </div>
                        <div style="position:absolute;top:1rem;right:1rem;font-size:1.4rem">{icon}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;
                                padding:1.25rem;color:white;margin-bottom:1rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2.2rem;font-weight:700;font-family:'Playfair Display',serif">
                            {t['trend_score']}
                        </div>
                        <div style="font-weight:600;font-size:0.95rem;margin:0.2rem 0">{t['title']}</div>
                        <div style="font-size:0.8rem;opacity:0.85">
                            📍 {t['city']}<br>
                            🏠 Predicted: <b>{t['predicted_bookings']}</b> bookings<br>
                            📅 Historical avg ({selected_month_name}): <b>{t['historical_same_month_avg']}</b><br>
                            📈 Avg Occupancy: <b>{t['avg_occupancy']}%</b><br>
                            🌡️ Seasonal multiplier: <b>{t['seasonal_mult']}</b>
                        </div>
                        <div style="position:absolute;top:1rem;right:1rem;font-size:1.4rem">{icon}</div>
                    </div>
                    """, unsafe_allow_html=True)

        # How scores change across all 12 months — sparkline table
        st.markdown("---")
        st.markdown("### 📆 Full Year Trend Score Heatmap — All Your Properties")
        st.caption("See how each property's ML trend score shifts month by month, learned from past booking patterns")

        year_rows = {}
        for m_num, m_name in enumerate(MONTH_NAMES, start=1):
            month_scores = predict_trending_by_month(m_num)
            for t in month_scores:
                if _int(t['property_id']) in owner_prop_ids:
                    if t['title'] not in year_rows:
                        year_rows[t['title']] = {}
                    year_rows[t['title']][m_name[:3]] = t['trend_score']

        if year_rows:
            df_heat = pd.DataFrame(year_rows).T
            df_heat = df_heat[[m[:3] for m in MONTH_NAMES]]

            def score_label(v):
                try:
                    v = float(v)
                    if v >= 70:   return f"🔴 {v:.0f}"
                    elif v >= 40: return f"🟡 {v:.0f}"
                    else:         return f"🔵 {v:.0f}"
                except:
                    return str(v)

            df_display = df_heat.map(score_label)
            st.dataframe(df_display, use_container_width=True)
            st.caption("🔴 ≥70 hot  🟡 40–69 warm  🔵 <40 cool — higher score = more demand expected that month")

    st.markdown("---")

    # ── Per-property deep dive ────────────────────────────────────────────────
    st.markdown("### 📊 Deep Dive — Historical + 6-Month Forecast")
    selected_title = st.selectbox("Select a property to analyze:", props['title'].tolist())
    _match = props[props['title'] == selected_title]
    selected_row = _match.iloc[0] if not _match.empty else props.iloc[0]
    pid = _int(pd.to_numeric(selected_row['id'], errors='coerce') or 0)

    # FIX #1: use df_query
    hist = df_query("""
        SELECT month, year, total_bookings, total_revenue, avg_occupancy
        FROM booking_history
        WHERE property_id=%s
        ORDER BY year, month
    """, params=[pid])

    if hist.empty:
        st.info("No historical data available for this property yet.")
    else:
        # Coerce all numeric columns from Decimal/string
        for col in ['month', 'year', 'total_bookings', 'total_revenue', 'avg_occupancy']:
            hist[col] = pd.to_numeric(hist[col], errors='coerce').fillna(0)
        hist['year']  = hist['year'].astype(int)
        hist['month'] = hist['month'].astype(int)

        hist['period'] = hist.apply(
            lambda r: datetime(_int(r['year']), _int(r['month']), 1).strftime("%b %Y"), axis=1
        )
        hist['avg_occupancy_pct'] = (hist['avg_occupancy'] * 100).round(1)

        tab1, tab2, tab3 = st.tabs(["📅 Historical Bookings", "💰 Revenue History", "📈 6-Month Forecast"])

        with tab1:
            st.markdown(f"**Monthly Bookings — {selected_title}**")
            st.caption("Past booking volume by month across all recorded years")
            hist_recent = hist.tail(24)
            st.bar_chart(hist_recent.set_index('period')['total_bookings'], height=300)

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Avg Bookings/Month", f"{hist['total_bookings'].mean():.1f}")
            with col_b:
                peak = hist.loc[hist['total_bookings'].idxmax()]
                st.metric("Peak Month", f"{peak['period']}", f"{int(peak['total_bookings'])} bookings")
            with col_c:
                st.metric("Avg Occupancy", f"{hist['avg_occupancy_pct'].mean():.1f}%")

        with tab2:
            st.markdown(f"**Monthly Revenue — {selected_title}**")
            st.caption("Total revenue earned per month based on historical data")
            hist_recent = hist.tail(24)
            st.line_chart(hist_recent.set_index('period')['total_revenue'], height=300)

            total_rev = hist['total_revenue'].sum()
            avg_rev = hist['total_revenue'].mean()
            best_rev = hist.loc[hist['total_revenue'].idxmax()]
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                st.metric("Total Revenue (All Time)", f"₱{total_rev:,.0f}")
            with col_b:
                st.metric("Avg Revenue/Month", f"₱{avg_rev:,.0f}")
            with col_c:
                st.metric("Best Month", best_rev['period'], f"₱{best_rev['total_revenue']:,.0f}")

        with tab3:
            st.markdown(f"**6-Month Forecast — {selected_title}**")
            st.caption("🤖 ML prediction using seasonal patterns, historical trends & booking momentum")
            forecast = get_monthly_forecast(pid)
            if forecast:
                df_f = pd.DataFrame(forecast)

                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.markdown("**Predicted Bookings**")
                    st.bar_chart(df_f.set_index('month')['predicted_bookings'], height=250)
                with col_chart2:
                    st.markdown("**Predicted Occupancy Rate (%)**")
                    st.line_chart(df_f.set_index('month')['occupancy_rate'], height=250)

                st.markdown("**Forecast Summary**")
                st.dataframe(
                    df_f.rename(columns={
                        'month': 'Month',
                        'predicted_bookings': 'Est. Bookings',
                        'predicted_revenue': 'Est. Revenue (₱)',
                        'occupancy_rate': 'Occupancy (%)'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

                peak_f = df_f.loc[df_f['predicted_bookings'].idxmax()]
                st.success(f"🌟 Projected peak: **{peak_f['month']}** with ~{peak_f['predicted_bookings']} bookings and ₱{peak_f['predicted_revenue']:,.0f} revenue.")

    # ── Seasonal pattern reminder ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🗓️ Philippine Seasonal Booking Weights")
    st.caption("These seasonal weights power the ML model — higher = more demand expected")
    seasonal = {
        'Jan': 0.85, 'Feb': 0.70, 'Mar': 0.75, 'Apr': 0.90,
        'May': 0.95, 'Jun': 1.00, 'Jul': 1.00, 'Aug': 0.85,
        'Sep': 0.70, 'Oct': 0.75, 'Nov': 0.85, 'Dec': 1.00
    }
    df_season = pd.DataFrame({'Month': list(seasonal.keys()), 'Demand Weight': list(seasonal.values())})
    current_month_abbr = datetime.now().strftime("%b")
    st.bar_chart(df_season.set_index('Month')['Demand Weight'], height=200)
    st.caption(f"📍 Current month: **{current_month_abbr}** — weight: **{seasonal.get(current_month_abbr, '—')}**")
