# Portfolio backend (Flask + SQLite)

Your portfolio site, plus:
- **Contact inbox**: the contact form saves messages to the database.
- **Admin area** at `/admin`: read, mark and delete messages; add, edit, hide, reorder and delete projects.

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python make_hash.py          # paste the ADMIN_PASSWORD_HASH line it prints into .env
# also set SECRET_KEY in .env to a long random string
flask --app app run          # open http://127.0.0.1:5000  and  /admin
```

## Demo sites
The restaurant, pharmacy and hotel demos are served by the app at `/demos/restaurant`, `/demos/pharmacy`, `/demos/hotel`, `/demos/realestate`, `/demos/barbershop` and `/demos/gym`
(files in `demos/`). Add more by dropping an HTML file in `demos/` and registering it in `DEMOS` in `app.py`.

## Updating your résumé or certificate
Replace `static/Paseda_Adeolu_Praise_Cybersecurity_CV.pdf`, `static/resume-page-1.jpg`, `static/resume-page-2.jpg` (page previews) and `static/degree-certificate.jpg`.

## Run the tests
```bash
python -m unittest discover -s tests -v
```

## Deploy (not yet deployed)
Any host that runs Python works (Render, Railway, PythonAnywhere, a VPS).
- Start command: `gunicorn app:app`
- Set the env vars from `.env.example` on the host; set `COOKIE_SECURE=1` once you have HTTPS.
- SQLite needs a persistent disk. Point `DATABASE_PATH` at it, or move to PostgreSQL later.
- Use a single gunicorn worker (rate limits are kept in memory), or add Redis for several.

## Security notes
No password is stored in code: only a hash in your environment. Admin forms use CSRF tokens, queries are parameterised,
the contact form has a honeypot and a rate limit, login attempts are throttled, and project URLs must be http(s).
If the app is behind a proxy, configure it so `request.remote_addr` is the real client IP (for the rate limits).

## Not included yet
Email notifications for new messages, password reset, image uploads and a multi-user admin.
