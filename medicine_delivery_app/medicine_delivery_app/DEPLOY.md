# Deploying Doorstep Meds

## 1. The server

**Option A: Render (easiest).** Push this folder to GitHub, create a Render "Blueprint" from `render.yaml`,
and fill in the secret values it asks for. The persistent disk keeps your database (disks need a paid plan).

**Option B: Docker anywhere.**
```
docker build -t doorstep-api .
docker run -d -p 8000:8000 -v doorstep-data:/data \
  -e DOORSTEP_ADMIN_PIN=choose-a-long-pin \
  -e SMS_PROVIDER=twilio -e TWILIO_ACCOUNT_SID=... -e TWILIO_AUTH_TOKEN=... -e TWILIO_FROM=+1... \
  doorstep-api
```

On first start in production the only account is **admin** with `DOORSTEP_ADMIN_PIN`. There is no demo data.
Sign in as admin, add your patients inside the app, create invite codes for colleagues, and approve messengers as they register.

Always put the server behind HTTPS (Render does this for you; otherwise use a reverse proxy such as Caddy).

## 2. Real SMS

Set `SMS_PROVIDER=twilio` and the three `TWILIO_*` variables. Numbers written 0821234567 are sent as +27821234567.
Without them the PIN is only printed in the server log and shown once on the clinic screen.
(To use a South African SMS gateway instead, add a small class with a `send(phone, text)` method in `notifier.py`.)
This was not tested against a live SMS account: send yourself a test parcel first.

## 3. Real email

Set `EMAIL_PROVIDER=smtp` and `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
Any SMTP service works (Gmail with an app password, Brevo, Mailgun, your clinic's mail server).
Without these, emails are only printed in the server log. Also not tested against a live mail account: send yourself a test first.

## 4. The app

Point the app at your server: `DOORSTEP_API_URL=https://your-server python main.py`.
To give people the app, build it with Flet: see https://docs.flet.dev/publish/ for Android (APK) and web publishing.
For packaged builds, set the server address in `API_URL` at the top of `main.py`.

## 5. Before real patients use it (POPIA)

Patient names, addresses, phone numbers and medicine collection are personal/health information under South Africa's POPIA.
Before a pilot: get written consent from patients, agree who at the clinic is responsible, set up backups of the
database file, and have the clinic or a lawyer review your approach. This project is a prototype, not legal advice.

## 6. Scaling later

The server runs one process so its rules stay consistent. To serve many clinics, move the data to PostgreSQL
and make each action a single database transaction.
