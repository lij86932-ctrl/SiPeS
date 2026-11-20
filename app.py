
import os
from functools import wraps
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "ganti-kunci-rahasia-ini"
)

db_user = os.getenv("DB_USER", "root")
db_password = quote_plus(os.getenv("DB_PASSWORD", ""))
db_host = os.getenv("DB_HOST", "127.0.0.1")
db_port = os.getenv("DB_PORT", "3306")
db_name = os.getenv("DB_NAME", "sipesat_db")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://{db_user}:{db_password}"
    f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

db = SQLAlchemy(app)


# =========================
# MODEL DATABASE
# =========================

class Admin(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)


class Sekolah(db.Model):
    __tablename__ = "sekolah"

    id = db.Column(db.Integer, primary_key=True)
    npsn = db.Column(db.String(20), unique=True, nullable=False)
    nama_sekolah = db.Column(db.String(150), nullable=False)
    jenjang = db.Column(db.String(20), nullable=False)
    kecamatan = db.Column(db.String(100), nullable=False)
    alamat = db.Column(db.Text, nullable=True)
    kepala_sekolah = db.Column(db.String(120), nullable=True)
    jumlah_siswa = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime, server_default=db.func.current_timestamp()
    )


# =========================
# AKSES KHUSUS ADMIN
# =========================

def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            flash("Silakan login sebagai admin terlebih dahulu.", "warning")
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, private"
    )
    response.headers["Pragma"] = "no-cache"
    return response


# =========================
# LOGIN
# =========================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if "admin_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password_hash, password):
            session.clear()
            session["admin_id"] = admin.id
            session["admin_username"] = admin.username
            return redirect(url_for("dashboard"))

        flash("Username atau password salah.", "danger")

    return render_template("login.html")


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
@admin_required
def dashboard():
    return render_template(
        "dashboard.html",
        total_sekolah=Sekolah.query.count(),
        total_sma=Sekolah.query.filter_by(jenjang="SMA").count(),
        total_smk=Sekolah.query.filter_by(jenjang="SMK").count(),
        sekolah_terbaru=Sekolah.query.order_by(
            Sekolah.id.desc()
        ).limit(5).all()
    )


# =========================
# DAFTAR DAN PENCARIAN
# =========================

@app.route("/sekolah")
@admin_required
def daftar_sekolah():
    q = request.args.get("q", "").strip()
    jenjang = request.args.get("jenjang", "").strip()

    query = Sekolah.query

    if q:
        pola = f"%{q}%"
        query = query.filter(or_(
            Sekolah.npsn.like(pola),
            Sekolah.nama_sekolah.like(pola),
            Sekolah.kecamatan.like(pola)
        ))

    if jenjang in ("SMA", "SMK"):
        query = query.filter_by(jenjang=jenjang)

    sekolah = query.order_by(Sekolah.nama_sekolah.asc()).all()

    return render_template(
        "daftar_sekolah.html",
        sekolah=sekolah, q=q, jenjang=jenjang
    )


# =========================
# TAMBAH DATA
# =========================

@app.route("/sekolah/tambah", methods=["GET", "POST"])
@admin_required
def tambah_sekolah():
    if request.method == "POST":
        npsn = request.form.get("npsn", "").strip()
        nama = request.form.get("nama_sekolah", "").strip()
        jenjang = request.form.get("jenjang", "").strip()
        kecamatan = request.form.get("kecamatan", "").strip()
        alamat = request.form.get("alamat", "").strip()
        kepala = request.form.get("kepala_sekolah", "").strip()
        jumlah = request.form.get("jumlah_siswa", "0").strip()

        if not all([npsn, nama, jenjang, kecamatan]):
            flash("NPSN, nama sekolah, jenjang, dan kecamatan wajib diisi.", "danger")
            return render_template("form_sekolah.html", data=request.form, mode="Tambah")

        if jenjang not in ("SMA", "SMK"):
            flash("Jenjang harus SMA atau SMK.", "danger")
            return render_template("form_sekolah.html", data=request.form, mode="Tambah")

        try:
            jumlah_siswa = int(jumlah or 0)
            if jumlah_siswa < 0:
                raise ValueError
        except ValueError:
            flash("Jumlah siswa harus berupa angka nol atau lebih.", "danger")
            return render_template("form_sekolah.html", data=request.form, mode="Tambah")

        if Sekolah.query.filter_by(npsn=npsn).first():
            flash("NPSN tersebut sudah terdaftar.", "danger")
            return render_template("form_sekolah.html", data=request.form, mode="Tambah")

        sekolah = Sekolah(
            npsn=npsn,
            nama_sekolah=nama,
            jenjang=jenjang,
            kecamatan=kecamatan,
            alamat=alamat,
            kepala_sekolah=kepala,
            jumlah_siswa=jumlah_siswa
        )

        db.session.add(sekolah)
        db.session.commit()
        flash("Data sekolah berhasil ditambahkan.", "success")
        return redirect(url_for("daftar_sekolah"))

    return render_template("form_sekolah.html", data={}, mode="Tambah")


# =========================
# EDIT DATA
# =========================

@app.route("/sekolah/edit/<int:id>", methods=["GET", "POST"])
@admin_required
def edit_sekolah(id):
    sekolah = db.get_or_404(Sekolah, id)

    if request.method == "POST":
        npsn = request.form.get("npsn", "").strip()
        nama = request.form.get("nama_sekolah", "").strip()
        jenjang = request.form.get("jenjang", "").strip()
        kecamatan = request.form.get("kecamatan", "").strip()
        jumlah = request.form.get("jumlah_siswa", "0").strip()

        if not all([npsn, nama, jenjang, kecamatan]):
            flash("Lengkapi semua kolom wajib.", "danger")
            return render_template(
                "form_sekolah.html", data=request.form, mode="Edit"
            )

        if jenjang not in ("SMA", "SMK"):
            flash("Jenjang harus SMA atau SMK.", "danger")
            return render_template(
                "form_sekolah.html", data=request.form, mode="Edit"
            )

        duplikat = Sekolah.query.filter(
            Sekolah.npsn == npsn, Sekolah.id != id
        ).first()

        if duplikat:
            flash("NPSN sudah digunakan sekolah lain.", "danger")
            return render_template(
                "form_sekolah.html", data=request.form, mode="Edit"
            )

        try:
            jumlah_siswa = int(jumlah or 0)
            if jumlah_siswa < 0:
                raise ValueError
        except ValueError:
            flash("Jumlah siswa tidak valid.", "danger")
            return render_template(
                "form_sekolah.html", data=request.form, mode="Edit"
            )

        sekolah.npsn = npsn
        sekolah.nama_sekolah = nama
        sekolah.jenjang = jenjang
        sekolah.kecamatan = kecamatan
        sekolah.alamat = request.form.get("alamat", "").strip()
        sekolah.kepala_sekolah = request.form.get("kepala_sekolah", "").strip()
        sekolah.jumlah_siswa = jumlah_siswa

        db.session.commit()
        flash("Data sekolah berhasil diperbarui.", "success")
        return redirect(url_for("daftar_sekolah"))

    data = {
        "npsn": sekolah.npsn,
        "nama_sekolah": sekolah.nama_sekolah,
        "jenjang": sekolah.jenjang,
        "kecamatan": sekolah.kecamatan,
        "alamat": sekolah.alamat or "",
        "kepala_sekolah": sekolah.kepala_sekolah or "",
        "jumlah_siswa": sekolah.jumlah_siswa
    }
    return render_template("form_sekolah.html", data=data, mode="Edit")


# =========================
# HAPUS DATA
# =========================

@app.route("/sekolah/hapus/<int:id>", methods=["POST"])
@admin_required
def hapus_sekolah(id):
    sekolah = db.get_or_404(Sekolah, id)
    db.session.delete(sekolah)
    db.session.commit()
    flash("Data sekolah berhasil dihapus.", "success")
    return redirect(url_for("daftar_sekolah"))


# =========================
# LAPORAN
# =========================

@app.route("/laporan")
@admin_required
def laporan():
    sekolah = Sekolah.query.order_by(Sekolah.nama_sekolah.asc()).all()
    return render_template("laporan.html", sekolah=sekolah)


# =========================
# LOGOUT
# =========================


# =========================
# KELOLA ADMIN
# =========================

@app.route("/admin/hapus/<int:id>", methods=["POST"])
@admin_required
def hapus_admin(id):
    admin = db.get_or_404(Admin, id)

    # Admin tidak boleh menghapus akunnya sendiri.
    if admin.id == session.get("admin_id"):
        flash("Kamu tidak bisa menghapus akun yang sedang digunakan.", "danger")
        return redirect(url_for("kelola_admin"))

    db.session.delete(admin)
    db.session.commit()

    flash("Akun admin berhasil dihapus.", "success")
    return redirect(url_for("kelola_admin"))


@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    flash("Kamu sudah logout.", "success")
    return redirect(url_for("login"))


# =========================
# INISIALISASI DATABASE
# ================


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def kelola_admin():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        konfirmasi = request.form.get("konfirmasi_password", "")

        if not username or not password or not konfirmasi:
            flash("Semua kolom wajib diisi.", "danger")

        elif len(username) < 3:
            flash("Username minimal 3 karakter.", "danger")

        elif len(password) < 8:
            flash("Password minimal 8 karakter.", "danger")

        elif password != konfirmasi:
            flash("Konfirmasi password tidak cocok.", "danger")

        elif Admin.query.filter_by(username=username).first():
            flash("Username sudah digunakan. Coba username lain.", "danger")

        else:
            try:
                admin_baru = Admin(
                    username=username,
                    password_hash=generate_password_hash(password)
                )

                db.session.add(admin_baru)
                db.session.commit()

                flash(
                    f"Akun admin '{username}' berhasil ditambahkan.",
                    "success"
                )
                return redirect(url_for("kelola_admin"))

            except Exception as e:
                db.session.rollback()
                app.logger.exception("Gagal menambahkan akun admin")
                flash(
                    "Akun gagal disimpan ke database. Periksa terminal VS Code.",
                    "danger"
                )

    daftar_admin = Admin.query.order_by(Admin.username.asc()).all()

    return render_template(
        "kelola_admin.html",
        daftar_admin=daftar_admin
    )


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

        # Akun awal hanya dibuat jika belum ada akun admin.
        if Admin.query.count() == 0:
            username_awal = os.getenv("INITIAL_ADMIN_USER", "admin")
            password_awal = os.getenv("INITIAL_ADMIN_PASSWORD", "admin123")

            admin_awal = Admin(
                username=username_awal,
                password_hash=generate_password_hash(password_awal)
            )
            db.session.add(admin_awal)
            db.session.commit()
            print(f"Akun admin awal dibuat: {username_awal}")
            print("Segera ganti password awal setelah login.")

    app.run(debug=True)
