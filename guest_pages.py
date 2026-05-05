import streamlit as st
import pandas as pd
import json, base64
from database import get_conn, adapt_sql, USE_POSTGRES, release_conn, df_query
from ui_components import metric_card, status_badge, property_emoji
from ml_model import predict_trending_properties, process_new_booking
from datetime import datetime, timedelta, date


def browse_properties(user=None):
    st.markdown('<div class="section-header">🔍 Browse Properties</div>', unsafe_allow_html=True)

    trending = predict_trending_properties(top_n=3)
    if trending:
        st.markdown(f"""
        <div class="hero-banner">
            <h1>🏘️ Find Your Perfect Stay</h1>
            <p style="opacity:0.85;font-size:1.1rem">Homes & Apartments across the Philippines</p>
            <p style="opacity:0.65;font-size:0.85rem">🤖 ML-powered trends updated for {datetime.now().strftime('%B %Y')}</p>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🔎 Search & Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            city_filter = st.text_input("City", placeholder="e.g. Makati")
        with col2:
            type_filter = st.selectbox("Type", ["All", "Apartment", "House"])
        with col3:
            max_price = st.number_input("Max Nightly Price (₱)", min_value=0, value=10000, step=500)
        with col4:
            sort_by = st.selectbox("Sort By", ["Newest", "Price: Low to High", "Price: High to Low"])

    # Build query using %s placeholders throughout — df_query handles dialect conversion
    query = """
        SELECT p.id, p.title, p.description, p.type, p.address, p.city, p.barangay,
               p.nightly_price, p.monthly_price, p.max_guests, p.bedrooms, p.bathrooms,
               p.amenities, p.images, p.status,
               u.name as owner_name, u.phone as owner_phone,
               (SELECT COUNT(*) FROM rooms r WHERE r.property_id = p.id AND r.is_available=1
                AND r.id NOT IN (
                    SELECT room_id FROM bookings
                    WHERE property_id = p.id
                    AND room_id IS NOT NULL
                    AND check_out > CURRENT_DATE
                    AND (
                        status = 'confirmed'
                        OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                    )
                )) as available_rooms,
               (SELECT MIN(check_out) FROM bookings
                WHERE property_id = p.id
                AND room_id IS NOT NULL
                AND check_out > CURRENT_DATE
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )) as next_available_date,
               (SELECT COUNT(*) FROM bookings
                WHERE property_id = p.id
                AND room_id IS NULL
                AND check_out > CURRENT_DATE
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )) as house_active_bookings,
               (SELECT MIN(check_out) FROM bookings
                WHERE property_id = p.id
                AND room_id IS NULL
                AND check_out > CURRENT_DATE
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )) as house_available_date
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        WHERE p.status='approved' AND p.is_active=1
    """
    params = []
    if city_filter:
        query += " AND (p.city ILIKE %s OR p.barangay ILIKE %s)" if USE_POSTGRES else " AND (p.city LIKE %s OR p.barangay LIKE %s)"
        params.extend([f"%{city_filter}%", f"%{city_filter}%"])
    if type_filter != "All":
        query += " AND p.type=%s"
        params.append(type_filter.lower())
    if max_price > 0:
        query += " AND p.nightly_price <= %s"
        params.append(max_price)

    if sort_by == "Price: Low to High":
        query += " ORDER BY p.nightly_price ASC"
    elif sort_by == "Price: High to Low":
        query += " ORDER BY p.nightly_price DESC"
    else:
        query += " ORDER BY p.id DESC"

    df = df_query(query, params=params if params else None)

    if trending and not city_filter:
        st.markdown('<div class="section-header">🔥 Trending This Month (AI Picks)</div>', unsafe_allow_html=True)
        tcols = st.columns(min(len(trending), 3))
        for i, t in enumerate(trending[:3]):
            with tcols[i]:
                st.markdown(f"""
                <div class="trend-card">
                    <div style="font-size:0.75rem;opacity:0.7">TREND SCORE</div>
                    <div class="trend-score">{t['trend_score']}</div>
                    <div style="font-weight:600">{t['title']}</div>
                    <div style="font-size:0.82rem;opacity:0.85">📍 {t['city']} | {t['type'].title()}</div>
                    <div style="font-size:0.82rem;margin-top:0.3rem">₱{t['nightly_price']:,.0f}/night</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("---")

    st.markdown(f'<div class="section-header">🏘️ Available Properties ({len(df)} found)</div>', unsafe_allow_html=True)

    if df.empty:
        st.info("No properties found matching your filters.")
        return

    # Show booking form at top if active
    if st.session_state.get('show_booking_modal') and st.session_state.get('booking_property'):
        _booking_form(st.session_state['booking_property'], user)
        st.markdown("---")
        return

    # Property grid
    for i in range(0, len(df), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i + j < len(df):
                row = df.iloc[i + j]
                with col:
                    _property_card(row, user)


def _property_card(row, user):
    emoji = property_emoji(row['type'])

    # Build photo HTML — replaces the emoji icon inside .property-img
    images_json = row.get('images') or ''
    photo_html = ''
    try:
        if images_json:
            imgs = json.loads(images_json)
            if imgs:
                # Show first image filling the card header slot
                photo_html = (
                    f"<img src='{imgs[0]}' style='width:100%;height:190px;"
                    f"object-fit:cover;display:block;' alt='property photo'>"
                )
    except Exception:
        pass


    is_apartment = row['type'] == 'apartment'
    available_rooms = int(row['available_rooms']) if is_apartment else None
    fully_booked = is_apartment and available_rooms == 0
    next_avail = row.get('next_available_date') if is_apartment else None

    is_house = row['type'] == 'house'
    house_occupied = is_house and int(row.get('house_active_bookings') or 0) > 0
    house_available_date = row.get('house_available_date') if is_house else None

    if is_apartment:
        if fully_booked and next_avail:
            rooms_line = (
                "<br><span style='color:#dc2626;font-weight:700;'>🚫 No rooms available</span>"
                "<br><span style='color:#d97706;font-size:0.8rem;'>📅 Next available: " + str(next_avail) + "</span>"
            )
        elif fully_booked:
            rooms_line = "<br><span style='color:#dc2626;font-weight:700;'>🚫 No rooms available</span>"
        else:
            rooms_line = "<br><span style='color:#16a34a;font-weight:600;'>🛏️ " + str(available_rooms) + " room" + ("s" if available_rooms != 1 else "") + " available</span>"
    else:
        if house_occupied and house_available_date:
            rooms_line = (
                "<br><span style='color:#dc2626;font-weight:700;'>🚫 Currently occupied</span>"
                "<br><span style='color:#d97706;font-size:0.8rem;'>📅 Available from: " + str(house_available_date) + "</span>"
            )
        elif house_occupied:
            rooms_line = "<br><span style='color:#dc2626;font-weight:700;'>🚫 Currently occupied</span>"
        else:
            rooms_line = "<br><span style='color:#16a34a;font-weight:600;'>✅ Available</span>"

    _card_html = (
        "<div class='property-card' style='" + ("opacity:0.75;" if fully_booked else "") + "'>"
        "<div class='property-img' style='padding:0;overflow:hidden;'>" + (photo_html if photo_html else emoji) + "</div>"
        + ("<div style='background:#dc2626;color:white;text-align:center;font-size:0.78rem;font-weight:700;padding:0.3rem;letter-spacing:0.05em;'>🚫 ALL ROOMS CURRENTLY BOOKED</div>" if fully_booked else "")
        + ("<div style='background:#d97706;color:white;text-align:center;font-size:0.78rem;font-weight:700;padding:0.3rem;letter-spacing:0.05em;'>⚠️ PARTIALLY BOOKED — OTHER DATES AVAILABLE</div>" if house_occupied else "")
        + "<div class='property-body'>"
        "<div class='property-title'>" + str(row['title']) + "</div>"
        "<div class='property-location'>📍 " + str(row['address']) + ", " + str(row['city']) + "</div>"
        "<div style='margin-bottom:0.5rem'>"
        "<span class='price-tag'>₱" + f"{row['nightly_price']:,.0f}" + "/night</span>"
        "<span class='price-tag' style='background:#e8a020'>₱" + f"{row['monthly_price']:,.0f}" + "/mo</span>"
        "</div>"
        "<div style='font-size:0.82rem;color:#6b7280;margin-bottom:0.5rem'>"
        "👥 " + str(row['max_guests']) + " guests | 🛏 " + str(row['bedrooms']) + " beds | 🚿 " + str(row['bathrooms']) + " baths"
        + rooms_line +
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(_card_html, unsafe_allow_html=True)

    if row['amenities']:
        tags = row['amenities'].split(',')[:5]
        amenities_html = " ".join([f'<span class="amenity-tag">{t.strip()}</span>' for t in tags])
        st.markdown('<div style="padding:0 0 0.75rem 0">' + amenities_html + '</div>', unsafe_allow_html=True)

    if user:
        if fully_booked:
            st.markdown(
                "<div style='background:#fee2e2;border:1.5px solid #dc2626;border-radius:10px;"
                "padding:0.5rem 1rem;text-align:center;font-size:0.88rem;color:#dc2626;"
                "font-weight:700;margin-bottom:0.5rem;'>🚫 No Rooms Available</div>",
                unsafe_allow_html=True
            )
        elif house_occupied:
            avail_msg = f"Next available: {house_available_date}" if house_available_date else ""
            st.markdown(
                f"<div style='background:#fef9c3;border:1.5px solid #d97706;border-radius:10px;"
                f"padding:0.4rem 0.75rem;font-size:0.8rem;color:#78350f;margin-bottom:0.5rem;'>"
                f"⚠️ Partially booked — {avail_msg}. You can still book on other dates.</div>",
                unsafe_allow_html=True
            )
            if st.button("📅 Book Now", key=f"book_{row['id']}"):
                st.session_state['booking_property'] = {
                    'id': int(float(row['id'])),
                    'title': str(row['title']),
                    'type': str(row['type']),
                    'nightly_price': float(row['nightly_price']),
                    'monthly_price': float(row['monthly_price']),
                }
                st.session_state['booking_property_id'] = int(float(row['id']))
                st.session_state['show_booking_modal'] = True
                st.rerun()
        else:
            if st.button("📅 Book Now", key=f"book_{row['id']}"):
                st.session_state['booking_property'] = {
                    'id': int(float(row['id'])),
                    'title': str(row['title']),
                    'type': str(row['type']),
                    'nightly_price': float(row['nightly_price']),
                    'monthly_price': float(row['monthly_price']),
                }
                st.session_state['booking_property_id'] = int(float(row['id']))
                st.session_state['show_booking_modal'] = True
                st.rerun()
    else:
        st.caption("Login as guest to book")


def _save_booking(user, prop_id, prop_type, room_id,
                  check_in, check_out_db, booking_type_val,
                  subtotal, service_fee, total, down_payment, balance_due,
                  payment_method, payment_status, special):
    from datetime import timedelta
    try:
        conn = get_conn()
        cur = conn.cursor()

        # Block if guest already has an active booking on this property
        cur.execute(adapt_sql("""
            SELECT id FROM bookings
            WHERE guest_id = %s
              AND property_id = %s
              AND status IN ('pending', 'confirmed')
            LIMIT 1
        """), (int(float(user['id'])), prop_id))
        existing = cur.fetchone()

        if existing:
            if USE_POSTGRES:
                release_conn(conn)
            else:
                conn.close()
            st.error(
                "❌ You already have an active booking for this property. "
                "Please wait until your current booking is completed or cancelled before booking again."
            )
            return

        cur.execute(adapt_sql("""
            INSERT INTO bookings (
                guest_id, property_id, room_id,
                check_in, check_out, booking_type,
                total_price, down_payment, balance_due,
                payment_method, payment_status,
                special_requests, status, is_open_ended
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s)
        """), (
            user['id'], prop_id, room_id,
            check_in.isoformat(), check_out_db.isoformat(),
            booking_type_val, total, down_payment, balance_due,
            payment_method, payment_status, special,
            1 if booking_type_val == 'monthly' else 0
        ))
        new_booking_id = cur.lastrowid
        conn.commit()
        if USE_POSTGRES:
            release_conn(conn)
        else:
            conn.close()

        if payment_method == 'online':
            process_new_booking(new_booking_id)

        for k in ['show_booking_modal','booking_property_id','booking_property']:
            st.session_state.pop(k, None)
        if booking_type_val == 'monthly':
            checkout_msg = "Check out whenever you're ready — just notify the owner."
        else:
            checkout_msg = f"Balance ₱{balance_due:,.0f} due at check-in."
        if payment_method == 'online':
            st.success(f"🎉 Booking confirmed! Down payment of ₱{down_payment:,.0f} charged. {checkout_msg}")
        else:
            st.success(f"🎉 Booking submitted! Please pay ₱{down_payment:,.0f} at the property office within 24 hours. {checkout_msg}")
        st.balloons()
        st.rerun()
    except Exception as e:
        st.error(f"❌ Booking failed: {str(e)}")


def _booking_form(prop, user):
    prop_id = prop['id']
    prop_title = prop['title']
    prop_type = prop['type']
    prop_nightly = prop['nightly_price']
    prop_monthly = prop['monthly_price']

    st.markdown(f"### 📅 Book: {prop_title}")

    # Block if guest already has an active booking
    _chk = get_conn()
    try:
        _cur = _chk.cursor()
        _cur.execute(adapt_sql("""
            SELECT id FROM bookings
            WHERE guest_id = %s AND property_id = %s
              AND status IN ('pending', 'confirmed')
            LIMIT 1
        """), (int(float(user['id'])), prop_id))
        _active = _cur.fetchone()
    finally:
        if USE_POSTGRES:
            release_conn(_chk)
        else:
            _chk.close()
    if _active:
        st.error(
            "❌ You already have an active booking for this property. "
            "Please wait until your current booking is completed or cancelled before booking again."
        )
        if st.button("✖ Close", key="bk_close_dup"):
            st.session_state.pop('show_booking_modal', None)
            st.session_state.pop('booking_property_id', None)
            st.session_state.pop('booking_property', None)
            st.rerun()
        return

    st.markdown("**Booking Type**")
    st.radio(
        "Booking Type", ["🌙 Nightly", "📅 Monthly"],
        horizontal=True, key="bk_type", label_visibility="collapsed"
    )
    _raw_type = st.session_state.get("bk_type", "🌙 Nightly")
    booking_type_val = "nightly" if "Nightly" in _raw_type else "monthly"

    if booking_type_val == "monthly":
        check_in = st.date_input(
            "📅 Check-in Date",
            value=date.today(),
            min_value=date.today(),
            key="bk_check_in_monthly"
        )
        check_out_db = check_in + timedelta(days=30)

        st.markdown("""
        <div style="background:#f0f4ff;border:1.5px solid #2563a8;border-radius:12px;
                    padding:1rem 1.25rem;margin:0.5rem 0 1rem;">
            <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.5rem;">
                <span style="font-size:1.2rem;">🏠</span>
                <span style="font-weight:700;color:#1a3c5e;">Boarding House — Monthly Stay</span>
            </div>
            <div style="display:flex;justify-content:space-between;font-size:0.88rem;margin-bottom:0.3rem;">
                <span style="color:#6b7280;">Check-out</span>
                <span style="font-weight:700;color:#2563a8;">You decide when to leave 🗓</span>
            </div>
            <div style="padding-top:0.5rem;border-top:1px dashed #c7d7f8;
                        font-size:0.82rem;color:#6b7280;margin-top:0.4rem;">
                💡 No fixed checkout date. Just inform the owner when you're ready to leave.
            </div>
        </div>
        """, unsafe_allow_html=True)

        months = 1
        subtotal = months * prop_monthly
        service_fee = round(subtotal * 0.05)
        total = subtotal + service_fee
        fee_pct = "5%"
        period_label = f"₱{prop_monthly:,.0f} / month (recurring)"
        nights = 30

    else:
        col1, col2 = st.columns(2)
        with col1:
            check_in = st.date_input(
                "Check-in Date",
                value=date.today() + timedelta(days=1),
                min_value=date.today(),
                key="bk_check_in_nightly"
            )
        with col2:
            checkout_min = check_in + timedelta(days=1)
            checkout_default = max(date.today() + timedelta(days=3), checkout_min)
            check_out = st.date_input(
                "Check-out Date",
                value=checkout_default,
                min_value=checkout_min,
                key="bk_check_out_nightly"
            )
        check_out_db = check_out

        nights = max((check_out - check_in).days, 1)
        months = max(round(nights / 30), 1)
        subtotal = nights * prop_nightly
        service_fee = round(subtotal * 0.12)
        total = subtotal + service_fee
        fee_pct = "12%"
        period_label = f"₱{prop_nightly:,.0f} × {nights} night{'s' if nights != 1 else ''}"

    down_payment = round(total * 0.30)
    balance_due = total - down_payment

    _checkout_row = (
        ""
        if booking_type_val == "monthly"
        else (
            "<div style='display:flex;justify-content:space-between;'>"
            "<span style='color:#6b7280;'>Check-out</span>"
            "<span style='font-weight:600;'>" + check_out_db.strftime('%b %d, %Y') + "</span>"
            "</div>"
        )
    )
    _breakdown_html = (
        "<div style='border:1px solid #e5e1d8;border-radius:14px;overflow:hidden;margin:0.75rem 0 1rem'>"
        "<div style='background:#f0ede6;padding:0.55rem 1rem;font-size:0.75rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.05em;color:#6b7280;border-bottom:1px solid #e5e1d8;'>"
        "💰 Cost Breakdown"
        "</div>"
        "<div style='padding:0.85rem 1rem;display:flex;flex-direction:column;gap:0.45rem;font-size:0.9rem;'>"
        "<div style='display:flex;justify-content:space-between;'>"
        "<span style='color:#6b7280;'>Check-in</span>"
        "<span style='font-weight:600;'>" + check_in.strftime('%b %d, %Y') + "</span>"
        "</div>"
        + _checkout_row +
        "<div style='border-top:1px solid #e5e1d8;padding-top:0.5rem;display:flex;justify-content:space-between;'>"
        "<span style='color:#6b7280;'>" + period_label + "</span>"
        "<span style='font-weight:600;'>₱" + f"{subtotal:,.0f}" + "</span>"
        "</div>"
        "<div style='display:flex;justify-content:space-between;'>"
        "<span style='color:#6b7280;'>Service fee (" + fee_pct + ")</span>"
        "<span style='font-weight:600;'>₱" + f"{service_fee:,.0f}" + "</span>"
        "</div>"
        "<div style='border-top:1px solid #e5e1d8;padding-top:0.5rem;"
        "display:flex;justify-content:space-between;font-size:1rem;'>"
        "<span style='font-weight:700;'>Total</span>"
        "<span style='font-weight:800;color:#1a3c5e;'>₱" + f"{total:,.0f}" + "</span>"
        "</div>"
        "<div style='border-top:1px dashed #c7d7f8;padding-top:0.5rem;"
        "display:flex;justify-content:space-between;color:#2563a8;'>"
        "<span style='font-weight:600;'>⬇️ Down Payment (30%) — due now</span>"
        "<span style='font-weight:700;'>₱" + f"{down_payment:,.0f}" + "</span>"
        "</div>"
        "<div style='display:flex;justify-content:space-between;color:#6b7280;'>"
        "<span>Remaining balance (due at check-in)</span>"
        "<span style='font-weight:600;'>₱" + f"{balance_due:,.0f}" + "</span>"
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(_breakdown_html, unsafe_allow_html=True)

    room_id = None

    # House availability guard
    if prop_type == 'house':
        conn_h = get_conn()
        try:
            cur_h = conn_h.cursor()
            cur_h.execute(adapt_sql("""
                SELECT COUNT(*) as n FROM bookings
                WHERE property_id=%s
                AND room_id IS NULL
                AND check_in < %s
                AND check_out > %s
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )
            """), (prop_id, check_out_db.isoformat(), check_in.isoformat()))
            house_conflict = cur_h.fetchone()
            cur_h.execute(adapt_sql("""
                SELECT MIN(check_out) as next_date FROM bookings
                WHERE property_id=%s AND room_id IS NULL
                AND check_out > CURRENT_DATE
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )
            """), (prop_id,))
            house_next = cur_h.fetchone()
        finally:
            if USE_POSTGRES:
                release_conn(conn_h)
            else:
                conn_h.close()
        if house_conflict and house_conflict['n'] > 0:
            st.error("🚫 This house is already booked for your selected dates.")
            if house_next and house_next['next_date']:
                st.info(f"📅 It may be available from **{house_next['next_date']}** onwards.")
            if st.button("✖ Close", key="bk_close_house"):
                st.session_state.pop('show_booking_modal', None)
                st.session_state.pop('booking_property_id', None)
                st.session_state.pop('booking_property', None)
                st.rerun()
            return

    if prop_type == 'apartment':
        rooms = df_query("""
            SELECT * FROM rooms
            WHERE property_id=%s
            AND is_available=1
            AND id NOT IN (
                SELECT room_id FROM bookings
                WHERE property_id=%s
                AND room_id IS NOT NULL
                AND check_in < %s
                AND check_out > %s
                AND (
                    status = 'confirmed'
                    OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                )
            )
        """, params=[prop_id, prop_id, check_out_db.isoformat(), check_in.isoformat()])

        if rooms.empty:
            conn2 = get_conn()
            try:
                cur2 = conn2.cursor()
                cur2.execute(adapt_sql("""
                    SELECT MIN(check_out) as next_date FROM bookings
                    WHERE property_id=%s
                    AND room_id IS NOT NULL
                    AND check_out > CURRENT_DATE
                    AND (
                        status = 'confirmed'
                        OR (status = 'pending' AND payment_method = 'online' AND payment_status = 'down_paid')
                    )
                """), (prop_id,))
                next_date = cur2.fetchone()
            finally:
                if USE_POSTGRES:
                    release_conn(conn2)
                else:
                    conn2.close()
            next_msg = f"📅 Rooms may be available from **{next_date['next_date']}** onwards." if next_date and next_date['next_date'] else ""
            st.error("🚫 No rooms available for your selected dates.")
            if next_msg:
                st.info(next_msg)
            if st.button("✖ Close", key="bk_close"):
                st.session_state.pop('show_booking_modal', None)
                st.session_state.pop('booking_property_id', None)
                st.session_state.pop('booking_property', None)
                st.rerun()
            return

        room_opts = {
            f"Room {r['room_number']} — {r['room_type'].title()} (Cap: {r['capacity']})": int(float(r['id']))
            for _, r in rooms.iterrows()
        }
        selected_room = st.selectbox("Select Room", list(room_opts.keys()), key="bk_room")
        room_id = room_opts[selected_room]

    special = st.text_area("Special Requests (optional)", key="bk_special")

    st.markdown("**Down Payment Method** *(30% = ₱{:,.0f} due now)*".format(down_payment))
    st.radio(
        "Payment Method", ["🚶 Walk-in", "💳 Online Card"],
        horizontal=True, key="bk_payment", label_visibility="collapsed"
    )
    _raw_payment = st.session_state.get("bk_payment", "🚶 Walk-in")
    payment_method_val = "walk-in" if "Walk-in" in _raw_payment else "online"

    st.markdown("---")

    if payment_method_val == "online":
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#1a3c5e,#2563a8);border-radius:16px;
                    padding:1.5rem;margin-bottom:1rem;color:white">
            <div style="font-size:0.75rem;opacity:0.7;letter-spacing:0.1em">SECURE CARD PAYMENT</div>
            <div style="font-size:1.1rem;font-weight:600;margin-top:0.25rem">
                💳 Pay Down Payment — ₱{down_payment:,.0f}
            </div>
            <div style="font-size:0.8rem;opacity:0.75;margin-top:0.2rem">
                Remaining ₱{balance_due:,.0f} due at check-in
            </div>
        </div>
        """, unsafe_allow_html=True)

        from datetime import datetime as _dt
        _now = _dt.now()
        _months = [f"{m:02d}" for m in range(1, 13)]
        _years = [str(y)[-2:] for y in range(_now.year, _now.year + 11)]

        with st.form("card_form"):
            card_name = st.text_input("👤 Cardholder Name", placeholder="Juan dela Cruz")
            card_raw = st.text_input(
                "💳 Card Number (digits only)",
                placeholder="1234567890123456",
                max_chars=16,
                help="Type your 16-digit card number without spaces"
            )
            digits_only = card_raw.replace(" ", "").replace("-", "")
            fmt_groups = " ".join(digits_only[i:i+4] for i in range(0, len(digits_only), 4))
            first = digits_only[0] if digits_only else ""
            card_brand = ("💳 Visa" if first == "4" else
                          "💳 Mastercard" if first == "5" else
                          "💳 Amex" if first == "3" else "💳 Card")
            if fmt_groups:
                st.markdown(
                    f'<div style="font-family:monospace;font-size:1.2rem;font-weight:700;'
                    f'letter-spacing:0.18em;color:#1a3c5e;background:#f0ede6;'
                    f'padding:0.5rem 0.85rem;border-radius:8px;margin-bottom:0.25rem">'
                    f'{fmt_groups}</div>'
                    f'<div style="font-size:0.85rem;color:#6b7280;margin-bottom:0.5rem">{card_brand}</div>',
                    unsafe_allow_html=True
                )

            col_m, col_y, col_cvv_col = st.columns([1, 1, 1])
            with col_m:
                exp_month = st.selectbox("📅 Month", _months, index=_now.month - 1)
            with col_y:
                exp_year = st.selectbox("📅 Year", _years, index=0)
            with col_cvv_col:
                cvv = st.text_input("🔒 CVV", placeholder="123", max_chars=4, type="password")

            card_submitted = st.form_submit_button(
                "✅ Confirm & Pay Down Payment",
                use_container_width=True,
            )

        if card_submitted:
            _cn = card_name.strip()
            _dg = digits_only
            _cv = cvv.strip()
            errors = []
            if len(_cn) < 3:
                errors.append("Cardholder name too short")
            if len(_dg) != 16 or not _dg.isdigit():
                errors.append(f"Card number must be 16 digits (got {len(_dg)})")
            if len(_cv) < 3:
                errors.append("CVV must be at least 3 digits")
            if errors:
                st.error("❌ " + " | ".join(errors))
            else:
                _save_booking(user, prop_id, prop_type, room_id if prop_type == 'apartment' else None,
                              check_in, check_out_db, booking_type_val,
                              subtotal, service_fee, total, down_payment, balance_due,
                              "online", "down_paid",
                              st.session_state.get("bk_special", ""))
        return

    else:
        checkin_label = check_in.strftime('%b %d, %Y')
        checkout_note = (
            "Open-ended — you decide when to check out"
            if booking_type_val == "monthly"
            else f"due at check-in ({checkin_label})"
        )
        st.markdown(f"""
        <div style="background:#fff8e1;border:1.5px solid #f59e0b;border-radius:14px;
                    padding:1.25rem;margin-bottom:1rem">
            <div style="font-size:1rem;font-weight:700;color:#92400e">🚶 Walk-in Down Payment Instructions</div>
            <div style="margin-top:0.6rem;font-size:0.9rem;color:#78350f;line-height:1.8">
                💰 <b>Down Payment Due Now:</b> ₱{down_payment:,.0f} <span style="opacity:0.7">(30% of total)</span><br>
                🏦 <b>Where:</b> Pay at the property office or front desk<br>
                ⏰ <b>Deadline:</b> Within <b>24 hours</b> of booking confirmation<br>
                ⚠️ Booking may be cancelled if down payment is not received in time<br>
                <br>
                🔑 <b>Remaining Balance:</b> ₱{balance_due:,.0f} — {checkout_note}
            </div>
        </div>
        """, unsafe_allow_html=True)

    if payment_method_val == "walk-in":
        st.markdown("---")
        col_s, col_c = st.columns(2)
        with col_s:
            confirm = st.button("✅ Confirm Booking", key="bk_confirm", use_container_width=True)
        with col_c:
            cancel_btn = st.button("✖ Cancel", key="bk_cancel", use_container_width=True)

        if cancel_btn:
            st.session_state.pop('show_booking_modal', None)
            st.session_state.pop('booking_property_id', None)
            st.session_state.pop('booking_property', None)
            st.rerun()

        if confirm:
            _save_booking(user, prop_id, prop_type, room_id,
                          check_in, check_out_db, booking_type_val,
                          subtotal, service_fee, total, down_payment, balance_due,
                          "walk-in", "walk_in_pending",
                          st.session_state.get("bk_special", special))
    else:
        st.markdown("---")
        if st.button("✖ Cancel Booking", key="bk_cancel_online", use_container_width=False):
            st.session_state.pop('show_booking_modal', None)
            st.session_state.pop('booking_property_id', None)
            st.session_state.pop('booking_property', None)
            st.rerun()


def guest_bookings(user):
    st.markdown('<div class="section-header">📋 My Bookings</div>', unsafe_allow_html=True)
    df = df_query("""
        SELECT DISTINCT b.id, b.check_in, b.check_out, b.booking_type, b.total_price,
               b.down_payment, b.balance_due,
               b.status, b.payment_method, b.payment_status,
               b.special_requests, b.created_at,
               COALESCE(b.is_open_ended, 0) as is_open_ended,
               p.title as property, p.city, p.type,
               r.room_number,
               u.name as owner_name, u.phone as owner_phone
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON p.owner_id = u.id
        LEFT JOIN rooms r ON b.room_id = r.id
        WHERE b.guest_id=%s
        ORDER BY b.created_at DESC
    """, params=[user['id']])
    df = df.drop_duplicates(subset=['id'])

    if df.empty:
        st.info("You haven't made any bookings yet. Browse properties to get started!")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(metric_card(len(df), "Total Bookings", "📋"), unsafe_allow_html=True)
    with col2:
        st.markdown(metric_card(len(df[df['status'] == 'confirmed']), "Confirmed", "✅"), unsafe_allow_html=True)
    with col3:
        down_paid_total = df[df['payment_status'] == 'down_paid']['down_payment'].sum()
        st.markdown(metric_card(f"₱{down_paid_total:,.0f}", "Down Payments Paid", "💰"), unsafe_allow_html=True)

    st.markdown("---")

    tab_all, tab_pending, tab_confirmed, tab_cancelled = st.tabs(
        ["📋 All", "⏳ Pending", "✅ Confirmed", "❌ Cancelled"]
    )

    def render_bookings(bdf, tab_key):
        if bdf.empty:
            st.info("No bookings in this category.")
            return
        for _, row in bdf.iterrows():
            emoji = property_emoji(row['type'])
            status_icon = {"pending": "⏳", "confirmed": "✅", "cancelled": "❌"}.get(row['status'], "📋")
            with st.expander(
                f"{emoji} {row['property']} | {row['check_in']} → {'Open-ended' if row.get('is_open_ended') else row['check_out']} | {status_icon} {row['status'].title()}",
                expanded=False
            ):
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.markdown(f"**Property:** {row['property']}, {row['city']}")
                    if row['room_number']:
                        st.markdown(f"**Room:** {row['room_number']}")
                    checkout_label = "Open-ended (monthly boarder)" if row.get('is_open_ended') else row['check_out']
                    st.markdown(f"**Check-in:** {row['check_in']} | **Check-out:** {checkout_label}")
                    st.markdown(f"**Booking Type:** {row['booking_type'].title()}")
                    st.markdown(f"**Owner:** {row['owner_name']} — {row['owner_phone']}")
                    st.markdown(f"**Total Amount:** ₱{row['total_price']:,.0f}")

                    down = row.get('down_payment') or 0
                    balance = row.get('balance_due') or 0
                    if down > 0:
                        pay_icon = "🌐" if row['payment_method'] == 'online' else "🏦"
                        pay_label = "Paid online" if row['payment_status'] == 'down_paid' else "Walk-in pending"
                        pay_color = "#16a34a" if row['payment_status'] == 'down_paid' else "#92400e"
                        pay_bg = "#dcfce7" if row['payment_status'] == 'down_paid' else "#fef3c7"
                        st.markdown(f"""
                        <div style="background:#f0f4ff;border-radius:10px;padding:0.75rem 1rem;
                                    margin-top:0.5rem;font-size:0.88rem;">
                            <div style="font-weight:700;color:#1a3c5e;margin-bottom:0.4rem;">💳 Down Payment (30%)</div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.2rem;">
                                <span style="color:#6b7280;">Down paid:</span>
                                <span style="font-weight:700;color:#2563a8;">₱{down:,.0f}
                                    &nbsp;<span style="background:{pay_bg};color:{pay_color};
                                        padding:0.1rem 0.5rem;border-radius:999px;font-size:0.75rem;font-weight:700;">
                                        {pay_icon} {pay_label}
                                    </span>
                                </span>
                            </div>
                            <div style="display:flex;justify-content:space-between;">
                                <span style="color:#6b7280;">Balance due at check-in:</span>
                                <span style="font-weight:600;">₱{balance:,.0f}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    if row['special_requests']:
                        st.markdown(f"**Special Requests:** {row['special_requests']}")

                with col2:
                    st.markdown(f"**Status:** {status_badge(row['status'])}", unsafe_allow_html=True)

                    if row['payment_method'] == 'walk-in' and row['payment_status'] == 'walk_in_pending':
                        down = row.get('down_payment') or 0
                        st.markdown(f"""
                        <div style="background:#fff8e1;border:1.5px solid #f59e0b;border-radius:12px;
                                    padding:0.85rem;font-size:0.82rem;color:#78350f;margin-top:0.5rem;">
                            🚶 <b>Walk-in Down Payment</b><br>
                            💰 Pay <b>₱{down:,.0f}</b> at the property office<br>
                            ⏰ Within <b>24 hours</b> to keep booking active
                        </div>
                        """, unsafe_allow_html=True)

                    if row['payment_method'] == 'online' and row['payment_status'] == 'pending_online':
                        down = row.get('down_payment') or 0
                        st.markdown('<div class="alert-box alert-warning">💳 Online down payment pending</div>', unsafe_allow_html=True)
                        with st.expander("💳 Pay Down Payment Now", expanded=False):
                            pay_card_name = st.text_input("Cardholder Name", placeholder="Juan dela Cruz", key=f"pn_name_{tab_key}_{row['id']}")
                            col_pcn, col_pexp = st.columns([2, 1])
                            with col_pcn:
                                pay_card_num = st.text_input("Card Number", placeholder="1234 5678 9012 3456", max_chars=19, key=f"pn_num_{tab_key}_{row['id']}")
                            with col_pexp:
                                pay_expiry = st.text_input("Expiry (MM/YY)", placeholder="12/27", max_chars=5, key=f"pn_exp_{tab_key}_{row['id']}")
                            col_pcvv, col_pbrand = st.columns([1, 2])
                            with col_pcvv:
                                pay_cvv = st.text_input("CVV", placeholder="123", max_chars=4, type="password", key=f"pn_cvv_{tab_key}_{row['id']}")
                            with col_pbrand:
                                first = pay_card_num[0] if pay_card_num else ""
                                brand = "💳 Visa" if first == "4" else ("💳 Mastercard" if first == "5" else ("💳 Amex" if first == "3" else "💳 Card"))
                                st.markdown(f'<div style="margin-top:1.9rem;font-weight:600;color:#1a3c5e">{brand}</div>', unsafe_allow_html=True)

                            digits = pay_card_num.replace(" ", "").replace("-", "")
                            pay_valid = (
                                len(pay_card_name.strip()) >= 3 and
                                len(digits) == 16 and digits.isdigit() and
                                len(pay_expiry) == 5 and "/" in pay_expiry and
                                len(pay_cvv) >= 3
                            )
                            st.markdown(f"""
                            <div class="alert-box {'alert-success' if pay_valid else 'alert-info'}">
                                💰 <b>Down Payment: ₱{down:,.0f}</b> — 
                                {'✅ Ready to charge' if pay_valid else 'Fill in all fields to proceed'}
                            </div>
                            """, unsafe_allow_html=True)

                            if st.button("✅ Pay Down Payment", key=f"pay_{tab_key}_{row['id']}", disabled=not pay_valid):
                                c = get_conn()
                                try:
                                    cur = c.cursor()
                                    cur.execute(adapt_sql("UPDATE bookings SET payment_status='down_paid' WHERE id=%s"), (int(float(row['id'])),))
                                    c.commit()
                                finally:
                                    if USE_POSTGRES:
                                        release_conn(c)
                                    else:
                                        c.close()
                                st.success("✅ Down payment successful!")
                                st.rerun()

                    if row['payment_status'] == 'down_paid':
                        balance = row.get('balance_due') or 0
                        st.markdown(f"""
                        <div class="alert-box alert-success">
                            ✅ Down payment confirmed<br>
                            <small>Balance ₱{balance:,.0f} due at check-in</small>
                        </div>
                        """, unsafe_allow_html=True)

                    if row['payment_status'] == 'paid':
                        st.markdown('<div class="alert-box alert-success">✅ Fully paid</div>', unsafe_allow_html=True)

                    if row['status'] == 'pending':
                        if st.button("❌ Cancel Booking", key=f"cancel_{tab_key}_{row['id']}"):
                            c = get_conn()
                            try:
                                cur = c.cursor()
                                cur.execute(adapt_sql("UPDATE bookings SET status='cancelled' WHERE id=%s"), (int(float(row['id'])),))
                                c.commit()
                            finally:
                                if USE_POSTGRES:
                                    release_conn(c)
                                else:
                                    c.close()
                            st.warning("Booking cancelled.")
                            st.rerun()

                    if row['status'] == 'confirmed':
                        label = '🚪 Leave / Move Out' if row.get('is_open_ended') else '🚪 Check Out'
                        note = 'Ready to move out? Notify the owner below.' if row.get('is_open_ended') else 'Want to check out? Notify the owner below.'
                        st.markdown(
                            f'<div style="background:#f0fdf4;border:1.5px solid #16a34a;border-radius:12px;'
                            f'padding:0.7rem 1rem;font-size:0.82rem;color:#14532d;margin-top:0.75rem;">'
                            f'🏠 <b>{"Monthly Stay" if row.get("is_open_ended") else "Your Stay"}</b><br>{note}'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                        if st.button(label, key=f"leave_{tab_key}_{row['id']}", use_container_width=True):
                            from datetime import date as _date
                            c = get_conn()
                            try:
                                cur = c.cursor()
                                cur.execute(adapt_sql(
                                    'UPDATE bookings SET status=\'completed\', check_out=%s, is_open_ended=0 WHERE id=%s'),
                                    (_date.today().isoformat(), row['id'])
                                )
                                c.commit()
                            finally:
                                if USE_POSTGRES:
                                    release_conn(c)
                                else:
                                    c.close()
                            st.success('✅ Check-out recorded! The owner has been notified.')
                            st.rerun()

    with tab_all:
        render_bookings(df, "all")
    with tab_pending:
        render_bookings(df[df['status'] == 'pending'], "pending")
    with tab_confirmed:
        render_bookings(df[df['status'] == 'confirmed'], "confirmed")
    with tab_cancelled:
        render_bookings(df[df['status'] == 'cancelled'], "cancelled")


def guest_profile(user):
    st.markdown('<div class="section-header">👤 My Profile</div>', unsafe_allow_html=True)
    conn = get_conn()
    try:
        c = conn.cursor()
        c.execute(adapt_sql("SELECT * FROM users WHERE id=%s"), (int(float(user['id'])),))
        u = dict(c.fetchone())
    finally:
        if USE_POSTGRES:
            release_conn(conn)
        else:
            conn.close()

    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="padding:2rem">
            <div style="font-size:4rem">👤</div>
            <div style="font-family:'Playfair Display',serif;font-size:1.2rem;font-weight:700">{u['name']}</div>
            <div style="color:#6b7280">{u['role'].title()}</div>
            <div style="color:#6b7280;font-size:0.85rem">Member since {str(u['created_at'])[:10]}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        with st.form("profile_form"):
            name = st.text_input("Full Name", value=u['name'])
            email = st.text_input("Email", value=u['email'])
            phone = st.text_input("Phone", value=u['phone'] or "")
            new_password = st.text_input("New Password (leave blank to keep current)", type="password")
            if st.form_submit_button("💾 Update Profile"):
                from database import hash_password
                c2 = get_conn()
                try:
                    if new_password:
                        if len(new_password) < 6:
                            st.error("Password must be at least 6 characters.")
                        else:
                            c2.execute(adapt_sql(
                                "UPDATE users SET name=%s, email=%s, phone=%s, password=%s WHERE id=%s"),
                                (name, email, phone, hash_password(new_password), u['id'])
                            )
                            c2.commit()
                            st.session_state['user']['name'] = name
                            st.session_state['user']['email'] = email
                            st.success("✅ Profile updated!")
                    else:
                        c2.execute(adapt_sql(
                            "UPDATE users SET name=%s, email=%s, phone=%s WHERE id=%s"),
                            (name, email, phone, u['id'])
                        )
                        c2.commit()
                        st.session_state['user']['name'] = name
                        st.session_state['user']['email'] = email
                        st.success("✅ Profile updated!")
                finally:
                    if USE_POSTGRES:
                        release_conn(c2)
                    else:
                        c2.close()
