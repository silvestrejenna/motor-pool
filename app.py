from flask import Flask, render_template, request, redirect, url_for
import os
import psycopg2

app = Flask(__name__)

# --- DATABASE CONNECTION ---
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="motorpool_database",
            user="postgres",
            password="motorpool_db"
        )
        return conn
    except Exception as e:
        print(f"Database connection failed: {e}")
        return None

# --- ASSIGN AND SYNC USER ---
def sync_assigned_user():
    # 1. You assign the user here
    assigned_email = "motorpool@pup.edu.ph"
    assigned_password = "tmps.123"

    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        # 2. Check if this specific user already exists in the DB
        cur.execute("SELECT email FROM users WHERE email = %s", (assigned_email,))
        exists = cur.fetchone()

        if not exists:
            # 3. If they don't exist, insert them into the database
            cur.execute("INSERT INTO users (email, password) VALUES (%s, %s)", 
                        (assigned_email, assigned_password))
            conn.commit()
            print(f"Assigned user {assigned_email} has been added to the database.")
        else:
            print(f"User {assigned_email} is already in the database.")
            
        cur.close()
        conn.close()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/home')
def home():
    return render_template('homepage.html')

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        # Check if the credentials entered match ANY user in the database
        cur.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            print(f"Welcome, {email}! Access Granted.")
            return redirect(url_for('home'))
        else:
            return "Invalid credentials. User does not exist in the database."
    return "Database connection error."

if __name__ == '__main__':
    # Run the sync function before starting the server
    sync_assigned_user() 
    
    port = int(os.getenv('PORT', 5055))
    app.run(debug=True, port=port)