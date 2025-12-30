from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import psycopg2

app = Flask(__name__)
app.secret_key = "motorpool_secret_key"

# --- CONNECT TO SUPABASE ---
def get_db_connection():
    DB_URI = "postgresql://postgres.nudeyxdtkmgrfbepsluf:motorpool_db.312@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"
    try:
        conn = psycopg2.connect(DB_URI)
        print("Connected to the database successfully.")
        return conn
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

# --- SYNC ADMIN USER ---
def sync_assigned_user():
    assigned_email = "motorpooladmin@pup.edu.ph"
    assigned_password = "tmps.123"
    assigned_name = "Admin"  # New Column
    assigned_position = "Student"  # New Column

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


# =======================================================
# 🚗 VEHICLE INVENTORY - NEW CODE STARTS HERE
# =======================================================

@app.route('/inventory')
def inventory():
    if 'user_name' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    vehicles = []
    
    if conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT vehicle_id, name, plate_number, color, type, status, mileage 
            FROM vehicle 
            ORDER BY vehicle_id ASC
        """)
        vehicles = cur.fetchall()
        cur.close()
        conn.close()

    return render_template("vehicle_inv.html", vehicles=vehicles)


@app.route('/add_vehicle', methods=['POST'])
def add_vehicle():
    name = request.form['name']
    plate_number = request.form['plate_number']
    color = request.form.get('color')
    type = request.form['type']
    status = request.form['status']
    mileage = request.form['mileage']

    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO vehicle (name, plate_number, color, type, status, mileage)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, plate_number, color, type, status, mileage))
        conn.commit()
        cur.close()
        conn.close()

    flash("Vehicle record added successfully!")
    return redirect(url_for('inventory'))


@app.route('/delete_vehicle/<int:id>')
def delete_vehicle(id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # This matches the vehicle_id in your Supabase table
            cur.execute("DELETE FROM vehicle WHERE vehicle_id = %s", (id,))
            conn.commit()
            flash("Vehicle deleted successfully!")
            cur.close()
        except Exception as e:
            print(f"Delete error: {e}")
            flash("Error deleting record.")
            conn.rollback()
        finally:
            conn.close()
    
    return redirect(url_for('inventory'))


@app.route('/update_vehicle/<int:id>', methods=['POST'])
def update_vehicle(id):
    name = request.form.get('name')
    plate = request.form.get('plate')
    color = request.form.get('color')
    v_type = request.form.get('type')
    status = request.form.get('status')
    
    # Ensure mileage is an integer
    mileage_raw = request.form.get('mileage', '0')
    try:
        mileage = int(mileage_raw)
    except (ValueError, TypeError):
        mileage = 0

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                UPDATE vehicle 
                SET name=%s, plate_number=%s, color=%s, type=%s, status=%s, mileage=%s 
                WHERE vehicle_id=%s
            """, (name, plate, color, v_type, status, mileage, id))
            conn.commit()
            cur.close()
            flash("Vehicle updated successfully!")
        except Exception as e:
            print(f"Update error: {e}")
            conn.rollback()
            flash("Failed to update record.")
        finally:
            conn.close()
    
    return redirect(url_for('inventory'))

# =======================================================
# 🚗 VEHICLE INVENTORY - NEW CODE ENDS HERE
# =======================================================

@app.route('/tools-equipment')
def tools_equipment():
    if 'user_name' not in session:
        return redirect(url_for('index'))
    return render_template("tools_equipment.html")

@app.route('/records')
def records():
    if 'user_name' not in session:
        return redirect(url_for('index'))

    return "<h1>Records Page (Under Development)</h1>"

@app.route('/auth/user')
def auth_user():
    if 'user_name' not in session:
        return {}, 401

    return {
        "full_name": session.get("user_name"),
        "email": "motorpooladmin@pup.edu.ph"
    }

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return '', 204

if __name__ == '__main__':
    sync_assigned_user()
    app.run(debug=True, port=5055)
