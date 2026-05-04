# 🏘️ PropBook PH — Property Booking Platform

A full-featured property booking platform built with **Python + Streamlit** with **ML-powered trend prediction**.

## 🚀 Features

### Three User Roles
| Role | Capabilities |
|------|-------------|
| **Admin** | Dashboard, approve/reject properties, manage users, view-only bookings |
| **Owner** | Dashboard with ML forecasts, add properties, manage rooms, accept/reject bookings |
| **Guest** | Browse properties, book (nightly or monthly), online/walk-in payment |

### 🤖 Machine Learning
- **Trend Prediction**: Predicts which properties will be most in-demand based on:
  - Historical booking data (3 years)
  - Philippine seasonal patterns (peak: Dec, Jun/Jul, Apr/May)
  - Revenue growth trajectory
  - Linear regression on booking trends
- **6-Month Forecast**: Per-property booking/revenue forecast for owners
- **Seasonal Heatmap**: City-level demand visualization

### 🏠 Property Features
- Supports **Houses** and **Apartments**
- Apartments have **Room Management** (add/remove rooms, toggle availability)
- **Monthly and Nightly pricing**
- Amenities tagging, guest capacity, bedrooms/bathrooms

### 💳 Booking Features
- Nightly or monthly booking types
- Online (simulated) or walk-in payment
- Room selection for apartments
- Special requests field
- Owner accept/reject flow
- Guest cancellation

---

## 🛠️ Local Setup

```bash
# 1. Clone / download the project
cd propbook

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The app will open at `http://localhost:8501`

---

## ☁️ Deploy to Streamlit Cloud (Free)

1. Push this folder to a **GitHub repository**
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **"New app"**
4. Select your repo → set **Main file path** to `app.py`
5. Click **Deploy** 🚀

> ⚠️ Note: Streamlit Cloud uses an ephemeral filesystem — the SQLite database resets on redeploy. For production, swap `sqlite3` with a **PostgreSQL** database (e.g., Supabase free tier) using `psycopg2`.

---

## 👤 Demo Accounts

| Role | Email | Password |
|------|-------|----------|
| Admin | admin@propbook.ph | admin123 |
| Owner | owner@propbook.ph | owner123 |
| Guest | guest@propbook.ph | guest123 |

---

## 📁 Project Structure

```
propbook/
├── app.py                  # Main entry point
├── database.py             # SQLite DB + seed data
├── auth.py                 # Login/register logic
├── ml_model.py             # ML trend prediction
├── ui_components.py        # Shared CSS + UI helpers
├── requirements.txt
├── .streamlit/
│   └── config.toml         # Theme config
└── pages/
    ├── auth_pages.py       # Login & register UI
    ├── admin_pages.py      # Admin dashboard & management
    ├── owner_pages.py      # Owner dashboard, properties, bookings
    └── guest_pages.py      # Browse, book, profile
```

---

## 🔧 Production Upgrades

To make this production-ready:

1. **Database**: Replace SQLite with PostgreSQL (Supabase, Neon, or Railway)
2. **File Uploads**: Use Cloudinary or S3 for property images
3. **Real Payments**: Integrate PayMongo (Philippines) for online payments
4. **Email Notifications**: Use SendGrid for booking confirmations
5. **Maps**: Add Folium/Leaflet for property map view

---

## 📊 ML Model Details

The trend prediction uses a **weighted composite score**:

```
trend_score = (
    0.30 × growth_momentum    # Linear regression slope
  + 0.25 × same_month_history # Historical same-month bookings
  + 0.25 × seasonal_weight    # PH seasonal pattern
  + 0.20 × revenue_growth     # Revenue trajectory
)
```

Philippine seasonal weights (June/July/December = peak at 1.0).