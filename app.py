from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
import base64

app = Flask(__name__)
app.secret_key = "welfare_intel_2024_secret"

DATABASE = "database.db"

# ======================================================
# DATABASE INITIALIZATION
# ======================================================
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        age INTEGER,
        income REAL,
        category TEXT,
        state TEXT,
        occupation TEXT,
        education TEXT,
        area_type TEXT,
        scheme_preference TEXT DEFAULT 'All',
        is_admin INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schemes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        scheme_name TEXT,
        short_description TEXT,
        full_description TEXT,
        min_age INTEGER,
        max_age INTEGER,
        max_income REAL,
        category TEXT,
        state TEXT,
        occupation TEXT,
        education TEXT,
        area_type TEXT,
        benefit_amount REAL,
        scheme_type TEXT,
        eligibility_details TEXT,
        application_steps TEXT,
        documents_required TEXT,
        reference_link TEXT
    )
    """)

    conn.commit()
    conn.close()


# ======================================================
# SEED DEFAULT ADMIN
# ======================================================
def seed_admin():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (name, email, password, is_admin) VALUES (?, ?, ?, ?)",
        ('Admin', 'admin@welfare.com', generate_password_hash('Admin@123'), 1)
    )
    conn.commit()
    conn.close()


# ======================================================
# LOAD SCHEMES FROM CSV
# ======================================================
def seed_schemes_from_csv():
    if not os.path.exists("schemes.csv"):
        print("CSV file not found")
        return

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    # Add UNIQUE constraint support by checking scheme_name uniqueness manually
    df = pd.read_csv("schemes.csv")
    df.columns = df.columns.str.strip()

    added = 0
    for _, row in df.iterrows():
        cursor.execute("SELECT id FROM schemes WHERE scheme_name=?", (row['scheme_name'],))
        if cursor.fetchone() is None:
            cursor.execute("""
            INSERT INTO schemes (
                scheme_name, short_description, full_description,
                min_age, max_age, max_income,
                category, state, occupation, education, area_type,
                benefit_amount, scheme_type,
                eligibility_details, application_steps,
                documents_required, reference_link
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, tuple(row))
            added += 1

    conn.commit()
    conn.close()
    if added:
        print(f"Seeded {added} new scheme(s) from CSV.")


# ======================================================
# HOME
# ======================================================
@app.route('/')
def home():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM schemes")
    total_schemes = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin=0")
    total_users = cursor.fetchone()[0]
    conn.close()
    return render_template("home.html", total_schemes=total_schemes, total_users=total_users)


# ======================================================
# REGISTER
# ======================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not name or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )
            conn.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "danger")
            return render_template("register.html")
        finally:
            conn.close()

    return render_template("register.html")


# ======================================================
# LOGIN
# ======================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = user[12]

            if user[12] == 1:
                return redirect('/admin/dashboard')
            else:
                flash(f"Welcome back, {user[1]}!", "success")
                return redirect('/dashboard')

        flash("Invalid email or password. Please try again.", "danger")

    return render_template("login.html")


# ======================================================
# ADMIN LOGIN
# ======================================================
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=? AND is_admin=1", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[3], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = 1
            return redirect(url_for('admin_dashboard'))

        flash("Invalid admin credentials.", "danger")

    return render_template("admin_login.html")


# ======================================================
# USER DASHBOARD
# ======================================================
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        flash("Please log in to continue.", "warning")
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        cursor.execute("""
        UPDATE users SET
            age=?, income=?, category=?, state=?,
            occupation=?, education=?, area_type=?, scheme_preference=?
        WHERE id=?
        """, (
            request.form['age'],
            request.form['income'],
            request.form['category'],
            request.form['state'],
            request.form['occupation'],
            request.form['education'],
            request.form['area_type'],
            request.form['scheme_preference'],
            session['user_id']
        ))
        conn.commit()
        flash("Profile updated! Here are your new recommendations.", "success")

    cursor.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cursor.fetchone()

    recommendations = []

    if user[4] is not None and user[5] is not None:
        age = int(user[4])
        income = float(user[5])
        occupation = user[8]
        education = user[9]
        area_type = user[10]
        scheme_preference = user[11] if user[11] else "All"

        cursor.execute("SELECT * FROM schemes")
        schemes = cursor.fetchall()

        for scheme in schemes:
            # Hard filters
            if scheme[7] != "All" and scheme[7] != user[6]:
                continue
            if not (scheme[4] <= age <= scheme[5]):
                continue
            if income > scheme[6]:
                continue
            if scheme_preference != "All" and scheme[13] != scheme_preference:
                continue

            # Scoring
            score = 50

            if scheme[9] == occupation:
                score += 30
            elif scheme[9] == "All":
                score += 10

            if scheme[10] == education:
                score += 20
            elif scheme[10] == "All":
                score += 5

            if scheme[11] == area_type:
                score += 15
            elif scheme[11] == "All":
                score += 5

            midpoint = (scheme[4] + scheme[5]) / 2
            if abs(age - midpoint) < 5:
                score += 5

            score = min(score, 100)

            recommendations.append({
                "id": scheme[0],
                "name": scheme[1],
                "description": scheme[2],
                "benefit": scheme[12],
                "type": scheme[13],
                "score": score
            })

        recommendations = sorted(recommendations, key=lambda x: x['score'], reverse=True)

    conn.close()

    return render_template("dashboard.html", user=user, recommendations=recommendations[:6])


# ======================================================
# ADMIN DASHBOARD
# ======================================================
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        flash("Admin access required.", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin=0")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM schemes")
    total_schemes = cursor.fetchone()[0]

    cursor.execute("SELECT scheme_type, COUNT(*) FROM schemes GROUP BY scheme_type")
    scheme_types = cursor.fetchall()

    cursor.execute("SELECT category, COUNT(*) FROM schemes GROUP BY category")
    categories = cursor.fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_schemes=total_schemes,
        scheme_types=scheme_types,
        categories=categories
    )


# ======================================================
# ADMIN — MANAGE SCHEMES (LIST)
# ======================================================
@app.route('/admin/schemes')
def admin_schemes():
    if not session.get('is_admin'):
        flash("Admin access required.", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, scheme_name, category, state, scheme_type, benefit_amount FROM schemes ORDER BY id")
    schemes = cursor.fetchall()
    conn.close()

    return render_template("manage_schemes.html", schemes=schemes)


# ======================================================
# ADMIN — ADD SCHEME
# ======================================================
@app.route('/admin/schemes/add', methods=['GET', 'POST'])
def admin_add_scheme():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        f = request.form
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO schemes (
                scheme_name, short_description, full_description,
                min_age, max_age, max_income, category, state,
                occupation, education, area_type, benefit_amount,
                scheme_type, eligibility_details, application_steps,
                documents_required, reference_link
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            f['scheme_name'], f['short_description'], f['full_description'],
            int(f['min_age']), int(f['max_age']), float(f['max_income']),
            f['category'], f['state'], f['occupation'], f['education'],
            f['area_type'], float(f['benefit_amount']), f['scheme_type'],
            f['eligibility_details'], f['application_steps'],
            f['documents_required'], f['reference_link']
        ))
        conn.commit()
        conn.close()
        flash(f"Scheme '{f['scheme_name']}' added successfully!", "success")
        return redirect(url_for('admin_schemes'))

    return render_template("scheme_form.html", scheme=None, action="Add")


# ======================================================
# ADMIN — EDIT SCHEME
# ======================================================
@app.route('/admin/schemes/edit/<int:scheme_id>', methods=['GET', 'POST'])
def admin_edit_scheme(scheme_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    if request.method == 'POST':
        f = request.form
        cursor.execute("""
            UPDATE schemes SET
                scheme_name=?, short_description=?, full_description=?,
                min_age=?, max_age=?, max_income=?, category=?, state=?,
                occupation=?, education=?, area_type=?, benefit_amount=?,
                scheme_type=?, eligibility_details=?, application_steps=?,
                documents_required=?, reference_link=?
            WHERE id=?
        """, (
            f['scheme_name'], f['short_description'], f['full_description'],
            int(f['min_age']), int(f['max_age']), float(f['max_income']),
            f['category'], f['state'], f['occupation'], f['education'],
            f['area_type'], float(f['benefit_amount']), f['scheme_type'],
            f['eligibility_details'], f['application_steps'],
            f['documents_required'], f['reference_link'],
            scheme_id
        ))
        conn.commit()
        conn.close()
        flash(f"Scheme updated successfully!", "success")
        return redirect(url_for('admin_schemes'))

    cursor.execute("SELECT * FROM schemes WHERE id=?", (scheme_id,))
    scheme = cursor.fetchone()
    conn.close()

    if not scheme:
        flash("Scheme not found.", "warning")
        return redirect(url_for('admin_schemes'))

    return render_template("scheme_form.html", scheme=scheme, action="Edit")


# ======================================================
# ADMIN — DELETE SCHEME
# ======================================================
@app.route('/admin/schemes/delete/<int:scheme_id>', methods=['POST'])
def admin_delete_scheme(scheme_id):
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT scheme_name FROM schemes WHERE id=?", (scheme_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM schemes WHERE id=?", (scheme_id,))
        conn.commit()
        flash(f"Scheme '{row[0]}' deleted.", "info")
    conn.close()
    return redirect(url_for('admin_schemes'))


# ======================================================
# SCHEME DETAIL
# ======================================================
@app.route('/scheme/<int:scheme_id>')
def scheme_detail(scheme_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM schemes WHERE id=?", (scheme_id,))
    scheme = cursor.fetchone()
    conn.close()

    if not scheme:
        flash("Scheme not found.", "warning")
        return redirect(url_for('dashboard'))

    return render_template("scheme_detail.html", scheme=scheme)


# ======================================================
# ANALYTICS
# ======================================================
def make_chart(fig, ax):
    """Helper to convert matplotlib figure to base64 PNG."""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight',
                facecolor='#0f172a', dpi=120)
    buf.seek(0)
    encoded = base64.b64encode(buf.getvalue()).decode()
    plt.close(fig)
    return encoded


@app.route('/analytics')
def analytics():
    if not session.get('is_admin'):
        flash("Admin access required.", "danger")
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect(DATABASE)
    users_df = pd.read_sql_query("SELECT * FROM users WHERE is_admin=0", conn)
    schemes_df = pd.read_sql_query("SELECT * FROM schemes", conn)
    conn.close()

    COLORS = ['#38bdf8', '#818cf8', '#34d399', '#fb923c', '#f472b6', '#a78bfa']
    TEXT_COLOR = '#e2e8f0'
    BG = '#0f172a'
    GRID_COLOR = '#1e293b'

    plots = {}

    # Age Distribution
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    age_data = users_df['age'].dropna()
    if not age_data.empty:
        ax.hist(age_data, bins=10, color=COLORS[0], edgecolor='#0f172a', linewidth=0.5)
    ax.set_title("Age Distribution of Users", color=TEXT_COLOR, fontsize=13, pad=12)
    ax.set_xlabel("Age", color=TEXT_COLOR)
    ax.set_ylabel("Count", color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.spines[:].set_color(GRID_COLOR)
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    plots['age'] = make_chart(fig, ax)

    # Income Distribution
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    inc_data = users_df['income'].dropna()
    if not inc_data.empty:
        ax.hist(inc_data, bins=8, color=COLORS[1], edgecolor='#0f172a', linewidth=0.5)
    ax.set_title("Income Distribution of Users", color=TEXT_COLOR, fontsize=13, pad=12)
    ax.set_xlabel("Annual Income (₹)", color=TEXT_COLOR)
    ax.set_ylabel("Frequency", color=TEXT_COLOR)
    ax.tick_params(colors=TEXT_COLOR)
    ax.spines[:].set_color(GRID_COLOR)
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    plots['income'] = make_chart(fig, ax)

    # Occupation Distribution
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    occ_data = users_df['occupation'].dropna().value_counts()
    if not occ_data.empty:
        bars = ax.barh(occ_data.index, occ_data.values,
                       color=COLORS[:len(occ_data)], edgecolor='#0f172a')
    ax.set_title("Occupation Breakdown", color=TEXT_COLOR, fontsize=13, pad=12)
    ax.tick_params(colors=TEXT_COLOR)
    ax.spines[:].set_color(GRID_COLOR)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    ax.set_facecolor(BG)
    plots['occupation'] = make_chart(fig, ax)

    # Scheme Type Pie
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    type_data = schemes_df['scheme_type'].value_counts()
    if not type_data.empty:
        wedges, texts, autotexts = ax.pie(
            type_data.values, labels=None,
            colors=COLORS[:len(type_data)],
            autopct='%1.1f%%', startangle=140,
            pctdistance=0.75,
            wedgeprops=dict(linewidth=2, edgecolor='#0f172a')
        )
        for t in autotexts:
            t.set_color(BG)
            t.set_fontsize(9)
        ax.legend(type_data.index, loc='lower right',
                  labelcolor=TEXT_COLOR,
                  facecolor='#1e293b', edgecolor='#334155',
                  fontsize=9)
    ax.set_title("Scheme Type Distribution", color=TEXT_COLOR, fontsize=13, pad=12)
    plots['scheme_type'] = make_chart(fig, ax)

    # Category Distribution
    fig, ax = plt.subplots(figsize=(6, 3.5))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    cat_data = schemes_df['category'].value_counts()
    if not cat_data.empty:
        ax.bar(cat_data.index, cat_data.values,
               color=COLORS[:len(cat_data)], edgecolor='#0f172a')
    ax.set_title("Schemes by Category", color=TEXT_COLOR, fontsize=13, pad=12)
    ax.tick_params(colors=TEXT_COLOR, axis='x', rotation=15)
    ax.tick_params(colors=TEXT_COLOR, axis='y')
    ax.spines[:].set_color(GRID_COLOR)
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5)
    plots['category'] = make_chart(fig, ax)

    return render_template("analytics.html",
                           total_users=len(users_df),
                           total_schemes=len(schemes_df),
                           plots=plots)


# ======================================================
# LOGOUT
# ======================================================
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect('/')


# ======================================================
# RUN
# ======================================================
if __name__ == "__main__":
    init_db()
    seed_admin()
    seed_schemes_from_csv()
    app.run(debug=True)