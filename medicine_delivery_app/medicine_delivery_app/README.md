# Doorstep Meds

![logo](assets/logo.svg)

A mobile/web app that moves repeat medication from the clinic to the doorstep of elderly
and disabled patients, using a trusted local **messenger** from the patient's own village.
It cuts clinic queues and saves patients a long, costly trip.

Built for the FNB App Academy capstone (Introduction to Python: Mobile and Web application development).

## How it works

1. **Clinic staff** add patients, then mark a parcel *Ready*. The server creates a 4-digit handover PIN and
   **sends it to the patient or caregiver by SMS** (and email if the patient has one). The village's messengers
   are notified that a parcel is waiting.
2. The **messenger** for that village sees only their village's parcels, taps *Collect from clinic*, then delivers.
3. At the door the patient or caregiver gives the PIN; the messenger types it in. The parcel becomes *Delivered*.
   If nobody is home, the messenger taps *Return to clinic* and the clinic can *Queue again*.
4. Every step is logged with a time and who did it.

Clinic and messengers use **different phones**: all data lives on the backend server.

## Features

- **Registration.** Anyone can *Create account*. Messengers apply and wait for clinic approval (the clinic gets
  notified and approves or declines in the app). Clinic staff join with a one-use **invite code** made by a colleague.
- **In-app messages.** Clinic to one messenger, to everyone in a village, or to all messengers. Messengers write to
  the clinic. Unread count on the Messages button. Tick *Also send by email / SMS* to push it to their phone or inbox.
- **Email and SMS notifications.** New parcel (to the village's messengers), approval or decline, returned parcel
  (to clinic), delivery confirmation (to the patient), temporary PIN, welcome messages.
- **Message a patient** by SMS, email or both from any delivery card.
- **Profile.** Everyone can save their email and phone and change their PIN.
- **PIN reset.** The clinic can give a messenger a temporary PIN (sent by SMS or email) after a forgotten PIN.
- **Safety.** See below.

## Architecture

```
 Flet app (phone / desktop / web)            Backend server (Flask + SQLite)
 main.py, views/, theme.py   --- HTTPS --->  backend/app.py  REST API + token login
 api_client.py (requests)    <-- JSON ----   models.py       rules and classes
                                             storage.py      SQLite (or JSON) persistence
                                             notifier.py     SMS (console or Twilio)
```

## Security and privacy

- PINs are never stored, only salted hashes. The handover PIN is shown to the clinic once, when created.
- Login tokens expire after 12 hours; five wrong logins lock that username for 5 minutes.
- Five wrong handover PINs lock the parcel until the clinic sends a new PIN.
- Sign-ups are limited per device, messengers need approval, and staff need an invite code.
- Role checks on the server: a messenger cannot use clinic actions or see another village.
- Messengers never receive the medicine label, only name, address and phone.

## Run it on your computer

```
python -m venv venv
venv\Scripts\activate          (Windows)   or   source venv/bin/activate
pip install -r requirements.txt -r backend/requirements.txt

# Terminal 1: the server (creates data/doorstep.db with demo data)
python -m backend.app

# Terminal 2: the app
python main.py
```

The app connects to `http://127.0.0.1:8000`. To use another server:
`set DOORSTEP_API_URL=https://your-server` (Windows) or `export DOORSTEP_API_URL=...`.
From an Android emulator use `http://10.0.2.2:8000`.

### Demo logins

| Role      | Username | PIN  | Village   |
|-----------|----------|------|-----------|
| Clinic    | clinic1  | 1234 | n/a       |
| Messenger | thabo    | 1111 | Lekubu    |
| Messenger | lerato   | 2222 | Dinokana  |
| Messenger (waiting for approval) | nomsa | 3333 | Lekubu |

The sample parcel for Dineo Molefe (Lekubu) has handover PIN **1234**.
Open the app twice (two windows) to play clinic and messenger at the same time. Use the refresh icon to load new data.
SMS and email messages print in the server terminal in development. To see approval in action, sign in as clinic1 and
approve the waiting messenger *Nomsa* (she signs in with nomsa / 3333 afterwards), or register a new messenger yourself.

## Deploy for real use

See [DEPLOY.md](DEPLOY.md) (Docker / Render, real SMS with Twilio, building the Android app).

## Folder structure

```
main.py            App start, theme, routing and role guards
api_client.py      RemoteManager: every call to the server
views/             One file per screen (login, register, clinic, messenger, messages, profile, ...)
theme.py           Shared colours, spacing, font sizes
models.py          User > ClinicStaff / Messenger, Patient, Delivery, DeliveryManager
storage.py         JsonStore and SqliteStore
notifier.py        SMS (Twilio) and email (SMTP) providers
backend/app.py     REST API
tests/             Unit, API and end-to-end tests
assets/            Logo
DEPLOY.md  PITCH.md  DEMO_SCRIPT.md  PEER_FEEDBACK.md
```

## Course concepts used

- **Functions and OOP**: inheritance, `super()`, polymorphism (`home_route`, `to_public`), composition (`DeliveryManager`).
- **Files and errors**: JSON and SQLite persistence, `try/except`, validation with `ValueError`.
- **Flet**: multi-view routing, themed UI, dialogs, field errors, role guards.
- **APIs**: the `requests` library with GET/POST, `raise_for_status`-style error handling, and our own REST API.
- **User-centred design**: large text, plain language, few steps per task, colour-coded statuses.

## Tests

```
python -m unittest discover -s tests     # 43 tests: models, storage, API, client against a live server
python tests/smoke_ui.py                 # builds every screen against a live server (no Flet needed)
```

## Known limits

- One server process (the rules run behind a lock). Fine for a clinic pilot; for many clinics move to PostgreSQL.
- Messages are not live: use the refresh icon (or reopen the screen) to load new ones.
- Clinic and messenger must be online. Offline mode is future work.
- The Flet screens were written to the course's Flet version; run them and report any error message.
