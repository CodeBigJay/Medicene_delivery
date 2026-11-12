"""REST API for Doorstep Meds (Flask + SQLite).

Run from the project folder:
    python -m backend.app                      (development)
    gunicorn -w 1 --threads 8 backend.app:app  (production)

Every endpoint except /api/health, /api/login and /api/register needs the header
    Authorization: Bearer <token>
"""
import os
import secrets
import threading
import time
from functools import wraps
from pathlib import Path

from flask import Flask, g, jsonify, request

from models import (ACTIVE, TO_CLINIC, DeliveryManager, Messenger, ClinicStaff)
from notifier import get_notifier, pin_message
from storage import JsonStore, SqliteStore

SESSION_SECONDS = 12 * 60 * 60
LOGIN_LIMIT = 5
LOCKOUT_SECONDS = 300
REGISTER_LIMIT = 10          # sign-ups per address per hour
REGISTER_WINDOW = 3600


def create_app(store=None, notifier=None, sync_notify=False):
    app = Flask(__name__)
    if store is None:
        root = Path(__file__).resolve().parent.parent
        db_path = os.environ.get("DOORSTEP_DB", str(root / "data" / "doorstep.db"))
        store = JsonStore(db_path) if db_path.endswith(".json") else SqliteStore(db_path)
    production = os.environ.get("DOORSTEP_ENV", "development") == "production"
    manager = DeliveryManager(store, demo=not production, admin_pin=os.environ.get("DOORSTEP_ADMIN_PIN"))
    notifier = notifier or get_notifier()
    lock = threading.Lock()           # one request changes data at a time
    failures = {}                     # username -> (count, first_failure_time)
    signups = {}                      # address -> [timestamps]
    memory_sessions = {}              # used when the store has no session table

    # ---- notifications (never allowed to break a request) -------------
    def in_background(job):
        def safe():
            try:
                job()
            except Exception as err:  # a failed email must not hurt the app
                print(f"Notification error: {err}")
        if sync_notify:
            safe()
        else:
            threading.Thread(target=safe, daemon=True).start()

    def tell(users, subject, text, use_sms=True, use_email=True):
        """Notify users on every channel they have a contact for."""
        contacts = [(u.phone, u.email) for u in users]

        def job():
            for phone, email in contacts:
                if use_email and email:
                    notifier.email(email, subject, text)
                if use_sms and phone:
                    notifier.sms(phone, f"Doorstep Meds: {text}")
        in_background(job)

    def tell_patient(patient, text, subject="Doorstep Meds"):
        phone, email = patient.contact, patient.email

        def job():
            notifier.sms(phone, f"Doorstep Meds: {text}")
            if email:
                notifier.email(email, subject, text)
        in_background(job)

    # ---- sessions -----------------------------------------------------
    def make_session(username):
        token = secrets.token_urlsafe(32)
        expires = time.time() + SESSION_SECONDS
        if hasattr(store, "add_session"):
            store.add_session(token, username, expires)
        else:
            memory_sessions[token] = (username, expires)
        return token

    def lookup_session(token):
        if hasattr(store, "get_session"):
            return store.get_session(token, time.time())
        entry = memory_sessions.get(token)
        return entry[0] if entry and entry[1] > time.time() else None

    def end_session(token):
        if hasattr(store, "delete_session"):
            store.delete_session(token)
        else:
            memory_sessions.pop(token, None)

    # ---- decorators ---------------------------------------------------
    def needs_role(role=None):
        def wrap(fn):
            @wraps(fn)
            def inner(*args, **kwargs):
                header = request.headers.get("Authorization", "")
                token = header[7:] if header.startswith("Bearer ") else ""
                username = lookup_session(token) if token else None
                user = manager.get_user(username) if username else None
                if user is None or user.status != ACTIVE:
                    return jsonify(detail="Please sign in again."), 401
                if role and user.role != role:
                    return jsonify(detail="You are not allowed to do that."), 403
                g.user, g.token = user, token
                with lock:
                    try:
                        return fn(*args, **kwargs)
                    except ValueError as err:
                        return jsonify(detail=str(err)), 400
            return inner
        return wrap

    def body():
        return request.get_json(silent=True) or {}

    # ---- public routes -------------------------------------------------
    @app.get("/api/health")
    def health():
        return jsonify(status="ok")

    @app.post("/api/login")
    def login():
        data = body()
        username = str(data.get("username", "")).strip().lower()
        with lock:
            count, first = failures.get(username, (0, 0))
            if count >= LOGIN_LIMIT and time.time() - first < LOCKOUT_SECONDS:
                return jsonify(detail="Too many tries. Wait a few minutes and try again."), 429
            if count >= LOGIN_LIMIT:
                count = 0
            try:
                user = manager.authenticate(username, data.get("pin", ""))
            except ValueError as err:       # right PIN, but the account is not active
                return jsonify(detail=str(err)), 403
            if user is None:
                failures[username] = (count + 1, first if count else time.time())
                return jsonify(detail="Wrong username or PIN."), 401
            failures.pop(username, None)
            return jsonify(token=make_session(user.username), user=user.to_public())

    @app.post("/api/register")
    def register():
        data = body()
        address = request.remote_addr or "?"
        with lock:
            recent = [t for t in signups.get(address, []) if time.time() - t < REGISTER_WINDOW]
            if len(recent) >= REGISTER_LIMIT:
                return jsonify(detail="Too many sign-ups from this device. Try again later."), 429
            try:
                role = str(data.get("role", "messenger"))
                args = (data.get("username"), data.get("full_name"), data.get("pin"))
                contact = dict(email=data.get("email", ""), phone=data.get("phone", ""))
                if role == "clinic":
                    user = manager.register_staff(data.get("invite_code"), *args, **contact)
                elif role == "messenger":
                    user = manager.register_messenger(*args, village=data.get("village"), **contact)
                else:
                    raise ValueError("Choose messenger or clinic staff.")
            except ValueError as err:
                return jsonify(detail=str(err)), 400
            signups[address] = recent + [time.time()]
            if user.status == ACTIVE:
                tell([user], "Welcome to Doorstep Meds",
                     f"Welcome {user.full_name}! Your clinic staff account is ready.")
            else:
                tell(manager.active_clinic_staff(), "New messenger registration",
                     f"{user.full_name} ({user.username}) wants to deliver in {user.village}. "
                     f"Open the app to approve or decline.")
                tell([user], "We got your registration",
                     f"Hi {user.full_name}, the clinic will review your registration and let you know.")
            return jsonify(status=user.status, username=user.username), 201

    # ---- any signed-in user --------------------------------------------
    @app.post("/api/logout")
    @needs_role()
    def logout():
        end_session(g.token)
        return jsonify(ok=True)

    @app.get("/api/snapshot")
    @needs_role()
    def snapshot():
        user = g.user
        unread = manager.unread_count(user)
        if user.role == "clinic":
            return jsonify(
                me=user.to_public(), unread=unread,
                patients=[p.to_dict() for p in manager.patients],
                deliveries=[d.to_public(True) for d in manager.deliveries],
                messengers=[u.to_public() for u in manager.active_messengers()],
                pending=[u.to_public() for u in manager.pending_users()],
                villages=manager.villages(),
            )
        active = manager.active_for_messenger(user)
        patients = {d.patient_id: manager.get_patient(d.patient_id) for d in active}
        delivered = sum(1 for d in manager.deliveries
                        if d.messenger == user.username and d.status == "Delivered")
        return jsonify(
            me=user.to_public(), unread=unread,
            patients=[p.to_dict() for p in patients.values() if p],
            deliveries=[d.to_public(False) for d in active],
            delivered_count=delivered,
        )

    @app.post("/api/me/pin")
    @needs_role()
    def change_pin():
        d = body()
        manager.change_pin(g.user, d.get("old_pin", ""), d.get("new_pin", ""))
        return jsonify(ok=True)

    @app.put("/api/me/contact")
    @needs_role()
    def update_contact():
        d = body()
        return jsonify(manager.update_contact(g.user, d.get("email", ""), d.get("phone", "")).to_public())

    @app.get("/api/messages")
    @needs_role()
    def list_messages():
        user = g.user
        names = {u.username: u.full_name for u in manager.users}
        out = []
        for m in manager.messages_for(user):
            row = m.to_dict()
            row["sender_name"] = names.get(m.sender, m.sender)
            row["to_name"] = names.get(m.to, m.to)
            row["mine"] = m.sender == user.username
            row["unread"] = m.message_id > user.last_read and not row["mine"]
            out.append(row)
        return jsonify(messages=out, unread=manager.unread_count(user))

    @app.post("/api/messages/read")
    @needs_role()
    def read_messages():
        manager.mark_read(g.user)
        return jsonify(ok=True)

    @app.post("/api/messages")
    @needs_role()
    def send_message():
        d = body()
        user = g.user
        message = manager.send_message(user, d.get("to"), d.get("text"), d.get("delivery_id"))
        recipients = [u for u in manager.recipients_of(message.to) if u.username != user.username]
        if d.get("email") or d.get("sms"):
            tell(recipients, f"Doorstep Meds: message from {user.full_name}",
                 f"{user.full_name}: {message.text}",
                 use_sms=bool(d.get("sms")), use_email=bool(d.get("email")))
        return jsonify(message.to_dict()), 201

    # ---- clinic ---------------------------------------------------------
    def sms_pin(delivery, pin):
        patient = manager.get_patient(delivery.patient_id)
        sent = notifier.sms(patient.contact, pin_message(patient.name, pin))
        if patient.email:
            notifier.email(patient.email, "Your Doorstep Meds PIN", pin_message(patient.name, pin))
        return sent

    @app.post("/api/patients")
    @needs_role("clinic")
    def add_patient():
        d = body()
        patient = manager.add_patient(d.get("name"), d.get("village"), d.get("address"),
                                      d.get("contact"), d.get("email", ""))
        return jsonify(patient.to_dict()), 201

    @app.post("/api/patients/<patient_id>/message")
    @needs_role("clinic")
    def message_patient(patient_id):
        d = body()
        patient = manager.get_patient(patient_id)
        text = str(d.get("text", "")).strip()
        channel = d.get("channel", "sms")
        if patient is None:
            raise ValueError("Patient not found.")
        if not text or len(text) > 300:
            raise ValueError("Write a message of up to 300 characters.")
        if channel not in ("sms", "email", "both"):
            raise ValueError("Choose SMS, email or both.")
        if channel in ("email", "both") and not patient.email:
            raise ValueError("This patient has no email address on file.")
        text = f"{g.user.full_name} (clinic): {text}"
        result = {"sms_sent": None, "email_sent": None}
        if channel in ("sms", "both"):
            result["sms_sent"] = bool(notifier.sms(patient.contact, f"Doorstep Meds: {text}"))
        if channel in ("email", "both"):
            result["email_sent"] = bool(notifier.email(patient.email, "Message from your clinic", text))
        return jsonify(result)

    @app.post("/api/messengers")
    @needs_role("clinic")
    def add_messenger():
        d = body()
        messenger = manager.add_messenger(d.get("username"), d.get("full_name"), d.get("pin"),
                                          d.get("village"), d.get("email", ""), d.get("phone", ""))
        return jsonify(messenger.to_public()), 201

    @app.post("/api/invites")
    @needs_role("clinic")
    def create_invite():
        return jsonify(code=manager.create_invite(g.user.username)), 201

    @app.post("/api/users/<username>/approve")
    @needs_role("clinic")
    def approve(username):
        user = manager.approve_user(username)
        tell([user], "Your Doorstep Meds account is approved",
             f"Good news {user.full_name}, the clinic approved your account. You can sign in now.")
        return jsonify(user.to_public())

    @app.post("/api/users/<username>/reject")
    @needs_role("clinic")
    def reject(username):
        user = manager.reject_user(username)
        tell([user], "Your Doorstep Meds registration",
             f"Hi {user.full_name}, the clinic could not approve your registration. Please contact them.")
        return jsonify(user.to_public())

    @app.post("/api/users/<username>/reset-pin")
    @needs_role("clinic")
    def reset_pin(username):
        pin = manager.reset_pin(username)
        user = manager.get_user(username)
        tell([user], "Your temporary Doorstep Meds PIN",
             f"Your temporary PIN is {pin}. Sign in and change it under Profile.")
        return jsonify(pin=pin)

    @app.post("/api/deliveries")
    @needs_role("clinic")
    def create_delivery():
        d = body()
        delivery, pin = manager.create_delivery(d.get("patient_id"), d.get("parcel_note"), g.user.username)
        patient = manager.get_patient(delivery.patient_id)
        tell(manager.messengers_for_village(patient.village), "New parcel ready",
             f"A parcel for {patient.village} is ready for collection at the clinic.")
        return jsonify(delivery=delivery.to_public(True), pin=pin, sms_sent=sms_pin(delivery, pin)), 201

    @app.post("/api/deliveries/<delivery_id>/requeue")
    @needs_role("clinic")
    def requeue(delivery_id):
        delivery, pin = manager.requeue(delivery_id, g.user.username)
        return jsonify(delivery=delivery.to_public(True), pin=pin, sms_sent=sms_pin(delivery, pin))

    @app.post("/api/deliveries/<delivery_id>/reissue-pin")
    @needs_role("clinic")
    def reissue(delivery_id):
        pin = manager.reissue_pin(delivery_id)
        delivery = manager.get_delivery(delivery_id)
        return jsonify(delivery=delivery.to_public(True), pin=pin, sms_sent=sms_pin(delivery, pin))

    # ---- messenger --------------------------------------------------------
    @app.post("/api/deliveries/<delivery_id>/collect")
    @needs_role("messenger")
    def collect(delivery_id):
        return jsonify(manager.collect(delivery_id, g.user).to_public(False))

    @app.post("/api/deliveries/<delivery_id>/confirm")
    @needs_role("messenger")
    def confirm(delivery_id):
        delivery = manager.confirm_delivery(delivery_id, body().get("pin", ""), g.user)
        patient = manager.get_patient(delivery.patient_id)
        tell_patient(patient, f"Your medicine was delivered by {g.user.full_name}. Thank you!",
                     "Your medicine was delivered")
        return jsonify(delivery.to_public(False))

    @app.post("/api/deliveries/<delivery_id>/return")
    @needs_role("messenger")
    def give_back(delivery_id):
        delivery = manager.mark_returned(delivery_id, g.user)
        patient = manager.get_patient(delivery.patient_id)
        tell(manager.active_clinic_staff(), "Parcel returned",
             f"{g.user.full_name} returned parcel {delivery.delivery_id} for {patient.name}. "
             f"Open the app to queue it again.")
        return jsonify(delivery.to_public(False))

    app.manager = manager
    return app


app = create_app() if os.environ.get("DOORSTEP_NO_AUTOSTART") != "1" else None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port)
