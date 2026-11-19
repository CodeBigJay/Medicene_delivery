"""Data models and business rules for Doorstep Meds (no UI code here).

The user classes share common account fields and behaviour. ClinicStaff and
Messenger specialise the User class, while DeliveryManager coordinates the
application records and business rules.
"""
import hashlib
import hmac
import re
import secrets
from datetime import datetime

# Delivery statuses
READY = "Ready"
COLLECTED = "Collected"
DELIVERED = "Delivered"
RETURNED = "Returned"
ALL_STATUSES = [READY, COLLECTED, DELIVERED, RETURNED]
ACTIVE_STATUSES = [READY, COLLECTED]

# Account statuses
ACTIVE = "active"
PENDING = "pending"
REJECTED = "rejected"

MAX_PIN_ATTEMPTS = 5
MAX_MESSAGE_LENGTH = 500

# Message recipients (besides a username)
TO_CLINIC = "@clinic"
TO_ALL_MESSENGERS = "@messengers"
TO_VILLAGE_PREFIX = "@village:"


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def hash_pin(username, pin):
    """Slow, salted hash for login PINs (the username is the salt)."""
    raw = hashlib.pbkdf2_hmac("sha256", str(pin).encode(), f"doorstep:{username}".encode(), 50_000)
    return raw.hex()


def hash_delivery_pin(delivery_id, pin):
    """Hash for the one-off 4-digit handover PIN. Wrong tries are limited instead."""
    return hashlib.sha256(f"{delivery_id}:{pin}".encode()).hexdigest()


def new_pin():
    return f"{secrets.randbelow(10000):04d}"


def new_temp_pin():
    return f"{secrets.randbelow(1000000):06d}"


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def same_text(a, b):
    """Compare two strings ignoring case and surrounding spaces."""
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def is_valid_contact(text):
    """A South African cell number written as 10 digits, e.g. 0821234567."""
    digits = (text or "").replace(" ", "")
    return digits.isdigit() and len(digits) == 10


def is_valid_email(text):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", text or ""))


def clean_optional_contact(phone, email):
    """Validate optional phone/email. Returns cleaned (phone, email)."""
    phone = (phone or "").replace(" ", "").strip()
    email = (email or "").strip().lower()
    if phone and not is_valid_contact(phone):
        raise ValueError("Phone number must be 10 digits, e.g. 0821234567.")
    if email and not is_valid_email(email):
        raise ValueError("That email address does not look right.")
    return phone, email


def check_new_pin(pin):
    pin = str(pin or "").strip()
    if len(pin) < 4 or not pin.isdigit():
        raise ValueError("PIN must be at least 4 digits.")
    return pin


def check_username(username):
    username = (username or "").strip().lower()
    if not username:
        raise ValueError("Please fill in every field.")
    if not username.isalnum():
        raise ValueError("Username can only use letters and numbers.")
    return username


# ----------------------------------------------------------------------
# Users (inheritance)
# ----------------------------------------------------------------------
class User:
    role = "user"

    def __init__(self, username, full_name, pin_hash, email="", phone="",
                 status=ACTIVE, last_read=0):
        self.username = username
        self.full_name = full_name
        self.pin_hash = pin_hash
        self.email = email
        self.phone = phone
        self.status = status
        self.last_read = last_read   # highest message id this user has seen

    def check_pin(self, pin):
        return hmac.compare_digest(hash_pin(self.username, str(pin).strip()), self.pin_hash)

    def set_pin(self, pin):
        self.pin_hash = hash_pin(self.username, str(pin).strip())

    def home_route(self):
        return "/login"

    def to_public(self):
        """Safe to send to the app: no PIN hash."""
        return {"role": self.role, "username": self.username, "full_name": self.full_name,
                "email": self.email, "phone": self.phone, "status": self.status}

    def to_dict(self):
        return {**self.to_public(), "pin_hash": self.pin_hash, "last_read": self.last_read}


class ClinicStaff(User):
    role = "clinic"

    def home_route(self):
        return "/clinic"


class Messenger(User):
    role = "messenger"

    def __init__(self, username, full_name, pin_hash, village, email="", phone="",
                 status=ACTIVE, last_read=0):
        super().__init__(username, full_name, pin_hash, email, phone, status, last_read)
        self.village = village

    def covers(self, village):
        return same_text(self.village, village)

    def home_route(self):
        return "/messenger"

    def to_public(self):
        data = super().to_public()
        data["village"] = self.village
        return data


def user_from_dict(data):
    common = dict(email=data.get("email") or "", phone=data.get("phone") or "",
                  status=data.get("status") or ACTIVE, last_read=data.get("last_read") or 0)
    if data["role"] == "clinic":
        return ClinicStaff(data["username"], data["full_name"], data["pin_hash"], **common)
    if data["role"] == "messenger":
        return Messenger(data["username"], data["full_name"], data["pin_hash"],
                         data["village"], **common)
    raise ValueError(f"Unknown role: {data['role']}")


# ----------------------------------------------------------------------
# Patients and deliveries
# ----------------------------------------------------------------------
class Patient:
    def __init__(self, patient_id, name, village, address, contact, email=""):
        self.patient_id = patient_id
        self.name = name
        self.village = village
        self.address = address
        self.contact = contact  # patient or caregiver cell number
        self.email = email      # optional

    def to_dict(self):
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "village": self.village,
            "address": self.address,
            "contact": self.contact,
            "email": self.email,
        }

    @staticmethod
    def from_dict(data):
        return Patient(data["patient_id"], data["name"], data["village"], data["address"],
                       data["contact"], data.get("email") or "")


class Delivery:
    def __init__(self, delivery_id, patient_id, parcel_note="", pin_hash=None,
                 status=READY, messenger=None, history=None, failed_attempts=0):
        self.delivery_id = delivery_id
        self.patient_id = patient_id
        self.parcel_note = parcel_note  # clinic-only label, never shown to messengers
        self.pin_hash = pin_hash        # the PIN itself is never stored
        self.status = status
        self.messenger = messenger      # username of the messenger who collected it
        self.history = history if history is not None else []
        self.failed_attempts = failed_attempts

    @property
    def locked(self):
        return self.failed_attempts >= MAX_PIN_ATTEMPTS

    def set_pin(self, pin):
        self.pin_hash = hash_delivery_pin(self.delivery_id, pin)
        self.failed_attempts = 0

    def check_pin(self, pin):
        return hmac.compare_digest(hash_delivery_pin(self.delivery_id, str(pin).strip()),
                                   self.pin_hash or "")

    def log(self, status, by):
        self.status = status
        self.history.append({"time": now_text(), "status": status, "by": by})

    def is_active(self):
        return self.status in ACTIVE_STATUSES

    def to_dict(self):
        """Full record, for the database."""
        return {
            "delivery_id": self.delivery_id,
            "patient_id": self.patient_id,
            "parcel_note": self.parcel_note,
            "pin_hash": self.pin_hash,
            "status": self.status,
            "messenger": self.messenger,
            "history": self.history,
            "failed_attempts": self.failed_attempts,
        }

    def to_public(self, include_note):
        """What the API may send out: never the PIN hash; the label only to the clinic."""
        data = {
            "delivery_id": self.delivery_id,
            "patient_id": self.patient_id,
            "status": self.status,
            "messenger": self.messenger,
            "history": self.history,
            "locked": self.locked,
        }
        if include_note:
            data["parcel_note"] = self.parcel_note
        return data

    @staticmethod
    def from_dict(data):
        return Delivery(
            data["delivery_id"], data["patient_id"], data.get("parcel_note", ""),
            data.get("pin_hash"), data["status"], data.get("messenger"),
            data.get("history", []), data.get("failed_attempts", 0) or 0,
        )


# ----------------------------------------------------------------------
# Messages and invites
# ----------------------------------------------------------------------
class Message:
    def __init__(self, message_id, sender, to, text, time, delivery_id=None):
        self.message_id = message_id
        self.sender = sender
        self.to = to                  # username, "@clinic", "@messengers" or "@village:<name>"
        self.text = text
        self.time = time
        self.delivery_id = delivery_id

    def to_dict(self):
        return {"message_id": self.message_id, "sender": self.sender, "to": self.to,
                "text": self.text, "time": self.time, "delivery_id": self.delivery_id}

    @staticmethod
    def from_dict(data):
        return Message(data["message_id"], data["sender"], data["to"], data["text"],
                       data["time"], data.get("delivery_id"))


class Invite:
    """A one-use code a clinic staff member gives to a new colleague so they can register."""

    def __init__(self, code, created_by, used_by=None):
        self.code = code
        self.created_by = created_by
        self.used_by = used_by

    def to_dict(self):
        return {"code": self.code, "created_by": self.created_by, "used_by": self.used_by}

    @staticmethod
    def from_dict(data):
        return Invite(data["code"], data["created_by"], data.get("used_by"))


# ----------------------------------------------------------------------
# Manager (composition): owns all the data and the rules
# ----------------------------------------------------------------------
class DeliveryManager:
    def __init__(self, store, demo=True, admin_pin=None):
        self.store = store
        self.demo = demo            # False in production: no demo accounts or patients
        self.admin_pin = admin_pin
        self.users = []
        self.patients = []
        self.deliveries = []
        self.messages = []
        self.invites = []
        self.load()

    # ---- persistence -------------------------------------------------
    def load(self):
        data = self.store.load()
        if data is not None:
            try:
                self.users = [user_from_dict(d) for d in data["users"]]
                self.patients = [Patient.from_dict(d) for d in data["patients"]]
                self.deliveries = [Delivery.from_dict(d) for d in data["deliveries"]]
                self.messages = [Message.from_dict(d) for d in data.get("messages", [])]
                self.invites = [Invite.from_dict(d) for d in data.get("invites", [])]
                return
            except (KeyError, TypeError, ValueError) as err:
                print(f"Saved data could not be read ({err}). Starting with fresh data.")
        self._seed()
        self.save()

    def save(self):
        return self.store.save({
            "users": [u.to_dict() for u in self.users],
            "patients": [p.to_dict() for p in self.patients],
            "deliveries": [d.to_dict() for d in self.deliveries],
            "messages": [m.to_dict() for m in self.messages],
            "invites": [i.to_dict() for i in self.invites],
        })

    def _seed(self):
        """First-run data. Demo mode adds sample people; production adds one admin only."""
        self.messages, self.invites = [], []
        if not self.demo:
            if not self.admin_pin or len(self.admin_pin) < 6:
                raise RuntimeError("Set DOORSTEP_ADMIN_PIN (6+ characters) for the first start.")
            self.users = [ClinicStaff("admin", "Clinic Admin", hash_pin("admin", self.admin_pin))]
            self.patients, self.deliveries = [], []
            return
        self.users = [
            ClinicStaff("clinic1", "Nurse Naledi", hash_pin("clinic1", "1234")),
            Messenger("thabo", "Thabo", hash_pin("thabo", "1111"), "Lekubu"),
            Messenger("lerato", "Lerato", hash_pin("lerato", "2222"), "Dinokana"),
            # Add a pending messenger for the approval workflow demonstration.
            Messenger("nomsa", "Nomsa Dlamini", hash_pin("nomsa", "3333"), "Lekubu",
                      status=PENDING),
        ]
        self.patients = [
            Patient("P001", "Dineo Molefe", "Lekubu", "12 Church Street", "0821234567"),
            Patient("P002", "Kagiso Mokoena", "Dinokana", "45 Main Road", "0839876543"),
            Patient("P003", "Sarah Tau", "Lekubu", "7 School Lane", "0845551234"),
        ]
        self.deliveries = []
        demo, _ = self.create_delivery("P001", "Monthly repeat, 1 bag", "clinic1", save=False)
        demo.set_pin("1234")  # fixed PIN so the demo is easy to follow

    # ---- lookups -----------------------------------------------------
    def get_user(self, username):
        for user in self.users:
            if user.username == username:
                return user
        return None

    def get_patient(self, patient_id):
        for patient in self.patients:
            if patient.patient_id == patient_id:
                return patient
        return None

    def get_delivery(self, delivery_id):
        for delivery in self.deliveries:
            if delivery.delivery_id == delivery_id:
                return delivery
        return None

    def authenticate(self, username, pin):
        """Return the user, None for a wrong username/PIN, or raise if the account is not active."""
        user = self.get_user((username or "").strip().lower())
        if user is None or not user.check_pin(pin):
            return None
        if user.status == PENDING:
            raise ValueError("Your registration is waiting for clinic approval.")
        if user.status == REJECTED:
            raise ValueError("Your registration was declined. Please contact the clinic.")
        return user

    def active_clinic_staff(self):
        return [u for u in self.users if isinstance(u, ClinicStaff) and u.status == ACTIVE]

    def active_messengers(self):
        return [u for u in self.users if isinstance(u, Messenger) and u.status == ACTIVE]

    def pending_users(self):
        return [u for u in self.users if u.status == PENDING]

    def find_messenger(self, village):
        for user in self.active_messengers():
            if user.covers(village):
                return user
        return None

    def messengers_for_village(self, village):
        return [m for m in self.active_messengers() if m.covers(village)]

    def villages(self):
        return sorted({u.village for u in self.active_messengers()})

    def has_active_delivery(self, patient_id):
        return any(d.patient_id == patient_id and d.is_active() for d in self.deliveries)

    def counts(self):
        return {s: sum(1 for d in self.deliveries if d.status == s) for s in ALL_STATUSES}

    # ---- registration and accounts -----------------------------------
    def register_messenger(self, username, full_name, pin, village, email="", phone=""):
        """A messenger applies for an account. It stays 'pending' until the clinic approves."""
        user = self._new_user(Messenger, username, full_name, pin, email, phone,
                              village=(village or "").strip(), status=PENDING)
        if not user.village:
            raise ValueError("Please fill in every field.")
        self.users.append(user)
        self.save()
        return user

    def register_staff(self, invite_code, username, full_name, pin, email="", phone=""):
        """Clinic staff join with a one-use invite code from a colleague."""
        code = (invite_code or "").strip().upper()
        invite = next((i for i in self.invites if i.code == code and i.used_by is None), None)
        if invite is None:
            raise ValueError("That invite code is not valid or was already used.")
        user = self._new_user(ClinicStaff, username, full_name, pin, email, phone, status=ACTIVE)
        invite.used_by = user.username
        self.users.append(user)
        self.save()
        return user

    def _new_user(self, cls, username, full_name, pin, email, phone, status, **extra):
        username = check_username(username)
        full_name = (full_name or "").strip()
        if not full_name:
            raise ValueError("Please fill in every field.")
        pin = check_new_pin(pin)
        phone, email = clean_optional_contact(phone, email)
        if self.get_user(username) is not None:
            raise ValueError("That username is already taken.")
        return cls(username, full_name, hash_pin(username, pin),
                   **extra, email=email, phone=phone, status=status,
                   last_read=max((m.message_id for m in self.messages), default=0))

    def add_messenger(self, username, full_name, pin, village, email="", phone=""):
        """Clinic creates a messenger directly (already approved)."""
        user = self._new_user(Messenger, username, full_name, pin, email, phone,
                              village=(village or "").strip(), status=ACTIVE)
        if not user.village:
            raise ValueError("Please fill in every field.")
        self.users.append(user)
        self.save()
        return user

    def create_invite(self, by):
        invite = Invite(secrets.token_hex(3).upper(), by)
        self.invites.append(invite)
        self.save()
        return invite.code

    def approve_user(self, username):
        return self._decide(username, ACTIVE)

    def reject_user(self, username):
        return self._decide(username, REJECTED)

    def _decide(self, username, status):
        user = self.get_user(username)
        if user is None or user.status != PENDING:
            raise ValueError("No waiting registration for that user.")
        user.status = status
        self.save()
        return user

    def reset_pin(self, username):
        """Clinic gives a messenger a temporary PIN (e.g. forgotten PIN). Returns the new PIN."""
        user = self.get_user(username)
        if user is None or not isinstance(user, Messenger):
            raise ValueError("Messenger not found.")
        pin = new_temp_pin()
        user.set_pin(pin)
        self.save()
        return pin

    def change_pin(self, user, old_pin, new_pin_text):
        if not user.check_pin(old_pin):
            raise ValueError("Your current PIN is wrong.")
        user.set_pin(check_new_pin(new_pin_text))
        self.save()

    def update_contact(self, user, email, phone):
        user.phone, user.email = clean_optional_contact(phone, email)
        self.save()
        return user

    # ---- clinic actions ----------------------------------------------
    def add_patient(self, name, village, address, contact, email=""):
        name, village = (name or "").strip(), (village or "").strip()
        address, contact = (address or "").strip(), (contact or "").strip()
        email = (email or "").strip().lower()
        if not (name and village and address and contact):
            raise ValueError("Please fill in every field.")
        if not is_valid_contact(contact):
            raise ValueError("Contact number must be 10 digits, e.g. 0821234567.")
        if email and not is_valid_email(email):
            raise ValueError("That email address does not look right.")
        patient = Patient(self._next_id("P", self.patients, "patient_id"),
                          name, village, address, contact.replace(" ", ""), email)
        self.patients.append(patient)
        self.save()
        return patient

    def create_delivery(self, patient_id, parcel_note, by, save=True):
        patient = self.get_patient(patient_id)
        if patient is None:
            raise ValueError("Patient not found.")
        note = (parcel_note or "").strip()
        if not note:
            raise ValueError("Enter a parcel label.")
        if self.has_active_delivery(patient_id):
            raise ValueError("This patient already has a delivery in progress.")
        if self.find_messenger(patient.village) is None:
            raise ValueError(f"No messenger covers {patient.village} yet.")
        delivery = Delivery(self._next_id("D", self.deliveries, "delivery_id"), patient_id, note)
        pin = new_pin()
        delivery.set_pin(pin)
        delivery.log(READY, by)
        self.deliveries.append(delivery)
        if save:
            self.save()
        return delivery, pin

    def reissue_pin(self, delivery_id):
        """Give an active delivery a fresh PIN (e.g. the old SMS was lost). Returns the new PIN."""
        delivery = self.get_delivery(delivery_id)
        if delivery is None or not delivery.is_active():
            raise ValueError("Only deliveries in progress can get a new PIN.")
        pin = new_pin()
        delivery.set_pin(pin)
        self.save()
        return pin

    def requeue(self, delivery_id, by):
        """Put a returned parcel back in the queue. Returns (delivery, new PIN)."""
        delivery = self.get_delivery(delivery_id)
        if delivery is None or delivery.status != RETURNED:
            raise ValueError("Only returned parcels can be queued again.")
        pin = new_pin()
        delivery.set_pin(pin)
        delivery.messenger = None
        delivery.log(READY, by)
        self.save()
        return delivery, pin

    # ---- messenger actions -------------------------------------------
    def active_for_messenger(self, messenger):
        """Active deliveries for patients in the messenger's village."""
        found = []
        for delivery in self.deliveries:
            patient = self.get_patient(delivery.patient_id)
            if delivery.is_active() and patient and messenger.covers(patient.village):
                found.append(delivery)
        return found

    def _delivery_for(self, messenger, delivery_id):
        for delivery in self.active_for_messenger(messenger):
            if delivery.delivery_id == delivery_id:
                return delivery
        raise ValueError("That parcel is not available to you.")

    def collect(self, delivery_id, messenger):
        delivery = self._delivery_for(messenger, delivery_id)
        if delivery.status != READY:
            raise ValueError("This parcel was already collected.")
        delivery.messenger = messenger.username
        delivery.log(COLLECTED, messenger.username)
        self.save()
        return delivery

    def confirm_delivery(self, delivery_id, pin, messenger):
        delivery = self._delivery_for(messenger, delivery_id)
        if delivery.status != COLLECTED:
            raise ValueError("Collect the parcel from the clinic first.")
        if delivery.locked:
            raise ValueError("Too many wrong PINs. Ask the clinic to send a new PIN.")
        if not delivery.check_pin(pin):
            delivery.failed_attempts += 1
            self.save()
            left = MAX_PIN_ATTEMPTS - delivery.failed_attempts
            if left <= 0:
                raise ValueError("Too many wrong PINs. Ask the clinic to send a new PIN.")
            raise ValueError(f"Wrong PIN. {left} tries left.")
        delivery.log(DELIVERED, messenger.username)
        self.save()
        return delivery

    def mark_returned(self, delivery_id, messenger):
        delivery = self._delivery_for(messenger, delivery_id)
        if delivery.status != COLLECTED:
            raise ValueError("Only a collected parcel can be returned.")
        delivery.log(RETURNED, messenger.username)
        self.save()
        return delivery

    # ---- messages ----------------------------------------------------
    def recipients_of(self, to):
        """The active users a recipient address points to."""
        if to == TO_CLINIC:
            return self.active_clinic_staff()
        if to == TO_ALL_MESSENGERS:
            return self.active_messengers()
        if to.startswith(TO_VILLAGE_PREFIX):
            return self.messengers_for_village(to[len(TO_VILLAGE_PREFIX):])
        user = self.get_user(to)
        return [user] if user is not None and user.status == ACTIVE else []

    def send_message(self, sender, to, text, delivery_id=None):
        text = (text or "").strip()
        if not text:
            raise ValueError("Write a message first.")
        if len(text) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"Messages can be at most {MAX_MESSAGE_LENGTH} characters.")
        to = (to or "").strip()
        if isinstance(sender, Messenger):
            if to != TO_CLINIC:
                raise ValueError("Messengers can only write to the clinic.")
        elif to != TO_CLINIC:
            target = self.get_user(to)
            if not (to == TO_ALL_MESSENGERS or to.startswith(TO_VILLAGE_PREFIX)
                    or isinstance(target, Messenger)):
                raise ValueError("Pick a messenger, a village or all messengers.")
        if not self.recipients_of(to):
            raise ValueError("There is nobody to receive that message.")
        message = Message(max((m.message_id for m in self.messages), default=0) + 1,
                          sender.username, to, text, now_text(), delivery_id)
        self.messages.append(message)
        self.save()
        return message

    def can_see(self, user, message):
        if message.sender == user.username or message.to == user.username:
            return True
        if message.to == TO_CLINIC:
            return isinstance(user, ClinicStaff)
        if message.to == TO_ALL_MESSENGERS:
            return isinstance(user, Messenger) and user.status == ACTIVE
        if message.to.startswith(TO_VILLAGE_PREFIX):
            return isinstance(user, Messenger) and user.covers(message.to[len(TO_VILLAGE_PREFIX):])
        return False

    def messages_for(self, user):
        return [m for m in self.messages if self.can_see(user, m)]

    def unread_count(self, user):
        return sum(1 for m in self.messages_for(user)
                   if m.message_id > user.last_read and m.sender != user.username)

    def mark_read(self, user):
        latest = max((m.message_id for m in self.messages_for(user)), default=0)
        if latest > user.last_read:
            user.last_read = latest
            self.save()

    # ---- internal ----------------------------------------------------
    @staticmethod
    def _next_id(prefix, items, attribute):
        highest = 0
        for item in items:
            number = getattr(item, attribute)[len(prefix):]
            if number.isdigit():
                highest = max(highest, int(number))
        return f"{prefix}{highest + 1:03d}"
