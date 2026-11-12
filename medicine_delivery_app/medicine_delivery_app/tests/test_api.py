"""API tests: real HTTP requests handled by Flask's test client."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DOORSTEP_NO_AUTOSTART"] = "1"

from backend.app import create_app
from storage import SqliteStore


class FakeNotifier:
    def __init__(self):
        self.sent = []      # SMS: (phone, text)
        self.emails = []    # (to, subject, text)

    def sms(self, phone, text):
        self.sent.append((phone, text))
        return True

    def email(self, to, subject, text):
        self.emails.append((to, subject, text))
        return True


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.sms = FakeNotifier()
        self.app = create_app(SqliteStore(os.path.join(self.dir.name, "t.db")), self.sms, sync_notify=True)
        self.c = self.app.test_client()

    def tearDown(self):
        self.dir.cleanup()

    def login(self, user, pin):
        r = self.c.post("/api/login", json={"username": user, "pin": pin})
        self.assertEqual(r.status_code, 200, r.get_json())
        return {"Authorization": "Bearer " + r.get_json()["token"]}

    def test_health_and_auth_required(self):
        self.assertEqual(self.c.get("/api/health").status_code, 200)
        self.assertEqual(self.c.get("/api/snapshot").status_code, 401)
        self.assertEqual(self.c.get("/api/snapshot", headers={"Authorization": "Bearer nope"}).status_code, 401)

    def test_wrong_login_and_lockout(self):
        for _ in range(5):
            self.assertEqual(self.c.post("/api/login", json={"username": "thabo", "pin": "9"}).status_code, 401)
        r = self.c.post("/api/login", json={"username": "thabo", "pin": "1111"})
        self.assertEqual(r.status_code, 429)

    def test_roles_are_enforced(self):
        messenger = self.login("thabo", "1111")
        self.assertEqual(self.c.post("/api/patients", headers=messenger, json={}).status_code, 403)
        clinic = self.login("clinic1", "1234")
        self.assertEqual(self.c.post("/api/deliveries/D001/collect", headers=clinic).status_code, 403)

    def test_full_flow_over_http(self):
        clinic = self.login("clinic1", "1234")
        r = self.c.post("/api/deliveries", headers=clinic, json={"patient_id": "P003", "parcel_note": "Bag 2"})
        self.assertEqual(r.status_code, 201)
        pin = r.get_json()["pin"]
        did = r.get_json()["delivery"]["delivery_id"]
        self.assertEqual(self.sms.sent[-1][0], "0845551234")   # SMS went to the patient
        self.assertIn(pin, self.sms.sent[-1][1])

        thabo = self.login("thabo", "1111")
        snap = self.c.get("/api/snapshot", headers=thabo).get_json()
        self.assertEqual(len(snap["deliveries"]), 2)
        for d in snap["deliveries"]:                      # messengers never see the label or PIN
            self.assertNotIn("parcel_note", d)
            self.assertNotIn("pin_hash", d)
        self.assertEqual(self.c.post(f"/api/deliveries/{did}/collect", headers=thabo).status_code, 200)
        bad = self.c.post(f"/api/deliveries/{did}/confirm", headers=thabo, json={"pin": "x"})
        self.assertEqual(bad.status_code, 400)
        ok = self.c.post(f"/api/deliveries/{did}/confirm", headers=thabo, json={"pin": pin})
        self.assertEqual(ok.get_json()["status"], "Delivered")
        self.assertEqual(self.c.get("/api/snapshot", headers=thabo).get_json()["delivered_count"], 1)

    def test_other_village_messenger_cannot_touch_parcel(self):
        lerato = self.login("lerato", "2222")   # covers Dinokana, P001 is Lekubu
        self.assertEqual(self.c.post("/api/deliveries/D001/collect", headers=lerato).status_code, 400)
        self.assertEqual(self.c.get("/api/snapshot", headers=lerato).get_json()["deliveries"], [])

    def test_clinic_snapshot_has_no_pin_hash_and_logout_works(self):
        clinic = self.login("clinic1", "1234")
        snap = self.c.get("/api/snapshot", headers=clinic).get_json()
        self.assertNotIn("pin_hash", str(snap))
        self.assertEqual(len(snap["messengers"]), 2)       # pending Nomsa is not listed as active
        self.assertEqual(len(snap["pending"]), 1)
        self.c.post("/api/logout", headers=clinic)
        self.assertEqual(self.c.get("/api/snapshot", headers=clinic).status_code, 401)

    def test_data_survives_restart(self):
        clinic = self.login("clinic1", "1234")
        self.c.post("/api/patients", headers=clinic, json={
            "name": "New P", "village": "Lekubu", "address": "1 St", "contact": "0821112222"})
        app2 = create_app(SqliteStore(os.path.join(self.dir.name, "t.db")), self.sms, sync_notify=True)
        self.assertEqual(len(app2.manager.patients), 4)

    # ---------------- registration ----------------
    def register(self, **kw):
        data = {"role": "messenger", "username": "sipho", "full_name": "Sipho K", "pin": "5555",
                "village": "Zeerust", "email": "sipho@example.com", "phone": "0831112222"}
        data.update(kw)
        return self.c.post("/api/register", json=data)

    def test_messenger_registration_needs_approval(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["status"], "pending")
        blocked = self.c.post("/api/login", json={"username": "sipho", "pin": "5555"})
        self.assertEqual(blocked.status_code, 403)
        self.assertIn("approval", blocked.get_json()["detail"])
        self.assertIn("sipho@example.com", [e[0] for e in self.sms.emails])   # "we got your registration"
        clinic = self.login("clinic1", "1234")
        pending = self.c.get("/api/snapshot", headers=clinic).get_json()["pending"]
        self.assertIn("sipho", [p["username"] for p in pending])
        self.assertEqual(self.c.post("/api/users/sipho/approve", headers=clinic).status_code, 200)
        self.assertEqual(self.sms.emails[-1][0], "sipho@example.com")   # approval email
        self.login("sipho", "5555")

    def test_rejected_registration_cannot_sign_in(self):
        self.register(username="rej")
        clinic = self.login("clinic1", "1234")
        self.c.post("/api/users/rej/reject", headers=clinic)
        r = self.c.post("/api/login", json={"username": "rej", "pin": "5555"})
        self.assertEqual(r.status_code, 403)
        self.assertIn("declined", r.get_json()["detail"])

    def test_registration_validation(self):
        self.assertEqual(self.register(username="thabo").status_code, 400)       # taken
        self.assertEqual(self.register(pin="12").status_code, 400)
        self.assertEqual(self.register(email="nope").status_code, 400)
        self.assertEqual(self.register(phone="123").status_code, 400)
        self.assertEqual(self.register(role="admin").status_code, 400)

    def test_staff_registration_needs_invite(self):
        self.assertEqual(self.register(role="clinic", invite_code="BAD").status_code, 400)
        clinic = self.login("clinic1", "1234")
        code = self.c.post("/api/invites", headers=clinic).get_json()["code"]
        ok = self.register(role="clinic", username="nurse2", invite_code=code)
        self.assertEqual(ok.get_json()["status"], "active")
        self.login("nurse2", "5555")
        again = self.register(role="clinic", username="nurse3", invite_code=code)  # code is one-use
        self.assertEqual(again.status_code, 400)

    def test_messenger_cannot_make_invites_or_approve(self):
        thabo = self.login("thabo", "1111")
        self.assertEqual(self.c.post("/api/invites", headers=thabo).status_code, 403)
        self.assertEqual(self.c.post("/api/users/nomsa/approve", headers=thabo).status_code, 403)

    def test_registration_rate_limit(self):
        codes = [self.register(username=f"u{i}").status_code for i in range(12)]
        self.assertEqual(codes[:10], [201] * 10)
        self.assertEqual(codes[10], 429)

    # ---------------- messages ----------------
    def test_messaging_both_ways(self):
        thabo, clinic = self.login("thabo", "1111"), self.login("clinic1", "1234")
        r = self.c.post("/api/messages", headers=thabo, json={"to": "@clinic", "text": "Road is flooded"})
        self.assertEqual(r.status_code, 201)
        snap = self.c.get("/api/snapshot", headers=clinic).get_json()
        self.assertEqual(snap["unread"], 1)
        msgs = self.c.get("/api/messages", headers=clinic).get_json()["messages"]
        self.assertEqual(msgs[0]["sender_name"], "Thabo")
        self.c.post("/api/messages/read", headers=clinic)
        self.assertEqual(self.c.get("/api/snapshot", headers=clinic).get_json()["unread"], 0)
        self.c.post("/api/messages", headers=clinic, json={"to": "thabo", "text": "Thanks, wait a day"})
        self.assertEqual(self.c.get("/api/snapshot", headers=thabo).get_json()["unread"], 1)

    def test_message_privacy_and_rules(self):
        thabo, lerato, clinic = (self.login("thabo", "1111"), self.login("lerato", "2222"),
                                 self.login("clinic1", "1234"))
        self.c.post("/api/messages", headers=clinic, json={"to": "thabo", "text": "private"})
        self.assertEqual(self.c.get("/api/messages", headers=lerato).get_json()["messages"], [])
        self.c.post("/api/messages", headers=clinic, json={"to": "@village:Lekubu", "text": "village note"})
        self.assertEqual(len(self.c.get("/api/messages", headers=thabo).get_json()["messages"]), 2)
        self.assertEqual(len(self.c.get("/api/messages", headers=lerato).get_json()["messages"]), 0)
        # messengers can only write to the clinic; empty and long messages refused
        self.assertEqual(self.c.post("/api/messages", headers=thabo, json={"to": "lerato", "text": "hi"}).status_code, 400)
        self.assertEqual(self.c.post("/api/messages", headers=thabo, json={"to": "@clinic", "text": " "}).status_code, 400)
        self.assertEqual(self.c.post("/api/messages", headers=thabo, json={"to": "@clinic", "text": "x" * 501}).status_code, 400)
        self.assertEqual(self.c.post("/api/messages", headers=clinic, json={"to": "@village:Nowhere", "text": "hi"}).status_code, 400)

    def test_message_can_also_email_and_sms(self):
        clinic, thabo = self.login("clinic1", "1234"), self.login("thabo", "1111")
        self.c.put("/api/me/contact", headers=thabo, json={"email": "thabo@example.com", "phone": "0821110000"})
        self.c.post("/api/messages", headers=clinic, json={
            "to": "thabo", "text": "Come in early", "email": True, "sms": True})
        self.assertEqual(self.sms.emails[-1][0], "thabo@example.com")
        self.assertEqual(self.sms.sent[-1][0], "0821110000")
        count = len(self.sms.emails)
        self.c.post("/api/messages", headers=clinic, json={"to": "thabo", "text": "In-app only"})
        self.assertEqual(len(self.sms.emails), count)

    def test_message_patient_by_sms_and_email(self):
        clinic = self.login("clinic1", "1234")
        r = self.c.post("/api/patients/P001/message", headers=clinic, json={"text": "Parcel tomorrow", "channel": "sms"})
        self.assertTrue(r.get_json()["sms_sent"])
        self.assertEqual(self.sms.sent[-1][0], "0821234567")
        no_mail = self.c.post("/api/patients/P001/message", headers=clinic, json={"text": "Hi", "channel": "email"})
        self.assertEqual(no_mail.status_code, 400)       # no email on file
        self.c.post("/api/patients", headers=clinic, json={
            "name": "Em P", "village": "Lekubu", "address": "1 St", "contact": "0821112222", "email": "em@example.com"})
        r = self.c.post("/api/patients/P004/message", headers=clinic, json={"text": "Hi", "channel": "both"})
        self.assertTrue(r.get_json()["email_sent"])
        self.assertEqual(self.sms.emails[-1][0], "em@example.com")

    # ---------------- notifications, pins, profile ----------------
    def test_events_notify_people(self):
        self.c.put("/api/me/contact", headers=self.login("thabo", "1111"), json={"email": "thabo@example.com", "phone": ""})
        clinic = self.login("clinic1", "1234")
        self.c.put("/api/me/contact", headers=clinic, json={"email": "nurse@example.com", "phone": ""})
        self.c.post("/api/deliveries", headers=clinic, json={"patient_id": "P003", "parcel_note": "Bag"})
        self.assertIn(("thabo@example.com", "New parcel ready"), [(e[0], e[1]) for e in self.sms.emails])
        thabo = self.login("thabo", "1111")
        self.c.post("/api/deliveries/D001/collect", headers=thabo)
        self.c.post("/api/deliveries/D001/return", headers=thabo)
        self.assertIn(("nurse@example.com", "Parcel returned"), [(e[0], e[1]) for e in self.sms.emails])
        self.c.post("/api/deliveries/D002/collect", headers=thabo)
        pin = self.c.post("/api/deliveries/D002/reissue-pin", headers=clinic).get_json()["pin"]
        self.c.post("/api/deliveries/D002/confirm", headers=thabo, json={"pin": pin})
        self.assertTrue(any("delivered" in text for _, text in self.sms.sent))   # patient SMS

    def test_change_pin_and_reset_pin(self):
        thabo = self.login("thabo", "1111")
        self.assertEqual(self.c.post("/api/me/pin", headers=thabo, json={"old_pin": "0", "new_pin": "2468"}).status_code, 400)
        self.assertEqual(self.c.post("/api/me/pin", headers=thabo, json={"old_pin": "1111", "new_pin": "12"}).status_code, 400)
        self.assertEqual(self.c.post("/api/me/pin", headers=thabo, json={"old_pin": "1111", "new_pin": "2468"}).status_code, 200)
        self.login("thabo", "2468")
        clinic = self.login("clinic1", "1234")
        temp = self.c.post("/api/users/thabo/reset-pin", headers=clinic).get_json()["pin"]
        self.login("thabo", temp)

    def test_contact_validation(self):
        thabo = self.login("thabo", "1111")
        bad = self.c.put("/api/me/contact", headers=thabo, json={"email": "bad", "phone": ""})
        self.assertEqual(bad.status_code, 400)


if __name__ == "__main__":
    unittest.main()
