import email
from fileinput import filename
from pydoc import doc
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import psycopg2
from psycopg2 import pool
from docx import Document
import psycopg2.extras
from flask import send_from_directory
from datetime import datetime
from functools import wraps
from threading import Thread
import bcrypt, random, smtplib
import calendar
from datetime import datetime, timedelta
import time



load_dotenv()  # Load environment variables from .env file


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

db_pool = None

class PooledConnection:
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        global db_pool
        if self._conn:
            db_pool.putconn(self._conn)
            self._conn = None


def init_db_pool():
    global db_pool
    if db_pool is None:
        DB_URI = os.getenv("DATABASE_URL")
        if not DB_URI:
            raise RuntimeError("DATABASE_URL is not configured")
        db_pool = pool.ThreadedConnectionPool(1, 10, dsn=DB_URI)

# =======================================================
# GLOBAL LOGIN PROTECTION
# =======================================================
@app.before_request
def require_login():

    allowed_routes = [
        'login',
        'register',
        'forgot_password',
        'verify_otp',
        'verify_reset_otp',
        'reset_password',
        'resend_otp',
        'static'
    ]

    if not request.endpoint:
        return

    if 'user_id' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))
    
    if 'user_id' in session and session.get('user_role') in ['Admin', 'Staff']:
        last_check = session.get('last_notification_check', 0)
        if time.time() - last_check > 60:
            create_pending_request_notifications()
            session['last_notification_check'] = time.time()

ALLOWED_DOMAINS = ["@pup.edu.ph", "@iskolarngbayan.pup.edu.ph"]
TEST_EMAILS = ["silvestrejennamae09@gmail.com"]

@app.template_filter('month_name')
def month_name_filter(month_number):
    try:
        return calendar.month_name[int(month_number)]
    except:
        return month_number


# =========================ROLE BASED AUTHENTICATION=========================
def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('index'))

            if session.get('user_role') not in allowed_roles:
                flash("Access denied")
                return redirect(url_for('home'))

            return f(*args, **kwargs)
        return wrapped
    return decorator
# =========================END ROLE BASED AUTHENTICATION=========================

# --- CONNECT TO SUPABASE ---6ymhn
def get_db_connection():
    try:
        init_db_pool()
        conn = db_pool.getconn()
        return PooledConnection(conn)
    except Exception as e:
        print(f"Connection failed: {e}")
        return None

# --- SYNC ADMIN USER ---
#def sync_assigned_user():
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

@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'GET':
        return render_template("login.html")
    session.clear()  # ✅ wipe previous user completely

    email = request.form.get('email')
    password = request.form.get('password')

    conn = get_db_connection()
    if not conn:
        flash("Database connection failed")
        return redirect(url_for('index'))

    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, email, full_name, position, role, password
        FROM users
        WHERE email = %s
        """,
        (email,)
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    # ❌ USER NOT FOUND
    if not user:
        flash("Invalid email or password")
        return redirect(url_for('index'))
    
    stored_password = user[5]

    if not stored_password:
        flash("Invalid email or password")
        return redirect(url_for('index'))

    if not bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
        flash("Invalid email or password")
        return redirect(url_for('index'))
    

    # ✅ LOGIN SUCCESS
    session['user_id'] = user[0]
    session['user_email'] = user[1]
    session['user_fullname'] = user[2]
    session['user_position'] = user[3]
    session['user_role'] = user[4]

    role = session.get('user_role')

    if role == "Admin":
        return redirect(url_for('home'))
    elif role == "Staff":
        return redirect(url_for('home'))
    elif role == "Client":
        return redirect(url_for('user_home'))
    else:
        flash("Role does not exist")
        return redirect(url_for('index'))

    

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'GET':
        return render_template("register.html")

    firstname = request.form.get('firstname')
    lastname = request.form.get('lastname')
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    full_name = f"{firstname} {lastname}"

    #EMAIL VALIDATION
    if not allowed_email(email):
        flash("Please use a valid PUP email address")
        return redirect(url_for('register'))

    if password != confirm_password:
            flash("Passwords do not match")
            return redirect(url_for('register'))
    
    #CHECK DUPLICATE EMAIL
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing_user = cur.fetchone()
    cur.close()
    conn.close()

    if existing_user:
        flash("An account with this email already exists.")
        return redirect(url_for('register'))
    
    #HASH PASSWORD
    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    #GENERATE OTP
    otp = generate_otp()

    print("Generated OTP:", otp)
    print("Sending to:", email)
    
    #STORE TEMPT DATA
    session['otp'] = otp
    session['register_email'] = email
    session['register_fullname'] = full_name
    session['register_password'] = hashed_password

    send_otp_email_async(email, otp)
    return redirect(url_for('verify_otp'))

    # Continue with account creation logic
    # ... (existing code for creating account)

#=========================== CREATE ACCOUNT OTP ==================================
def allowed_email(email):
    if email.endswith(tuple(ALLOWED_DOMAINS)) or email in TEST_EMAILS:
        return True
    return False


@app.route('/')
def index():
    return render_template('login.html')

@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('index.html')

# =======================================================
# 🚗 VEHICLE INVENTORY - NEW CODE STARTS HERE
# =======================================================

@app.route('/inventory')
@role_required('Admin', 'Staff')
def inventory():

    conn = get_db_connection()
    vehicles = []
    rfids = []
    
    if conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT vehicle_id, name, plate_number, color, type, status, mileage 
            FROM vehicle 
            ORDER BY vehicle_id ASC
        """)
        vehicles = cur.fetchall()

        # ================= RFID =================
        cur.execute("""
            SELECT
                id,
                vehicle_name,
                plate_number,
                autosweep_account,
                autosweep_card,
                easytrip_account,
                easytrip_card
            FROM rfid_records
            ORDER BY id ASC
        """)

        rfids = cur.fetchall()

        cur.close()
        conn.close()

    return render_template(
        "vehicle_inv.html",
        vehicles=vehicles,
        rfids=rfids
    )


@app.route('/add_vehicle', methods=['POST'])
@role_required('Admin')
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
@role_required('Admin')
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
@role_required('Admin')
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

# ================= RFID =================

@app.route("/add_rfid", methods=["POST"])
def add_rfid():

    vehicle = request.form["vehicle"]
    plate = request.form["plate"]

    autosweep_account = request.form["autosweep_account"]
    autosweep_card = request.form["autosweep_card"]

    easytrip_account = request.form["easytrip_account"]
    easytrip_card = request.form["easytrip_card"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO rfid_records
        (
            vehicle_name,
            plate_number,
            autosweep_account,
            autosweep_card,
            easytrip_account,
            easytrip_card
        )
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (

        vehicle,
        plate,

        autosweep_account,
        autosweep_card,

        easytrip_account,
        easytrip_card

    ))

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("inventory"))

# ================= UPDATE RFID =================

@app.route("/update_rfid/<int:id>", methods=["POST"])
@role_required('Admin')
def update_rfid(id):

    try:

        vehicle = request.form.get("vehicle")
        plate = request.form.get("plate")

        auto_acc = request.form.get("auto_acc")
        auto_card = request.form.get("auto_card")

        easy_acc = request.form.get("easy_acc")
        easy_card = request.form.get("easy_card")

        print("RFID UPDATE DATA:")
        print(vehicle)
        print(plate)
        print(auto_acc)
        print(auto_card)
        print(easy_acc)
        print(easy_card)

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE rfid_records
            SET
                vehicle_name=%s,
                plate_number=%s,
                autosweep_account=%s,
                autosweep_card=%s,
                easytrip_account=%s,
                easytrip_card=%s
            WHERE id=%s
        """, (
            vehicle,
            plate,
            auto_acc,
            auto_card,
            easy_acc,
            easy_card,
            id
        ))

        conn.commit()

        print("ROWS UPDATED:", cur.rowcount)

        cur.close()
        conn.close()

        flash("RFID record updated!")

    except Exception as e:

        print("RFID UPDATE ERROR:", e)

    return redirect(url_for("inventory"))


# ================= DELETE RFID =================

@app.route("/delete_rfid/<int:id>")
def delete_rfid(id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM rfid_records
        WHERE id=%s
    """, (id,))

    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for("inventory"))

# =======================================================
# 🚗 VEHICLE INVENTORY - NEW CODE ENDS HERE
# =======================================================

# --- GASOLINE & RFID ROUTES ---

@app.route('/gas_rfid')
@role_required('Admin', 'Staff')
def gas_rfid():

    conn = get_db_connection()
    records = []
    vehicles = [] 
    summary = {"total_fuel": "0L", "avg_fuel": "0L", "easytrip": "₱0", "autosweep": "₱0"}
    
    if conn:
        try:
            cur = conn.cursor()
            # Fetch vehicles for dropdown
            cur.execute("SELECT name FROM vehicle ORDER BY name ASC")
            vehicles = cur.fetchall()

            # FIX: Added double quotes to "gasRfid_id" and fixed plate_number
            cur.execute("""
                SELECT f.*, v.plate_number 
                FROM gas_rfid f 
                LEFT JOIN vehicle v ON f.v_name = v.name 
                ORDER BY f."gasRfid_id" ASC
            """)
            records = cur.fetchall()

            # FIX: Changed purchased_trip to purchased_tri to match your DB schema
            cur.execute("""
                SELECT SUM(purchased_trip), AVG(purchased_trip), 
                       SUM(easy_rfid_bal), SUM(auto_rfid_bal) 
                FROM gas_rfid
            """)
            row = cur.fetchone()
            if row and row[0] is not None:
                summary = {
                    "total_fuel": f"{row[0]:,.1f}L",
                    "avg_fuel": f"{row[1]:,.1f}L",
                    "easytrip": f"₱{row[2]:,.2f}",
                    "autosweep": f"₱{row[3]:,.2f}"
                }
            cur.close()
        except Exception as e:
            print(f"Query Error: {e}")
        finally:
            conn.close()

    return render_template("gas&rfid_inv.html", records=records, vehicles=vehicles, summary=summary)

@app.route('/add_fuel', methods=['POST'])
@role_required('Admin')
def add_fuel():
    # Make sure your form uses name="v_name" for the vehicle selection
    data = (
        request.form['v_name'], request.form['date'], request.form['driver'],
        request.form['gas_bal_tank'], request.form['purchased_trip'], request.form['bal_after_trip'],
        request.form['km_beginning'], request.form['km_end'], request.form['km_used'],
        request.form['easy_rfid_bal'], request.form['auto_rfid_bal'], request.form['remarks']
    )
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO gas_rfid (v_name, date, driver, gas_bal_tank, purchased_trip, bal_after_trip, km_beginning, km_end, km_used, easy_rfid_bal, auto_rfid_bal, remarks)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, data)
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('gas_rfid'))

from flask import jsonify # Ensure jsonify is imported at the top

@app.route('/update_fuel', methods=['POST'])
@role_required('Admin')
def update_fuel():
    data = request.get_json()
    record_id = data.get('id')
    
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            # We use the double quotes because gasRfid_id is case-sensitive in Supabase
            query = """
                UPDATE gas_rfid 
                SET v_name = %s, date = %s, driver = %s, 
                    gas_bal_tank = %s, purchased_trip = %s, bal_after_trip = %s, 
                    km_beginning = %s, km_end = %s, km_used = %s, 
                    easy_rfid_bal = %s, auto_rfid_bal = %s
                WHERE "gasRfid_id" = %s
            """
            cur.execute(query, (
                data['v_name'], data['date'], data['driver'],
                data['gas_bal_tank'], data['purchased_trip'], data['bal_after_trip'],
                data['km_beginning'], data['km_end'], data['km_used'],
                data['easy_rfid_bal'], data['auto_rfid_bal'], record_id
            ))
            conn.commit()
            cur.close()
            return jsonify({"status": "success"}), 200
        except Exception as e:
            print(f"Update Error: {e}")
            return jsonify({"status": "error", "message": str(e)}), 400
        finally:
            conn.close()
    return jsonify({"status": "error", "message": "No DB connection"}), 500


@app.route('/delete_fuel/<int:id>')
@role_required('Admin')
def delete_fuel(id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM gas_rfid WHERE "gasRfid_id" = %s', (id,))
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"Delete Error: {e}")
        finally:
            conn.close()
    return redirect(url_for('gas_rfid'))

# --- END OF GASOLINE & RFID ROUTES ---

# ================================
# 🧰 TOOLS & EQUIPMENT
# ================================

@app.route('/tools-equipment')
@role_required('Admin', 'Staff')
def tools_equipment():
    
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, item_code, name, category, quantity, condition
        FROM tools_equipment
        ORDER BY id ASC
    """)
    tools = cur.fetchall()

    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE condition = 'Excellent') AS excellent,
            COUNT(*) FILTER (WHERE condition = 'Good') AS good
        FROM tools_equipment
    """)
    row = cur.fetchone()
    total = row[0]
    excellent = row[1]
    good = row[2]

    cur.close()
    conn.close()

    return render_template(
        "tools_equipment.html",
        tools=tools,
        total=total,
        excellent=excellent,
        good=good
    )


# ================================
# ➕ SAVE TOOL
# ================================
@app.route("/save_tool", methods=["POST"])
@role_required('Admin')
def save_tool():
    conn = get_db_connection()
    cur = conn.cursor()

    name = request.form["name"]
    category = request.form["category"]
    quantity = request.form["quantity"]
    condition = request.form["condition"]

    # 1️⃣ Get the last item_code number (T001 → 1)
    cur.execute("""
        SELECT COALESCE(
            MAX(CAST(SUBSTRING(item_code FROM 2) AS INTEGER)),
            0
        )
        FROM tools_equipment
    """)
    last_number = cur.fetchone()[0]

    # 2️⃣ Generate next code
    next_number = last_number + 1
    item_code = f"T{next_number:03d}"   # T001, T002, T003

    # 3️⃣ Insert with generated item_code
    cur.execute("""
        INSERT INTO tools_equipment (item_code, name, category, quantity, condition)
        VALUES (%s, %s, %s, %s, %s)
    """, (item_code, name, category, quantity, condition))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("tools_equipment"))

# ================================
# ✏️ UPDATE TOOL (INLINE EDIT)
# ================================
@app.route("/update_tool", methods=["POST"])
@role_required('Admin')
def update_tool():
    data = request.get_json()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE tools_equipment
        SET
            name = %s,
            category = %s,
            quantity = %s,
            condition = %s
        WHERE id = %s
    """, (
        data["name"],
        data["category"],
        data["quantity"],
        data["condition"],
        data["id"]
    ))

    conn.commit()
    cur.close()
    conn.close()

    return "", 204


# ================================
# 🗑️ DELETE TOOL
# ================================
@app.route('/delete_tool/<int:id>')
@role_required('Admin')
def delete_tool(id):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM tools_equipment WHERE id = %s", (id,))
    conn.commit()

    cur.close()
    conn.close()

    return redirect(url_for('tools_equipment'))

# =======================================================
# 🧰 END TOOLS & EQUIPMENT
# =======================================================

# --- maintenance & pms ---
@app.route('/maintenance_pms')
@role_required('Admin', 'Staff')
def maintenance_pms():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # 1. Fetch Vehicles for the dropdown selectors in your modals
        # Note: Your table is named 'vehicle' (singular) based on your sidebar screenshot
        cur.execute('SELECT vehicle_id, name FROM vehicle')
        vehicles = cur.fetchall()
        
        # 2. Fetch Maintenance Logs (Matches your 'maintenance_log' Supabase table)
        cur.execute('SELECT * FROM maintenance_log ORDER BY date DESC')
        m_records = cur.fetchall()
        
        # 3. Fetch PMS Logs (Matches your 'pms_log' Supabase table)
        cur.execute('SELECT * FROM pms_log ORDER BY last_pms_date DESC')
        p_records = cur.fetchall()
        
        # 4. Calculate Stats for the UI Cards
        cur.execute("""
            SELECT
                COALESCE(SUM(cost), 0) AS total_m_cost,
                COUNT(*) FILTER (WHERE date >= date_trunc('month', CURRENT_DATE)) AS m_count
            FROM maintenance_log
        """)
        row = cur.fetchone()
        total_m_cost = row[0]
        m_count = row[1]
        
        # Total PMS Scheduled (Count of records in PMS table)
        pms_scheduled_count = len(p_records)

        return render_template('maintenance_pms.html', 
                               vehicles=vehicles, 
                               m_records=m_records, 
                               p_records=p_records,
                               total_m_cost=total_m_cost,
                               m_count=m_count,
                               pms_count=pms_scheduled_count)
                               
    except Exception as e:
        print(f"Error connecting to Maintenance/PMS: {e}")
        return f"Database Error: {e}", 500
    finally:
        cur.close()
        conn.close()

# Route to save a new Maintenance Record
@app.route('/add_maintenance', methods=['POST'])
@role_required('Admin')
def add_maintenance():
    # Mapping HTML form names to your Supabase columns
    date = request.form.get('date')
    v_name = request.form.get('vehicle_name') # Matches your column 'vehicle_name'
    prob = request.form.get('problem')
    action = request.form.get('action_taken')
    cost = request.form.get('cost')
    mech = request.form.get('mechanic')

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''INSERT INTO maintenance_log (date, vehicle_name, problem, action_taken, cost, mechanic) 
                    VALUES (%s, %s, %s, %s, %s, %s)''', 
                (date, v_name, prob, action, cost, mech))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance_pms'))

@app.route('/update_maintenance/<int:id>', methods=['POST'])
@role_required('Admin')
def update_maintenance(id):
    date = request.form.get('date')
    vehicle = request.form.get('vehicle')          # ✅ MATCH JS
    problem = request.form.get('problem')
    action_taken = request.form.get('action_taken')
    cost = request.form.get('cost')
    mechanic = request.form.get('mechanic')

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE maintenance_log
            SET
                date = %s,
                vehicle_name = %s,
                problem = %s,
                action_taken = %s,
                cost = %s,
                mechanic = %s
            WHERE id = %s
        """, (
            date,
            vehicle,
            problem,
            action_taken,
            cost,
            mechanic,
            id
        ))
        conn.commit()
    except Exception as e:
        print(f"Error updating maintenance record: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    print(request.form)
    return redirect(url_for('maintenance_pms'))


@app.route('/delete_maintenance/<int:id>', methods=['POST'])
@role_required('Admin')
def delete_maintenance(id):
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM maintenance_log WHERE id = %s', (id,))
            conn.commit()
            flash("Maintenance record deleted successfully!")
            cur.close()
        except Exception as e:
            print(f"Delete error: {e}")
            flash("Error deleting maintenance record.")
            conn.rollback()
        finally:
            conn.close()
        
    return redirect(url_for('maintenance_pms'))
    

#--pms--#
# --- ROUTE TO ADD PMS RECORD ---
@app.route('/add_pms', methods=['POST'])
@role_required('Admin')
def add_pms():
    # Fetching data from the form (matches your expected modal fields)
    v_name = request.form.get('vehicle_name')
    last_pms = request.form.get('last_pms_date')
    km = request.form.get('km')
    oil = request.form.get('oil_liters')
    next_pms = request.form.get('next_pms_date')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Note: 'next_pms_date' matches your database schema
        cur.execute('''
            INSERT INTO pms_log (vehicle_name, last_pms_date, km, oil_liters, next_pms_date)
            VALUES (%s, %s, %s, %s, %s)
        ''', (v_name, last_pms, km, oil, next_pms))
        conn.commit()
    except Exception as e:
        print(f"Error adding PMS record: {e}")
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('maintenance_pms'))

# --- ACTION BUTTON FUNCTIONS (DELETE) ---
@app.route('/update_pms/<int:id>', methods=['POST'])
@role_required('Admin')
def update_pms(id):
    vehicle = request.form.get('vehicle')
    last_pms = request.form.get('last_pms_date')
    km = request.form.get('km')
    oil = request.form.get('oil_liters')
    next_pms = request.form.get('next_pms_date')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            UPDATE pms_log
            SET
                vehicle_name = %s,
                last_pms_date = %s,
                km = %s,
                oil_liters = %s,
                next_pms_date = %s
            WHERE id = %s
        """, (
            vehicle,
            last_pms,
            km,
            oil,
            next_pms,
            id
        ))
        conn.commit()
    except Exception as e:
        print(f"Error updating PMS record: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

    print(request.form)

    if not last_pms or not next_pms:
        flash("PMS dates cannot be empty.")
    return redirect(url_for('maintenance_pms'))

    


@app.route('/delete_pms/<int:id>', methods=['POST'])
@role_required('Admin')
def delete_pms(id):
    conn = get_db_connection()

    if conn:
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM pms_log WHERE id = %s', (id,))
            conn.commit()
            flash("PMS record deleted successfully!")   
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Delete error: {e}")
            flash("Error deleting PMS record.")
            conn.rollback()
        finally:
            conn.close()

        return redirect(url_for('maintenance_pms'))

# --- END maintenance & pms ---

# =======================================================
# 🧰 PARTS & SUPPLIES
# =======================================================

@app.route('/parts-supplies')
@role_required('Admin', 'Staff')
def parts_supplies():

    conn = get_db_connection()
    parts = []
    total = in_stock = low_stock = out_stock = 0

    if conn:
        cur = conn.cursor()

        # IMPORTANT: use part_id (not id)
        cur.execute("SELECT * FROM parts_supplies ORDER BY part_id ASC")
        parts = cur.fetchall()

        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE stock > min_stock) AS in_stock,
                COUNT(*) FILTER (WHERE stock <= min_stock AND stock > 0) AS low_stock,
                COUNT(*) FILTER (WHERE stock = 0) AS out_stock
            FROM parts_supplies
        """)
        row = cur.fetchone()
        total = row[0]
        in_stock = row[1]
        low_stock = row[2]
        out_stock = row[3]

        cur.close()
        conn.close()

    return render_template(
        "parts_supplies.html",
        parts=parts,
        total=total,
        in_stock=in_stock,
        low_stock=low_stock,
        out_stock=out_stock
    )


# ===============================
# ➕ ADD PART
# ===============================
@app.route('/add-part', methods=['POST'])
@role_required('Admin')
def add_part():

    name = request.form['name']
    category = request.form['category']
    stock = int(request.form['stock'])
    min_stock = int(request.form['min_stock'])
    unit = request.form['unit']

    # ===============================
    # AUTO PART CODE GENERATION
    # ===============================
    conn = get_db_connection()
    if not conn:
        return redirect(url_for('parts_supplies'))

    cur = conn.cursor()

    cur.execute("""
        SELECT part_code
        FROM parts_supplies
        ORDER BY part_id DESC
        LIMIT 1
    """)
    last_code = cur.fetchone()

    if last_code:
        last_num = int(last_code[0][1:])  # remove 'P'
        new_code = f"P{last_num + 1:03d}"
    else:
        new_code = "P001"

    # AUTO STATUS
    if stock == 0:
        status = "Out of Stock"
    elif stock <= min_stock:
        status = "Low Stock"
    else:
        status = "In Stock"

    cur.execute("""
        INSERT INTO parts_supplies
        (part_code, name, category, stock, min_stock, unit, status)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
    """, (new_code, name, category, stock, min_stock, unit, status))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('parts_supplies'))

# ===============================
# ✏️ UPDATE PART
# ===============================
@app.route('/update-part/<int:part_id>', methods=['POST'])
@role_required('Admin')
def update_part(part_id):
    stock = int(request.form['stock'])
    min_stock = int(request.form['min_stock'])

    # AUTO STATUS
    if stock == 0:
        status = "Out of Stock"
    elif stock <= min_stock:
        status = "Low Stock"
    else:
        status = "In Stock"

    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE parts_supplies
            SET stock=%s, min_stock=%s, status=%s
            WHERE part_id=%s
        """, (stock, min_stock, status, part_id))
        conn.commit()
        cur.close()
        conn.close()

    return redirect(url_for('parts_supplies'))

# ===============================
# 🗑️ DELETE PART
# ===============================
@app.route('/delete-part/<int:part_id>', methods=['POST'])
@role_required('Admin')
def delete_part(part_id):

    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM parts_supplies WHERE part_id = %s",
                (part_id,)
            )
            conn.commit()
            cur.close()
        except Exception as e:
            print(f"Delete error: {e}")
            conn.rollback()
        finally:
            conn.close()

    return redirect(url_for('parts_supplies'))

# =======================================================
# 🧰 PARTS & SUPPLIES -- END
# =======================================================

# =======================================================
# REPORTS START
# =======================================================
@app.route("/reports", methods=["GET"])
@role_required("Admin", "Staff")
def reports():

    recent_reports = fetch_recent_reports()
    summary = fetch_reports_summary()

    return render_template(
        "reports.html",
        recent_reports=recent_reports,
        total_reports=summary["total_reports"],
        reports_this_month=summary["this_month"],
        month_name=summary["month_name"],
        most_generated_title=summary["most_generated"]
    )




#==========GAS&RFID REPORT GENERATION=============================

def fetch_gas_rfid_rows(month, year):
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor()

    query = """
        SELECT
            date,
            v_name,
            driver,
            gas_bal_tank,
            purchased_trip,
            bal_after_trip,
            km_beginning,
            km_end,
            km_used,
            easy_rfid_bal,
            auto_rfid_bal,
            remarks
        FROM gas_rfid
        WHERE EXTRACT(MONTH FROM date) = %s
          AND EXTRACT(YEAR FROM date) = %s
        ORDER BY date ASC
    """

    cur.execute(query, (month, year))
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return rows

def insert_gas_rfid_rows(doc, rows):
    table = doc.tables[0]  # first table in the template

    for row in rows:
        cells = table.add_row().cells

        cells[0].text = str(row[0])   # date
        cells[1].text = str(row[1])   # vehicle name
        cells[2].text = str(row[2])   # driver
        cells[3].text = str(row[3])   # gas balance in tank
        cells[4].text = str(row[4])   # purchased during trip
        cells[5].text = str(row[5])   # balance after trip
        cells[6].text = str(row[6])   # KM beginning
        cells[7].text = str(row[7])   # KM end
        cells[8].text = str(row[8])   # KM used
        cells[9].text = str(row[9])   # RFID EasyTrip
        cells[10].text = str(row[10]) # RFID AutoSweep
        cells[11].text = ""            # remarks
        cells[12].text = ""            # signature


def calculate_gas_rfid_summary(month, year):
    conn = get_db_connection()
    if not conn:
        return {}

    cur = conn.cursor()

    cur.execute("""
        SELECT
            SUM(purchased_trip) AS total_gas,
            AVG(purchased_trip) AS avg_gas,
            SUM(auto_rfid_bal) AS total_autosweep,
            SUM(easy_rfid_bal) AS total_easytrip
        FROM gas_rfid
        WHERE
            date >= make_date(%s, %s, 1)
            AND date < (make_date(%s, %s, 1) + INTERVAL '1 month')
    """, (year, month, year, month))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "total_gas": round(result[0] or 0, 2),
        "avg_gas": round(result[1] or 0, 2),
        "total_autosweep": round(result[2] or 0, 2),
        "total_easytrip": round(result[3] or 0, 2),
    }


def replace_placeholder(doc, key, value):
    for paragraph in doc.paragraphs:
        if key in paragraph.text:
            paragraph.text = paragraph.text.replace(key, value)

#========SAVE REPORT RECORD TO DB=============================

def save_report_record(report_type, month, year, file_name, file_path):
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO reports (report_type, month, year, file_name, file_path)
        VALUES (%s, %s, %s, %s, %s)
    """, (report_type, month, year, file_name, file_path))


    conn.commit()
    cur.close()
    conn.close()
#========GAS&RFID END==========================================

#==========VEHICLE INVENTORY REPORT GENERATION============================= 

#===FETCH VEHICLE ROWS FROM DB====
def fetch_vehicle_rows():
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
                SELECT 
                    name, plate_number, color, type, status, mileage
                FROM vehicle
                ORDER BY name
            """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

#=====INSERT VEHICLE ROWS INTO DOCX TABLE====
def insert_vehicle_rows(doc,rows):
    table = doc.tables[0]

    for row in rows:
        cells = table.add_row().cells

        cells[0].text = str(row[0])   # name
        cells[1].text = str(row[1])   # plate_number
        cells[2].text = str(row[2])   # color
        cells[3].text = str(row[3])   # type
        cells[4].text = str(row[4])   # status
        cells[5].text = str(row[5])   # mileage

#==for summary====
def calculate_vehicle_summary():
    # Placeholder for future summary calculations
    conn = get_db_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM vehicle")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vehicle WHERE status = 'Active'")
    active = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vehicle WHERE status = 'Inactive'")
    inactive = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM vehicle WHERE status = 'Maintenance'")
    maintenance = cur.fetchone()[0]

    cur.execute("""
                SELECT name, mileage
                FROM vehicle
                ORDER BY mileage DESC
                LIMIT 1
                """)
    
    top_vehicle = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "total": total,
        "active": active,
        "inactive": inactive,
        "maintenance": maintenance,
        "most_mileage": (
            f"{top_vehicle[0]} ({top_vehicle[1]}km)"
            if top_vehicle else "N/A"
        )
    }


def fetch_vehicle_type_distribution():
    conn = get_db_connection()
    if not conn:
        return {}

    cur = conn.cursor()

    cur.execute("""
        SELECT type, COUNT(*) 
        FROM vehicle 
        GROUP BY type
        ORDER BY COUNT(*) DESC        
    """)
    results = cur.fetchall()

    cur.close()
    conn.close()

    return results

def insert_vehicle_type_distribution(doc, distribution_rows):
    lines = []  # second table in the template

    for vehicle_type, count in distribution_rows:
        lines.append(f"{vehicle_type} : {count}")

    distribution_text = "\n".join(lines)

    replace_placeholder(
        doc,
        "{{vehicle_type_distribution}}",
        distribution_text
    )

#========VEHICLE INVENTORY REPORT END==========================================
#=========Vehicle_details start==========================================
@app.route("/vehicle/<int:vehicle_id>")
def vehicle_details(vehicle_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, plate_number, color, type, status, mileage
        FROM vehicle
        WHERE id = %s
    """, (vehicle_id,))
    vehicle = cur.fetchone()

    if vehicle is None:
        return "Vehicle not found", 404

    cur.execute("""
        SELECT date, description
        FROM maintenance_log
        WHERE vehicle_id = %s
        ORDER BY date DESC
    """, (vehicle_id,))
    maintenance = cur.fetchall()

    cur.execute("""
        SELECT date, liters
        FROM gas_rfid
        WHERE vehicle_id = %s
        ORDER BY date DESC
    """, (vehicle_id,))
    gas = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "vehicle_details.html",
        vehicle=vehicle,
        maintenance=maintenance,
        gas=gas
    )

#=========Vehicle_details end==========================================
#=========MAINTENANCE & PMS REPORT START==========================================

def fetch_maintenance_rows():
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
                SELECT
                    date,
                    vehicle_name,
                    problem, 
                    action_taken, 
                    cost, 
                    mechanic
                FROM maintenance_log
                ORDER BY date
            """)
    
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def insert_maintenance_rows(doc, rows):
    # Insert maintenance and PMS rows into the document
    table = doc.tables[0]  # Assuming the first table is for maintenance and PMS
    
    for row in rows:
        cells = table.add_row().cells
        cells[0].text = str(row[0])  # date
        cells[1].text = str(row[1])  # vehicle_name
        cells[2].text = str(row[2])  # problem
        cells[3].text = str(row[3])  # action_taken
        cells[4].text = str(row[4])  # cost
        cells[5].text = str(row[5])  # mechanic


def calculate_maintenance_summary():
    conn = get_db_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM maintenance_log")
    total_maintenance = cur.fetchone()[0]

    cur.execute("SELECT SUM(cost) FROM maintenance_log")
    total_cost = cur.fetchone()[0]

    cur.execute("SELECT COUNT(problem) FROM maintenance_log")
    total_problems = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT mechanic) FROM maintenance_log")
    total_mechanics = cur.fetchone()[0]

    cur.execute("""
                SELECT vehicle_name, cost
                FROM maintenance_log
                WHERE cost = (SELECT MAX(cost) FROM maintenance_log)
                LIMIT 1
                """)
    highest_cost = cur.fetchone()

    cur.execute("""
                SELECT vehicle_name, cost
                FROM maintenance_log
                WHERE cost = (SELECT MIN(cost) FROM maintenance_log)
                LIMIT 1
                """)
    lowest_cost = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "total_maintenance": total_maintenance,
        "total_cost": round(total_cost, 2),
        "total_problems": total_problems,
        "total_mechanics": total_mechanics,
        "highest_cost": highest_cost,
        "lowest_cost": lowest_cost
    }


#=========MAINTENANCE REPORT END==========================================
#=========PMS REPORT START==========================================

def fetch_pms_rows():
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
                SELECT
                    vehicle_name,
                    last_pms_date,
                    km,
                    oil_liters,
                    next_pms_date
                FROM pms_log
                ORDER BY vehicle_name
            """)
    
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def insert_pms_rows(doc, rows):
    # Insert maintenance and PMS rows into the document
    table = doc.tables[0]  # Assuming the second table is for PMS
    
    for row in rows:
        cells = table.add_row().cells
        cells[0].text = str(row[0])  # vehicle_name
        cells[1].text = str(row[1])  # last_pms_date
        cells[2].text = str(row[2])  # km
        cells[3].text = str(row[3])  # oil_liters
        cells[4].text = str(row[4])  # next_pms_date


#=========PMS REPORT END==========================================
#=========TOOLS & EQUIPMENT REPORT START==========================================

def fetch_tools_equipment_rows():
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
                SELECT
                    name,
                    category,
                    quantity,
                    condition
                FROM tools_equipment
                ORDER BY name
            """)
    
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def insert_tools_equipment_rows(doc, rows):
    # Insert tools & equipment rows into the document
    table = doc.tables[0]  # Assuming the first table is for tools & equipment
    
    for row in rows:
        cells = table.add_row().cells
        cells[0].text = str(row[0])  # name
        cells[1].text = str(row[1])  # category
        cells[2].text = str(row[2])  # quantity
        cells[3].text = str(row[3])  # condition

def calculate_tools_equipment_summary():
    conn = get_db_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM tools_equipment")
    total_items = cur.fetchone()[0]

    cur.execute("""
                SELECT name, quantity
                FROM tools_equipment
                WHERE quantity = (SELECT MAX(quantity) FROM tools_equipment)
                LIMIT 1
                """)
    most_qty = cur.fetchone()

    cur.execute("""
                SELECT name, quantity
                FROM tools_equipment
                WHERE quantity = (SELECT MIN(quantity) FROM tools_equipment)
                LIMIT 1
                """)
    least_qty = cur.fetchone()

    cur.execute("""
                SELECT COUNT(*) FROM tools_equipment WHERE condition = 'Excellent'
                """)
    excellent = cur.fetchone()[0]

    cur.execute("""
                SELECT COUNT(*) FROM tools_equipment WHERE condition = 'Good'
                """)
    good = cur.fetchone()[0]

    cur.execute("""
                SELECT COUNT(*) FROM tools_equipment WHERE condition = 'Fair'
                """)
    fair = cur.fetchone()[0]

    cur.execute("""
                SELECT COUNT(*) FROM tools_equipment WHERE condition = 'Damaged'
                """)
    damaged = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "total_items": total_items,
        "most_qty": most_qty,
        "least_qty": least_qty,
        "excellent": excellent,
        "good": good,
        "fair": fair,
        "damaged": damaged
    }


#=========TOOLS & EQUIPMENT REPORT END==========================================
#=========PARTS & SUPPLIES REPORT START==========================================

def fetch_parts_supplies_rows():
    conn = get_db_connection()
    if not conn:
        return []
    
    cur = conn.cursor()
    cur.execute("""
                SELECT
                    name,
                    category,
                    stock,
                    unit,
                    status
                FROM parts_supplies
                ORDER BY name
            """)
    
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def insert_parts_supplies_rows(doc, rows):
    # Insert parts & supplies rows into the document
    table = doc.tables[0]  # Assuming the first table is for parts & supplies
    
    for row in rows:
        cells = table.add_row().cells
        cells[0].text = str(row[0])  # name
        cells[1].text = str(row[1])  # category
        cells[2].text = str(row[2])  # stock
        cells[3].text = str(row[3])  # unit
        cells[4].text = str(row[4])  # status

def calculate_parts_supplies_summary():
    conn = get_db_connection()
    if not conn:
        return {}
    
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM parts_supplies")
    total_items = cur.fetchone()[0]

    cur.execute("""
                SELECT name, stock
                FROM parts_supplies
                WHERE stock = (SELECT MAX(stock) FROM parts_supplies)
                LIMIT 1
                """)
    most_stock = cur.fetchone()

    cur.execute("""
                SELECT name, stock
                FROM parts_supplies
                WHERE stock = (SELECT MIN(stock) FROM parts_supplies)
                LIMIT 1
                """)
    lowest_stock = cur.fetchone()

    cur.execute("""
                SELECT COUNT(*) FROM parts_supplies WHERE status = 'In Stock'
                """)
    in_stock = cur.fetchone()[0]

    cur.execute("""
                SELECT COUNT(*) FROM parts_supplies WHERE status = 'Low Stock'
                """)
    low_stock = cur.fetchone()[0]

    cur.execute("""
                SELECT COUNT(*) FROM parts_supplies WHERE status = 'Out of Stock'
                """)
    out_stock = cur.fetchone()[0]

    cur.close()
    conn.close()

    return {
        "total_items": total_items,
        "most_stock": most_stock,
        "lowest_stock": lowest_stock,
        "in_stock": in_stock,
        "low_stock": low_stock,
        "out_stock": out_stock
    }

#=========PARTS & SUPPLIES REPORT END==========================================
#=========MONTHLY MONITORING REPORT START==========================================
#=========ANNEX B1 START==========================================

def insert_annex_b1_rows(doc, rows, monitoring_date, schedule):
    table = doc.tables[0]  # first table in the template

    for row in rows:
        status = row[4]

        if status == "Condition":
            remark = "Condition"
        elif status == "For PMS":
            remark = "Upon the availability of funds (For PMS)"
        elif status == "For Repair":
            remark = "Upon the availability of funds (For Repair)"
        elif status == "For Repair & PMS":
            remark = "Upon the availability of funds (For Repair & PMS)"
        elif status == "Disposal":
            remark = "Disposal"

        else:
            remark = " N/A"

        cells = table.add_row().cells

        cells[0].text = monitoring_date
        cells[1].text = row[0]   # vehicle name
        cells[2].text = remark
        cells[3].text = schedule
        cells[4].text = ""   # Date accomplished
        cells[5].text = ""  # No. of days
        
#=========ANNEX B1 END==========================================
#=========ANNEX B2 START==========================================
def insert_annex_b2_rows(doc, rows, schedule):
    table = doc.tables[1]  # 2nd table in the template

    for row in rows:
        status = row[4]

        if status == "Condition":
            detail = "Condition"
        elif status == "For PMS":
            detail = "Upon the availability of funds (For PMS)"
        elif status == "For Repair":
            detail = "Upon the availability of funds (For Repair)"
        elif status == "For Repair & PMS":
            detail = "Upon the availability of funds (For Repair & PMS)"
        elif status == "Disposal":
            detail = "Disposal"

        else:
            detail = " N/A"

        cells = table.add_row().cells

        cells[0].text = row[0]
        cells[1].text = detail
        cells[2].text = schedule
        cells[3].text = ""   # Date accomplished
        cells[4].text = ""   # No. of days
        

#=========ANNEX B2 END==========================================
#=========ANNEX B3 START==========================================
def insert_annex_b3_rows(doc, rows):
    table = doc.tables[2]  # 3rd table in the template

    for row in rows:
        status = row[4]

        if status == "Condition":
            detail = "Condition"
        elif status == "For PMS":
            detail = "Upon the availability of funds (For PMS)"
        elif status == "For Repair":
            detail = "Upon the availability of funds (For Repair)"
        elif status == "For Repair & PMS":
            detail = "Upon the availability of funds (For Repair & PMS)"
        elif status == "Disposal":
            detail = "Disposal"

        else:
            detail = " N/A"

        cells = table.add_row().cells

        cells[0].text = row[0]
        cells[1].text = detail
        cells[2].text = ""   #SI / OR
        cells[3].text = ""   # Date procured
        cells[4].text = ""   # blank
        cells[5].text = ""   # date accomplished
        cells[6].text = ""   # remarks
        cells[7].text = ""   # no. of days
#=========ANNEX B3 END==========================================

@app.route("/generate_report", methods=["POST"])
@role_required("Admin", "Staff")
def generate_report():

    report_type = request.form.get("report_type")
    month = request.form.get("month")
    year = request.form.get("year")

    if not report_type:
        return redirect(url_for("reports"))

    if report_type != "monthly_monitoring":
        if not month or not year:
            return redirect(url_for("reports"))

    import calendar
    month_name = None
    if month:
        month_name = calendar.month_name[int(month)]

    print("Generating report:", report_type, month, year)

    # Output file setup
    output_filename = f"{report_type}_{month_name}_{year}.docx"
    output_path = os.path.join("reports_output", output_filename)

    os.makedirs("reports_output", exist_ok=True)
    
    # ===============================
    # GAS & RFID REPORT (CURRENT)
    # ===============================
    if report_type == "gas_rfid":
        rows = fetch_gas_rfid_rows(month, year)

        doc = Document("report_template/gas&rfid_temp.docx")

        # Header placeholder
        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        # Table rows
        insert_gas_rfid_rows(doc, rows)

        # Summary values
        summary = calculate_gas_rfid_summary(month, year)
        replace_placeholder(doc, "{{total_gas}}", str(summary["total_gas"]))
        replace_placeholder(doc, "{{avg_gas}}", str(summary["avg_gas"]))
        replace_placeholder(doc, "{{total_autosweep}}", str(summary["total_autosweep"]))
        replace_placeholder(doc, "{{total_easytrip}}", str(summary["total_easytrip"]))

        doc.save(output_path)

    # ===============================
    # VEHICLE INVENTORY REPORT
    # ===============================
    elif report_type == "vehicle":

        doc = Document("report_template/vehicle_temp.docx")

        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        vehicle_rows = fetch_vehicle_rows()
        insert_vehicle_rows(doc, vehicle_rows)

        type_distribution = fetch_vehicle_type_distribution()
        insert_vehicle_type_distribution(doc, type_distribution)

        summary = calculate_vehicle_summary()
        replace_placeholder(doc, "{{total_vehicles}}", str(summary["total"]))
        replace_placeholder(doc, "{{active_vehicles}}", str(summary["active"]))
        replace_placeholder(doc, "{{inactive_vehicles}}", str(summary["inactive"]))
        replace_placeholder(doc, "{{maintenance_vehicles}}", str(summary["maintenance"]))
        replace_placeholder(doc, "{{most_mileage}}", summary["most_mileage"])

        doc.save(output_path)

    # ===============================
    # MAINTENANCE REPORT
    # ===============================

    elif report_type == "maintenance_log":
        doc = Document("report_template/maintenance_temp.docx")

        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        maintenance_rows = fetch_maintenance_rows()
        insert_maintenance_rows(doc, maintenance_rows)

        summary = calculate_maintenance_summary()
        replace_placeholder(doc, "{{total_maintenance}}", str(summary["total_maintenance"]))
        replace_placeholder(doc, "{{total_cost}}", str(summary["total_cost"]))
        replace_placeholder(doc, "{{total_problems}}", str(summary["total_problems"]))
        replace_placeholder(doc, "{{total_mechanics}}", str(summary["total_mechanics"]))
        replace_placeholder(doc, "{{highest_cost}}", f"{summary['highest_cost'][0]} (₱{summary['highest_cost'][1]})" if summary['highest_cost'] else "N/A")
        replace_placeholder(doc, "{{lowest_cost}}", f"{summary['lowest_cost'][0]} (₱{summary['lowest_cost'][1]})" if summary['lowest_cost'] else "N/A")

        doc.save(output_path)

    # ===============================
    # PMS REPORT
    # ===============================

    elif report_type == "pms_log":
        doc = Document("report_template/pms_temp.docx")

        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        pms_rows = fetch_pms_rows()
        insert_pms_rows(doc, pms_rows)

        doc.save(output_path)

    # ===============================
    # TOOLS & EQUIPMENT REPORT
    # ===============================
    
    elif report_type == "tools_equipment":
        doc = Document("report_template/tools&eq_temp.docx")

        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        tools_rows = fetch_tools_equipment_rows()
        insert_tools_equipment_rows(doc, tools_rows)

        summary = calculate_tools_equipment_summary()
        replace_placeholder(doc, "{{total_items}}", str(summary["total_items"]))
        replace_placeholder(doc, "{{most_qty}}", f"{summary['most_qty'][0]} ({summary['most_qty'][1]})" if summary['most_qty'] else "N/A")
        replace_placeholder(doc, "{{least_qty}}", f"{summary['least_qty'][0]} ({summary['least_qty'][1]})" if summary['least_qty'] else "N/A")
        replace_placeholder(doc, "{{excellent}}", str(summary["excellent"]))
        replace_placeholder(doc, "{{good}}", str(summary["good"]))
        replace_placeholder(doc, "{{fair}}", str(summary["fair"]))
        replace_placeholder(doc, "{{damaged}}", str(summary["damaged"]))

        doc.save(output_path)

    # ===============================
    # PARTS & SUPPLIES REPORT
    # ===============================

    elif report_type == "parts_supplies":
        doc = Document("report_template/parts&supplies_temp.docx")

        month_year = f"{month_name} {year}"
        replace_placeholder(doc, "{{month_year}}", month_year)

        parts_rows = fetch_parts_supplies_rows()
        insert_parts_supplies_rows(doc, parts_rows)

        summary = calculate_parts_supplies_summary()
        replace_placeholder(doc, "{{total_items}}", str(summary["total_items"]))
        replace_placeholder(doc, "{{most_stock}}", f"{summary['most_stock'][0]} ({summary['most_stock'][1]})" if summary['most_stock'] else "N/A")
        replace_placeholder(doc, "{{lowest_stock}}", f"{summary['lowest_stock'][0]} ({summary['lowest_stock'][1]})" if summary['lowest_stock'] else "N/A")
        replace_placeholder(doc, "{{in_stock}}", str(summary["in_stock"]))
        replace_placeholder(doc, "{{low_stock}}", str(summary["low_stock"]))
        replace_placeholder(doc, "{{out_stock}}", str(summary["out_stock"]))

        doc.save(output_path)
    
    # ===============================
    # MONTHLY MONITORING REPORT
    # ===============================

    elif report_type == "monthly_monitoring":

        monitoring_date = request.form.get("monitoring_date")
        m_month = request.form.get("m_month")
        m_week = request.form.get("m_week")

        week_map = {
            "1": "1st Week to 2nd Week",
            "2": "2nd Week to 3rd Week",
            "3": "3rd Week to 4th Week",
            "4": "4th Week to 5th Week",
        }

        week_label = week_map.get(m_week, "")

        month_name = calendar.month_name[int(m_month)]

        schedule = f"{month_name} {week_label}"

        if not monitoring_date:
            print("No monitoring date selected")
            return redirect(url_for("reports"))


        dt = datetime.strptime(monitoring_date, "%Y-%m-%d")

        month = dt.month
        year = dt.year
        month_name = calendar.month_name[month]

        # regenerate filename
        output_filename = f"{report_type}_{month_name}_{year}.docx"
        output_path = os.path.join("reports_output", output_filename)
        
        # ✅ FORMAT FOR DOCUMENT
        monitoring_date = dt.strftime("%B %d, %Y")

        rows = fetch_vehicle_rows()

        doc = Document("report_template/monitoring_temp.docx")

        insert_annex_b1_rows(doc, rows, monitoring_date, schedule)
        insert_annex_b2_rows(doc, rows, schedule)
        insert_annex_b3_rows(doc, rows)

        doc.save(output_path)

    # ✅ ADD THIS
        

    else:
        print("Report type not implemented yet:", report_type)
        return redirect(url_for("reports"))

    # ===============================
    # SAVE REPORT METADATA (ONCE)
    # ===============================
    save_report_record(    
            report_type=report_type,
            month=int(month),
            year=int(year),
            file_name=output_filename,
            file_path=output_path
    )

    doc = Document(output_path)
    replace_placeholder(doc, "{{generated_by}}", session.get("user_position", ""))
    replace_placeholder(doc, "{{generated_on}}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    doc.save(output_path)

    print("Report saved at:", output_path)
    return send_file(output_path, as_attachment=True)
    #return redirect(url_for("reports"))



def fetch_recent_reports(limit=3):
    conn = get_db_connection()
    if not conn:
        return []

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT report_id, report_type, month, year, file_name, created_at
        FROM reports
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))

    reports = cur.fetchall()
    cur.close()
    conn.close()

    return reports

def fetch_reports_summary():
    conn = get_db_connection()
    if not conn:
        return {
            "total_reports": 0,
            "this_month": 0,
            "month_name": "",
            "most_generated": "N/A"
        }

    cur = conn.cursor()

    # Total reports (all time)
    cur.execute("SELECT COUNT(*) FROM reports")
    total_reports = cur.fetchone()[0]

    # This month
    cur.execute("""
        SELECT COUNT(*)
        FROM reports
        WHERE EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)
          AND EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM CURRENT_DATE)
    """)
    this_month = cur.fetchone()[0]

    # Month name (for subtitle)
    cur.execute("""
        SELECT TO_CHAR(CURRENT_DATE, 'Month')
    """)
    month_name = cur.fetchone()[0].strip()

    # Most generated report type
    cur.execute("""
        SELECT report_type, COUNT(*) AS total
        FROM reports
        GROUP BY report_type
        ORDER BY total DESC
        LIMIT 1
    """)
    row = cur.fetchone()
    most_generated = row[0].upper() if row else "N/A"

    cur.close()
    conn.close()

    return {
        "total_reports": total_reports,
        "this_month": this_month,
        "month_name": month_name,
        "most_generated": most_generated
    }

@app.route("/download_report/<filename>")
@role_required("Admin", "Staff")
def download_report(filename):
    return send_from_directory(
        directory="reports_output",
        path=filename,
        as_attachment=True
    )





#========ROUTES==========================================
# =========================
# 📄 RECORDS PAGE
# =========================
@app.route('/records')
@role_required('Admin', 'Staff')
def records():

    import calendar

    search = request.args.get('search')
    month = request.args.get('month')
    rtype = request.args.get('type')

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    query = """
        SELECT report_id, report_type, month, year, file_name, created_at
        FROM reports
        WHERE 1=1
    """
    params = []

    if search:
        query += " AND report_type ILIKE %s"
        params.append(f"%{search}%")

    if month:
        query += " AND month = %s"
        params.append(int(month))

    if rtype:
        query += " AND report_type = %s"
        params.append(rtype)

    query += " ORDER BY created_at DESC"

    cur.execute(query, params)
    records = cur.fetchall()

    for r in records:
        r["month_name"] = calendar.month_name[r["month"]]

    cur.execute("SELECT COUNT(*) FROM reports")
    total = cur.fetchone()["count"]

    cur.execute("""
        SELECT COUNT(*) FROM reports
        WHERE date_trunc('month', created_at) = date_trunc('month', CURRENT_DATE)
    """)
    this_month = cur.fetchone()["count"]

    cur.close()
    conn.close()

    return render_template(
        "records.html",
        records=records,
        total_reports=total,
        this_month=this_month
    )

@app.route("/delete_record/<int:id>", methods=["POST"])
@role_required("Admin", "Staff")
def delete_record(id):

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT file_path FROM reports WHERE report_id = %s", (id,))
    row = cur.fetchone()

    if row:
        file_path = row[0]

        if file_path and os.path.exists(file_path):
            os.remove(file_path)

        cur.execute("DELETE FROM reports WHERE report_id = %s", (id,))
        conn.commit()

    cur.close()
    conn.close()
    return redirect(url_for("records"))


#=====END RECORDS PAGE=====


# =======================================================
# USER SIDE ROUTES
# =======================================================

# ================= HOME PAGE =================
@app.route("/user/home")
@role_required ('Client')
def user_home():

    if "user_id" not in session:
        return redirect(url_for("login"))

    firstname = (session.get("user_fullname") or "User").split()[0]

    return render_template(
        "user-dashboard/home.html",
        firstname=firstname
    )

# ================= DASHBOARD =================
@app.route("/user_dashboard")
@role_required ('Client')
def user_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='pending') AS pending,
            COUNT(*) FILTER (WHERE status='approved') AS approved
        FROM vehicle_requests
        WHERE user_id = %s
    """, (user_id,))

    stats = cur.fetchone()

    cur.execute("""
        SELECT vehicle_id, name, plate_number
        FROM vehicle
        ORDER BY name
    """)
    vehicles = cur.fetchall()

    cur.close()
    conn.close()

    firstname = (session.get("user_fullname") or "User").split()[0]



    return render_template(
        "user-dashboard/dashboard.html",
        firstname=firstname,
        total_requests=stats[0],
        pending_requests=stats[1],
        approved_requests=stats[2],
        vehicles=vehicles
    )


# ================= NEW REQUEST PAGE =================
@app.route("/user/new-request", methods=["GET", "POST"])
@role_required ('Client')
def user_new_request():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    if request.method == "POST":
        vehicle_type = request.form.get("vehicle_type")
        destination = request.form.get("destination")
        purpose = request.form.get("purpose")
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        time = request.form.get("time")
        days = request.form.get("days")
        passengers = request.form.get("passengers")
        office = request.form.get("office")

        if not destination or not purpose:
            flash("Please fill in all required fields.")
            return redirect(url_for("user_new_request"))

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO vehicle_requests
            (user_id, vehicle_type, destination, purpose, start_date, end_date, time, days,
                    passengers, office, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
            RETURNING id
        """,
        (user_id, vehicle_type, destination, purpose, start_date, end_date, time, days,
         passengers, office)
        )

        new_request_id = cur.fetchone()[0]
        requester_name = session.get("user_fullname") or "A user"

        cur.execute("""
                SELECT id
                FROM users
                WHERE role IN ('Admin', 'Staff')
            """)
        admin_staff_users = cur.fetchall()

        message = f"{requester_name} has submitted a new vehicle request for {vehicle_type}."

        for admin_user in admin_staff_users:
            admin_id = admin_user[0]
            cur.execute("""
                        INSERT INTO notifications (user_id, request_id, message, type)
                        VALUES (%s, %s, %s, %s)
                        """, (admin_id, new_request_id, message, "new_request"))

        conn.commit()

        cur.close()
        conn.close()

        return redirect(url_for("user_my_requests"))

    firstname = (session.get("full_name") or "users").split()[0]



    return render_template(
        "user-dashboard/new_request.html",
        firstname=firstname
    )


# ================= MY REQUESTS =================
@app.route("/user_my_requests")
@role_required ('Client')
def user_my_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT *
        FROM vehicle_requests
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))

    requests = cur.fetchall()

    cur.close()
    conn.close()

    firstname = (session.get("user_fullname") or "User").split()[0]

    return render_template(
        "user-dashboard/my_requests.html",
        requests=requests,
        firstname=firstname
    )


# ================= TRIP TICKETS =================
@app.route("/user/trip-tickets")
@role_required ('Client')
def user_trip_tickets():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session.get("user_id")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT *
        FROM vehicle_requests
        WHERE user_id = %s
        AND status = 'approved'
        AND trip_ticket_file IS NOT NULL
        ORDER BY created_at DESC
    """, (user_id,))

    tickets = cur.fetchall()

    cur.close()
    conn.close()

    firstname = (session.get("user_fullname") or "User").split()[0]

    return render_template(
        "user-dashboard/trip_tickets.html",
        tickets=tickets,
        firstname=firstname
    )
# =======================================================
# USER SIDE ROUTES---end
# =======================================================

# =======================================================
# FORGOT PASSWORD
# =======================================================
@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():

    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email=%s", (email,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        flash("Email not registered")
        return redirect(url_for("forgot_password"))

    otp = generate_otp()

    session['reset_email'] = email
    session['reset_otp'] = otp
    session['otp_time'] = time.time()   # OTP timestamp added here

    send_otp_email_async(email, otp)

    return redirect(url_for("verify_reset_otp"))


# =======================================================
# VERIFY RESET OTP
# =======================================================
@app.route('/verify-reset-otp', methods=['GET','POST'])
def verify_reset_otp():

    if request.method == "POST":

        user_otp = request.form.get("otp")

        # Check if OTP expired (5 minutes)
        if time.time() - session.get('otp_time', 0) > 300:
            flash("OTP expired. Please request again.")
            return redirect(url_for("forgot_password"))

        if user_otp == session.get("reset_otp"):
            return redirect(url_for("reset_password"))

        else:
            flash("Invalid OTP")

    return render_template("verify_otp.html")


# =======================================================
# RESET PASSWORD
# =======================================================
@app.route('/reset-password', methods=['GET','POST'])
def reset_password():

    if not session.get("reset_email"):
        return redirect(url_for("forgot_password"))

    if request.method == "GET":
        return render_template("reset_password.html")

    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if not password:
        flash("Password is required")
        return redirect(url_for("reset_password"))

    if password != confirm_password:
        flash("Passwords do not match")
        return redirect(url_for("reset_password"))

    email = session.get("reset_email")

    hashed_password = bcrypt.hashpw(
        password.encode('utf-8'),
        bcrypt.gensalt()
    ).decode('utf-8')

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET password = %s
        WHERE email = %s
    """, (hashed_password, email))

    conn.commit()

    cur.close()
    conn.close()

    session.pop('reset_email', None)
    session.pop('reset_otp', None)
    session.pop('otp_time', None)

    flash("Password updated successfully")

    return redirect(url_for("login"))

#================ AUTH/OTP IN ACCOUNT CREATION ===========
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == "POST":
        user_otp = request.form.get("otp")

        if user_otp == session.get('otp'):

            email = session.get('register_email')
            fullname = session.get('register_fullname')
            hashed_password = session.get('register_password')

            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                        INSERT INTO users (email, full_name, role, position, password)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (email, fullname, "Client", "EndUser", hashed_password))
            
            conn.commit()
            cur.close()
            conn.close()

            session.pop('otp', None)

            flash("Account created succesfully!")
            return redirect(url_for('login'))
        
        else:
            flash("Invalid OTP")

    return render_template("verify_otp.html")

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp_email(receiver_email, otp):

    try:
        sender_email = "tmps.pup@gmail.com"
        sender_password = "ayxj yrer wmud irxl"

        subject = "PUP Motor Pool Account Verification"
        body = f"Your OTP code is: {otp}"

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)

        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()

        print("OTP EMAIL SENT SUCCESSFULLY")

    except Exception as e:
        print("EMAIL ERROR:", e)


def send_otp_email_async(receiver_email, otp):
    Thread(target=send_otp_email, args=(receiver_email, otp), daemon=True).start()

#============== RESEND OTP ================================
@app.route('/resend-otp')
def resend_otp():

    email = session.get("register_email")

    if not email:
        return redirect(url_for("register"))

    otp = generate_otp()

    session['otp'] = otp

    send_otp_email_async(email, otp)

    flash("A new OTP has been sent to your email.")

    return redirect(url_for("verify_otp"))

#============== REQUEST ADMIN SIDE ================================
@app.route("/req_dashboard")
@role_required ('Admin', 'Staff')
def req_dashboard():

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='pending') AS pending,
            COUNT(*) FILTER (WHERE status='approved') AS approved
        FROM vehicle_requests
    """)

    stats = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "admin-request/req_dashboard.html",
        total_requests=stats[0],
        pending_requests=stats[1],
        approved_requests=stats[2],
    )

#============================ LIST OF REQUESTS ==============================
@app.route('/admin-request/requests')
@role_required('Admin', 'Staff')
def requests():

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            vr.id,
            u.full_name,
            vr.office,
            vr.destination,
            vr.created_at,
            vr.status
        FROM vehicle_requests vr
        JOIN users u ON vr.user_id = u.id
        ORDER BY vr.created_at DESC
    """)

    vehicle_requests = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin-request/requests.html",
        vehicle_requests=vehicle_requests
    )
# =========================
# request details 
# =========================
@app.route('/admin-request/req_details/<req_id>', methods=["GET", "POST"])
@role_required('Admin', 'Staff')
def req_details(req_id):

    # =========================
    # POST: Generate Trip Ticket
    # =========================
    if request.method == "POST":

        conn = get_db_connection()
        cur = conn.cursor()

        # 🔒 CHECK STATUS FIRST
        cur.execute("""
            SELECT status FROM vehicle_requests
            WHERE id = %s::uuid
        """, (req_id,))

        result = cur.fetchone()

        if not result:
            cur.close()
            conn.close()
            return "Request not found", 404

        status = result[0]

        if status != "pending":
            cur.close()
            conn.close()
            return f"Cannot process. Already {status}.", 400

        # =========================
        # GET FORM DATA
        # =========================
        vehicle_id = request.form["vehicles"]
        driver_name = request.form["driver_name"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # =========================
        # CHECK SCHEDULE CONFLICT
        # =========================
        cur.execute("""
            SELECT schedule_date
            FROM vehicle_schedule
            WHERE vehicle_id = %s
            AND schedule_date BETWEEN %s AND %s
        """, (vehicle_id, start, end))

        conflicts = cur.fetchall()

        if conflicts:
            cur.close()
            conn.close()
            return "Vehicle already booked on selected dates.", 400

        # =========================
        # INSERT TRIP TICKET
        # =========================
        cur.execute("""
            INSERT INTO trip_tickets
            (request_id, vehicle_id, driver_name, start_date, end_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (req_id, vehicle_id, driver_name, start_date, end_date))

        # =========================
        # INSERT VEHICLE SCHEDULE
        # =========================
        current_day = start
        while current_day <= end:
            cur.execute("""
                INSERT INTO vehicle_schedule (vehicle_id, request_id, schedule_date)
                VALUES (%s, %s, %s)
            """, (vehicle_id, req_id, current_day))

            current_day += timedelta(days=1)

        # =========================
        # UPDATE STATUS → APPROVED
        # =========================
        cur.execute("""
            UPDATE vehicle_requests
            SET status = 'approved'
            WHERE id = %s
        """, (req_id,))

        # 🧹 remove pending reminders
        cur.execute("""
            DELETE FROM notifications
            WHERE request_id = %s
            AND type = 'pending_reminder'
        """, (req_id,))

        # =========================
        # SEND NOTIFICATION
        # =========================
        cur.execute("""
            SELECT user_id, vehicle_type
            FROM vehicle_requests
            WHERE id = %s
        """, (req_id,))

        owner_row = cur.fetchone()

        if owner_row:
            requester_user_id = owner_row[0]
            vehicle_name = owner_row[1]

            approval_message = f"Your vehilcle request for {vehicle_name} has been approved. Your trip ticket is ready."

            cur.execute("""
                INSERT INTO notifications (user_id, vehicle_name, request_id, message, type)
                VALUES (%s, %s, %s, %s, %s)
            """, (requester_user_id, vehicle_name, req_id, approval_message, "approved"))

        conn.commit()
        cur.close()
        conn.close()

        # 🔄 Redirect after success
        return redirect(url_for("req_details", vehicle_name=vehicle_name, req_id=req_id))

    # =========================
    # GET: Load Page
    # =========================
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT vr.*, u.full_name
        FROM vehicle_requests vr
        JOIN users u ON vr.user_id = u.id
        WHERE vr.id = %s
    """, (req_id,))
    
    req_data = cur.fetchone()

    if req_data is None:
        cur.close()
        conn.close()
        return "Request not found", 404

    cur.execute("""
        SELECT vehicle_id, name, plate_number
        FROM vehicle
        ORDER BY name
    """)
    
    vehicles = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "admin-request/req_details.html",
        request=req_data,
        vehicles=vehicles
    )

    #=====================TRIP TICKET===========================
 #=====================TRIP TICKET TEMPLATE OPTION===========================
def is_metro_mnla(destination):
    if not destination:
        return False
    
    destination = destination.strip().lower()
    metro_mnla_places = [
        "manila", "quezon city", "qc", "caloocan", "las piñas", "las pinas",
        "makati", "taguig city", "malabon", "mandaluyong", "marikina",
        "muntinlupa", "navotas", "parañaque", "pasay", "pasig", "pateros",
        "san juan", "valenzuela", "metro manila", "ncr"
    ]
    for place in metro_mnla_places:
        if place in destination:
            return True
    return False

@app.route("/generate_trip_ticket/<req_id>")
@role_required("Admin", "Staff")
def generate_trip_ticket(req_id):

    import os
    from docx import Document

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
            vr.id AS request_id,
            vr.destination,
            vr.purpose,
            vr.start_date,
            vr.end_date,
            u.full_name,
            tt.driver_name,
            v.name AS vehicle_name,
            v.plate_number
        FROM vehicle_requests vr
        LEFT JOIN trip_tickets tt ON tt.request_id = vr.id 
        JOIN users u ON vr.user_id = u.id
        LEFT JOIN vehicle v ON v.vehicle_id = tt.vehicle_id
        WHERE vr.id = %s
        LIMIT 1
    """, (req_id,))

    data = cur.fetchone()
    print("DATA FROM DB:", data)
    cur.close()
    conn.close()

    if not data:
        return "No trip ticket data found", 404

    # ✅ ALWAYS USE UUID (request_id)
    filename = f"trip_ticket_{data['request_id']}.docx"

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    if is_metro_mnla(data["destination"]):
        template_file = "trip-ticket_mnla.docx"
    else:
        template_file = "trip-ticket_outmnl.docx"
    TEMPLATE_PATH = os.path.join(BASE_DIR, "report_template", template_file)
    print("USING TEMPLATE:", template_file)
    OUTPUT_DIR = os.path.join(BASE_DIR, "reports_output")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    filepath = os.path.join(OUTPUT_DIR, filename)

    doc = Document(TEMPLATE_PATH)
    print("FILE SHOULD BE SAVED HERE:", filepath)
    print("FILE EXISTS AFTER SAVE:", os.path.exists(filepath))

    for p in doc.paragraphs:
        if "{{full_name}}" in p.text:
            p.text = p.text.replace("{{full_name}}", data["full_name"])

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if "{{driver_name}}" in cell.text:
                    cell.text = cell.text.replace("{{driver_name}}", data["driver_name"])
                if "{{vehicle_name}}" in cell.text:
                    cell.text = cell.text.replace("{{vehicle_name}}", data["vehicle_name"])
                if "{{purpose}}" in cell.text:
                    cell.text = cell.text.replace("{{purpose}}", data["purpose"])
                if "{{destination}}" in cell.text:
                    cell.text = cell.text.replace("{{destination}}", data["destination"])
                if "{{start_date}}" in cell.text:
                    cell.text = cell.text.replace("{{start_date}}", str(data["start_date"]))
    try:
        doc.save(filepath)
        print("✅ FILE SAVED:", filepath)
        print("EXISTS AFTER SAVE:", os.path.exists(filepath))
    except Exception as e:
        print("❌ ERROR SAVING FILE:", e)

    # ✅ SAVE CORRECT FILENAME
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE vehicle_requests
        SET trip_ticket_file = %s
        WHERE id = %s
    """, (filename, data["request_id"]))

    conn.commit()
    cur.close()
    conn.close()

    print("Saved file:", filename)

    return redirect(url_for("admin_trip_tickets"))


@app.route("/admin/trip-tickets")
@role_required("Admin","Staff")
def admin_trip_tickets():

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
    SELECT 
        tt.id,
        tt.request_id,
        v.name AS vehicle_name,
        tt.start_date,
        vr.destination,
        vr.trip_ticket_file AS file
    FROM trip_tickets tt
    JOIN vehicle_requests vr ON vr.id = tt.request_id
    JOIN vehicle v ON v.vehicle_id = tt.vehicle_id
    ORDER BY tt.id DESC
""")

    tickets = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin-request/trip_ticket.html", tickets=tickets)


@app.route("/download-trip/<path:filename>")
def download_trip(filename):
    import os
    from docx import Document
    import psycopg2.extras
    from datetime import date

    today = date.today().strftime("%B %d, %Y")
    user_id = session.get("user_id")


    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(BASE_DIR, "reports_output")
    filepath = os.path.join(directory, filename)

    print("DOWNLOADING:", filename)
    print("FULL PATH:", filepath)
    print("EXISTS BEFORE:", os.path.exists(filepath))

    # ✅ IF FILE DOES NOT EXIST → GENERATE IT
    if not os.path.exists(filepath):

        print("⚠️ File missing. Generating now...")

        # 🔥 Extract req_id from filename
        # example: trip_ticket_14.docx → 14
        ticket_id = filename.replace("trip_ticket_", "").replace(".docx", "")

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        cur.execute("""
            SELECT
                tt.request_id,
                tt.driver_name,
                v.name AS vehicle_name,
                v.plate_number,
                tt.start_date,
                tt.end_date,
                vr.purpose,
                vr.destination,
                u.full_name AS prepared_by
            FROM trip_tickets tt
            JOIN vehicle_requests vr ON vr.id = tt.request_id
            JOIN users u ON u.id = vr.user_id
            JOIN vehicle v ON v.vehicle_id = tt.vehicle_id
            WHERE tt.id = %s
            LIMIT 1
        """, (ticket_id,))

        data = cur.fetchone()
        print("DOWNLOAD DATA:", data)

        if not data:
            cur.close()
            conn.close()
            return f"❌ No data found for request {ticket_id}", 404

        prepared_by = data.get("prepared_by", "")

        cur.close()
        conn.close()

        if is_metro_mnla(data["destination"]):
            template_file = "trip-ticket_mnla.docx"
        else:
            template_file = "trip-ticket_outmnl.docx"

        print("USING TEMPLATE:", template_file)

        TEMPLATE_PATH = os.path.join(BASE_DIR, "report_template", template_file)

        if not os.path.exists(TEMPLATE_PATH):
            return "❌ Template file missing", 500

        doc = Document(TEMPLATE_PATH)

        for p in doc.paragraphs:
            if "{{driver_name}}" in p.text:
                p.text = p.text.replace("{{driver_name}}", data["driver_name"])
            if "{{vehicle_name}}" in p.text:
                p.text = p.text.replace("{{vehicle_name}}", data["vehicle_name"])
            if "{{plate_number}}" in p.text:
                p.text = p.text.replace("{{plate_number}}", data["plate_number"])
            if "{{purpose}}" in p.text:
                p.text = p.text.replace("{{purpose}}", data["purpose"])
            if "{{DATE}}" in p.text:
                p.text = p.text.replace("{{DATE}}", today)
            if "{{full_name}}" in p.text:
                p.text = p.text.replace("{{full_name}}", prepared_by)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if "{{driver_name}}" in cell.text:
                        cell.text = cell.text.replace("{{driver_name}}", str(data["driver_name"] or ""))
                    if "{{vehicle_name}}" in cell.text:
                        cell.text = cell.text.replace("{{vehicle_name}}", str(data["vehicle_name"] or ""))
                    if "{{plate_number}}" in cell.text:
                        cell.text = cell.text.replace("{{plate_number}}", str(data["plate_number"] or ""))
                    if "{{purpose}}" in cell.text:
                        cell.text = cell.text.replace("{{purpose}}", str(data["purpose"] or ""))
                    if "{{destination}}" in cell.text:
                        cell.text = cell.text.replace("{{destination}}", str(data["destination"] or ""))
                    if "{{start_date}}" in cell.text:
                        cell.text = cell.text.replace("{{start_date}}", str(data["start_date"] or ""))

        os.makedirs(directory, exist_ok=True)
        doc.save(filepath)

        print("✅ FILE GENERATED:", filepath)

    print("EXISTS AFTER:", os.path.exists(filepath))

    # ✅ NOW DOWNLOAD
    return send_from_directory(directory, filename, as_attachment=True)

@app.route("/get_vehicle_schedule")
@role_required("Admin", "Staff", "Client")
def get_vehicle_schedule():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)

    if not year or not month:
        return jsonify({"error": "Missing year or month"}), 400
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
            SELECT 
                vs.schedule_date,
                v.name AS vehicle_name,
                v.plate_number
            FROM vehicle_schedule vs
            JOIN vehicle v ON vs.vehicle_id = v.vehicle_id
            WHERE EXTRACT(YEAR FROM vs.schedule_date) = %s
                AND EXTRACT(MONTH FROM vs.schedule_date) = %s
                AND vs.schedule_date >= CURRENT_DATE
            ORDER BY vs.schedule_date ASC, v.name ASC
                """, (year, month))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    grouped = {}

    for row in rows:
        date_key = row["schedule_date"].strftime("%Y-%m-%d")

        if date_key not in grouped:
            grouped[date_key] = []

        grouped[date_key].append({
            "vehicle_name": row["vehicle_name"],
            "plate_number": row["plate_number"]
        })

    return jsonify(grouped)

#============================ NOTIFICATION =======================================================================
@app.route("/get_notifications")
@role_required("Admin", "Staff", "Client")
def get_notifications():
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = session.get("user_id")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
                SELECT id, message, type, is_read, created_at, request_id
                FROM notifications
                WHERE user_id = %s
                ORDER BY created_at DESC
                """, (user_id,))
    notifications = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify(notifications)


@app.route("/get_unread_notif_count")
def get_unread_notif_count():
    if "user_id" not in session:
        return jsonify({"count": 0})
    
    user_id = session.get("user_id")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
                SELECT COUNT(*)
                FROM notifications
                WHERE user_id = %s AND is_read = FALSE
                """, (user_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()

    return jsonify({"count": count})

#============================ MARK NOTIFICATION AS READ =======================================================================
@app.route("/mark_notification_read/<notif_id>")
@role_required("Admin", "Staff", "Client")
def mark_notification_read(notif_id):

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. mark as read
    cur.execute("""
        UPDATE notifications
        SET is_read = TRUE
        WHERE id = %s
        RETURNING request_id
    """, (notif_id,))

    result = cur.fetchone()

    conn.commit()
    cur.close()
    conn.close()

    if not result:
        return jsonify({"error": "Notification not found"}), 404

    request_id = result[0]

    # 2. return redirect URL
    return jsonify({
        "redirect_url": f"/admin-request/req_details/{request_id}"
    })

#============================ CREATE PENDING REQUEST NOTIFICATIONS =======================================================================
def create_pending_request_notifications():
    conn = get_db_connection()
    if not conn:
        return

    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT
                vr.id,
                vr.office,
                u.full_name
        FROM vehicle_requests vr
        JOIN users u ON vr.user_id = u.id
        WHERE vr.status = 'pending'
        AND vr.created_at <= NOW() - INTERVAL '2 hours'
    """)
    requests = cur.fetchall()

    if not requests:
        cur.close()
        conn.close()
        return

    cur.execute("""
        SELECT id
        FROM users
        WHERE role IN ('Admin', 'Staff')
    """)
    admins = [row['id'] for row in cur.fetchall()]

    if not admins:
        cur.close()
        conn.close()
        return

    request_ids = [str(req['id']) for req in requests]
    cur.execute("""
        SELECT CAST(request_id AS TEXT) AS request_id, user_id
        FROM notifications
        WHERE CAST(request_id AS TEXT) = ANY(%s)
          AND user_id = ANY(%s)
          AND notifications.created_at >= NOW() - INTERVAL '2 hours'
    """, (request_ids, admins))

    existing_notifications = {
        (row['request_id'], row['user_id'])
        for row in cur.fetchall()
    }

    insert_rows = []
    for req in requests:
        requester_name = req["full_name"] or "A requester"
        message = f"{requester_name} from {req['office']} needs approval"
        for admin_id in admins:
            if (str(req['id']), admin_id) not in existing_notifications:
                insert_rows.append((admin_id, req['id'], message, 'pending_reminder'))

    if insert_rows:
        cur.executemany("""
            INSERT INTO notifications (user_id, request_id, message, type)
            VALUES (%s, %s, %s, %s)
        """, insert_rows)
        conn.commit()

    cur.close()
    conn.close()
#=============================================================================

@app.route('/auth/user')
def auth_user():
    if 'user_id' not in session:
        return {}, 401

    return {
        "full_name": session.get("user_fullname"),
        "email": session.get("user_email"),
        "position": session.get("user_position"),
        "role": session.get("user_role")
    }
# =======================================================
# REJECT REQUEST-admin side
# =======================================================
@app.route("/reject_request", methods=["POST"])
def reject_request():
    try:
        data = request.json
        request_id = str(data["request_id"])
        reason = data["reason"]

        conn = get_db_connection()
        cur = conn.cursor()

        # 🔒 CHECK STATUS FIRST
        cur.execute("""
            SELECT status FROM vehicle_requests
            WHERE id = %s::uuid
        """, (request_id,))
        result = cur.fetchone()

        if not result:
            return jsonify({"success": False, "error": "Request not found"})

        status = result[0]

        if status != "pending":
            return jsonify({
                "success": False,
                "error": f"Cannot reject. Already {status}."
            })

        # ✅ ONLY IF PENDING
        cur.execute("""
            UPDATE vehicle_requests
            SET status = 'rejected',
                rejection_reason = %s
            WHERE id = %s::uuid
        """, (reason, request_id))

        cur.execute("""
            DELETE FROM notifications
            WHERE request_id = %s
            AND type = 'pending_reminder'
        """, (request_id,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"success": True})

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"success": False, "error": str(e)})

# =======================================================
# HOMEPAGE APPROVAL REMINDERS
# =======================================================   
@app.route("/get_home_reminders")
@role_required("Admin", "Staff")
def get_home_reminders():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ✅ GET REAL PENDING COUNT
    cur.execute("""
        SELECT COUNT(*) AS total
        FROM vehicle_requests
        WHERE status = 'pending'
    """)
    count = cur.fetchone()["total"]

    cur.close()
    conn.close()

    return jsonify({"count": count})

@app.route("/admin-request")
@role_required("Admin", "Staff")
def admin_request_list():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cur.execute("""
        SELECT *
        FROM vehicle_requests
        WHERE status = 'pending'
        ORDER BY created_at DESC
    """)

    requests = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("admin_request_list.html", requests=requests)

# =======================================================
# SUPPORT PAGES
# =======================================================
@app.route('/faq')
def faq():
    return render_template('user-dashboard/faq.html')


@app.route('/user-guide')
def user_guide():
    return render_template('user-dashboard/user-guide.html')

# =======================================================
# legal pages
# =======================================================

@app.route('/privacy-policy')
def privacy_policy():
    return render_template(
        'user-dashboard/privacy-policy.html'
    )

@app.route('/terms-conditions')
def terms_conditions():
    return render_template(
        'user-dashboard/terms-conditions.html'
    )


@app.route('/data-privacy')
def data_privacy():
    return render_template(
        'user-dashboard/data-privacy.html'
    )
# =======================================================
# LOGOUT
# =======================================================
@app.route('/logout')
def logout():

    session.clear()   # clears all login/session data

    flash("You have been logged out.")

    return redirect(url_for("login"))


if __name__ == '__main__':
    #sync_assigned_user()
    app.run(debug=True, port=5055)
