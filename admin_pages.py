import streamlit as st
import pandas as pd
from database import get_conn, adapt_sql, USE_POSTGRES, release_conn, df_query
from ui_components import metric_card, status_badge, property_emoji, sidebar_nav
from ml_model import (predict_trending_properties, predict_trending_by_month, get_seasonal_insights,
                      get_monthly_forecast, run_backtest, get_data_quality_report, learn_seasonal_weights,
                      rebuild_booking_history_from_real_data)
from datetime import datetime

def admin_dashboard():
    rebuild_booking_history_from_real_data()

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) as n FROM properties WHERE status='approved'")
        total_props = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM properties WHERE status='pending'")
        pending_props = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM users WHERE role='guest'")
        total_guests = c.fetchone()['n']
        c.execute("SELECT COUNT(*) as n FROM bookings")
        total_bookings = c.fetchone()['n']
        c.execute("SELECT COALESCE(SUM(total_price),0) as rev FROM bookings WHERE status='confirmed'")
        total_revenue = c.fetchone()['rev']
        c.execute("SELECT COUNT(*) as n FROM users WHERE role='owner'")
        total_owners = c.fetchone()['n']
    finally:
        if USE_POSTGRES:
            release_conn(conn)
        else:
            conn.close()

    st.markdown('<div class="section-header">📊 Admin Dashboard</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.markdown(metric_card(total_props, "Active Properties", "🏘️"), unsafe_allow_html=True)
    with col2: st.markdown(metric_card(total_bookings, "Total Bookings", "📋"), unsafe_allow_html=True)
    with col3: st.markdown(metric_card(total_guests, "Registered Guests", "👥"), unsafe_allow_html=True)
    with col4: st.markdown(metric_card(f"₱{total_revenue:,.0f}", "Total Revenue", "💰"), unsafe_allow_html=True)

    st.markdown("---")

    dq = get_data_quality_report()
    bt = run_backtest()

    col_dq1, col_dq2, col_dq3, col_dq4 = st.columns(4)
    with col_dq1:
        label = "Real bookings" if not dq['is_synthetic'] else "Synthetic only"
        st.markdown(metric_card(dq['real_confirmed_bookings'], label, "📦"), unsafe_allow_html=True)
    with col_dq2:
        st.markdown(metric_card(dq['history_rows'], "History rows", "📂"), unsafe_allow_html=True)
    with col_dq3:
        acc = f"{bt['accuracy_pct']}%" if bt and bt.get('accuracy_pct') is not None else "N/A"
        st.markdown(metric_card(acc, "Model accuracy", "🎯"), unsafe_allow_html=True)
    with col_dq4:
        mape = f"{bt['mape']}%" if bt else "N/A"
        st.markdown(metric_card(mape, "Forecast error (MAPE)", "📉"), unsafe_allow_html=True)

    if dq['is_synthetic']:
        st.warning("⚠️ **Running on synthetic data.** Accuracy improves as guests make confirmed bookings — the model retrains on every app restart.")
    else:
        st.success(f"✅ **Trained on real data** — {dq['real_confirmed_bookings']} confirmed bookings from {dq['earliest_booking']} to {dq['latest_booking']}.")

    st.markdown("---")
    col_l, col_r = st.columns([1.3, 1])

    with col_l:
        st.markdown('<div class="section-header">🔥 ML Trending Properties</div>', unsafe_allow_html=True)

        MONTH_NAMES = ['January','February','March','April','May','June',
                       'July','August','September','October','November','December']
        current_month = datetime.now().month
        selected_month_name = st.selectbox(
            "📅 Pick a month to analyze",
            MONTH_NAMES,
            index=current_month - 1,
            key="admin_month_picker"
        )
        selected_month_num = MONTH_NAMES.index(selected_month_name) + 1
        st.caption(f"🤖 AI trend scores for **{selected_month_name}** — recency-weighted seasonal model + OLS momentum")

        all_scores = predict_trending_by_month(selected_month_num)

        if not all_scores:
            st.info("Not enough historical data yet.")
        else:
            df_scores = pd.DataFrame(all_scores)
            df_scores = df_scores.sort_values('trend_score', ascending=False)
            df_scores['short_title'] = df_scores['title'].apply(
                lambda t: t[:22] + '…' if len(t) > 22 else t
            )

            st.markdown("**Trend Score Comparison — All Properties**")
            st.bar_chart(df_scores.set_index('short_title')['trend_score'], height=220, color="#1a3c5e")

            st.markdown("**Predicted Bookings Comparison**")
            st.bar_chart(df_scores.set_index('short_title')['predicted_bookings'], height=180, color="#e8a020")

            st.markdown(f"**🏆 Top Properties for {selected_month_name}**")
            top3 = all_scores[:3]
            for i, t in enumerate(top3):
                medal = ["🥇", "🥈", "🥉"][i]
                no_data = t.get('years_of_data', 0) == 0 and t['trend_score'] == 0.0
                bg = "linear-gradient(135deg,#6b7280,#9ca3af)" if no_data else "linear-gradient(135deg,#1a3c5e,#2563a8)"
                icon = "🆕" if no_data else "🔥"
                if no_data:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;padding:1.1rem;color:white;margin-bottom:0.75rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2rem;font-weight:700;font-family:'Playfair Display',serif">—</div>
                        <div style="font-weight:600;font-size:0.95rem;margin:0.2rem 0">{t['title']}</div>
                        <div style="font-size:0.8rem;opacity:0.85">📍 {t['city']}<br>📭 No bookings yet</div>
                        <div style="position:absolute;top:1rem;right:1rem;font-size:1.3rem">{icon}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;padding:1.1rem;color:white;margin-bottom:0.75rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2rem;font-weight:700;font-family:'Playfair Display',serif">{t['trend_score']}</div>
                        <div style="font-weight:600;font-size:0.95rem;margin:0.2rem 0">{t['title']}</div>
                        <div style="font-size:0.8rem;opacity:0.85">
                            📍 {t['city']}<br>
                            🏠 Predicted: <b>{t['predicted_bookings']}</b> bookings<br>
                            📅 Hist. avg ({selected_month_name[:3]}): <b>{t['historical_same_month_avg']}</b><br>
                            📈 Avg Occupancy: <b>{t['avg_occupancy']}%</b><br>
                            🌡️ Seasonal mult: <b>{t['seasonal_mult']}</b> &nbsp;|&nbsp; 🗂️ Confidence: <b>{t['data_confidence']}%</b>
                        </div>
                        <div style="position:absolute;top:1rem;right:1rem;font-size:1.3rem">{icon}</div>
                    </div>
                    """, unsafe_allow_html=True)

    with col_r:
        st.markdown('<div class="section-header">⚠️ Pending Approvals</div>', unsafe_allow_html=True)
        pending = df_query("""
            SELECT p.id, p.title, p.city, p.type, u.name as owner
            FROM properties p JOIN users u ON p.owner_id = u.id
            WHERE p.status='pending' LIMIT 5
        """)

        if pending.empty:
            st.info("No pending properties.")
        else:
            for _, row in pending.iterrows():
                st.markdown(f"""
                <div class="booking-card">
                    <b>{row['title']}</b><br>
                    <small>{property_emoji(row['type'])} {row['city']} | By {row['owner']}</small>
                </div>
                """, unsafe_allow_html=True)

        if pending_props > 0:
            st.warning(f"⚠️ {pending_props} propert{'y' if pending_props==1 else 'ies'} awaiting approval")

        if bt:
            st.markdown("---")
            st.markdown('<div class="section-header">🔬 Model Backtest</div>', unsafe_allow_html=True)
            st.caption("Hold-out validation — last 3 months predicted vs actual")
            with st.expander("View backtest details"):
                st.caption(f"MAE: {bt['mae']} | RMSE: {bt['rmse']} | MAPE: {bt['mape']}% | Samples: {bt['n_samples']}")
                bt_df = pd.DataFrame(bt['results'])
                if not bt_df.empty:
                    bt_df['month_label'] = bt_df.apply(
                        lambda r: datetime(int(float(r['year'])), int(float(r['month'])), 1).strftime("%b %Y"), axis=1
                    )
                    st.dataframe(
                        bt_df[['property','month_label','actual','predicted','error']].rename(columns={
                            'property': 'Property', 'month_label': 'Month',
                            'actual': 'Actual', 'predicted': 'Predicted', 'error': 'Error'
                        }),
                        use_container_width=True, hide_index=True
                    )

    st.markdown("---")
    st.markdown('<div class="section-header">📈 Seasonal Booking Patterns (ML Insights)</div>', unsafe_allow_html=True)

    learned_weights = learn_seasonal_weights()
    month_abbrs = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    df_season = pd.DataFrame({
        'Month': month_abbrs,
        'Learned Weight': [round(learned_weights.get(m, 0.8), 3) for m in range(1, 13)]
    })
    current_month_abbr = datetime.now().strftime("%b")
    current_month_num = datetime.now().month

    insights = get_seasonal_insights()
    col_chart1, col_chart2, col_chart3 = st.columns(3)
    with col_chart1:
        st.markdown("**Avg Bookings per Month (historical)**")
        if insights:
            df_i = pd.DataFrame(insights)
            st.bar_chart(df_i.set_index('month')['avg_bookings'], height=200)
    with col_chart2:
        st.markdown("**Avg Occupancy Rate % (historical)**")
        if insights:
            st.line_chart(df_i.set_index('month')['avg_occupancy'], height=200)
    with col_chart3:
        st.markdown("**Learned Seasonal Demand Weights**")
        st.bar_chart(df_season.set_index('Month')['Learned Weight'], height=200)
        st.caption(f"📍 Current: **{current_month_abbr}** = **{learned_weights.get(current_month_num, '—')}** | Derived from real data, not hardcoded")


def _int(val):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0








def admin_properties():
    st.markdown('<div class="section-header">🏘️ Property Management</div>', unsafe_allow_html=True)

    col_f1, col_f2 = st.columns([1, 3])
    with col_f1:
        status_filter = st.selectbox("Filter by Status", ["all", "pending", "approved", "rejected"])

    query = """
        SELECT p.id, p.title, p.description, p.type, p.address, p.city, p.barangay, p.province,
               p.nightly_price, p.monthly_price, p.max_guests, p.bedrooms, p.bathrooms,
               p.amenities, p.status, p.created_at, p.is_active,
               u.name as owner_name, u.email as owner_email, u.phone as owner_phone, u.id as owner_id
        FROM properties p JOIN users u ON p.owner_id = u.id
    """
    params = []
    if status_filter != "all":
        query += " WHERE p.status = %s"
        params.append(status_filter)
    query += " ORDER BY p.created_at DESC"

    df = df_query(query, params=params if params else None)

    for col in ['id', 'nightly_price', 'monthly_price', 'max_guests', 'bedrooms', 'bathrooms']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    if df.empty:
        st.info("No properties found.")
        return

    st.markdown(f"**{len(df)} propert{'y' if len(df)==1 else 'ies'} found**")

    for idx, (_, row) in enumerate(df.iterrows()):
        _status_icons = {'approved': '✅', 'pending': '⏳', 'rejected': '❌'}
        _sicon = _status_icons.get(row['status'], '•')
        prop_id = _int(row['id'])
        _raw_ia = row.get('is_active'); _is_blocked = (int(_raw_ia) == 0) if _raw_ia is not None else False
        _blocked_tag = " | 🚫 BLOCKED" if _is_blocked else ""

        with st.expander(
            f"{property_emoji(row['type'])} {row['title']} — {row['city']} | {_sicon} {row['status'].title()}{_blocked_tag} | 👤 {row['owner_name']}",
            expanded=False
        ):
            if _is_blocked:
                st.error("🚫 This property is currently **blocked**. The owner cannot edit it and guests cannot view or book it.")
            # ── Approve / Reject action bar (only shown for pending properties) ──
            if row['status'] == 'pending':
                act_cols = st.columns([1, 1, 4])
                with act_cols[0]:
                    if st.button("✅ Approve", key=f"app_{prop_id}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET status='approved' WHERE id=%s"), (prop_id,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.success("Approved!"); st.rerun()
                with act_cols[1]:
                    if st.button("❌ Reject", key=f"rej_{prop_id}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET status='rejected' WHERE id=%s"), (prop_id,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.warning("Rejected."); st.rerun()

            # ── Details ──────────────────────────────────────────────────────
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Owner:** {row['owner_name']}")
                st.markdown(f"**Email:** {row['owner_email']}")
                st.markdown(f"**Phone:** {row.get('owner_phone') or '—'}")
                st.markdown(f"**City:** {row['city']}")
                st.markdown(f"**Address:** {row.get('address', '')} {row.get('barangay', '')}")
                st.markdown(f"**Province:** {row.get('province') or '—'}")
                st.markdown(f"**Type:** {row['type'].title()}")
                st.markdown(f"**Max Guests:** {_int(row['max_guests'])}")
                st.markdown(f"**Bedrooms:** {_int(row['bedrooms'])} | **Bathrooms:** {_int(row['bathrooms'])}")
            with col2:
                st.markdown(f"**Nightly:** ₱{float(row['nightly_price']):,.0f}")
                st.markdown(f"**Monthly:** ₱{float(row['monthly_price']):,.0f}")
                st.markdown(f"**Status:** {status_badge(row['status'])}", unsafe_allow_html=True)
                st.markdown(f"**Added:** {str(row['created_at'])[:10]}")
                _ia = row.get('is_active')
                is_active = 1 if _ia is None else int(_ia)
                active_label = "🟢 Active" if is_active else "🔴 Blocked"
                st.markdown(f"**Listing:** {active_label}")
                if row.get('amenities'):
                    st.markdown("**Amenities:**")
                    ams = row['amenities'].split(',')
                    st.markdown(" ".join([f'<span class="amenity-tag">{a.strip()}</span>' for a in ams]), unsafe_allow_html=True)
            if row.get('description'):
                st.markdown(f"**Description:** {row['description']}")

            # Booking summary
            bdf = df_query("""
                SELECT b.status, COUNT(*) as n, COALESCE(SUM(b.total_price),0) as rev
                FROM bookings b WHERE b.property_id=%s GROUP BY b.status
            """, params=[prop_id])
            if not bdf.empty:
                st.markdown("---")
                st.markdown("**Booking Summary:**")
                bcols = st.columns(len(bdf))
                for i, (_, br) in enumerate(bdf.iterrows()):
                    with bcols[i]:
                        st.metric(br['status'].title(), int(br['n']), f"₱{float(br['rev']):,.0f}")

            # ── Block / Unblock (approved properties only) ────────────────────
            if row['status'] == 'approved':
                st.markdown("---")
                # NOTE: must not use (row.get('is_active') or 1) — that turns 0 into 1 because 0 is falsy
                _raw_active = row.get('is_active')
                is_active = 1 if _raw_active is None else int(_raw_active)
                if is_active:
                    if st.button("🚫 Block Property", key=f"block_{prop_id}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET is_active=0 WHERE id=%s"), (prop_id,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.warning("Property blocked — guests can no longer book it."); st.rerun()
                else:
                    st.warning("🚫 This property is currently **blocked**.")
                    if st.button("✅ Unblock Property", key=f"unblock_{prop_id}"):
                        c = get_conn()
                        cur = c.cursor()
                        cur.execute(adapt_sql("UPDATE properties SET is_active=1 WHERE id=%s"), (prop_id,))
                        c.commit(); release_conn(c) if USE_POSTGRES else c.close()
                        st.success("Property unblocked — guests can book it again."); st.rerun()




def admin_users():
    st.markdown('<div class="section-header">👥 User Management</div>', unsafe_allow_html=True)
    role_filter = st.selectbox("Filter by Role", ["all", "guest", "owner", "admin"])
    q = "SELECT id, name, email, role, phone, created_at, is_active FROM users"
    params = []
    if role_filter != "all":
        q += " WHERE role=%s"
        params.append(role_filter)
    q += " ORDER BY created_at DESC"
    df = df_query(q, params=params if params else None)

    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Toggle User Status")
    uid = st.number_input("User ID to toggle", min_value=1, step=1)
    if st.button("Toggle Active/Inactive"):
        c = get_conn()
        try:
            cur = c.cursor()
            cur.execute(adapt_sql("UPDATE users SET is_active = 1 - is_active WHERE id=%s"), (uid,))
            c.commit()
        finally:
            if USE_POSTGRES:
                release_conn(c)
            else:
                c.close()
        st.success("User status updated!"); st.rerun()


def admin_bookings():
    st.markdown('<div class="section-header">📋 All Bookings</div>', unsafe_allow_html=True)
    df = df_query("""
        SELECT b.id, u.name as guest_name, p.title as property, r.room_number,
               b.check_in, b.check_out, b.booking_type, b.total_price,
               b.status, b.payment_method, b.payment_status, b.created_at
        FROM bookings b
        JOIN users u ON b.guest_id = u.id
        JOIN properties p ON b.property_id = p.id
        LEFT JOIN rooms r ON b.room_id = r.id
        ORDER BY b.created_at DESC
    """)

    if df.empty:
        st.info("No bookings yet.")
        return

    col1, col2, col3 = st.columns(3)
    with col1: st.markdown(metric_card(len(df), "Total Bookings", "📋"), unsafe_allow_html=True)
    with col2: st.markdown(metric_card(len(df[df['status']=='confirmed']), "Confirmed", "✅"), unsafe_allow_html=True)
    with col3: st.markdown(metric_card(f"₱{df[df['payment_status']=='paid']['total_price'].sum():,.0f}", "Collected", "💰"), unsafe_allow_html=True)

    st.markdown("---")
    st.caption("👁️ View only — admin cannot edit bookings per policy")
    st.dataframe(df, use_container_width=True, hide_index=True)


def admin_trends():
    st.markdown('<div class="section-header">📈 Platform Trends & ML Insights</div>', unsafe_allow_html=True)
    st.caption("AI-powered trend analysis across all platform properties — based on historical booking data and Philippine seasonal patterns.")

    rebuild_booking_history_from_real_data()

    props = df_query("SELECT id, title, city, type FROM properties WHERE status='approved'")

    if props.empty:
        st.info("No approved properties on the platform yet.")
        return

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
                    lambda r: datetime(int(float(r['year'])), int(float(r['month'])), 1).strftime("%b %Y"), axis=1
                )
                st.dataframe(
                    bt_df[['property', 'month_label', 'actual', 'predicted', 'error']].rename(columns={
                        'property': 'Property', 'month_label': 'Month',
                        'actual': 'Actual', 'predicted': 'Predicted', 'error': 'Error'
                    }),
                    use_container_width=True, hide_index=True
                )

    st.markdown("---")
    MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December']
    current_month = datetime.now().month

    st.markdown("### 🔥 All Properties — Month-by-Month Trend Analysis")
    selected_month_name = st.selectbox(
        "📅 Select a month to analyze platform-wide trends",
        MONTH_NAMES,
        index=current_month - 1,
        key="admin_trends_month_picker"
    )
    selected_month_num = MONTH_NAMES.index(selected_month_name) + 1
    st.caption(f"🤖 ML scores learned from 3 years of historical data — showing predictions for **{selected_month_name}**")

    all_scores = predict_trending_by_month(selected_month_num)

    if not all_scores:
        st.info("No trend data available yet.")
    else:
        df_scores = pd.DataFrame(all_scores)
        df_scores['short_title'] = df_scores['title'].apply(
            lambda t: t[:22] + '…' if len(t) > 22 else t
        )

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.markdown("**📊 Trend Score by Property**")
            st.bar_chart(df_scores.set_index('short_title')['trend_score'], height=260, color="#1a3c5e")
            st.caption("Higher = AI expects more demand this month")
        with col_c2:
            st.markdown("**🏠 Predicted Bookings**")
            st.bar_chart(df_scores.set_index('short_title')['predicted_bookings'], height=260, color="#e8a020")
            st.caption("Based on historical same-month avg × seasonal weight × growth trend")

        st.markdown(f"**🏆 Top Properties for {selected_month_name}**")
        top3 = all_scores[:3]
        cols = st.columns(len(top3))
        for i, t in enumerate(top3):
            medal = ["🥇", "🥈", "🥉"][i]
            no_data = t.get('years_of_data', 0) == 0 and t['trend_score'] == 0.0
            bg = "linear-gradient(135deg,#6b7280,#9ca3af)" if no_data else "linear-gradient(135deg,#1a3c5e,#2563a8)"
            icon = "🆕" if no_data else "🔥"
            with cols[i]:
                if no_data:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;padding:1.25rem;color:white;margin-bottom:1rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2.2rem;font-weight:700;font-family:'Playfair Display',serif">—</div>
                        <div style="font-weight:600;font-size:0.95rem;margin:0.2rem 0">{t['title']}</div>
                        <div style="font-size:0.8rem;opacity:0.85">
                            📍 {t['city']}<br>
                            📭 No bookings yet — score appears after first confirmed booking
                        </div>
                        <div style="position:absolute;top:1rem;right:1rem;font-size:1.4rem">{icon}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div style="background:{bg};border-radius:16px;padding:1.25rem;color:white;margin-bottom:1rem;position:relative">
                        <div style="font-size:0.72rem;opacity:0.7;text-transform:uppercase;letter-spacing:0.08em">{medal} Trend Score</div>
                        <div style="font-size:2.2rem;font-weight:700;font-family:'Playfair Display',serif">{t['trend_score']}</div>
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

    st.markdown("---")
    st.markdown("### 📆 Full Year Trend Score Heatmap — All Properties")
    st.caption("See how each property's ML trend score shifts month by month, learned from past booking patterns")

    year_rows = {}
    for m_num, m_name in enumerate(MONTH_NAMES, start=1):
        month_scores = predict_trending_by_month(m_num)
        for t in month_scores:
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
    st.markdown("### 📊 Deep Dive — Historical + 6-Month Forecast")
    selected_title = st.selectbox("Select a property to analyze:", props['title'].tolist())
    selected_row = props[props['title'] == selected_title].iloc[0]
    pid = int(float(selected_row['id']))

    hist = df_query("""
        SELECT month, year, total_bookings, total_revenue, avg_occupancy
        FROM booking_history
        WHERE property_id=%s
        ORDER BY year, month
    """, params=[pid])

    if hist.empty:
        st.info("No historical data available for this property yet.")
    else:
        hist['period'] = hist.apply(
            lambda r: datetime(int(float(r['year'])), int(float(r['month'])), 1).strftime("%b %Y"), axis=1
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
                        'ci_low': 'Low (CI)',
                        'ci_high': 'High (CI)',
                        'predicted_revenue': 'Est. Revenue (₱)',
                        'occupancy_rate': 'Occupancy (%)',
                        'confidence': 'Confidence'
                    }),
                    use_container_width=True,
                    hide_index=True
                )
                peak_f = df_f.loc[df_f['predicted_bookings'].idxmax()]
                st.success(f"🌟 Projected peak: **{peak_f['month']}** with ~{peak_f['predicted_bookings']} bookings and ₱{peak_f['predicted_revenue']:,.0f} revenue.")

    st.markdown("---")
    st.markdown("### 🗓️ Learned Seasonal Booking Weights")
    st.caption("Recency-weighted weights derived from actual booking history — blended with PH priors when data is sparse")
    learned_weights = learn_seasonal_weights()
    month_abbrs = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    df_season = pd.DataFrame({
        'Month': month_abbrs,
        'Demand Weight': [round(learned_weights.get(m, 0.8), 3) for m in range(1, 13)]
    })
    current_month_abbr = datetime.now().strftime("%b")
    current_month_num = datetime.now().month
    st.bar_chart(df_season.set_index('Month')['Demand Weight'], height=200)
    st.caption(f"📍 Current month: **{current_month_abbr}** — learned weight: **{learned_weights.get(current_month_num, '—')}** | Higher = more demand expected")
