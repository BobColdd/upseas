import os
import uuid
from datetime import date
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "upseasconsultants")

# --- PostgreSQL connection config: edit to match your local setup ---
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "upseas")
DB_USER = os.environ.get("DB_USER", "alvis")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "alvis")

# --- Admin credentials: edit / set as environment variables ---
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")

# --- Mail config: edit / set as environment variables ---
app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "smtp.zoho.com")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "info@keenheart.net")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "JD2Z05SzUb4s")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", "info@keenheart.net")

mail = Mail(app)
reset_serializer = URLSafeTimedSerializer(app.secret_key)
RESET_TOKEN_MAX_AGE = 3600  # 1 hour

# --- Local file storage config ---
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", os.path.expanduser("~/Documents/uploads"))
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {
    "pdf": {"pdf"},
    "mp3": {"mp3"},
    "mp4": {"mp4"},
}


def allowed_file(filename, kind):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS[kind]


def save_lecture_note(file, title, kind):
    filename = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    subfolder = os.path.join(UPLOAD_FOLDER, kind)
    os.makedirs(subfolder, exist_ok=True)
    file.save(os.path.join(subfolder, unique_name))

    relative_path = f"{kind}/{unique_name}"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO lecture_notes (title, file_path) VALUES (%s, %s)", (title, relative_path))
    conn.commit()
    cur.close()
    conn.close()


def send_password_email(email, subject, intro):
    token = reset_serializer.dumps(email, salt="password-reset")
    reset_url = url_for("reset_password", token=token, _external=True)
    msg = Message(
        subject=subject,
        recipients=[email],
        body=f"{intro}\n\n{reset_url}\n\nThis link expires in 1 hour.",
    )
    mail.send(msg)


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def student_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("student_login"))
        return f(*args, **kwargs)
    return decorated


def admin_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated


# ---------------- Student routes ----------------

@app.route("/")
def index():
    return redirect(url_for("student_login"))


@app.route("/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE email = %s", (email,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if student and check_password_hash(student["password_hash"], password):
            session["student_id"] = student["id"]
            session["student_firstname"] = student["firstname"]
            return redirect(url_for("student_dashboard"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("student_login"))

    return render_template("students_login.html")


@app.route("/dashboard")
@student_login_required
def student_dashboard():
    return render_template("skills_menu.html", firstname=session.get("student_firstname"))


@app.route("/home")
@student_login_required
def home_page():
    return render_template("home.html", firstname=session.get("student_firstname"))

@app.route("/tasks")
@student_login_required
def tasks_page():
    return render_template("home2.html", firstname=session.get("student_firstname"))

@app.route("/reading")
@student_login_required
def reading_module():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, file_path FROM lecture_notes ORDER BY id DESC")
    lecture_notes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("reading_module.html", lecture_notes=lecture_notes, firstname=session.get("student_firstname"))


@app.route("/writing")
@student_login_required
def writing_module():
    return render_template("writing_module.html", firstname=session.get("student_firstname"))



@app.route("/listening")
@student_login_required
def listening_module():
    return render_template("listening_module.html", firstname=session.get("student_firstname"))


@app.route("/speaking")
@student_login_required
def speaking_module():
    return render_template("speaking_module.html", firstname=session.get("student_firstname"))







@app.route("/reading_task")
@student_login_required
def reading_task():
    return render_template("reading_task.html", firstname=session.get("student_firstname"))


@app.route("/writing_task")
@student_login_required
def writing_task():
    return render_template("writing_task.html", firstname=session.get("student_firstname"))


@app.route("/speaking_task")
@student_login_required
def speaking_task():
    return render_template("speaking_task.html", firstname=session.get("student_firstname"))

# updated
@app.route("/listening")
@student_login_required
def listening_task():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, file_path FROM lecture_notes WHERE file_path LIKE 'mp3/%%' ORDER BY id DESC")
    mp3_notes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("listening_task.html", mp3_notes=mp3_notes)
    
# updated
@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    if "student_id" not in session and not session.get("is_admin"):
        return redirect(url_for("student_login"))
    return send_from_directory(UPLOAD_FOLDER, filepath)

'''
@app.route("/reading/<int:note_id>")
@student_login_required
def reading_module(note_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, title, file_path FROM lecture_notes WHERE id = %s", (note_id,))
    note = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("reading_module.html", note=note)
'''

@app.route("/logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_firstname", None)
    return redirect(url_for("student_login"))


# ---------------- Password reset routes ----------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM students WHERE email = %s", (email,))
        student = cur.fetchone()
        cur.close()
        conn.close()

        if student:
            send_password_email(email, "Reset your password", "Click the link below to reset your password:")

        flash("If that email exists, a password reset link has been sent.")
        return redirect(url_for("student_login"))

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = reset_serializer.loads(token, salt="password-reset", max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        flash("This reset link has expired. Please request a new one.")
        return redirect(url_for("forgot_password"))
    except BadSignature:
        flash("This reset link is invalid.")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password")
        password_hash = generate_password_hash(new_password)

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE students SET password_hash = %s WHERE email = %s", (password_hash, email))
        conn.commit()
        cur.close()
        conn.close()

        flash("Your password has been updated. You can now log in.")
        return redirect(url_for("student_login"))

    return render_template("reset_password.html", token=token)


# ---------------- Admin routes ----------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid admin credentials.")
            return redirect(url_for("admin_login"))

    return render_template("admin_login.html")

'''
@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, firstname, middlename, lastname, email, months, registration_date FROM students ORDER BY id")
    students = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("admin.html", students=students)
'''

# updated
@app.route("/admin/dashboard")
@admin_login_required
def admin_dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, firstname, middlename, lastname, email, months, registration_date FROM students ORDER BY id")
    students = cur.fetchall()

    cur.execute(
        """
        SELECT speaking_submissions.id, speaking_submissions.file_path, speaking_submissions.submitted_at,
               students.firstname, students.lastname, students.email
        FROM speaking_submissions
        JOIN students ON students.id = speaking_submissions.student_id
        ORDER BY speaking_submissions.submitted_at DESC
        """
    )
    speaking_submissions = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("admin_dashboard.html", students=students, speaking_submissions=speaking_submissions)

@app.route("/admin/create", methods=["GET", "POST"])
@admin_login_required
def admin_create_student():
    if request.method == "POST":
        firstname = request.form.get("firstname")
        middlename = request.form.get("middlename")
        lastname = request.form.get("lastname")
        email = request.form.get("email")
        months = request.form.get("months")
        password = request.form.get("password")
        password_hash = generate_password_hash(password)
        registration_date = date.today()

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO students (firstname, middlename, lastname, email, months, password_hash, registration_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (firstname, middlename, lastname, email, months, password_hash, registration_date),
        )
        conn.commit()
        cur.close()
        conn.close()

        send_password_email(email, "Set your password", "Your student account has been created. Click the link below to set your password:")

        flash("Student account created and email sent.")
        return redirect(url_for("admin_dashboard"))

    return render_template("create_student.html")


@app.route("/admin/upload/pdf", methods=["POST"])
@admin_login_required
def admin_upload_pdf():
    title = request.form.get("title")
    file = request.files.get("pdf_file")

    if file and file.filename and allowed_file(file.filename, "pdf"):
        save_lecture_note(file, title, "pdf")
        flash("PDF uploaded.")
    else:
        flash("Please choose a valid PDF file.")

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/upload/mp3", methods=["POST"])
@admin_login_required
def admin_upload_mp3():
    title = request.form.get("title")
    file = request.files.get("mp3_file")

    if file and file.filename and allowed_file(file.filename, "mp3"):
        save_lecture_note(file, title, "mp3")
        flash("MP3 uploaded.")
    else:
        flash("Please choose a valid MP3 file.")

    return redirect(url_for("admin_dashboard"))
'''
@app.route("/uploads/<path:filepath>")
def uploaded_file(filepath):
    if "student_id" not in session and not session.get("is_admin"):
        return redirect(url_for("student_login"))
    return send_from_directory(UPLOAD_FOLDER, filepath)

@app.route("/speaking/submit", methods=["POST"])
@student_login_required
def speaking_submit():
    file = request.files.get("audio")
    if file and file.filename:
        save_speaking_submission(file, session["student_id"])
        return {"status": "ok"}
    return {"status": "error", "message": "No audio received"}, 400
'''
# new
@app.route("/speaking/submit", methods=["POST"])
@student_login_required
def speaking_submit():
    file = request.files.get("audio")
    if file and file.filename:
        save_speaking_submission(file, session["student_id"])
        return {"status": "ok"}
    return {"status": "error", "message": "No audio received"}, 400

def save_speaking_submission(file, student_id):
    filename = secure_filename(file.filename) or "recording.webm"
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    subfolder = os.path.join(UPLOAD_FOLDER, "speaking")
    os.makedirs(subfolder, exist_ok=True)
    file.save(os.path.join(subfolder, unique_name))

    relative_path = f"speaking/{unique_name}"

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO speaking_submissions (student_id, file_path) VALUES (%s, %s)",
        (student_id, relative_path),
    )
    conn.commit()
    cur.close()
    conn.close()
    
@app.route("/assign-task/<int:student_id>", methods=["GET", "POST"])
@admin_login_required
def assign_task(student_id):
    if request.method == "POST":
        # Handle task assignment logic here
        pass
    return render_template("assign_task.html", student_id=student_id)
    
@app.route("/admin/upload/mp4", methods=["POST"])
@admin_login_required
def admin_upload_mp4():
    title = request.form.get("title")
    file = request.files.get("mp4_file")

    if file and file.filename and allowed_file(file.filename, "mp4"):
        save_lecture_note(file, title, "mp4")
        flash("MP4 uploaded.")
    else:
        flash("Please choose a valid MP4 file.")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
