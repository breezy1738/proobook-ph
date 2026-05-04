from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from functools import wraps
import sqlite3
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import hashlib
import json
from collections import defaultdict

# ML trend prediction model
from ml_model import (
    compute_trend_scores,
    compute_monthly_heatmap,
    MONTH_CONTEXT,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== SUPABASE GOOGLE OAUTH CONFIG ====================
SUPABASE_URL    = os.environ.get('SUPABASE_URL', '')       # e.g. https://xxxx.supabase.co
SUPABASE_KEY    = os.environ.get('SUPABASE_ANON_KEY', '')  # your anon/public key

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def get_db_connection():
    conn = sqlite3.connect('booking.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'owner', 'guest')),
            full_name TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            google_id TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            property_type TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            price_per_night REAL NOT NULL,
            bedrooms INTEGER,
            bathrooms INTEGER,
            max_guests INTEGER,
            amenities TEXT,
            images TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (owner_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            guest_id INTEGER NOT NULL,
            check_in DATE NOT NULL,
            check_out DATE NOT NULL,
            total_price REAL NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'confirmed', 'cancelled', 'completed')),
            guest_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties (id),
            FOREIGN KEY (guest_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL,
            guest_id INTEGER NOT NULL,
            rating INTEGER CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (property_id) REFERENCES properties (id),
            FOREIGN KEY (guest_id) REFERENCES users (id)
        )
    ''')

    conn.commit()

    cursor.execute("SELECT * FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        hashed_pw = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('''
            INSERT INTO users (username, email, password, role, full_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin@booking.com', hashed_pw, 'admin', 'System Administrator'))
        conn.commit()
        print("Default admin created: username='admin', password='admin123'")

    conn.close()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login first.', 'warning')
                return redirect(url_for('login'))
            if session.get('role') not in roles:
                flash('Access denied.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def login_user(user):
    """Helper to set session after any login method."""
    session['user_id']   = user['id']
    session['username']  = user['username']
    session['role']      = user['role']
    session['full_name'] = user['full_name']

def redirect_by_role():
    """Redirect to the correct dashboard based on session role."""
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif role == 'owner':
        return redirect(url_for('owner_dashboard'))
    else:
        return redirect(url_for('guest_dashboard'))

# ==================== GOOGLE OAUTH VIA SUPABASE ====================

@app.route('/auth/google')
def google_login():
    """Redirect user to Supabase Google OAuth URL."""
    if not SUPABASE_URL:
        flash('Google login is not configured yet.', 'warning')
        return redirect(url_for('login'))

    callback_url = url_for('google_callback', _external=True)
    supabase_oauth_url = (
        f"{SUPABASE_URL}/auth/v1/authorize"
        f"?provider=google"
        f"&redirect_to={callback_url}"
    )
    return redirect(supabase_oauth_url)


@app.route('/auth/google/callback')
def google_callback():
    """
    Supabase redirects back here with an access_token in the URL fragment (#).
    Since fragments aren't sent to the server, we render a small page that
    reads the token from the fragment and POSTs it to /auth/google/verify.
    """
    return render_template('auth/google_callback.html')


@app.route('/auth/google/verify', methods=['POST'])
def google_verify():
    """
    Receives the Supabase access_token from the frontend,
    fetches the user's profile, then creates/logs in the local DB user.
    """
    import urllib.request
    import urllib.error

    access_token = request.json.get('access_token')
    if not access_token:
        return jsonify({'error': 'No access token provided'}), 400

    # Fetch user info from Supabase
    try:
        req = urllib.request.Request(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                'Authorization': f'Bearer {access_token}',
                'apikey': SUPABASE_KEY,
            }
        )
        with urllib.request.urlopen(req) as response:
            user_data = json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        return jsonify({'error': 'Failed to verify token with Supabase'}), 401

    email     = user_data.get('email', '')
    full_name = user_data.get('user_metadata', {}).get('full_name', '') or \
                user_data.get('user_metadata', {}).get('name', '')
    google_id = user_data.get('id', '')

    if not email:
        return jsonify({'error': 'Could not retrieve email from Google'}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    if not user:
        # Auto-register as guest
        username = email.split('@')[0]
        existing = conn.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        if existing:
            username = f"{username}_{google_id[-4:]}"

        conn.execute('''
            INSERT INTO users (username, email, password, role, full_name, google_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, '', 'guest', full_name, google_id))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()

    conn.close()

    if not user['is_active']:
        return jsonify({'error': 'Your account has been deactivated.'}), 403

    login_user(user)
    flash(f'Welcome, {user["full_name"] or user["username"]}!', 'success')

    role = user['role']
    if role == 'admin':
        redirect_url = url_for('admin_dashboard')
    elif role == 'owner':
        redirect_url = url_for('owner_dashboard')
    else:
        redirect_url = url_for('guest_dashboard')

    return jsonify({'redirect': redirect_url})


# ==================== MAIN ROUTES ====================

@app.route('/')
def index():
    conn = get_db_connection()
    properties = conn.execute('''
        SELECT p.*, u.full_name as owner_name, u.email as owner_email
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        WHERE p.status = 'approved'
        ORDER BY p.created_at DESC
        LIMIT 6
    ''').fetchall()
    conn.close()
    return render_template('index.html', properties=properties)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username         = request.form['username']
        email            = request.form['email']
        password         = request.form['password']
        confirm_password = request.form['confirm_password']
        role             = request.form['role']
        full_name        = request.form['full_name']
        phone            = request.form['phone']

        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))

        conn = get_db_connection()
        try:
            hashed_pw = hash_password(password)
            conn.execute('''
                INSERT INTO users (username, email, password, role, full_name, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, hashed_pw, role, full_name, phone))
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username  = request.form['username']
        password  = request.form['password']
        hashed_pw = hash_password(password)

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, hashed_pw)
        ).fetchone()
        conn.close()

        if user:
            if not user['is_active']:
                flash('Your account has been deactivated.', 'danger')
                return redirect(url_for('login'))

            login_user(user)
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect_by_role()
        else:
            flash('Invalid username or password!', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    return redirect_by_role()

# ==================== ADMIN ROUTES ====================
@app.route('/admin/dashboard')
@role_required(['admin'])
def admin_dashboard():
    conn = get_db_connection()

    stats = {
        'total_users': conn.execute("SELECT COUNT(*) as count FROM users WHERE role != 'admin'").fetchone()['count'],
        'total_properties': conn.execute("SELECT COUNT(*) as count FROM properties").fetchone()['count'],
        'pending_properties': conn.execute("SELECT COUNT(*) as count FROM properties WHERE status = 'pending'").fetchone()['count'],
        'total_bookings': conn.execute("SELECT COUNT(*) as count FROM bookings").fetchone()['count'],
        'total_revenue': conn.execute("SELECT COALESCE(SUM(total_price), 0) as total FROM bookings WHERE status = 'completed'").fetchone()['total']
    }

    recent_bookings = conn.execute('''
        SELECT b.*, p.title as property_title, u.full_name as guest_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.guest_id = u.id
        ORDER BY b.created_at DESC
        LIMIT 5
    ''').fetchall()

    conn.close()
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)

@app.route('/admin/users')
@role_required(['admin'])
def admin_users():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users WHERE role != 'admin' ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/toggle_user/<int:user_id>')
@role_required(['admin'])
def admin_toggle_user(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user:
        new_status = 0 if user['is_active'] else 1
        conn.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
        conn.commit()
        action = 'activated' if new_status else 'deactivated'
        flash(f'User {action} successfully!', 'success')
    conn.close()
    return redirect(url_for('admin_users'))

@app.route('/admin/properties')
@role_required(['admin'])
def admin_properties():
    conn = get_db_connection()
    properties = conn.execute('''
        SELECT p.*, u.full_name as owner_name
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        ORDER BY p.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/properties.html', properties=properties)

@app.route('/admin/approve_property/<int:property_id>/<string:action>')
@role_required(['admin'])
def admin_approve_property(property_id, action):
    if action not in ['approved', 'rejected']:
        flash('Invalid action!', 'danger')
        return redirect(url_for('admin_properties'))

    conn = get_db_connection()
    conn.execute("UPDATE properties SET status = ? WHERE id = ?", (action, property_id))
    conn.commit()
    conn.close()
    flash(f'Property {action} successfully!', 'success')
    return redirect(url_for('admin_properties'))

@app.route('/admin/bookings')
@role_required(['admin'])
def admin_bookings():
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT b.*, p.title as property_title, 
               guest.full_name as guest_name, owner.full_name as owner_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users guest ON b.guest_id = guest.id
        JOIN users owner ON p.owner_id = owner.id
        ORDER BY b.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('admin/bookings.html', bookings=bookings)

# ==================== OWNER ROUTES ====================
@app.route('/owner/dashboard')
@role_required(['owner'])
def owner_dashboard():
    owner_id = session['user_id']
    conn = get_db_connection()

    stats = {
        'total_properties': conn.execute(
            "SELECT COUNT(*) as count FROM properties WHERE owner_id = ?", (owner_id,)
        ).fetchone()['count'],
        'pending_bookings': conn.execute('''
            SELECT COUNT(*) as count FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE p.owner_id = ? AND b.status = 'pending'
        ''', (owner_id,)).fetchone()['count'],
        'total_bookings': conn.execute('''
            SELECT COUNT(*) as count FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE p.owner_id = ?
        ''', (owner_id,)).fetchone()['count'],
        'total_earnings': conn.execute('''
            SELECT COALESCE(SUM(b.total_price), 0) as total FROM bookings b
            JOIN properties p ON b.property_id = p.id
            WHERE p.owner_id = ? AND b.status = 'completed'
        ''', (owner_id,)).fetchone()['total']
    }

    recent_bookings = conn.execute('''
        SELECT b.*, p.title as property_title, u.full_name as guest_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.guest_id = u.id
        WHERE p.owner_id = ?
        ORDER BY b.created_at DESC
        LIMIT 5
    ''', (owner_id,)).fetchall()

    conn.close()
    return render_template('owner/dashboard.html', stats=stats, recent_bookings=recent_bookings)

@app.route('/owner/properties')
@role_required(['owner'])
def owner_properties():
    owner_id = session['user_id']
    conn = get_db_connection()
    properties = conn.execute('''
        SELECT p.*, 
               (SELECT COUNT(*) FROM bookings WHERE property_id = p.id) as booking_count
        FROM properties p
        WHERE p.owner_id = ?
        ORDER BY p.created_at DESC
    ''', (owner_id,)).fetchall()
    conn.close()
    return render_template('owner/properties.html', properties=properties)

@app.route('/owner/add_property', methods=['GET', 'POST'])
@role_required(['owner'])
def owner_add_property():
    if request.method == 'POST':
        title          = request.form['title']
        description    = request.form['description']
        property_type  = request.form['property_type']
        address        = request.form['address']
        city           = request.form['city']
        price_per_night = float(request.form['price_per_night'])
        bedrooms       = int(request.form['bedrooms'])
        bathrooms      = int(request.form['bathrooms'])
        max_guests     = int(request.form['max_guests'])
        amenities      = request.form['amenities']

        images = []
        if 'images' in request.files:
            files = request.files.getlist('images')
            for file in files:
                if file and allowed_file(file.filename):
                    filename  = secure_filename(file.filename)
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename  = f"{timestamp}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    images.append(filename)

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO properties (owner_id, title, description, property_type, address, city,
                                   price_per_night, bedrooms, bathrooms, max_guests, amenities, images)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], title, description, property_type, address, city,
              price_per_night, bedrooms, bathrooms, max_guests, amenities, ','.join(images)))
        conn.commit()
        conn.close()

        flash('Property added successfully! Waiting for admin approval.', 'success')
        return redirect(url_for('owner_properties'))

    return render_template('owner/add_property.html')

@app.route('/owner/edit_property/<int:property_id>', methods=['GET', 'POST'])
@role_required(['owner'])
def owner_edit_property(property_id):
    conn = get_db_connection()
    property = conn.execute(
        "SELECT * FROM properties WHERE id = ? AND owner_id = ?",
        (property_id, session['user_id'])
    ).fetchone()

    if not property:
        flash('Property not found!', 'danger')
        conn.close()
        return redirect(url_for('owner_properties'))

    if request.method == 'POST':
        title          = request.form['title']
        description    = request.form['description']
        property_type  = request.form['property_type']
        address        = request.form['address']
        city           = request.form['city']
        price_per_night = float(request.form['price_per_night'])
        bedrooms       = int(request.form['bedrooms'])
        bathrooms      = int(request.form['bathrooms'])
        max_guests     = int(request.form['max_guests'])
        amenities      = request.form['amenities']

        conn.execute('''
            UPDATE properties 
            SET title = ?, description = ?, property_type = ?, address = ?, city = ?,
                price_per_night = ?, bedrooms = ?, bathrooms = ?, max_guests = ?, amenities = ?
            WHERE id = ?
        ''', (title, description, property_type, address, city, price_per_night,
              bedrooms, bathrooms, max_guests, amenities, property_id))
        conn.commit()
        conn.close()
        flash('Property updated successfully!', 'success')
        return redirect(url_for('owner_properties'))

    conn.close()
    return render_template('owner/edit_property.html', property=property)

@app.route('/owner/bookings')
@role_required(['owner'])
def owner_bookings():
    owner_id = session['user_id']
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT b.*, p.title as property_title, u.full_name as guest_name, u.email as guest_email
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON b.guest_id = u.id
        WHERE p.owner_id = ?
        ORDER BY b.created_at DESC
    ''', (owner_id,)).fetchall()
    conn.close()
    return render_template('owner/bookings.html', bookings=bookings)

@app.route('/owner/update_booking/<int:booking_id>/<string:action>')
@role_required(['owner'])
def owner_update_booking(booking_id, action):
    if action not in ['confirmed', 'cancelled']:
        flash('Invalid action!', 'danger')
        return redirect(url_for('owner_bookings'))

    conn = get_db_connection()
    booking = conn.execute('''
        SELECT b.*, p.owner_id 
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.id = ?
    ''', (booking_id,)).fetchone()

    if not booking or booking['owner_id'] != session['user_id']:
        flash('Booking not found!', 'danger')
        conn.close()
        return redirect(url_for('owner_bookings'))

    conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (action, booking_id))
    conn.commit()
    conn.close()
    flash(f'Booking {action} successfully!', 'success')
    return redirect(url_for('owner_bookings'))

# ==================== GUEST ROUTES ====================
@app.route('/guest/dashboard')
@role_required(['guest'])
def guest_dashboard():
    guest_id = session['user_id']
    conn = get_db_connection()

    stats = {
        'total_bookings': conn.execute(
            "SELECT COUNT(*) as count FROM bookings WHERE guest_id = ?", (guest_id,)
        ).fetchone()['count'],
        'upcoming_bookings': conn.execute('''
            SELECT COUNT(*) as count FROM bookings 
            WHERE guest_id = ? AND check_in >= DATE('now') AND status IN ('pending', 'confirmed')
        ''', (guest_id,)).fetchone()['count'],
        'completed_bookings': conn.execute('''
            SELECT COUNT(*) as count FROM bookings 
            WHERE guest_id = ? AND status = 'completed'
        ''', (guest_id,)).fetchone()['count']
    }

    recent_bookings = conn.execute('''
        SELECT b.*, p.title as property_title, p.images
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.guest_id = ?
        ORDER BY b.created_at DESC
        LIMIT 5
    ''', (guest_id,)).fetchall()

    conn.close()
    return render_template('guest/dashboard.html', stats=stats, recent_bookings=recent_bookings)

@app.route('/properties')
def browse_properties():
    conn = get_db_connection()

    query  = "SELECT p.*, u.full_name as owner_name FROM properties p JOIN users u ON p.owner_id = u.id WHERE p.status = 'approved'"
    params = []

    city          = request.args.get('city')
    property_type = request.args.get('type')
    min_price     = request.args.get('min_price')
    max_price     = request.args.get('max_price')

    if city:
        query += " AND p.city LIKE ?"
        params.append(f"%{city}%")
    if property_type:
        query += " AND p.property_type = ?"
        params.append(property_type)
    if min_price:
        query += " AND p.price_per_night >= ?"
        params.append(float(min_price))
    if max_price:
        query += " AND p.price_per_night <= ?"
        params.append(float(max_price))

    query += " ORDER BY p.created_at DESC"

    properties = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('guest/browse.html', properties=properties)

@app.route('/property/<int:property_id>')
def property_detail(property_id):
    conn = get_db_connection()
    property = conn.execute('''
        SELECT p.*, u.full_name as owner_name, u.email as owner_email
        FROM properties p
        JOIN users u ON p.owner_id = u.id
        WHERE p.id = ? AND p.status = 'approved'
    ''', (property_id,)).fetchone()

    if not property:
        flash('Property not found!', 'danger')
        conn.close()
        return redirect(url_for('browse_properties'))

    reviews = conn.execute('''
        SELECT r.*, u.full_name as guest_name
        FROM reviews r
        JOIN users u ON r.guest_id = u.id
        WHERE r.property_id = ?
        ORDER BY r.created_at DESC
    ''', (property_id,)).fetchall()

    avg_rating = conn.execute('''
        SELECT COALESCE(AVG(rating), 0) as avg_rating, COUNT(*) as count
        FROM reviews WHERE property_id = ?
    ''', (property_id,)).fetchone()

    conn.close()
    return render_template('guest/property_detail.html', property=property, reviews=reviews, avg_rating=avg_rating)

@app.route('/book/<int:property_id>', methods=['GET', 'POST'])
@role_required(['guest'])
def book_property(property_id):
    conn = get_db_connection()
    property = conn.execute(
        "SELECT * FROM properties WHERE id = ? AND status = 'approved'", (property_id,)
    ).fetchone()

    if not property:
        flash('Property not found!', 'danger')
        conn.close()
        return redirect(url_for('browse_properties'))

    if request.method == 'POST':
        check_in      = request.form['check_in']
        check_out     = request.form['check_out']
        guest_message = request.form.get('guest_message', '')

        check_in_date  = datetime.strptime(check_in, '%Y-%m-%d')
        check_out_date = datetime.strptime(check_out, '%Y-%m-%d')
        nights         = (check_out_date - check_in_date).days

        if nights <= 0:
            flash('Check-out date must be after check-in date!', 'danger')
            conn.close()
            return redirect(url_for('book_property', property_id=property_id))

        total_price = nights * property['price_per_night']

        conn.execute('''
            INSERT INTO bookings (property_id, guest_id, check_in, check_out, total_price, guest_message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (property_id, session['user_id'], check_in, check_out, total_price, guest_message))
        conn.commit()
        conn.close()

        flash('Booking request sent successfully! Waiting for owner confirmation.', 'success')
        return redirect(url_for('guest_dashboard'))

    conn.close()
    return render_template('guest/book.html', property=property)

@app.route('/guest/bookings')
@role_required(['guest'])
def guest_bookings():
    guest_id = session['user_id']
    conn = get_db_connection()
    bookings = conn.execute('''
        SELECT b.*, p.title as property_title, p.images, p.address, u.full_name as owner_name
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        JOIN users u ON p.owner_id = u.id
        WHERE b.guest_id = ?
        ORDER BY b.created_at DESC
    ''', (guest_id,)).fetchall()
    conn.close()
    return render_template('guest/bookings.html', bookings=bookings)

@app.route('/guest/cancel_booking/<int:booking_id>')
@role_required(['guest'])
def guest_cancel_booking(booking_id):
    conn = get_db_connection()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id = ? AND guest_id = ?",
        (booking_id, session['user_id'])
    ).fetchone()

    if not booking:
        flash('Booking not found!', 'danger')
        conn.close()
        return redirect(url_for('guest_bookings'))

    if booking['status'] != 'pending':
        flash('Only pending bookings can be cancelled!', 'danger')
        conn.close()
        return redirect(url_for('guest_bookings'))

    conn.execute("UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,))
    conn.commit()
    conn.close()
    flash('Booking cancelled successfully!', 'success')
    return redirect(url_for('guest_bookings'))

@app.route('/guest/add_review/<int:booking_id>', methods=['GET', 'POST'])
@role_required(['guest'])
def guest_add_review(booking_id):
    conn = get_db_connection()
    booking = conn.execute('''
        SELECT b.*, p.title as property_title
        FROM bookings b
        JOIN properties p ON b.property_id = p.id
        WHERE b.id = ? AND b.guest_id = ? AND b.status = 'completed'
    ''', (booking_id, session['user_id'])).fetchone()

    if not booking:
        flash('Booking not found or not eligible for review!', 'danger')
        conn.close()
        return redirect(url_for('guest_bookings'))

    existing_review = conn.execute(
        "SELECT * FROM reviews WHERE property_id = ? AND guest_id = ?",
        (booking['property_id'], session['user_id'])
    ).fetchone()

    if existing_review:
        flash('You have already reviewed this booking!', 'warning')
        conn.close()
        return redirect(url_for('guest_bookings'))

    if request.method == 'POST':
        rating  = int(request.form['rating'])
        comment = request.form['comment']

        conn.execute('''
            INSERT INTO reviews (property_id, guest_id, rating, comment)
            VALUES (?, ?, ?, ?)
        ''', (booking['property_id'], session['user_id'], rating, comment))
        conn.commit()
        conn.close()
        flash('Review added successfully!', 'success')
        return redirect(url_for('guest_bookings'))

    conn.close()
    return render_template('guest/add_review.html', booking=booking)


# ==================== TREND ROUTES ====================

@app.route('/trends')
def property_trends():
    month = request.args.get('month', datetime.now().month, type=int)
    month = max(1, min(12, month))

    results, chart_data = compute_trend_scores(month)
    heatmap    = compute_monthly_heatmap()
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")

    return render_template(
        'trends.html',
        results=results,
        chart_data=json.dumps(chart_data),
        heatmap=heatmap,
        selected_month=month,
        month_name=month_name,
        month_ctx=ctx,
        total_results=len(results),
    )


@app.route('/api/trends/<int:month>')
def api_trends(month):
    month      = max(1, min(12, month))
    results, chart_data = compute_trend_scores(month)
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")
    return jsonify({
        "month": month, "month_name": month_name,
        "context": ctx, "results": results,
        "chart_data": chart_data, "total": len(results),
    })


@app.route('/admin/trends')
@role_required(['admin'])
def admin_trends():
    month = request.args.get('month', datetime.now().month, type=int)
    month = max(1, min(12, month))

    results, chart_data = compute_trend_scores(month)
    heatmap    = compute_monthly_heatmap()
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")

    return render_template(
        'trends.html',
        results=results, chart_data=json.dumps(chart_data),
        heatmap=heatmap, selected_month=month,
        month_name=month_name, month_ctx=ctx,
        total_results=len(results), view_mode='admin'
    )


@app.route('/admin/api/trends/<int:month>')
@role_required(['admin'])
def admin_api_trends(month):
    month      = max(1, min(12, month))
    results, chart_data = compute_trend_scores(month)
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")
    return jsonify({
        "month": month, "month_name": month_name,
        "context": ctx, "results": results,
        "chart_data": chart_data, "total": len(results),
    })


@app.route('/owner/trends')
@role_required(['owner'])
def owner_trends():
    month    = request.args.get('month', datetime.now().month, type=int)
    month    = max(1, min(12, month))
    owner_id = session['user_id']

    results, chart_data = compute_trend_scores(month, owner_id=owner_id)
    heatmap    = compute_monthly_heatmap()
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")

    return render_template(
        'trends.html',
        results=results, chart_data=json.dumps(chart_data),
        heatmap=heatmap, selected_month=month,
        month_name=month_name, month_ctx=ctx,
        total_results=len(results), view_mode='owner'
    )


@app.route('/owner/api/trends/<int:month>')
@role_required(['owner'])
def owner_api_trends(month):
    month    = max(1, min(12, month))
    owner_id = session['user_id']
    results, chart_data = compute_trend_scores(month, owner_id=owner_id)
    ctx        = MONTH_CONTEXT[month]
    month_name = datetime(2000, month, 1).strftime("%B")
    return jsonify({
        "month": month, "month_name": month_name,
        "context": ctx, "results": results,
        "chart_data": chart_data, "total": len(results),
    })


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)