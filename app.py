from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import os
import psycopg2
from docx import Document
import psycopg2.extras
from flask import send_from_directory



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

# --- GASOLINE & RFID ROUTES ---

@app.route('/gas_rfid')
def gas_rfid():
    if 'user_name' not in session:
        return redirect(url_for('index'))

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
def tools_equipment():
    if 'user_name' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, item_code, name, category, quantity, condition
        FROM tools_equipment
        ORDER BY id ASC
    """)
    tools = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM tools_equipment")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tools_equipment WHERE condition='Excellent'")
    excellent = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM tools_equipment WHERE condition='Good'")
    good = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "tools_equipment.html",
        tools=tools,
        total=total,
        excellent=excellent,
        good=good
    )


@app.route('/save_tool', methods=['POST'])
def save_tool():
    tool_id = request.form.get('id')
    name = request.form['name']
    category = request.form['category']
    quantity = request.form['quantity']
    condition = request.form['condition']

    conn = get_db_connection()
    cur = conn.cursor()

    if tool_id:
        cur.execute("""
            UPDATE tools_equipment
            SET name=%s, category=%s, quantity=%s, condition=%s
            WHERE id=%s
        """, (name, category, quantity, condition, tool_id))
    else:
        cur.execute("SELECT COUNT(*) FROM tools_equipment")
        count = cur.fetchone()[0] + 1
        item_code = f"T-{count:04d}"

        cur.execute("""
            INSERT INTO tools_equipment (item_code, name, category, quantity, condition)
            VALUES (%s, %s, %s, %s, %s)
        """, (item_code, name, category, quantity, condition))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for('tools_equipment'))


@app.route('/delete_tool/<int:id>')
def delete_tool(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM tools_equipment WHERE id=%s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('tools_equipment'))

# =======================================================
# 🧰 END TOOLS & EQUIPMENT
# =======================================================

# --- maintenance & pms ---
@app.route('/maintenance_pms')
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
        # Total Monthly Maintenance Cost
        cur.execute("SELECT SUM(cost) FROM maintenance_log WHERE date >= date_trunc('month', CURRENT_DATE)")
        cost_res = cur.fetchone()
        total_m_cost = cost_res[0] if cost_res and cost_res[0] else 0
        
        # Total Records this month
        cur.execute("SELECT COUNT(*) FROM maintenance_log WHERE date >= date_trunc('month', CURRENT_DATE)")
        m_count = cur.fetchone()[0]
        
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

#--pms--#
# --- ROUTE TO ADD PMS RECORD ---
@app.route('/add_pms', methods=['POST'])
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
@app.route('/delete_maintenance/<int:id>')
def delete_maintenance(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM maintenance_log WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance_pms'))

@app.route('/delete_pms/<int:id>')
def delete_pms(id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM pms_log WHERE id = %s', (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('maintenance_pms'))

# --- END maintenance & pms ---

# =======================================================
# 🧰 PARTS & SUPPLIES
# =======================================================

@app.route('/parts-supplies')
def parts_supplies():
    if 'user_name' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    parts = []
    total = in_stock = low_stock = out_stock = 0

    if conn:
        cur = conn.cursor()

        # IMPORTANT: use part_id (not id)
        cur.execute("SELECT * FROM parts_supplies ORDER BY part_id ASC")
        parts = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM parts_supplies")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM parts_supplies WHERE stock > min_stock")
        in_stock = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) 
            FROM parts_supplies 
            WHERE stock <= min_stock AND stock > 0
        """)
        low_stock = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM parts_supplies WHERE stock = 0")
        out_stock = cur.fetchone()[0]

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
def add_part():
    if 'user_name' not in session:
        return redirect(url_for('index'))

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
def delete_part(part_id):
    if 'user_name' not in session:
        return redirect(url_for('index'))

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
def reports():
    if "user_name" not in session:
        return redirect(url_for("login"))
    recent_reports = fetch_recent_reports()
    return render_template("reports.html", recent_reports=recent_reports)



#STEP 9: TEST REPORT ROUTE

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



#==find STEP 10: PRODUCTION REPORT ROUTE==

@app.route("/generate_report", methods=["POST"])
def generate_report():
    

    report_type = request.form.get("report_type")
    month = request.form.get("month")
    year = request.form.get("year")

    rows = fetch_gas_rfid_rows(month, year)

    import calendar
    month_name = calendar.month_name[int(month)]

    print("Generating report:", report_type, month, year)

    # TEMP: hardcode file name for now
    output_filename = f"{report_type}_{month}_{year}.docx"
    output_path = os.path.join("reports_output", output_filename)

    # Make sure folder exists
    os.makedirs("reports_output", exist_ok=True)

    # Load your template
    doc = Document("report_template/gas&rfid_temp.docx")

    month_year = f"{month_name} {year}"
    replace_placeholder(doc, "{{month_year}}", month_year)

    # STEP 2.2 — insert table rows
    insert_gas_rfid_rows(doc, rows)

    summary = calculate_gas_rfid_summary(month, year)

    replace_placeholder(doc, "{{total_gas}}", str(summary["total_gas"]))
    replace_placeholder(doc, "{{avg_gas}}", str(summary["avg_gas"]))
    replace_placeholder(doc, "{{total_autosweep}}", str(summary["total_autosweep"]))
    replace_placeholder(doc, "{{total_easytrip}}", str(summary["total_easytrip"]))


    # TEMP: just save it (we already tested filling earlier)
    doc.save(output_path)

    save_report_record(
    report_type=report_type,
    month=month,
    year=year,
    file_name=output_filename,
    file_path=output_path
)


    print("Report saved at:", output_path)

    # STEP 3.2.5 — save report metadata
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO reports (report_type, month, year, file_name, file_path)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            report_type,
            int(month),
            int(year),
            output_filename,
            output_path
        ))
        conn.commit()
        cur.close()
        conn.close()


    return redirect(url_for("reports"))


def fetch_recent_reports(limit=5):
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

@app.route("/download_report/<filename>")
def download_report(filename):
    return send_from_directory(
        directory="reports_output",
        path=filename,
        as_attachment=True
    )





#========ROUTES==========================================


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
