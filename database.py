"""
database.py  —  PropBook PH
Supports BOTH SQLite (local dev) and PostgreSQL (Supabase / production).

Set the environment variable  DATABASE_URL  to a PostgreSQL connection string
to switch to Postgres automatically.  If the variable is absent the app falls
back to the local SQLite file  propbook.db  so local development still works
without any extra setup.

Streamlit Cloud → add this secret in the app dashboard:
    DATABASE_URL = "postgresql://user:password@host:5432/dbname"
"""

import os
import hashlib
import random
import math
from contextlib import contextmanager

# ── Driver selection ───────────────────────────────────────────────────────────
def _get_database_url() -> str:
    """
    Read DATABASE_URL from environment or Streamlit secrets.
    On Streamlit Cloud, secrets are NOT automatically injected into os.environ,
    so we must check st.secrets explicitly as a fallback.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets["DATABASE_URL"] if "DATABASE_URL" in st.secrets else ""
        except Exception:
            pass
    return url

DATABASE_URL = _get_database_url()

USE_POSTGRES = bool(DATABASE_URL)

from sqlalchemy import create_engine, text as sa_text
_SA_ENGINE = None  # lazy-initialised once

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras          # RealDictCursor
else:
    import sqlite3


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _pg_conn():
    """Open a psycopg2 connection with RealDictRow factory."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def get_conn():
    """
    Return a live DB connection.
    • Postgres  → psycopg2 connection (rows behave like dicts)
    • SQLite    → sqlite3 connection  (rows behave like dicts via Row factory)
    """
    if USE_POSTGRES:
        return _pg_conn()
    else:
        conn = sqlite3.connect("propbook.db", check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn


def get_engine():
    """
    Return a SQLAlchemy engine — required for pd.read_sql_query on Postgres.
    SQLite: uses the same file path.
    Postgres: built from DATABASE_URL (cached globally).
    """
    global _SA_ENGINE
    if USE_POSTGRES:
        if _SA_ENGINE is None:
            # psycopg2 dialect; future=False keeps legacy behaviour compatible
            pg_url = DATABASE_URL
            # SQLAlchemy needs postgresql:// not postgres://
            if pg_url.startswith("postgres://"):
                pg_url = pg_url.replace("postgres://", "postgresql://", 1)
            _SA_ENGINE = create_engine(pg_url, pool_pre_ping=True)
        return _SA_ENGINE
    else:
        return create_engine("sqlite:///propbook.db")


def release_conn(conn):
    """
    Close / release a DB connection.
    • Postgres  → closes the psycopg2 connection (return to pool if pooling is added later)
    • SQLite    → closes the connection
    Call this in every finally block instead of conn.close() for forward-compatibility.
    """
    try:
        conn.close()
    except Exception:
        pass


def df_query(sql: str, params=None):
    """
    Execute a SELECT and return a pandas DataFrame.
    Works correctly for both SQLite and PostgreSQL.

    SQLAlchemy 2.x + pandas requires named bindparams (:p0, :p1 …) when
    passing parameters through sa_text().  This helper converts any positional
    placeholders (%s or ?) in the SQL string to :p0, :p1, … and builds the
    corresponding dict so pd.read_sql_query always receives valid input.
    """
    import pandas as pd
    import re

    engine = get_engine()

    if params:
        # Replace every positional placeholder (%s or ?) with :p0, :p1, …
        counter = {"n": 0}

        def _replace(_match):
            key = f"p{counter['n']}"
            counter["n"] += 1
            return f":{key}"

        named_sql = re.sub(r"%s|\?", _replace, sql)
        param_dict = {f"p{i}": v for i, v in enumerate(params)}
        result = pd.read_sql_query(sa_text(named_sql), engine, params=param_dict)
    else:
        result = pd.read_sql_query(sa_text(sql), engine)

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  SQL dialect helpers  (SQLite uses ? placeholders, Postgres uses %s)
# ─────────────────────────────────────────────────────────────────────────────

def _ph(n: int = 1) -> str:
    """Return n comma-separated placeholders for the active driver."""
    ph = "%s" if USE_POSTGRES else "?"
    return ", ".join([ph] * n)


def _p() -> str:
    """Single placeholder."""
    return "%s" if USE_POSTGRES else "?"


def adapt_sql(sql: str) -> str:
    """
    Translate a SQL string written with %s placeholders to the correct
    dialect for the active driver.
    - Postgres (psycopg2): keeps %s as-is
    - SQLite:              replaces %s with ?
    Also normalises :param style → ? for SQLite (needed by SQLAlchemy text()).
    Call this on every SQL string that contains %s before passing to cursor.execute().
    """
    if USE_POSTGRES:
        return sql
    return sql.replace("%s", "?")


# ─────────────────────────────────────────────────────────────────────────────
#  Schema DDL — written for both dialects
# ─────────────────────────────────────────────────────────────────────────────

_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT UNIQUE NOT NULL,
    password    TEXT NOT NULL,
    role        TEXT NOT NULL DEFAULT 'guest',
    phone       TEXT,
    avatar      TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active   INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS properties (
    id            SERIAL PRIMARY KEY,
    owner_id      INTEGER NOT NULL REFERENCES users(id),
    title         TEXT NOT NULL,
    description   TEXT,
    type          TEXT NOT NULL,
    address       TEXT NOT NULL,
    city          TEXT NOT NULL,
    barangay      TEXT,
    province      TEXT,
    latitude      REAL,
    longitude     REAL,
    nightly_price REAL NOT NULL,
    monthly_price REAL NOT NULL,
    max_guests    INTEGER DEFAULT 2,
    bedrooms      INTEGER DEFAULT 1,
    bathrooms     INTEGER DEFAULT 1,
    amenities     TEXT,
    images        TEXT,
    status        TEXT DEFAULT 'pending',
    is_active     INTEGER DEFAULT 1,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rooms (
    id           SERIAL PRIMARY KEY,
    property_id  INTEGER NOT NULL REFERENCES properties(id),
    room_number  TEXT NOT NULL,
    floor        INTEGER DEFAULT 1,
    room_type    TEXT DEFAULT 'standard',
    capacity     INTEGER DEFAULT 2,
    nightly_price REAL,
    monthly_price REAL,
    is_available  INTEGER DEFAULT 1,
    description   TEXT
);

CREATE TABLE IF NOT EXISTS bookings (
    id              SERIAL PRIMARY KEY,
    guest_id        INTEGER NOT NULL REFERENCES users(id),
    property_id     INTEGER NOT NULL REFERENCES properties(id),
    room_id         INTEGER REFERENCES rooms(id),
    check_in        DATE NOT NULL,
    check_out       DATE,
    booking_type    TEXT DEFAULT 'nightly',
    total_price     REAL NOT NULL,
    down_payment    REAL DEFAULT 0,
    balance_due     REAL DEFAULT 0,
    is_open_ended   INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    payment_method  TEXT DEFAULT 'walk-in',
    payment_status  TEXT DEFAULT 'unpaid',
    special_requests TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    id          SERIAL PRIMARY KEY,
    booking_id  INTEGER NOT NULL REFERENCES bookings(id),
    guest_id    INTEGER NOT NULL REFERENCES users(id),
    property_id INTEGER NOT NULL REFERENCES properties(id),
    rating      INTEGER NOT NULL,
    comment     TEXT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_history (
    id             SERIAL PRIMARY KEY,
    property_id    INTEGER NOT NULL REFERENCES properties(id),
    month          INTEGER NOT NULL,
    year           INTEGER NOT NULL,
    total_bookings INTEGER DEFAULT 0,
    total_revenue  REAL DEFAULT 0,
    avg_occupancy  REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ml_snapshots (
    id         SERIAL PRIMARY KEY,
    key        TEXT UNIQUE NOT NULL,
    value      TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_events (
    id           SERIAL PRIMARY KEY,
    booking_id   INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
    property_id  INTEGER NOT NULL REFERENCES properties(id),
    check_in     DATE NOT NULL,
    check_out    DATE,
    total_price  REAL NOT NULL,
    booking_type TEXT,
    is_open_ended INTEGER DEFAULT 0,
    processed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'guest',
    phone TEXT,
    avatar TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    barangay TEXT,
    province TEXT,
    latitude REAL,
    longitude REAL,
    nightly_price REAL NOT NULL,
    monthly_price REAL NOT NULL,
    max_guests INTEGER DEFAULT 2,
    bedrooms INTEGER DEFAULT 1,
    bathrooms INTEGER DEFAULT 1,
    amenities TEXT,
    images TEXT,
    status TEXT DEFAULT 'pending',
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    room_number TEXT NOT NULL,
    floor INTEGER DEFAULT 1,
    room_type TEXT DEFAULT 'standard',
    capacity INTEGER DEFAULT 2,
    nightly_price REAL,
    monthly_price REAL,
    is_available INTEGER DEFAULT 1,
    description TEXT,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guest_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    room_id INTEGER,
    check_in DATE NOT NULL,
    check_out DATE,
    booking_type TEXT DEFAULT 'nightly',
    total_price REAL NOT NULL,
    down_payment REAL DEFAULT 0,
    balance_due REAL DEFAULT 0,
    is_open_ended INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    payment_method TEXT DEFAULT 'walk-in',
    payment_status TEXT DEFAULT 'unpaid',
    special_requests TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guest_id) REFERENCES users(id),
    FOREIGN KEY (property_id) REFERENCES properties(id),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL,
    guest_id INTEGER NOT NULL,
    property_id INTEGER NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (guest_id) REFERENCES users(id),
    FOREIGN KEY (property_id) REFERENCES properties(id)
);
CREATE TABLE IF NOT EXISTS booking_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    total_bookings INTEGER DEFAULT 0,
    total_revenue REAL DEFAULT 0,
    avg_occupancy REAL DEFAULT 0,
    FOREIGN KEY (property_id) REFERENCES properties(id)
);
CREATE TABLE IF NOT EXISTS ml_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS booking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id INTEGER NOT NULL UNIQUE,
    property_id INTEGER NOT NULL,
    check_in DATE NOT NULL,
    check_out DATE,
    total_price REAL NOT NULL,
    booking_type TEXT,
    is_open_ended INTEGER DEFAULT 0,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (booking_id) REFERENCES bookings(id),
    FOREIGN KEY (property_id) REFERENCES properties(id)
);
"""


# ─────────────────────────────────────────────────────────────────────────────
#  init_db
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    c = conn.cursor()

    if USE_POSTGRES:
        # psycopg2 does not support executescript — run each statement separately
        for stmt in _PG_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    c.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()
    else:
        c.executescript(_SQLITE_SCHEMA)

    # ── Seed users ─────────────────────────────────────────────────────────────
    if USE_POSTGRES:
        c.execute(
            "INSERT INTO users (name, email, password, role) VALUES (%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING",
            ("Admin", "admin@propbook.ph", hash_password("admin123"), "admin")
        )
        c.execute(
            "INSERT INTO users (name, email, password, role, phone) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING",
            ("Maria Santos", "owner@propbook.ph", hash_password("owner123"), "owner", "+63 912 345 6789")
        )
        c.execute(
            "INSERT INTO users (name, email, password, role, phone) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING",
            ("Juan dela Cruz", "guest@propbook.ph", hash_password("guest123"), "guest", "+63 917 123 4567")
        )
    else:
        ph = _p()
        c.execute(f"SELECT id FROM users WHERE email={ph}", ("admin@propbook.ph",))
        if not c.fetchone():
            c.execute(
                f"INSERT INTO users (name, email, password, role) VALUES ({_ph(4)})",
                ("Admin", "admin@propbook.ph", hash_password("admin123"), "admin")
            )
        c.execute(f"SELECT id FROM users WHERE email={ph}", ("owner@propbook.ph",))
        if not c.fetchone():
            c.execute(
                f"INSERT INTO users (name, email, password, role, phone) VALUES ({_ph(5)})",
                ("Maria Santos", "owner@propbook.ph", hash_password("owner123"), "owner", "+63 912 345 6789")
            )
        c.execute(f"SELECT id FROM users WHERE email={ph}", ("guest@propbook.ph",))
        if not c.fetchone():
            c.execute(
                f"INSERT INTO users (name, email, password, role, phone) VALUES ({_ph(5)})",
                ("Juan dela Cruz", "guest@propbook.ph", hash_password("guest123"), "guest", "+63 917 123 4567")
            )

    conn.commit()

    # ── Seed properties ────────────────────────────────────────────────────────
    ph = _p()  # ensure ph is always defined for both Postgres and SQLite paths
    c.execute(f"SELECT id FROM properties LIMIT 1")
    if not c.fetchone():
        c.execute(f"SELECT id FROM users WHERE email={ph}", ("owner@propbook.ph",))
        owner = c.fetchone()
        owner_id = owner["id"]

        properties_data = [
            (owner_id, "Azure Residences BGC",
             "Modern fully-furnished apartment in the heart of BGC with stunning city views.",
             "apartment", "32nd Street, Bonifacio Global City", "Taguig", "BGC", "Metro Manila",
             14.5507, 121.0474, 2500, 45000, 2, 1, 1, "WiFi,AC,Parking,Pool,Gym,Security", "apt1.jpg", "approved"),
            (owner_id, "Cozy House in Quezon City",
             "Spacious family house near Trinoma with garden and parking.",
             "house", "15 Mindanao Ave", "Quezon City", "Project 6", "Metro Manila",
             14.6760, 121.0437, 3500, 60000, 6, 3, 2, "WiFi,AC,Parking,Garden,CCTV", "house1.jpg", "approved"),
            (owner_id, "Sea View Condo Pasay",
             "Beautiful beachfront-style condo near MOA with ocean views.",
             "apartment", "Ocean Drive, Mall of Asia", "Pasay", "Tambo", "Metro Manila",
             14.5352, 120.9822, 1800, 35000, 2, 1, 1, "WiFi,AC,Pool,Gym,Balcony,Beach Access", "condo1.jpg", "approved"),
            (owner_id, "Heritage House Intramuros",
             "Charming heritage house inside the Walled City. Unique historic experience.",
             "house", "General Luna Street", "Manila", "Intramuros", "Metro Manila",
             14.5896, 120.9747, 4000, 75000, 8, 4, 3, "WiFi,AC,Historic,Tour Guide,Parking", "heritage.jpg", "approved"),
            (owner_id, "Studio Loft Makati CBD",
             "Compact modern studio loft perfect for business travelers.",
             "apartment", "Ayala Avenue", "Makati", "Bel-Air", "Metro Manila",
             14.5547, 121.0244, 1500, 28000, 1, 0, 1, "WiFi,AC,Security,24hr Concierge", "studio.jpg", "approved"),
            (owner_id, "Sunset Villa Boracay",
             "Luxurious beachfront villa steps from White Beach with private pool.",
             "house", "Station 1, White Beach", "Malay", "Boracay", "Aklan",
             11.9674, 121.9248, 8500, 150000, 10, 5, 4, "WiFi,AC,Private Pool,Beach Access,BBQ,Staff", "boracay.jpg", "approved"),
            (owner_id, "Cebu IT Park Condo",
             "Modern condo in the heart of Cebu IT Park, ideal for BPO workers and digital nomads.",
             "apartment", "Cebu IT Park, Lahug", "Cebu City", "Lahug", "Cebu",
             10.3310, 123.9053, 1200, 22000, 2, 1, 1, "WiFi,AC,Gym,24hr Security,Co-working Space", "cebu.jpg", "approved"),
            (owner_id, "Tagaytay Ridge House",
             "Cool-climate house with panoramic Taal Lake and volcano views.",
             "house", "Aguinaldo Highway", "Tagaytay", "Maharlika West", "Cavite",
             14.0996, 120.9626, 5000, 90000, 8, 4, 3, "WiFi,AC,Fireplace,Garden,Parking,BBQ Pit", "tagaytay.jpg", "approved"),
            (owner_id, "Palawan Beach Cottage",
             "Rustic-chic cottage near El Nido with crystal-clear lagoon access.",
             "house", "Corong-Corong Beach", "El Nido", "Corong-Corong", "Palawan",
             11.1786, 119.3963, 6500, 110000, 6, 3, 2, "WiFi,Beach Access,Kayak,Snorkel Gear,Breakfast", "palawan.jpg", "approved"),
            (owner_id, "Davao Garden Apartment",
             "Spacious apartment surrounded by tropical garden near Davao city center.",
             "apartment", "JP Laurel Avenue", "Davao City", "Poblacion", "Davao del Sur",
             7.0731, 125.6128, 1400, 25000, 4, 2, 1, "WiFi,AC,Garden,Parking,Security,Near Mall", "davao.jpg", "approved"),
        ]

        insert_sql = (
            f"INSERT INTO properties "
            f"(owner_id,title,description,type,address,city,barangay,province,"
            f"latitude,longitude,nightly_price,monthly_price,max_guests,bedrooms,bathrooms,"
            f"amenities,images,status) VALUES ({_ph(18)})"
        )
        for p in properties_data:
            c.execute(insert_sql, p)

        conn.commit()

        # Rooms for apartments
        c.execute(f"SELECT id, type FROM properties WHERE owner_id={ph}", (owner_id,))
        props = c.fetchall()
        room_sql = (
            f"INSERT INTO rooms (property_id,room_number,floor,room_type,capacity,"
            f"nightly_price,monthly_price,is_available) VALUES ({_ph(8)})"
        )
        for prop in props:
            if prop["type"] == "apartment":
                for i in range(1, 6):
                    c.execute(room_sql, (
                        prop["id"], f"R{i:02d}", (i % 3) + 1,
                        ["standard", "deluxe", "suite"][i % 3], 2,
                        None, None, 1
                    ))

        conn.commit()

        # Historical booking data
        _seed_all_history(c)
        conn.commit()

    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  migrate_db
# ─────────────────────────────────────────────────────────────────────────────

def migrate_db():
    """Safe migrations for existing databases."""
    conn = get_conn()
    c = conn.cursor()

    if USE_POSTGRES:
        # Add columns if missing (Postgres)
        for col, definition in [
            ("down_payment",  "REAL DEFAULT 0"),
            ("balance_due",   "REAL DEFAULT 0"),
            ("is_open_ended", "INTEGER DEFAULT 0"),
        ]:
            c.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='bookings' AND column_name=%s",
                (col,)
            )
            if not c.fetchone():
                c.execute(f"ALTER TABLE bookings ADD COLUMN {col} {definition}")

        # Ensure new tables exist
        for stmt in _PG_SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    c.execute(stmt)
                    conn.commit()
                except Exception:
                    conn.rollback()
    else:
        existing_cols = [row[1] for row in c.execute("PRAGMA table_info(bookings)").fetchall()]
        for col, definition in [
            ("down_payment",  "REAL DEFAULT 0"),
            ("balance_due",   "REAL DEFAULT 0"),
            ("is_open_ended", "INTEGER DEFAULT 0"),
        ]:
            if col not in existing_cols:
                c.execute(f"ALTER TABLE bookings ADD COLUMN {col} {definition}")
        c.executescript(_SQLITE_SCHEMA)

    ph = _p()

    # Ensure demo owner exists
    c.execute(f"SELECT id FROM users WHERE email={ph}", ("owner@propbook.ph",))
    owner_row = c.fetchone()
    if not owner_row:
        c.execute(
            f"INSERT INTO users (name,email,password,role,phone) VALUES ({_ph(5)})",
            ("Maria Santos", "owner@propbook.ph", hash_password("owner123"), "owner", "+63 912 345 6789")
        )
        conn.commit()
        c.execute(f"SELECT id FROM users WHERE email={ph}", ("owner@propbook.ph",))
        owner_row = c.fetchone()
    owner_id = owner_row["id"]

    # Seed any missing demo properties
    new_properties = [
        ("Studio Loft Makati CBD",
         "Compact modern studio loft perfect for business travelers.", "apartment",
         "Ayala Avenue", "Makati", "Bel-Air", "Metro Manila", 14.5547, 121.0244,
         1500, 28000, 1, 0, 1, "WiFi,AC,Security,24hr Concierge", "studio.jpg", "approved"),
        ("Sunset Villa Boracay",
         "Luxurious beachfront villa steps from White Beach with private pool.", "house",
         "Station 1, White Beach", "Malay", "Boracay", "Aklan", 11.9674, 121.9248,
         8500, 150000, 10, 5, 4, "WiFi,AC,Private Pool,Beach Access,BBQ,Staff", "boracay.jpg", "approved"),
        ("Cebu IT Park Condo",
         "Modern condo in the heart of Cebu IT Park, ideal for BPO workers and digital nomads.", "apartment",
         "Cebu IT Park, Lahug", "Cebu City", "Lahug", "Cebu", 10.3310, 123.9053,
         1200, 22000, 2, 1, 1, "WiFi,AC,Gym,24hr Security,Co-working Space", "cebu.jpg", "approved"),
        ("Tagaytay Ridge House",
         "Cool-climate house with panoramic Taal Lake and volcano views.", "house",
         "Aguinaldo Highway", "Tagaytay", "Maharlika West", "Cavite", 14.0996, 120.9626,
         5000, 90000, 8, 4, 3, "WiFi,AC,Fireplace,Garden,Parking,BBQ Pit", "tagaytay.jpg", "approved"),
        ("Palawan Beach Cottage",
         "Rustic-chic cottage near El Nido with crystal-clear lagoon access.", "house",
         "Corong-Corong Beach", "El Nido", "Corong-Corong", "Palawan", 11.1786, 119.3963,
         6500, 110000, 6, 3, 2, "WiFi,Beach Access,Kayak,Snorkel Gear,Breakfast", "palawan.jpg", "approved"),
        ("Davao Garden Apartment",
         "Spacious apartment surrounded by tropical garden near Davao city center.", "apartment",
         "JP Laurel Avenue", "Davao City", "Poblacion", "Davao del Sur", 7.0731, 125.6128,
         1400, 25000, 4, 2, 1, "WiFi,AC,Garden,Parking,Security,Near Mall", "davao.jpg", "approved"),
    ]

    insert_sql = (
        f"INSERT INTO properties "
        f"(owner_id,title,description,type,address,city,barangay,province,"
        f"latitude,longitude,nightly_price,monthly_price,max_guests,bedrooms,bathrooms,"
        f"amenities,images,status) VALUES ({_ph(18)})"
    )
    for prop in new_properties:
        title = prop[0]
        c.execute(f"SELECT id FROM properties WHERE title={ph}", (title,))
        if not c.fetchone():
            c.execute(insert_sql, (owner_id,) + prop)

    c.execute(f"UPDATE properties SET status='approved' WHERE title={ph}", ("Studio Loft Makati CBD",))
    conn.commit()

    # Seed missing booking_history for demo properties
    DEMO_TITLES = {
        "Azure Residences BGC", "Cozy House in Quezon City", "Sea View Condo Pasay",
        "Heritage House Intramuros", "Studio Loft Makati CBD", "Sunset Villa Boracay",
        "Cebu IT Park Condo", "Tagaytay Ridge House", "Palawan Beach Cottage",
        "Davao Garden Apartment",
    }
    c.execute("SELECT id, title FROM properties")
    all_props = c.fetchall()
    for prop in all_props:
        if prop["title"] in DEMO_TITLES:
            _seed_history_for_property(c, prop["id"], prop["title"])

    conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────────────────────
#  Historical booking-history seeders  (unchanged logic, dialect-aware SQL)
# ─────────────────────────────────────────────────────────────────────────────

_PH_SEASONAL = {
    1: 0.82, 2: 0.68, 3: 0.74, 4: 0.88,
    5: 0.93, 6: 1.00, 7: 1.00, 8: 0.84,
    9: 0.67, 10: 0.72, 11: 0.83, 12: 1.00
}

_PROFILES = {
    "Azure Residences BGC":       {"base": 18, "rev": 2800, "growth": 0.08, "noise": 0.12,
                                   "seasonal_tweak": {2: -0.10, 9: -0.15, 10: -0.08},
                                   "covid_factor": {2020: 0.30, 2021: 0.55}},
    "Cozy House in Quezon City":  {"base": 12, "rev": 3800, "growth": 0.05, "noise": 0.18,
                                   "seasonal_tweak": {4: 0.15, 5: 0.18, 12: 0.20, 6: -0.05, 7: -0.05},
                                   "covid_factor": {2020: 0.20, 2021: 0.45}},
    "Sea View Condo Pasay":       {"base": 15, "rev": 2200, "growth": 0.10, "noise": 0.14,
                                   "seasonal_tweak": {4: 0.18, 5: 0.20, 6: 0.12, 9: -0.22, 12: 0.18},
                                   "covid_factor": {2020: 0.15, 2021: 0.40}},
    "Heritage House Intramuros":  {"base": 8,  "rev": 5500, "growth": 0.12, "noise": 0.20,
                                   "seasonal_tweak": {1: 0.20, 4: 0.22, 9: -0.25, 10: -0.18, 12: 0.25},
                                   "covid_factor": {2020: 0.08, 2021: 0.25}},
    "Studio Loft Makati CBD":     {"base": 22, "rev": 1800, "growth": 0.09, "noise": 0.10,
                                   "seasonal_tweak": {2: -0.05, 8: -0.08, 12: 0.08},
                                   "covid_factor": {2020: 0.50, 2021: 0.70}},
    "Sunset Villa Boracay":       {"base": 10, "rev": 9500, "growth": 0.14, "noise": 0.25,
                                   "seasonal_tweak": {3: 0.20, 4: 0.40, 5: 0.45, 6: 0.30,
                                                      9: -0.30, 10: -0.25, 11: -0.15, 12: 0.35},
                                   "covid_factor": {2020: 0.10, 2021: 0.30}},
    "Cebu IT Park Condo":         {"base": 25, "rev": 1500, "growth": 0.07, "noise": 0.09,
                                   "seasonal_tweak": {12: -0.10, 1: -0.08, 6: 0.05, 7: 0.05},
                                   "covid_factor": {2020: 0.60, 2021: 0.75}},
    "Tagaytay Ridge House":       {"base": 14, "rev": 6000, "growth": 0.11, "noise": 0.22,
                                   "seasonal_tweak": {1: 0.25, 2: 0.22, 3: 0.15, 4: 0.18,
                                                      7: -0.20, 8: -0.18, 9: -0.25, 12: 0.30},
                                   "covid_factor": {2020: 0.25, 2021: 0.55}},
    "Palawan Beach Cottage":      {"base": 9,  "rev": 8000, "growth": 0.16, "noise": 0.28,
                                   "seasonal_tweak": {11: 0.35, 12: 0.45, 1: 0.40, 2: 0.42,
                                                      3: 0.38, 4: 0.30, 5: 0.10,
                                                      6: -0.45, 7: -0.50, 8: -0.48, 9: -0.50, 10: -0.30},
                                   "covid_factor": {2020: 0.05, 2021: 0.20}},
    "Davao Garden Apartment":     {"base": 16, "rev": 1700, "growth": 0.06, "noise": 0.13,
                                   "seasonal_tweak": {8: 0.20, 12: 0.15, 1: 0.12, 9: -0.10},
                                   "covid_factor": {2020: 0.40, 2021: 0.65}},
}

_DEFAULT_PROFILE = {"base": 10, "rev": 2000, "growth": 0.06, "noise": 0.15,
                    "seasonal_tweak": {}, "covid_factor": {2020: 0.30, 2021: 0.55}}


def _seed_history_for_property(c, prop_id, prop_title):
    """Insert 5 years of booking_history for one property (skips years already present)."""
    random.seed(99)
    ph = _p()
    years = [2020, 2021, 2022, 2023, 2024]

    if USE_POSTGRES:
        c.execute(
            "SELECT DISTINCT year FROM booking_history WHERE property_id=%s",
            (prop_id,)
        )
    else:
        c.execute(
            "SELECT DISTINCT year FROM booking_history WHERE property_id=?",
            (prop_id,)
        )
    existing_years = {row["year"] for row in c.fetchall()}

    if len(existing_years) < len(years):
        if USE_POSTGRES:
            c.execute("DELETE FROM booking_history WHERE property_id=%s", (prop_id,))
        else:
            c.execute("DELETE FROM booking_history WHERE property_id=?", (prop_id,))
        existing_years = set()

    prof = _PROFILES.get(prop_title, _DEFAULT_PROFILE)
    covid_factors = prof.get("covid_factor", {})
    insert_sql = (
        f"INSERT INTO booking_history "
        f"(property_id,month,year,total_bookings,total_revenue,avg_occupancy) "
        f"VALUES ({_ph(6)})"
    )

    for y_idx, year in enumerate(years):
        if year in existing_years:
            continue
        for month in range(1, 13):
            base_w = _PH_SEASONAL[month]
            tweak  = prof["seasonal_tweak"].get(month, 0.0)
            weight = max(0.15, base_w + tweak)
            growth_factor = (1 + prof["growth"]) ** y_idx
            covid_mult    = covid_factors.get(year, 1.0)
            noise = max(-0.40, min(random.gauss(0, prof["noise"]), 0.40))
            raw_bookings  = prof["base"] * weight * growth_factor * covid_mult * (1 + noise)
            total_bookings = max(1, int(round(raw_bookings)))
            rev_noise     = random.uniform(0.85, 1.15)
            total_revenue = round(total_bookings * prof["rev"] * growth_factor * covid_mult * rev_noise, 2)
            occ_base      = weight * 0.78 * growth_factor * covid_mult
            avg_occupancy = round(min(max(occ_base + random.gauss(0, 0.06), 0.05), 0.98), 4)
            c.execute(insert_sql, (prop_id, month, year, total_bookings, total_revenue, avg_occupancy))


def _seed_all_history(c):
    """Called once during first init to seed all approved properties."""
    ph = _p()
    c.execute("SELECT id, title FROM properties WHERE status='approved'")
    for prop in c.fetchall():
        _seed_history_for_property(c, prop["id"], prop["title"])
