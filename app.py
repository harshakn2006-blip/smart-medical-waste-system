import os
import sqlite3
from functools import wraps
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from io import BytesIO
import qrcode
from ai_classifier import predict_waste_category
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "medical_waste.db")

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static")
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-this-secret-key")
app.config["DATABASE"] = DATABASE


# This is a conservative teaching/demo lookup, not a substitute for local SOPs.
# Anything not confidently matched is sent for trained staff review.
WASTE_GUIDE = [
    {
        "terms": ["soiled dressing", "blood stained gauze", "blood-stained gauze", "cotton with blood",
                  "human tissue", "anatomical waste", "expired medicine", "discarded medicine",
                  "microbiology lab waste"],
        "category": "Yellow", "container": "Yellow bag/container",
        "guidance": "Examples can fall under the Yellow category under the applicable rules. Confirm the exact waste subtype and local SOP before disposal.",
        "confidence": "Review exact subtype"
    },
    {
        "terms": ["contaminated iv set", "iv tubing", "intravenous tubing", "urine bag",
                  "syringe without needle", "contaminated gloves", "plastic tubing"],
        "category": "Red", "container": "Red bag/container",
        "guidance": "Specified contaminated recyclable plastic waste may belong in the Red category. Confirm the item is eligible and has no attached sharp.",
        "confidence": "Likely match; verify"
    },
    {
        "terms": ["needle", "scalpel", "blade", "metal sharp", "fixed needle"],
        "category": "White (translucent)", "container": "Puncture-proof, leak-proof, tamper-proof white translucent container",
        "guidance": "Specified waste sharps, including metals, may belong in the White category. Never recap, bend, or handle a sharp by hand.",
        "confidence": "Likely match; verify"
    },
    {
        "terms": ["contaminated glass vial", "medicine glass vial", "glass bottle", "glass slide", "metal implant"],
        "category": "Blue", "container": "Blue-marked cardboard box/container as prescribed",
        "guidance": "Specified contaminated glassware and metallic implants may belong in the Blue category. Confirm the item's exact status and local SOP.",
        "confidence": "Likely match; verify"
    }
]

STATUSES = ["Pending", "Assigned", "Collected", "Completed"]
ROLES = ["staff", "collector", "admin"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(app.config["DATABASE"])
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('staff','collector','admin')),
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS waste_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_name TEXT NOT NULL,
        department TEXT NOT NULL,
        quantity_kg REAL NOT NULL CHECK(quantity_kg > 0),
        category TEXT NOT NULL,
        container TEXT NOT NULL,
        guidance TEXT NOT NULL,
        review_required INTEGER NOT NULL DEFAULT 0,
        created_by INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(created_by) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS collection_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        waste_record_id INTEGER,
        department TEXT NOT NULL,
        pickup_notes TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Pending'
            CHECK(status IN ('Pending','Assigned','Collected','Completed')),
        assigned_to INTEGER,
        requested_by INTEGER NOT NULL,
        requested_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(waste_record_id) REFERENCES waste_records(id) ON DELETE SET NULL,
        FOREIGN KEY(assigned_to) REFERENCES users(id),
        FOREIGN KEY(requested_by) REFERENCES users(id)
    );
    """)
    # Seed demonstration accounts only when the users table is empty.
    count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        now = datetime.now().isoformat(timespec="seconds")
        demo_users = [
            ("admin", generate_password_hash("Admin123!"), "admin", now),
            ("staff", generate_password_hash("Staff123!"), "staff", now),
            ("collector", generate_password_hash("Collector123!"), "collector", now),
        ]
        db.executemany(
            "INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
            demo_users
        )
        db.commit()
    db.close()


@app.before_request
def ensure_db():
    if not os.path.exists(app.config["DATABASE"]):
        init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped



def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if session.get("role") not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator




def classify_waste(item_name):
    """Use existing safety rules first; AI is only an additional suggestion."""

    normalized = " ".join(item_name.lower().strip().split())
    matches = []

    for rule in WASTE_GUIDE:
        if any(term in normalized for term in rule["terms"]):
            matches.append(rule)

    categories = {m["category"] for m in matches}

    # Existing rule-based classification remains the priority.
    if len(categories) == 1:
        match = matches[0]
        return {
            "category": match["category"],
            "container": match["container"],
            "guidance": match["guidance"],
            "review_required": 1 if match["confidence"] != "Likely match; verify" else 0
        }

    # If rules are uncertain, ask the AI for an additional suggestion.
    ai_result = predict_waste_category(item_name)

    return {
        "category": "Needs trained staff review",
        "container": "Do not guess; isolate safely and follow facility SOP",
        "guidance": (
            "AI demo suggestion: " + ai_result["category"] +
            " (" + str(ai_result["confidence"]) + "% confidence). " +
            "This is not a disposal decision. Ask trained staff to verify "
            "the item using current facility rules and SOP."
        ),
        "review_required": 1
    }

    """Return a cautious rule-based suggestion; unknown/ambiguous items need review."""
    normalized = " ".join(item_name.lower().strip().split())
    matches = []
    for rule in WASTE_GUIDE:
        if any(term in normalized for term in rule["terms"]):
            matches.append(rule)
    # If zero or multiple category matches, do not guess.
    categories = {m["category"] for m in matches}
    if len(categories) != 1:
        return {
            "category": "Needs trained staff review",
            "container": "Do not guess; isolate safely and follow facility SOP",
            "guidance": "The system could not confidently map this item to one category. Ask the facility's trained biomedical-waste officer and consult current rules/SOP.",
            "review_required": 1
        }
    match = matches[0]
    return {
        "category": match["category"],
        "container": match["container"],
        "guidance": match["guidance"],
        "review_required": 1 if match["confidence"] != "Likely match; verify" else 0
    }


@app.context_processor
def inject_user():
    return {"current_user": session.get("username"), "current_role": session.get("role")}


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Signed in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("index"))



@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()

    # Overall waste statistics
    totals = db.execute("""
        SELECT COUNT(*) AS records,
               COALESCE(SUM(quantity_kg), 0) AS kg,
               COALESCE(SUM(CASE WHEN review_required=1 THEN 1 ELSE 0 END), 0) AS reviews
        FROM waste_records
    """).fetchone()

    # Collection status
    statuses = db.execute("""
        SELECT status, COUNT(*) AS count
        FROM collection_requests
        GROUP BY status
    """).fetchall()

    # Category-wise waste
    categories = db.execute("""
        SELECT category, ROUND(SUM(quantity_kg), 2) AS kg
        FROM waste_records
        GROUP BY category
        ORDER BY kg DESC
    """).fetchall()

    # Department-wise waste analytics
    department_stats = db.execute("""
        SELECT department,
               COUNT(*) AS records,
               ROUND(SUM(quantity_kg), 2) AS kg
        FROM waste_records
        GROUP BY department
        ORDER BY kg DESC
    """).fetchall()

    # Monthly waste generation
    monthly_stats = db.execute("""
        SELECT SUBSTR(created_at, 1, 7) AS month,
               ROUND(SUM(quantity_kg), 2) AS kg
        FROM waste_records
        GROUP BY SUBSTR(created_at, 1, 7)
        ORDER BY month DESC
        LIMIT 6
    """).fetchall()

    monthly_stats = list(reversed(monthly_stats))

    # Recent waste entries
    recent = db.execute("""
        SELECT w.*, u.username
        FROM waste_records w
        JOIN users u ON u.id = w.created_by
        ORDER BY w.id DESC
        LIMIT 8
    """).fetchall()

    # Recent collection requests
    requests = db.execute("""
        SELECT c.*, u.username AS requester,
               a.username AS collector
        FROM collection_requests c
        JOIN users u ON u.id = c.requested_by
        LEFT JOIN users a ON a.id = c.assigned_to
        ORDER BY c.id DESC
        LIMIT 8
    """).fetchall()

    return render_template(
        "dashboard.html",
        totals=totals,
        statuses=statuses,
        categories=categories,
        department_stats=department_stats,
        monthly_stats=monthly_stats,
        recent=recent,
        requests=requests
    )



@app.route("/segregation", methods=["GET", "POST"])
@login_required
def segregation():
    result = None
    item = ""
    if request.method == "POST":
        item = request.form.get("item_name", "").strip()
        if item:
            result = classify_waste(item)
        else:
            flash("Enter an item name first.", "warning")
    return render_template("segregation.html", result=result, item=item)


@app.route("/waste", methods=["GET", "POST"])
@roles_required("staff", "admin")
def waste_records():
    db = get_db()
    if request.method == "POST":
        item_name = request.form.get("item_name", "").strip()
        department = request.form.get("department", "").strip()
        quantity_raw = request.form.get("quantity_kg", "").strip()
        if not item_name or not department:
            flash("Item name and department are required.", "danger")
        else:
            try:
                quantity = float(quantity_raw)
                if quantity <= 0 or quantity > 100000:
                    raise ValueError()
                result = classify_waste(item_name)
                db.execute("""
                    INSERT INTO waste_records
                    (item_name, department, quantity_kg, category, container, guidance,
                     review_required, created_by, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?)
                """, (item_name, department, quantity, result["category"], result["container"],
                      result["guidance"], result["review_required"], session["user_id"],
                      datetime.now().isoformat(timespec="seconds")))
                db.commit()
                flash("Waste record saved. Review flags must be checked by trained staff.", "success")
                return redirect(url_for("waste_records"))
            except ValueError:
                flash("Enter a valid quantity greater than 0 kg.", "danger")
    rows = db.execute("""
        SELECT w.*, u.username FROM waste_records w
        JOIN users u ON u.id=w.created_by ORDER BY w.id DESC
    """).fetchall()
    return render_template("waste.html", records=rows)


@app.route("/waste/<int:record_id>/qr")
@login_required
def waste_qr(record_id):
    record = get_db().execute(
        "SELECT id FROM waste_records WHERE id = ?",
        (record_id,)
    ).fetchone()

    if not record:
        abort(404)

    tracking_url = url_for(
        "track_waste",
        record_id=record_id,
        _external=True
    )

    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4
    )
    qr.add_data(tracking_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    image_bytes = BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    return send_file(image_bytes, mimetype="image/png")


@app.route("/track/waste/<int:record_id>")
@login_required
def track_waste(record_id):
    record = get_db().execute("""
        SELECT w.*, u.username
        FROM waste_records w
        JOIN users u ON u.id = w.created_by
        WHERE w.id = ?
    """, (record_id,)).fetchone()

    if not record:
        abort(404)

    return render_template("track.html", record=record)

@app.route("/collections", methods=["GET", "POST"])
@login_required
def collections():
    db = get_db()
    if request.method == "POST":
        department = request.form.get("department", "").strip()
        record_id = request.form.get("waste_record_id", "").strip()
        notes = request.form.get("pickup_notes", "").strip()
        if not department:
            flash("Department is required.", "danger")
        else:
            valid_record_id = None
            if record_id:
                try:
                    candidate = int(record_id)
                    exists = db.execute("SELECT id FROM waste_records WHERE id=?", (candidate,)).fetchone()
                    if exists:
                        valid_record_id = candidate
                except ValueError:
                    pass
            now = datetime.now().isoformat(timespec="seconds")
            db.execute("""
                INSERT INTO collection_requests
                (waste_record_id,department,pickup_notes,status,requested_by,requested_at,updated_at)
                VALUES (?,?,?,'Pending',?,?,?)
            """, (valid_record_id, department, notes, session["user_id"], now, now))
            db.commit()
            flash("Collection request created.", "success")
            return redirect(url_for("collections"))

    records = db.execute("SELECT id,item_name,department,quantity_kg FROM waste_records ORDER BY id DESC").fetchall()
    if session["role"] == "staff":
        rows = db.execute("""
            SELECT c.*, u.username AS requester, a.username AS collector
            FROM collection_requests c JOIN users u ON u.id=c.requested_by
            LEFT JOIN users a ON a.id=c.assigned_to
            WHERE c.requested_by=? ORDER BY c.id DESC
        """, (session["user_id"],)).fetchall()
    elif session["role"] == "collector":
        rows = db.execute("""
            SELECT c.*, u.username AS requester, a.username AS collector
            FROM collection_requests c JOIN users u ON u.id=c.requested_by
            LEFT JOIN users a ON a.id=c.assigned_to
            WHERE c.status IN ('Assigned','Collected') OR c.assigned_to=?
            ORDER BY c.id DESC
        """, (session["user_id"],)).fetchall()
    else:
        rows = db.execute("""
            SELECT c.*, u.username AS requester, a.username AS collector
            FROM collection_requests c JOIN users u ON u.id=c.requested_by
            LEFT JOIN users a ON a.id=c.assigned_to
            ORDER BY c.id DESC
        """).fetchall()
    collectors = db.execute("SELECT id,username FROM users WHERE role='collector' ORDER BY username").fetchall()
    return render_template("collections.html", requests=rows, records=records, collectors=collectors,
                           statuses=STATUSES)


@app.route("/collections/<int:request_id>/update", methods=["POST"])
@roles_required("collector", "admin")
def update_collection(request_id):
    db = get_db()
    row = db.execute("SELECT * FROM collection_requests WHERE id=?", (request_id,)).fetchone()
    if not row:
        abort(404)
    if session["role"] == "collector":
        # Collectors can update only requests assigned to them, and can move assigned -> collected -> completed.
        if row["assigned_to"] not in (None, session["user_id"]):
            abort(403)
        new_status = request.form.get("status", "")
        if new_status not in ("Collected", "Completed"):
            abort(400)
        db.execute("UPDATE collection_requests SET assigned_to=?, status=?, updated_at=? WHERE id=?",
                   (session["user_id"], new_status, datetime.now().isoformat(timespec="seconds"), request_id))
    else:
        new_status = request.form.get("status", "")
        assigned_raw = request.form.get("assigned_to", "").strip()
        assigned_to = None
        if assigned_raw:
            try:
                assigned_to = int(assigned_raw)
            except ValueError:
                abort(400)
            collector = db.execute("SELECT id FROM users WHERE id=? AND role='collector'", (assigned_to,)).fetchone()
            if not collector:
                abort(400)
        if new_status not in STATUSES:
            abort(400)
        db.execute("UPDATE collection_requests SET assigned_to=?, status=?, updated_at=? WHERE id=?",
                   (assigned_to, new_status, datetime.now().isoformat(timespec="seconds"), request_id))
    db.commit()
    flash("Collection status updated.", "success")
    return redirect(url_for("collections"))


@app.route("/users", methods=["GET", "POST"])
@roles_required("admin")
def users():
    db = get_db()
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        if len(username) < 3 or len(password) < 8 or role not in ROLES:
            flash("Use a username of at least 3 characters, password of at least 8 characters, and valid role.", "danger")
        else:
            try:
                db.execute("INSERT INTO users (username,password_hash,role,created_at) VALUES (?,?,?,?)",
                           (username, generate_password_hash(password), role,
                            datetime.now().isoformat(timespec="seconds")))
                db.commit()
                flash("User created.", "success")
                return redirect(url_for("users"))
            except sqlite3.IntegrityError:
                flash("That username already exists.", "danger")
    rows = db.execute("SELECT id,username,role,created_at FROM users ORDER BY id").fetchall()
    return render_template("users.html", users=rows, roles=ROLES)


@app.errorhandler(403)
def forbidden(_error):
    return render_template("error.html", code=403, message="You do not have permission to view this page."), 403


@app.errorhandler(404)
def not_found(_error):
    return render_template("error.html", code=404, message="The requested page was not found."), 404



# ==========================================
# PDF WASTE REPORT
# ==========================================

@app.route("/reports/pdf")
@roles_required("admin")
def download_pdf_report():
    db = get_db()

    records = db.execute("""
        SELECT item_name, department, quantity_kg, category,
               created_at, review_required
        FROM waste_records
        ORDER BY id DESC
    """).fetchall()

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4)
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(
        "Smart Medical Waste Management Report",
        styles["Title"]
    ))

    elements.append(Spacer(1, 15))

    table_data = [[
        "Item",
        "Department",
        "Quantity (kg)",
        "Category",
        "Date",
        "Review"
    ]]

    for record in records:
        table_data.append([
            record["item_name"],
            record["department"],
            str(record["quantity_kg"]),
            record["category"],
            str(record["created_at"])[:10],
            "Required" if record["review_required"] else "Verify SOP"
        ])

    report_table = Table(table_data, repeatRows=1)

    report_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#173B57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE")
    ]))

    elements.append(report_table)
    document.build(elements)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="medical_waste_report.pdf",
        mimetype="application/pdf"
    )


# ==========================================
# EXCEL WASTE REPORT
# ==========================================

@app.route("/reports/excel")
@roles_required("admin")
def download_excel_report():
    db = get_db()

    records = db.execute("""
        SELECT item_name, department, quantity_kg, category,
               created_at, review_required
        FROM waste_records
        ORDER BY id DESC
    """).fetchall()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Waste Report"

    headers = [
        "Item",
        "Department",
        "Quantity (kg)",
        "Category",
        "Date",
        "Review"
    ]

    sheet.append(headers)

    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(
            start_color="173B57",
            end_color="173B57",
            fill_type="solid"
        )

    for record in records:
        sheet.append([
            record["item_name"],
            record["department"],
            record["quantity_kg"],
            record["category"],
            str(record["created_at"])[:10],
            "Required" if record["review_required"] else "Verify SOP"
        ])

    # Adjust column widths
    for column in sheet.columns:
        max_length = 0
        column_letter = column[0].column_letter

        for cell in column:
            if cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))

        sheet.column_dimensions[column_letter].width = max_length + 4

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="medical_waste_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
