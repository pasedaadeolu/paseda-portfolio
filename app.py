"""Portfolio backend: public site, contact inbox, and an admin area to add/edit projects."""
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict
from functools import wraps

from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_from_directory, session, url_for)
from werkzeug.security import check_password_hash

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
  tech TEXT NOT NULL DEFAULT '', emoji TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Live',
  live_url TEXT NOT NULL DEFAULT '', source_url TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0, published INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL, topic TEXT NOT NULL,
  message TEXT NOT NULL, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, is_read INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY);
"""
SEED = [
    ("Ember & Oak Bistro", "Restaurant website with an interactive menu, opening hours and a validated reservation form.", "HTML, CSS, JavaScript", "🔥", "Live", "/demos/restaurant", "", 1),
    ("Oakwell Community Pharmacy", "Pharmacy site with a searchable service directory, live open-now badge, FAQ and contact form.", "HTML, CSS, JavaScript, Accessibility", "💊", "Live", "/demos/pharmacy", "", 2),
    ("Aurelia Grand Hotel", "Luxury hotel site with room filters, availability checker and an instant stay estimate.", "HTML, CSS, JavaScript", "🏨", "Live", "/demos/hotel", "", 3),
]
SEED_V2 = [  # added once to existing databases, so new demos appear without manual steps
    ("Havenridge Realty", "Real estate site with filterable listings, saved homes, a mortgage estimate and viewing requests.", "HTML, CSS, JavaScript", "🏠", "Live", "/demos/realestate", "", 4),
    ("Blade & Bloom Studio", "Barbershop and salon site with a service picker, live price total and time-slot booking.", "HTML, CSS, JavaScript", "✂️", "Live", "/demos/barbershop", "", 5),
]
SEED_V3 = [("Pulse Fitness Studio", "Gym site with a weekly class timetable, filters, class reservations, yearly or monthly plans and a trial form.", "HTML, CSS, JavaScript", "🏋️", "Live", "/demos/gym", "", 6)]
TOPICS = ("General", "Cybersecurity", "Networking", "Web development")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
URL_RE = re.compile(r"^(https?://[^\s]+|/(?!/)[^\s]*)$")  # http(s) link or a path on this site


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.environ.get("DATABASE_PATH", "portfolio.db"),
        ADMIN_USERNAME=os.environ.get("ADMIN_USERNAME", "admin"),
        ADMIN_PASSWORD_HASH=os.environ.get("ADMIN_PASSWORD_HASH", ""),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE") == "1",
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    hits = defaultdict(list)

    def too_many(key, limit, window):
        now = time.time()
        hits[key] = [t for t in hits[key] if now - t < window]
        return len(hits[key]) >= limit

    def record(key):
        hits[key].append(time.time())

    def db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn:
            conn.close()

    conn = sqlite3.connect(app.config["DATABASE"])
    conn.executescript(SCHEMA)
    if conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
        conn.executemany("INSERT INTO projects(title,description,tech,emoji,status,live_url,source_url,sort_order) VALUES(?,?,?,?,?,?,?,?)", SEED)
    if not conn.execute("SELECT 1 FROM meta WHERE k='demos_v2'").fetchone():
        for row in SEED_V2:
            if not conn.execute("SELECT 1 FROM projects WHERE live_url=?", (row[5],)).fetchone():
                conn.execute("INSERT INTO projects(title,description,tech,emoji,status,live_url,source_url,sort_order) VALUES(?,?,?,?,?,?,?,?)", row)
        conn.execute("INSERT INTO meta(k) VALUES('demos_v2')")
    if not conn.execute("SELECT 1 FROM meta WHERE k='demos_v3'").fetchone():
        for row in SEED_V3:
            if not conn.execute("SELECT 1 FROM projects WHERE live_url=?", (row[5],)).fetchone():
                conn.execute("INSERT INTO projects(title,description,tech,emoji,status,live_url,source_url,sort_order) VALUES(?,?,?,?,?,?,?,?)", row)
        conn.execute("INSERT INTO meta(k) VALUES('demos_v3')")
    conn.commit()
    conn.close()

    # ---------- security ----------
    def token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = token

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and request.path.startswith("/admin"):
            sent = request.form.get("csrf", "").encode()
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "").encode()):
                abort(400)

    @app.after_request
    def headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com; img-src 'self' data:; script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'; form-action 'self'")
        return resp

    def login_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if not session.get("admin"):
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped

    # ---------- public ----------
    @app.get("/")
    def index():
        rows = db().execute("SELECT * FROM projects WHERE published=1 ORDER BY sort_order,id").fetchall()
        return render_template("index.html", projects=rows)

    DEMOS = {"restaurant": "ember-oak-bistro.html", "pharmacy": "oakwell-pharmacy.html", "hotel": "aurelia-hotel.html",
             "realestate": "havenridge-realty.html", "barbershop": "blade-bloom-studio.html", "gym": "pulse-fitness-studio.html"}

    @app.get("/demos/<slug>")
    def demo(slug):
        name = DEMOS.get(slug) or abort(404)
        return send_from_directory(os.path.join(app.root_path, "demos"), name)

    @app.post("/contact")
    def contact():
        d = request.get_json(silent=True) or request.form
        if d.get("website"):  # honeypot: bots fill this hidden field
            return jsonify(ok=True)
        ip = request.remote_addr or "?"
        if too_many("c:" + ip, 5, 600):
            return jsonify(ok=False, error="Too many messages. Please try again later."), 429
        name = str(d.get("name") or "").strip()
        email = str(d.get("email") or "").strip()
        topic = str(d.get("topic") or "General").strip()
        text = str(d.get("message") or "").strip()
        errs = {}
        if not 2 <= len(name) <= 80:
            errs["name"] = "Enter your name."
        if len(email) > 120 or not EMAIL_RE.match(email):
            errs["email"] = "Enter a valid email."
        if topic not in TOPICS:
            errs["topic"] = "Choose a topic."
        if not 10 <= len(text) <= 2000:
            errs["message"] = "Message must be 10 to 2000 characters."
        if errs:
            return jsonify(ok=False, error="Please check the form and try again.", fields=errs), 400
        db().execute("INSERT INTO messages(name,email,topic,message) VALUES(?,?,?,?)", (name, email, topic, text))
        db().commit()
        record("c:" + ip)
        return jsonify(ok=True)

    # ---------- admin ----------
    @app.route("/admin/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            ip = request.remote_addr or "?"
            if too_many("l:" + ip, 5, 900):
                flash("Too many attempts. Try again in 15 minutes.")
                return render_template("login.html"), 429
            h = app.config["ADMIN_PASSWORD_HASH"]
            user_ok = secrets.compare_digest(request.form.get("username", "").encode(), app.config["ADMIN_USERNAME"].encode())
            if h and check_password_hash(h, request.form.get("password", "")) and user_ok:
                session.clear()
                session["admin"] = True
                return redirect(url_for("dashboard"))
            record("l:" + ip)
            flash("Invalid credentials." if h else "Admin password is not configured on the server.")
        return render_template("login.html")

    @app.post("/admin/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/admin")
    @login_required
    def dashboard():
        msgs = db().execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
        projects = db().execute("SELECT * FROM projects ORDER BY sort_order,id").fetchall()
        return render_template("dashboard.html", msgs=msgs, projects=projects,
                               unread=sum(1 for m in msgs if not m["is_read"]))

    def clean_project(f):
        p = {k: f.get(k, "").strip() for k in ("title", "description", "tech", "emoji", "status", "live_url", "source_url")}
        errs = []
        if not 2 <= len(p["title"]) <= 80:
            errs.append("Title must be 2 to 80 characters.")
        if len(p["description"]) > 400 or len(p["tech"]) > 120 or len(p["emoji"]) > 8:
            errs.append("Description (400), tech (120) or emoji (8) is too long.")
        if p["status"] not in ("Live", "In progress"):
            errs.append("Choose a status.")
        for k in ("live_url", "source_url"):
            if p[k] and not (URL_RE.match(p[k]) and len(p[k]) <= 300):
                errs.append("Links must start with http://, https:// or a single /.")
        try:
            p["sort_order"] = int(f.get("sort_order", "0") or 0)
        except ValueError:
            errs.append("Order must be a number.")
            p["sort_order"] = 0
        p["published"] = 1 if f.get("published") else 0
        return p, errs

    COLS = "title,description,tech,emoji,status,live_url,source_url,sort_order,published"

    @app.route("/admin/projects/new", methods=["GET", "POST"])
    @login_required
    def project_new():
        p = {"status": "Live", "published": 1, "sort_order": 0}
        if request.method == "POST":
            p, errs = clean_project(request.form)
            if not errs:
                db().execute(f"INSERT INTO projects({COLS}) VALUES(?,?,?,?,?,?,?,?,?)", [p[c] for c in COLS.split(",")])
                db().commit()
                flash("Project added.")
                return redirect(url_for("dashboard"))
            for e in errs:
                flash(e)
        return render_template("project_form.html", p=p, heading="Add project")

    @app.route("/admin/projects/<int:pid>/edit", methods=["GET", "POST"])
    @login_required
    def project_edit(pid):
        row = db().execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone() or abort(404)
        p = dict(row)
        if request.method == "POST":
            p, errs = clean_project(request.form)
            if not errs:
                sets = ",".join(c + "=?" for c in COLS.split(","))
                db().execute(f"UPDATE projects SET {sets} WHERE id=?", [p[c] for c in COLS.split(",")] + [pid])
                db().commit()
                flash("Project saved.")
                return redirect(url_for("dashboard"))
            for e in errs:
                flash(e)
        return render_template("project_form.html", p=p, heading="Edit project")

    @app.post("/admin/projects/<int:pid>/delete")
    @login_required
    def project_delete(pid):
        db().execute("DELETE FROM projects WHERE id=?", (pid,))
        db().commit()
        flash("Project deleted.")
        return redirect(url_for("dashboard"))

    @app.post("/admin/messages/<int:mid>/read")
    @login_required
    def message_read(mid):
        db().execute("UPDATE messages SET is_read = 1 - is_read WHERE id=?", (mid,))
        db().commit()
        return redirect(url_for("dashboard"))

    @app.post("/admin/messages/<int:mid>/delete")
    @login_required
    def message_delete(mid):
        db().execute("DELETE FROM messages WHERE id=?", (mid,))
        db().commit()
        return redirect(url_for("dashboard"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False)
