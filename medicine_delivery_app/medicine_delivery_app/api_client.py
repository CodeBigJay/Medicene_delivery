"""Talks to the Doorstep Meds backend over HTTP (Unit 4: requests / REST).

RemoteManager offers the same kind of methods the screens used before
(add_patient, collect, ...), but each one calls the server. Business rules
and the database live on the server; this class only sends and receives JSON.
"""
import requests

from models import ClinicStaff, Delivery, Messenger, Patient

TIMEOUT = 10


class ApiError(ValueError):
    """Anything that went wrong talking to the server, with a message safe to show."""


class SessionExpired(ApiError):
    pass


def user_from_public(data):
    common = dict(email=data.get("email", ""), phone=data.get("phone", ""),
                  status=data.get("status", "active"))
    if data["role"] == "messenger":
        return Messenger(data["username"], data["full_name"], "", data.get("village", ""), **common)
    return ClinicStaff(data["username"], data["full_name"], "", **common)


class RemoteManager:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")
        self.http = requests.Session()
        self.token = None
        self.me = None
        self.patients = []
        self.deliveries = []
        self.messengers = []      # clinic only: [{username, full_name, village}]
        self.known_villages = []  # clinic only
        self.delivered_count = 0  # messenger only
        self.pending = []         # clinic only: registrations waiting for approval
        self.unread = 0           # unread in-app messages

    # ---- low level -----------------------------------------------------
    def _call(self, method, path, payload=None):
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = self.http.request(method, self.base_url + path, json=payload,
                                         headers=headers, timeout=TIMEOUT)
        except requests.exceptions.RequestException:
            raise ApiError("Cannot reach the server. Check your internet and try again.")
        try:
            data = response.json()
        except ValueError:
            data = {}
        if response.status_code == 401 and self.token:
            self.token = None
            self.me = None
            raise SessionExpired(data.get("detail", "Please sign in again."))
        if response.status_code >= 400:
            raise ApiError(data.get("detail", f"Server error ({response.status_code})."))
        return data

    # ---- registration (no sign-in needed) ------------------------------
    def register(self, role, username, full_name, pin, village="", email="", phone="", invite_code=""):
        """Returns 'pending' (messenger, waits for the clinic) or 'active' (clinic staff)."""
        data = self._call("POST", "/api/register", {
            "role": role, "username": username, "full_name": full_name, "pin": pin,
            "village": village, "email": email, "phone": phone, "invite_code": invite_code})
        return data["status"]

    # ---- session -------------------------------------------------------
    def login(self, username, pin):
        data = self._call("POST", "/api/login", {"username": username, "pin": pin})
        self.token = data["token"]
        self.me = user_from_public(data["user"])
        return self.me

    def logout(self):
        try:
            if self.token:
                self._call("POST", "/api/logout")
        except ApiError:
            pass
        self.token = None
        self.me = None

    def sync(self):
        """Download the latest data this user is allowed to see."""
        data = self._call("GET", "/api/snapshot")
        self.me = user_from_public(data["me"])
        self.patients = [Patient.from_dict(p) for p in data["patients"]]
        self.deliveries = [Delivery.from_dict(d) for d in data["deliveries"]]
        self.messengers = data.get("messengers", [])
        self.known_villages = data.get("villages", [])
        self.delivered_count = data.get("delivered_count", 0)
        self.pending = data.get("pending", [])
        self.unread = data.get("unread", 0)

    # ---- lookups (from the last sync) ----------------------------------
    def get_patient(self, patient_id):
        return next((p for p in self.patients if p.patient_id == patient_id), None)

    def villages(self):
        return self.known_villages

    def has_active_delivery(self, patient_id):
        return any(d.patient_id == patient_id and d.is_active() for d in self.deliveries)

    def counts(self):
        statuses = ["Ready", "Collected", "Delivered", "Returned"]
        return {s: sum(1 for d in self.deliveries if d.status == s) for s in statuses}

    # ---- clinic actions ------------------------------------------------
    def add_patient(self, name, village, address, contact, email=""):
        data = self._call("POST", "/api/patients", {
            "name": name, "village": village, "address": address, "contact": contact, "email": email})
        return Patient.from_dict(data)

    def add_messenger(self, username, full_name, pin, village, email="", phone=""):
        return self._call("POST", "/api/messengers", {
            "username": username, "full_name": full_name, "pin": pin, "village": village,
            "email": email, "phone": phone})

    def create_invite(self):
        return self._call("POST", "/api/invites")["code"]

    def approve(self, username):
        self._call("POST", f"/api/users/{username}/approve")

    def reject(self, username):
        self._call("POST", f"/api/users/{username}/reject")

    def reset_pin(self, username):
        return self._call("POST", f"/api/users/{username}/reset-pin")["pin"]

    def message_patient(self, patient_id, text, channel):
        return self._call("POST", f"/api/patients/{patient_id}/message",
                          {"text": text, "channel": channel})

    def create_delivery(self, patient_id, parcel_note):
        """Returns (pin, sms_sent). The PIN is only ever shown once."""
        data = self._call("POST", "/api/deliveries",
                          {"patient_id": patient_id, "parcel_note": parcel_note})
        return data["pin"], data["sms_sent"]

    def requeue(self, delivery_id):
        data = self._call("POST", f"/api/deliveries/{delivery_id}/requeue")
        return data["pin"], data["sms_sent"]

    def reissue_pin(self, delivery_id):
        data = self._call("POST", f"/api/deliveries/{delivery_id}/reissue-pin")
        return data["pin"], data["sms_sent"]

    # ---- messenger actions ---------------------------------------------
    def collect(self, delivery_id):
        self._call("POST", f"/api/deliveries/{delivery_id}/collect")

    def confirm_delivery(self, delivery_id, pin):
        self._call("POST", f"/api/deliveries/{delivery_id}/confirm", {"pin": pin})

    def mark_returned(self, delivery_id):
        self._call("POST", f"/api/deliveries/{delivery_id}/return")

    # ---- profile -------------------------------------------------------
    def change_pin(self, old_pin, new_pin):
        self._call("POST", "/api/me/pin", {"old_pin": old_pin, "new_pin": new_pin})

    def update_contact(self, email, phone):
        data = self._call("PUT", "/api/me/contact", {"email": email, "phone": phone})
        self.me = user_from_public(data)

    # ---- messages ------------------------------------------------------
    def load_messages(self):
        """Newest first. Opening the inbox marks everything as read."""
        data = self._call("GET", "/api/messages")
        self._call("POST", "/api/messages/read")
        self.unread = 0
        return list(reversed(data["messages"]))

    def send_message(self, to, text, by_email=False, by_sms=False):
        return self._call("POST", "/api/messages",
                          {"to": to, "text": text, "email": by_email, "sms": by_sms})
