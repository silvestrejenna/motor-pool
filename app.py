from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "motorpool_secret_key"

# --- CONNECT TO SUPABASE ---
def get_db_connection():
    # PASTE YOUR UPDATED URI HERE
    DB_URI = "postgresql://postgres.nudeyxdtkmgrfbepsluf:motorpool_db.312@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
    try:
        conn = psycopg2.connect(DB_URI)
        return conn
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

# --- SYNC ADMIN USER ---
def sync_assigned_user():
    assigned_email = "motorpooladmin@pup.edu.ph"
    assigned_password = "tmps.123"
    assigned_name = "Admin" # New Column
    assigned_position = "Student" # New Column

    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT email FROM users WHERE email = %s", (assigned_email,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO users (email, password, full_name, position) 
                VALUES (%s, %s, %s, %s)
            """, (assigned_email, assigned_password, assigned_name, assigned_position))
            conn.commit()
            print("Cloud Admin Synced!")
        cur.close()
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            # Store everything in session: user[3] is Name, user[4] is Position
            session['user_name'] = user[3]
            session['user_position'] = user[4]
            return redirect(url_for('home'))
        else:
            flash("Invalid credentials!")
            return redirect(url_for('index'))
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_name' not in session:
        return redirect(url_for('index'))
    return render_template('index.html')

@app.route('/auth/user')
def auth_user():
    if 'user_name' not in session:
        return {}, 401

    return {
        "full_name": session.get("user_name"),
        "email": session.get("user_email", "motorpool@pup.edu.ph")
    }

@app.route('/inventory')
def inventory():
    return "<h1>Inventory Page (Under Development)</h1>"

@app.route('/records')
def records():
    return "<h1>Records Page (Under Development)</h1>"

if __name__ == '__main__':
    sync_assigned_user()
    app.run(debug=True, port=5055)