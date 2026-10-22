import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from werkzeug.security import generate_password_hash
from app import create_app

GOOD = {"name": "Ada Obi", "email": "ada@example.com", "topic": "General", "message": "Hello, I would like a website."}


class T(unittest.TestCase):
    def setUp(self):
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close(); self.path = f.name
        self.app = create_app({"DATABASE": self.path, "TESTING": True, "SECRET_KEY": "t",
                               "ADMIN_USERNAME": "admin",
                               "ADMIN_PASSWORD_HASH": generate_password_hash("correct horse battery")})
        self.c = self.app.test_client()

    def tearDown(self):
        os.unlink(self.path)

    def tok(self, path):
        self.c.get(path)
        with self.c.session_transaction() as s:
            return s["csrf"]

    def login(self):
        t = self.tok("/admin/login")
        return self.c.post("/admin/login", data={"username": "admin", "password": "correct horse battery", "csrf": t})

    def post(self, path, data=None, page="/admin"):
        d = dict(data or {}); d["csrf"] = self.tok(page)
        return self.c.post(path, data=d)

    def count(self, table):
        import sqlite3
        c = sqlite3.connect(self.path); n = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]; c.close(); return n

    def test_public_page_shows_seed_project(self):
        r = self.c.get("/"); self.assertEqual(r.status_code, 200); self.assertIn(b"Ember &amp; Oak Bistro", r.data)
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_demos_served(self):
        for slug, title in (("restaurant", b"Ember"), ("pharmacy", b"Oakwell"), ("hotel", b"Aurelia"), ("realestate", b"Havenridge"), ("barbershop", b"Blade"), ("gym", b"Pulse")):
            r = self.c.get("/demos/" + slug); self.assertEqual(r.status_code, 200); self.assertIn(title, r.data)
        self.assertEqual(self.c.get("/demos/unknown").status_code, 404)
        self.assertIn(b'href="/demos/restaurant"', self.c.get("/").data)

    def test_relative_link_ok_but_protocol_relative_rejected(self):
        self.login()
        self.post("/admin/projects/new", {"title": "Local", "status": "Live", "live_url": "/demos/x"}, "/admin/projects/new")
        self.post("/admin/projects/new", {"title": "Sneaky", "status": "Live", "live_url": "//evil.example"}, "/admin/projects/new")
        self.assertEqual(self.count("projects"), 7)

    def test_new_demos_listed_once(self):
        html = self.c.get("/").data
        self.assertIn(b"Havenridge Realty", html); self.assertIn(b'href="/demos/barbershop"', html); self.assertIn(b'href="/demos/gym"', html)
        self.assertNotIn(b"claude.ai/artifact", html)

    def test_certificate_image_served(self):
        r = self.c.get("/static/degree-certificate.jpg"); self.assertEqual(r.status_code, 200); self.assertEqual(r.mimetype, "image/jpeg")
        self.assertIn(b"/static/degree-certificate.jpg", self.c.get("/").data)

    def test_resume_served(self):
        r = self.c.get("/static/Paseda_Adeolu_Praise_Cybersecurity_CV.pdf"); self.assertEqual(r.status_code, 200); self.assertEqual(r.mimetype, "application/pdf")
        self.assertIn(b"Download PDF", self.c.get("/").data)

    def test_contact_valid_saved(self):
        r = self.c.post("/contact", json=GOOD); self.assertTrue(r.get_json()["ok"]); self.assertEqual(self.count("messages"), 1)

    def test_contact_invalid_rejected(self):
        r = self.c.post("/contact", json={**GOOD, "email": "nope", "message": "short"})
        self.assertEqual(r.status_code, 400); self.assertEqual(self.count("messages"), 0)

    def test_honeypot_ignored(self):
        self.c.post("/contact", json={**GOOD, "website": "http://spam"}); self.assertEqual(self.count("messages"), 0)

    def test_contact_rate_limit(self):
        for _ in range(5): self.assertEqual(self.c.post("/contact", json=GOOD).status_code, 200)
        self.assertEqual(self.c.post("/contact", json=GOOD).status_code, 429)

    def test_admin_requires_login(self):
        self.assertEqual(self.c.get("/admin").status_code, 302)

    def test_wrong_password(self):
        t = self.tok("/admin/login")
        self.c.post("/admin/login", data={"username": "admin", "password": "bad", "csrf": t})
        self.assertEqual(self.c.get("/admin").status_code, 302)

    def test_post_without_csrf_rejected(self):
        self.login(); self.assertEqual(self.c.post("/admin/projects/1/delete").status_code, 400); self.assertEqual(self.count("projects"), 6)

    def test_project_crud(self):
        self.login()
        r = self.post("/admin/projects/new", {"title": "Gym Site", "status": "In progress", "published": "on", "sort_order": "9"}, "/admin/projects/new")
        self.assertEqual(r.status_code, 302); self.assertEqual(self.count("projects"), 7)
        self.assertIn(b"Gym Site", self.c.get("/").data)
        self.post("/admin/projects/7/edit", {"title": "Gym Studio", "status": "Live", "live_url": "https://example.com", "published": "on"}, "/admin/projects/7/edit")
        self.assertIn(b"Gym Studio", self.c.get("/").data)
        self.post("/admin/projects/7/edit", {"title": "Gym Studio", "status": "Live"}, "/admin/projects/7/edit")
        self.assertNotIn(b"Gym Studio", self.c.get("/").data)
        self.post("/admin/projects/7/delete"); self.assertEqual(self.count("projects"), 6)

    def test_bad_url_rejected(self):
        self.login()
        self.post("/admin/projects/new", {"title": "Evil", "status": "Live", "live_url": "javascript:alert(1)"}, "/admin/projects/new")
        self.assertEqual(self.count("projects"), 6)

    def test_message_inbox_actions(self):
        self.c.post("/contact", json=GOOD); self.login()
        self.assertIn(b"Ada Obi", self.c.get("/admin").data)
        self.post("/admin/messages/1/read"); self.post("/admin/messages/1/delete")
        self.assertEqual(self.count("messages"), 0)


if __name__ == "__main__":
    unittest.main()
