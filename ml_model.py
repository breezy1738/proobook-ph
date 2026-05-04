import numpy as np
import pandas as pd
from database import get_conn, adapt_sql, df_query
from datetime import datetime
import calendar
import json
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _coerce_numeric(df, *cols):
    """Force columns to float/int — prevents Arrow string dtype issues with psycopg2."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# ─────────────────────────────────────────────────────────────────────────────
# SNAPSHOT PERSISTENCE — survives Streamlit Cloud redeploys via SQLite
# ─────────────────────────────────────────────────────────────────────────────

def _save_snapshot(key: str, value):
    from database import USE_POSTGRES
    conn = get_conn()
    c = conn.cursor()
    if USE_POSTGRES:
        c.execute("""
            INSERT INTO ml_snapshots (key, value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value, updated_at=CURRENT_TIMESTAMP
        """, (key, json.dumps(value)))
    else:
        c.execute("""
            INSERT INTO ml_snapshots (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """, (key, json.dumps(value)))
    conn.commit()
    conn.close()


def _load_snapshot(key: str, default=None):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(adapt_sql("SELECT value FROM ml_snapshots WHERE key=%s"), (key,))
        row = c.fetchone()
        conn.close()
        return json.loads(row['value']) if row else default
    except Exception:
        conn.close()
        return default


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Incremental real-time booking history update
# ─────────────────────────────────────────────────────────────────────────────

def process_new_booking(booking_id: int):
    """
    Incrementally update booking_history for a single newly confirmed booking.
    """
    from database import USE_POSTGRES, release_conn

    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(adapt_sql("SELECT id FROM booking_events WHERE booking_id=%s"), (booking_id,))
        if c.fetchone():
            return

        c.execute(adapt_sql("""
            SELECT b.property_id, b.check_in, b.check_out, b.total_price,
                   b.booking_type, COALESCE(b.is_open_ended,0) as is_open_ended
            FROM bookings b WHERE b.id=%s
        """), (booking_id,))
        row = c.fetchone()

        if not row or not row['check_in']:
            return

        ci = pd.to_datetime(row['check_in'])
        co = pd.to_datetime(row['check_out']) if row['check_out'] else ci + pd.Timedelta(days=1)
        if row['is_open_ended']:
            co = ci + pd.Timedelta(days=30)

        nights = max((co - ci).days, 1)
        daily_rev = row['total_price'] / nights
        prop_id = row['property_id']

        nightly = {}
        for d in range(nights):
            night = ci + pd.Timedelta(days=d)
            key = (night.year, night.month)
            nightly[key] = nightly.get(key, 0.0) + daily_rev

        for (year, month), rev in nightly.items():
            days_in_month = calendar.monthrange(year, month)[1]

            c.execute(adapt_sql("""
                SELECT id, total_bookings, total_revenue, avg_occupancy
                FROM booking_history WHERE property_id=%s AND year=%s AND month=%s
            """), (prop_id, year, month))
            existing = c.fetchone()

            nights_in_month = len([
                d for d in range(nights)
                if (ci + pd.Timedelta(days=d)).year == year
                and (ci + pd.Timedelta(days=d)).month == month
            ])

            if existing:
                new_booking_count = 1 if ci.year == year and ci.month == month else 0
                new_total_bookings = existing['total_bookings'] + new_booking_count
                new_total_revenue  = round(existing['total_revenue'] + rev, 2)
                new_occupancy      = round(min(nights_in_month / days_in_month + existing['avg_occupancy'], 1.0), 4)
                c.execute(adapt_sql("""
                    UPDATE booking_history
                    SET total_bookings=%s, total_revenue=%s, avg_occupancy=%s
                    WHERE property_id=%s AND year=%s AND month=%s
                """), (new_total_bookings, new_total_revenue, new_occupancy, prop_id, year, month))
            else:
                new_booking_count = 1 if ci.year == year and ci.month == month else 0
                new_occupancy = round(min(nights_in_month / days_in_month, 1.0), 4)
                c.execute(adapt_sql("""
                    INSERT INTO booking_history (property_id, month, year, total_bookings, total_revenue, avg_occupancy)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """), (prop_id, month, year, new_booking_count, round(rev, 2), new_occupancy))

        if USE_POSTGRES:
            c.execute(adapt_sql("""
                INSERT INTO booking_events
                    (booking_id, property_id, check_in, check_out, total_price, booking_type, is_open_ended)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (booking_id) DO NOTHING
            """), (booking_id, prop_id, row['check_in'], row['check_out'],
                  row['total_price'], row['booking_type'], row['is_open_ended']))
        else:
            c.execute(adapt_sql("""
                INSERT OR IGNORE INTO booking_events
                    (booking_id, property_id, check_in, check_out, total_price, booking_type, is_open_ended)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """), (booking_id, prop_id, row['check_in'], row['check_out'],
                  row['total_price'], row['booking_type'], row['is_open_ended']))

        conn.commit()
    finally:
        release_conn(conn)

    _save_snapshot('seasonal_weights_dirty', True)


def rebuild_booking_history_from_real_data():
    """
    Full rebuild — aggregates ALL confirmed bookings into booking_history.
    Called on app startup.
    """
    # Use df_query (SQLAlchemy/pandas) for all read queries — avoids
    # RealDictCursor vs sqlite3.Row incompatibilities entirely.
    count_df = df_query(
        "SELECT COUNT(*) as n FROM bookings WHERE status IN ('confirmed','pending')"
    )
    confirmed_count = int(count_df.iloc[0, 0]) if not count_df.empty else 0

    if confirmed_count == 0:
        return

    pending_df = df_query("""
        SELECT b.id FROM bookings b
        LEFT JOIN booking_events be ON b.id = be.booking_id
        WHERE b.status IN ('confirmed','pending')
          AND b.check_in IS NOT NULL
          AND be.id IS NULL
    """)

    for booking_id in pending_df['id'].tolist():
        process_new_booking(int(booking_id))

    _save_snapshot('seasonal_weights_dirty', True)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Learn seasonal weights FROM real data (recency-weighted)
# ─────────────────────────────────────────────────────────────────────────────

def learn_seasonal_weights():
    """
    Derive seasonal multipliers from historical booking_history data.
    Uses recency-weighted averaging: recent years count more than old ones.
    Results cached in ml_snapshots; invalidated on new bookings.
    """
    dirty = _load_snapshot('seasonal_weights_dirty', True)
    if not dirty:
        cached = _load_snapshot('seasonal_weights')
        if cached:
            return {int(k): v for k, v in cached.items()}

    df = df_query("""
        SELECT month, year, AVG(total_bookings) as avg_b
        FROM booking_history
        GROUP BY year, month
        ORDER BY year, month
    """)

    fallback = {
        1: 0.85, 2: 0.70, 3: 0.75, 4: 0.90,
        5: 0.95, 6: 1.00, 7: 1.00, 8: 0.85,
        9: 0.70, 10: 0.75, 11: 0.85, 12: 1.00
    }

    if df.empty or len(df) < 6:
        return fallback

    df = _coerce_numeric(df, 'year', 'month', 'avg_b')
    df['year']  = df['year'].fillna(0).astype(int)
    df['month'] = df['month'].fillna(0).astype(int)
    df = df[(df['year'] > 0) & (df['month'] > 0)].copy()

    # Guard: after filtering, df may be empty or year column all-NaN
    if df.empty or len(df) < 6 or df['year'].isna().all():
        return fallback

    max_year_val = df['year'].max()
    if pd.isna(max_year_val):
        return fallback
    max_year = int(max_year_val)
    decay    = 0.6

    weighted_sums = {m: 0.0 for m in range(1, 13)}
    weight_totals = {m: 0.0 for m in range(1, 13)}
    sample_counts = {m: 0   for m in range(1, 13)}

    for _, row in df.iterrows():
        m   = int(row['month'])
        yr  = int(row['year'])
        age = max_year - yr
        w   = decay ** age
        weighted_sums[m] += row['avg_b'] * w
        weight_totals[m] += w
        sample_counts[m] += 1

    monthly_wavg = {
        m: (weighted_sums[m] / weight_totals[m] if weight_totals[m] > 0 else 0.0)
        for m in range(1, 13)
    }

    overall_wavg = np.mean(list(monthly_wavg.values()))
    if overall_wavg == 0:
        return fallback

    learned = {}
    for m in range(1, 13):
        raw_weight = monthly_wavg[m] / overall_wavg
        n_years    = sample_counts[m]
        data_trust = min(n_years / 3.0, 1.0)
        blended    = data_trust * raw_weight + (1 - data_trust) * fallback[m]
        learned[m] = round(min(max(blended, 0.3), 1.5), 3)

    mean_w = np.mean(list(learned.values()))
    if mean_w > 0:
        learned = {m: round(v / mean_w, 3) for m, v in learned.items()}

    _save_snapshot('seasonal_weights', {str(k): v for k, v in learned.items()})
    _save_snapshot('seasonal_weights_dirty', False)

    return learned


# ─────────────────────────────────────────────────────────────────────────────
# MATH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _exponential_smooth(series: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    """Simple exponential smoothing — reduces noise before fitting trend slope."""
    smoothed = np.zeros_like(series, dtype=float)
    smoothed[0] = series[0]
    for i in range(1, len(series)):
        smoothed[i] = alpha * series[i] + (1 - alpha) * smoothed[i - 1]
    return smoothed


def _ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Ordinary least squares slope, safe against degenerate inputs."""
    n = len(x)
    if n < 2:
        return 0.0
    denom = n * np.dot(x, x) - x.sum() ** 2
    if abs(denom) < 1e-9:
        return 0.0
    return (n * np.dot(x, y) - x.sum() * y.sum()) / denom


def _holt_winters_double(series: np.ndarray, alpha: float = 0.4, beta: float = 0.2) -> tuple:
    """
    Holt's double exponential smoothing (trend + level).
    Returns (smoothed_series, final_level, final_trend) so we can project
    forward. Better than simple EMA at capturing accelerating/decelerating trends.
    """
    if len(series) < 2:
        return series, series[-1], 0.0

    level = series[0]
    trend = series[1] - series[0]
    smoothed = [level + trend]

    for val in series[1:]:
        prev_level = level
        level = alpha * val + (1 - alpha) * (level + trend)
        trend = beta  * (level - prev_level) + (1 - beta) * trend
        smoothed.append(level + trend)

    return np.array(smoothed, dtype=float), level, trend


def _yoy_growth_rate(df_prop: pd.DataFrame, target_month: int) -> float:
    """
    Year-over-year growth rate for a specific month.
    Compares the two most recent years that have data for target_month.
    Returns a rate: 0.10 = +10% growth, -0.15 = -15% decline.
    Falls back to 0.0 if insufficient data.
    """
    month_data = df_prop[df_prop['month'] == target_month].sort_values('year')
    if len(month_data) < 2:
        return 0.0

    recent_two = month_data.tail(2)
    older_val  = float(recent_two.iloc[0]['total_bookings'])
    newer_val  = float(recent_two.iloc[1]['total_bookings'])

    if older_val < 1e-6:
        return 0.0
    return (newer_val - older_val) / older_val


def _recency_weighted_same_month_avg(df_prop: pd.DataFrame, target_month: int,
                                     decay: float = 0.55) -> tuple:
    """
    Recency-weighted average of total_bookings for a specific month.
    More recent occurrences of that month are weighted higher.
    Returns (weighted_avg, n_samples, std_dev).
    """
    month_data = df_prop[df_prop['month'] == target_month].sort_values('year')
    if month_data.empty:
        return 0.0, 0, 0.0

    vals   = month_data['total_bookings'].values.astype(float)
    n      = len(vals)
    # weights: most recent = 1, going back: decay^1, decay^2, ...
    weights = np.array([decay ** (n - 1 - i) for i in range(n)])
    weights /= weights.sum()

    wavg  = float(np.dot(vals, weights))
    std   = float(np.sqrt(np.dot(weights, (vals - wavg) ** 2)))  # weighted std
    return wavg, n, std


def _booking_velocity(df_prop: pd.DataFrame) -> float:
    """
    Booking velocity = acceleration of recent bookings (2nd derivative).
    Positive = speeding up, Negative = slowing down.
    Uses the last 6 months of smoothed data.
    Normalised to [-1, 1] range.
    """
    raw_y = df_prop['total_bookings'].values.astype(float)
    if len(raw_y) < 4:
        return 0.0

    tail = raw_y[-min(6, len(raw_y)):]
    smoothed = _exponential_smooth(tail, alpha=0.5)

    if len(smoothed) < 3:
        return 0.0

    # First differences (velocity), then second difference (acceleration)
    diffs  = np.diff(smoothed)
    accel  = np.diff(diffs)
    if len(accel) == 0:
        return 0.0

    avg_accel = accel.mean()
    # Normalise by the mean booking level to get a relative measure
    mean_level = max(smoothed.mean(), 1e-6)
    normalised = avg_accel / mean_level
    return float(np.clip(normalised, -1.0, 1.0))


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Backtesting: measure real accuracy
# ─────────────────────────────────────────────────────────────────────────────

def run_backtest():
    """
    Hold-out validation: train on all data except the last 3 months,
    predict those 3 months, compare vs actual.
    Returns MAE, RMSE, MAPE and per-prediction detail rows.
    Now uses the improved scoring logic for consistency.
    """
    df = df_query("""
        SELECT bh.property_id, bh.month, bh.year, bh.total_bookings, p.title
        FROM booking_history bh
        JOIN properties p ON bh.property_id = p.id
        WHERE p.status = 'approved'
        ORDER BY bh.year, bh.month
    """)

    if df.empty or len(df) < 6:
        return None

    df = _coerce_numeric(df, 'year', 'month', 'total_bookings')
    df['year']  = df['year'].fillna(0).astype(int)
    df['month'] = df['month'].fillna(0).astype(int)
    df = df[(df['year'] > 0) & (df['month'] > 0)].copy()
    df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2) + '-01')
    max_date = df['date'].max()
    cutoff   = max_date - pd.DateOffset(months=3)

    train = df[df['date'] <= cutoff]
    test  = df[df['date'] >  cutoff]

    if train.empty or test.empty:
        return None

    seasonal_weights = learn_seasonal_weights()
    results = []

    for prop_id in test['property_id'].unique():
        prop_train = train[train['property_id'] == prop_id].sort_values(['year', 'month'])
        prop_test  = test[test['property_id'] == prop_id]

        if prop_train.empty:
            continue

        for _, row in prop_test.iterrows():
            m = int(row['month'])

            # Use the improved month-specific prediction helpers
            wavg, n_samples, _ = _recency_weighted_same_month_avg(prop_train, m)
            yoy_rate            = _yoy_growth_rate(prop_train, m)
            seasonal            = seasonal_weights.get(m, 0.8)

            if wavg == 0:
                wavg = prop_train['total_bookings'].mean()

            # Apply YoY growth once (most recent signal)
            yoy_capped = np.clip(yoy_rate, -0.4, 0.6)
            predicted  = wavg * seasonal * (1 + yoy_capped * 0.5)
            actual     = row['total_bookings']
            error      = predicted - actual

            results.append({
                'property':    row['title'],
                'month':       m,
                'year':        int(row['year']),
                'predicted':   round(predicted, 1),
                'actual':      actual,
                'error':       round(error, 2),
                'abs_error':   abs(error),
            })

    if not results:
        return None

    rdf  = pd.DataFrame(results)
    mae  = round(rdf['abs_error'].mean(), 2)
    rmse = round(np.sqrt((rdf['error'] ** 2).mean()), 2)
    mape_vals = rdf[rdf['actual'] > 0].apply(
        lambda r: abs(r['error']) / r['actual'] * 100, axis=1)
    mape = round(mape_vals.mean(), 1) if len(mape_vals) > 0 else None
    accuracy_pct = round(max(0, 100 - (mape or 100)), 1) if mape else None

    return {
        'mae':          mae,
        'rmse':         rmse,
        'mape':         mape,
        'accuracy_pct': accuracy_pct,
        'n_samples':    len(rdf),
        'results':      rdf.to_dict('records'),
        'has_real_data': True
    }


def get_data_quality_report():
    """
    How much real vs synthetic data exists in booking_history.
    """
    r1 = df_query("SELECT COUNT(*) as n FROM bookings WHERE status IN ('confirmed', 'pending')")
    real_bookings = int(r1.iloc[0, 0]) if not r1.empty else 0

    r2 = df_query("SELECT COUNT(*) as n FROM booking_history")
    history_rows = int(r2.iloc[0, 0]) if not r2.empty else 0

    r3 = df_query("SELECT COUNT(DISTINCT property_id) as n FROM bookings WHERE status='confirmed'")
    props_with_data = int(r3.iloc[0, 0]) if not r3.empty else 0

    r4 = df_query("""
        SELECT MIN(check_in) as earliest, MAX(check_in) as latest
        FROM bookings WHERE status='confirmed'
    """)
    earliest = r4.iloc[0]['earliest'] if not r4.empty and r4.iloc[0]['earliest'] else None
    latest   = r4.iloc[0]['latest']   if not r4.empty and r4.iloc[0]['latest']   else None

    return {
        'real_confirmed_bookings':   real_bookings,
        'history_rows':              history_rows,
        'properties_with_real_data': props_with_data,
        'earliest_booking':          earliest,
        'latest_booking':            latest,
        'is_synthetic':              real_bookings == 0,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CORE SCORING ENGINE — shared by STEP 4 and STEP 4b
# ─────────────────────────────────────────────────────────────────────────────

def _score_property_for_month(prop_df: pd.DataFrame, target_month: int,
                               seasonal_weights: dict, price_p33: float,
                               price_p66: float) -> dict:
    """
    Upgraded composite scoring for ONE property for a given month.

    Signal breakdown (weights):
      0.28 — YoY same-month growth  (how did this exact month grow year-on-year?)
      0.24 — Recency-weighted same-month history  (what normally happens in this month?)
      0.20 — Learned seasonal multiplier          (platform-wide pattern for this month)
      0.16 — Revenue growth trajectory            (is the property growing overall?)
      0.12 — Booking velocity / acceleration      (is demand speeding up lately?)

    All components are:
      • Recency-weighted (recent data > old data)
      • Confidence-scaled (more data = more trust in the signal)
      • Occupancy-headroom capped (near-full properties can't grow much more)
      • Price-tier adjusted
    """
    prop_df = prop_df.sort_values(['year', 'month']).copy()
    n_months = len(prop_df)

    if n_months < 1:
        return None

    # ── Raw booking series ─────────────────────────────────────────────────
    raw_y = prop_df['total_bookings'].values.astype(float)
    max_bookings = raw_y.max() or 1.0

    # ── Holt-Winters double smoothing for trend level + slope ──────────────
    smoothed_y, hw_level, hw_trend = _holt_winters_double(raw_y, alpha=0.4, beta=0.2)
    ols_x    = np.arange(len(smoothed_y))
    ols_slope = _ols_slope(ols_x, smoothed_y)
    recent_avg = float(smoothed_y[-3:].mean()) if n_months >= 3 else float(smoothed_y.mean())

    # ── 1. YoY same-month growth rate ─────────────────────────────────────
    yoy_rate   = _yoy_growth_rate(prop_df, target_month)
    # Dampen extreme outliers: cap at +80% / -50%
    yoy_capped = float(np.clip(yoy_rate, -0.50, 0.80))
    # Normalise to [0, 1] for composite: 0% growth → 0.5, +80% → 1.0, -50% → 0.0
    yoy_component = (yoy_capped + 0.50) / 1.30
    yoy_component = float(np.clip(yoy_component, 0.0, 1.0))

    # ── 2. Recency-weighted same-month historical average ─────────────────
    rw_avg, n_same_month, rw_std = _recency_weighted_same_month_avg(prop_df, target_month)
    if rw_avg == 0:
        rw_avg = recent_avg
    history_component = rw_avg / max_bookings  # normalise to [0, 1]
    history_component = float(np.clip(history_component, 0.0, 1.0))

    # ── 3. Seasonal multiplier ─────────────────────────────────────────────
    seasonal_mult = seasonal_weights.get(target_month, 0.8)
    seasonal_component = min(seasonal_mult / 1.2, 1.0)

    # ── 4. Revenue growth trajectory ──────────────────────────────────────
    rev_y       = prop_df['total_revenue'].values.astype(float)
    _, rev_level, rev_trend = _holt_winters_double(rev_y, alpha=0.4, beta=0.2)
    rev_growth  = (rev_trend / (rev_level + 1e-9))  # relative trend per period
    rev_component = float(np.clip((rev_growth + 0.1) / 0.3, 0.0, 1.0))

    # ── 5. Booking velocity / acceleration ────────────────────────────────
    velocity = _booking_velocity(prop_df)
    velocity_component = float((velocity + 1.0) / 2.0)  # map [-1,1] → [0,1]

    # ── Occupancy headroom cap ─────────────────────────────────────────────
    # High occupancy → less room to grow → dampen growth signals
    recent_occ  = float(prop_df['avg_occupancy'].tail(3).mean())
    occ_headroom = max(0.0, 1.0 - recent_occ)
    # Growth-sensitive components get capped by occupancy headroom
    occ_cap = float(min(occ_headroom * 2.5, 1.0))

    # Apply occupancy cap to growth-sensitive signals only (1, 4, 5)
    yoy_component      *= occ_cap if recent_occ > 0.7 else 1.0
    rev_component      *= occ_cap if recent_occ > 0.7 else 1.0
    velocity_component  = velocity_component * occ_cap if recent_occ > 0.7 else velocity_component

    # ── Confidence weight by data richness ────────────────────────────────
    # 36 months (3 years) of data = full confidence
    data_confidence = float(min(n_months / 36.0, 1.0))
    # For same-month signals: need at least 2 years for good estimate
    month_confidence = float(min(n_same_month / 2.0, 1.0))

    # ── Price-tier elasticity ─────────────────────────────────────────────
    prop_price = float(prop_df['nightly_price'].iloc[-1])
    if prop_price <= price_p33:
        price_elasticity = 1.10   # budget: volume-driven
    elif prop_price <= price_p66:
        price_elasticity = 1.00   # mid: neutral
    else:
        price_elasticity = 0.90   # luxury: revenue-driven

    # ── Composite score ────────────────────────────────────────────────────
    # YoY growth is downweighted when same-month data is scarce
    effective_yoy_weight = 0.28 * month_confidence
    effective_hist_weight = 0.24
    remaining = 1.0 - effective_yoy_weight - effective_hist_weight

    raw_score = (
        effective_yoy_weight   * yoy_component       +
        effective_hist_weight  * history_component   +
        remaining * 0.40       * seasonal_component  +
        remaining * 0.35       * rev_component       +
        remaining * 0.25       * velocity_component
    )

    # Blend toward seasonal prior when data is thin
    seasonal_prior = seasonal_component * 0.5
    trend_score    = (data_confidence * raw_score +
                      (1 - data_confidence) * seasonal_prior)
    trend_score   *= price_elasticity
    trend_score    = float(np.clip(trend_score, 0.0, 1.0))

    # ── Predicted bookings ─────────────────────────────────────────────────
    # Base = recency-weighted same-month average (most accurate for that month)
    # If no same-month data: fall back to Holt-Winters projected level
    base_pred = rw_avg if n_same_month > 0 else max(hw_level + hw_trend, 0)

    # Apply YoY growth partially (50% weight — don't overfit to 1 year jump)
    yoy_adj    = 1.0 + yoy_capped * 0.50
    predicted  = base_pred * seasonal_mult * yoy_adj
    # Cap at 15% above historical peak to avoid absurd extrapolation
    max_cap    = max_bookings * 1.15
    predicted  = float(np.clip(predicted, 0.0, max_cap))

    last_row = prop_df.iloc[-1]
    return {
        'property_id':               int(last_row['property_id']) if 'property_id' in prop_df.columns else None,
        'title':                     last_row['title'],
        'city':                      last_row['city'],
        'type':                      last_row['type'],
        'nightly_price':             float(last_row.get('nightly_price', 0)),
        'monthly_price':             float(last_row.get('monthly_price', 0)),
        'images':                    last_row.get('images', ''),
        'trend_score':               round(trend_score * 100, 1),
        'predicted_bookings':        int(round(predicted)),
        'recent_avg_bookings':       round(recent_avg, 1),
        'yoy_growth_rate':           round(yoy_rate * 100, 1),      # % for display
        'slope':                     round(ols_slope, 3),
        'seasonal_mult':             round(seasonal_mult, 3),
        'avg_occupancy':             round(recent_occ * 100, 1),
        'data_confidence':           round(data_confidence * 100, 0),
        'years_of_data':             int(prop_df['year'].nunique()),
        'historical_same_month_avg': round(rw_avg, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Predict trending properties for CURRENT month
# ─────────────────────────────────────────────────────────────────────────────

def predict_trending_properties(top_n=4):
    """
    Score all approved properties for the current month and return top N.
    Uses the upgraded _score_property_for_month engine.
    """
    current_month = datetime.now().month

    df = df_query("""
        SELECT bh.property_id, bh.month, bh.year, bh.total_bookings,
               bh.total_revenue, bh.avg_occupancy,
               p.title, p.city, p.type, p.nightly_price, p.monthly_price, p.images, p.id
        FROM booking_history bh
        JOIN properties p ON bh.property_id = p.id
        WHERE p.status = 'approved' AND p.is_active = 1
        ORDER BY bh.year, bh.month
    """)

    if df.empty:
        return []

    df = _coerce_numeric(df, 'year', 'month', 'total_bookings', 'total_revenue',
                         'avg_occupancy', 'nightly_price', 'monthly_price')
    df['year']  = df['year'].fillna(0).astype(int)
    df['month'] = df['month'].fillna(0).astype(int)
    df = df[(df['year'] > 0) & (df['month'] > 0)].copy()

    seasonal_weights = learn_seasonal_weights()
    all_prices = df.groupby('property_id')['nightly_price'].first()
    price_p33  = float(all_prices.quantile(0.33))
    price_p66  = float(all_prices.quantile(0.66))

    property_scores = []

    for prop_id in df['property_id'].unique():
        prop_df = df[df['property_id'] == prop_id].copy()
        prop_df['property_id'] = prop_id
        result = _score_property_for_month(prop_df, current_month, seasonal_weights,
                                           price_p33, price_p66)
        if result:
            result['property_id'] = int(prop_id)
            property_scores.append(result)

    property_scores.sort(key=lambda x: x['trend_score'], reverse=True)
    return property_scores[:top_n]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4b — Predict trending properties for ANY chosen month
# ─────────────────────────────────────────────────────────────────────────────

def predict_trending_by_month(selected_month: int):
    """
    Score ALL approved properties for a user-selected month (1-12).
    Uses the same upgraded composite formula as predict_trending_properties.
    Returns full list sorted by trend_score descending.
    """
    df = df_query("""
        SELECT bh.property_id, bh.month, bh.year, bh.total_bookings,
               bh.total_revenue, bh.avg_occupancy,
               p.title, p.city, p.type, p.nightly_price, p.monthly_price
        FROM booking_history bh
        JOIN properties p ON bh.property_id = p.id
        WHERE p.status = 'approved' AND p.is_active = 1
        ORDER BY bh.year, bh.month
    """)

    if df.empty:
        return []

    df = _coerce_numeric(df, 'year', 'month', 'total_bookings', 'total_revenue',
                         'avg_occupancy', 'nightly_price', 'monthly_price')
    df['year']  = df['year'].fillna(0).astype(int)
    df['month'] = df['month'].fillna(0).astype(int)
    df = df[(df['year'] > 0) & (df['month'] > 0)].copy()

    seasonal_weights = learn_seasonal_weights()
    all_prices = df.groupby('property_id')['nightly_price'].first()
    price_p33  = float(all_prices.quantile(0.33))
    price_p66  = float(all_prices.quantile(0.66))

    property_scores = []

    for prop_id in df['property_id'].unique():
        prop_df = df[df['property_id'] == prop_id].copy()
        prop_df['property_id'] = prop_id
        result = _score_property_for_month(prop_df, selected_month, seasonal_weights,
                                           price_p33, price_p66)
        if result:
            result['property_id'] = int(prop_id)
            # Add same-month occupancy for display
            same_month_occ = prop_df[prop_df['month'] == selected_month]['avg_occupancy']
            result['avg_occupancy'] = round(same_month_occ.mean() * 100, 1) if len(same_month_occ) > 0 \
                                      else result['avg_occupancy']
            property_scores.append(result)

    # Include approved properties with zero history so they appear in rankings
    scored_ids = {s['property_id'] for s in property_scores}
    unscored = df_query("""
        SELECT p.id, p.title, p.city, p.type, p.nightly_price, p.monthly_price
        FROM properties p
        WHERE p.status = 'approved' AND p.is_active = 1
          AND p.id NOT IN (
              SELECT DISTINCT property_id FROM booking_history
          )
    """)

    seasonal_mult = seasonal_weights.get(selected_month, 0.8)
    for _, row in unscored.iterrows():
        if int(row['id']) not in scored_ids:
            property_scores.append({
                'property_id':               int(row['id']),
                'title':                     row['title'],
                'city':                      row['city'],
                'type':                      row['type'],
                'trend_score':               0.0,
                'predicted_bookings':        0,
                'avg_occupancy':             0.0,
                'seasonal_mult':             round(seasonal_mult, 3),
                'historical_same_month_avg': 0.0,
                'yoy_growth_rate':           0.0,
                'years_of_data':             0,
                'slope':                     0.0,
                'data_confidence':           0.0,
            })

    property_scores.sort(key=lambda x: x['trend_score'], reverse=True)
    return property_scores


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Improved 6-month forecast using Holt-Winters + YoY signals
# ─────────────────────────────────────────────────────────────────────────────

def get_monthly_forecast(property_id):
    """
    Per-property 6-month forward forecast.

    Improvements over previous version:
    - Holt-Winters double smoothing replaces simple EMA + OLS slope
    - YoY same-month growth rate incorporated (strongest single predictor)
    - Recency-weighted same-month average as base (instead of simple mean)
    - Confidence intervals use recency-weighted std dev, not simple std
    - Booking velocity (acceleration) signal added for near-term months
    - Momentum dampening uses 1/(1+sqrt(horizon)) as before
    """
    property_id = int(property_id)
    df = df_query("""
        SELECT month, year, total_bookings, total_revenue, avg_occupancy
        FROM booking_history
        WHERE property_id = %s
        ORDER BY year, month
    """, params=[property_id])

    if df.empty:
        return []

    df = _coerce_numeric(df, 'year', 'month', 'total_bookings', 'total_revenue', 'avg_occupancy')
    df['year']  = df['year'].fillna(0).astype(int)
    df['month'] = df['month'].fillna(0).astype(int)
    df = df[(df['year'] > 0) & (df['month'] > 0)].copy()

    # Add property_id column so _recency_weighted helpers work
    df['property_id'] = property_id

    seasonal_weights = learn_seasonal_weights()
    current_month    = datetime.now().month
    current_year     = datetime.now().year

    # Holt-Winters for overall trend momentum
    raw_y = df['total_bookings'].values.astype(float)
    _, hw_level, hw_trend = _holt_winters_double(raw_y, alpha=0.4, beta=0.2)

    # Normalised momentum
    recent_avg = float(raw_y[-3:].mean()) if len(raw_y) >= 3 else float(raw_y.mean())
    momentum   = float(np.clip(hw_trend / (recent_avg + 1e-9), -0.5, 0.5))

    # Revenue Holt-Winters
    rev_y = df['total_revenue'].values.astype(float)
    _, rev_level, rev_trend = _holt_winters_double(rev_y, alpha=0.4, beta=0.2)

    # Booking velocity (current acceleration)
    velocity = _booking_velocity(df)

    forecasts = []
    for i in range(6):
        m     = ((current_month - 1 + i) % 12) + 1
        y_val = current_year + (current_month - 1 + i) // 12

        # Recency-weighted same-month stats
        rw_avg, n_same, rw_std   = _recency_weighted_same_month_avg(df, m)
        rw_rev, n_rev, _          = _recency_weighted_same_month_avg(
            df.drop(columns=['total_bookings']).rename(columns={'total_revenue': 'total_bookings'}), m)
        # occupancy
        same_occ = df[df['month'] == m]['avg_occupancy']
        base_occ = float(same_occ.mean()) if len(same_occ) > 0 else float(df['avg_occupancy'].mean())

        # YoY growth for this month
        yoy_rate  = _yoy_growth_rate(df, m)
        yoy_adj   = 1.0 + float(np.clip(yoy_rate, -0.5, 0.8)) * 0.50

        if rw_avg == 0:
            rw_avg = max(hw_level, 0)
        if rw_rev == 0:
            rw_rev = max(rev_level, 0)

        seasonal = seasonal_weights.get(m, 0.8)

        # Momentum dampens with sqrt of horizon
        horizon_damp  = 1.0 / (1.0 + np.sqrt(i))
        # Velocity only relevant for near-term (first 2 months)
        vel_factor    = 1.0 + velocity * 0.08 * (1.0 if i < 2 else 0.0)

        trend_factor  = 1.0 + momentum * 0.10 * horizon_damp
        trend_factor  = float(np.clip(trend_factor, 0.5, 2.0))

        pred_bookings = max(rw_avg  * seasonal * yoy_adj * trend_factor * vel_factor, 0)
        pred_revenue  = max(rw_rev  * seasonal * yoy_adj * trend_factor, 0)
        pred_occ      = float(np.clip(base_occ * trend_factor, 0.0, 0.98)) * 100

        # Confidence interval: recency-weighted std scaled by seasonal
        ci_spread = rw_std * seasonal * (1 + 0.1 * i)  # widen further out
        ci_low    = max(pred_bookings - ci_spread, 0)
        ci_high   = pred_bookings + ci_spread

        confidence = ('High'   if n_same >= 3 else
                      'Medium' if n_same >= 1 else 'Low')

        forecasts.append({
            'month':              datetime(y_val, m, 1).strftime("%b %Y"),
            'predicted_bookings': round(pred_bookings, 1),
            'ci_low':             round(ci_low, 1),
            'ci_high':            round(ci_high, 1),
            'predicted_revenue':  round(pred_revenue, 0),
            'occupancy_rate':     round(pred_occ, 1),
            'yoy_growth_rate':    round(yoy_rate * 100, 1),
            'confidence':         confidence,
        })

    return forecasts


# ─────────────────────────────────────────────────────────────────────────────
# Helpers (kept for compatibility with admin_pages / owner_pages)
# ─────────────────────────────────────────────────────────────────────────────

def get_historical_data():
    df = df_query("""
        SELECT bh.*, p.city, p.type, p.title
        FROM booking_history bh
        JOIN properties p ON bh.property_id = p.id
        WHERE p.status = 'approved'
    """)
    return df


def get_city_demand_heatmap():
    current_month = datetime.now().month
    df = df_query("""
        SELECT p.city, SUM(bh.total_bookings) as bookings, SUM(bh.total_revenue) as revenue
        FROM booking_history bh
        JOIN properties p ON bh.property_id = p.id
        WHERE bh.month = %s AND p.status = 'approved'
        GROUP BY p.city
        ORDER BY bookings DESC
    """, params=[current_month])
    return df.to_dict('records')


def get_seasonal_insights():
    df = df_query("""
        SELECT month, AVG(total_bookings) as avg_bookings, AVG(avg_occupancy) as avg_occupancy
        FROM booking_history
        GROUP BY month
        ORDER BY month
    """)
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    result = []
    for _, row in df.iterrows():
        result.append({
            'month':         months[int(row['month']) - 1],
            'avg_bookings':  round(row['avg_bookings'], 1),
            'avg_occupancy': round(row['avg_occupancy'] * 100, 1)
        })
    return result