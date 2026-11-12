"""End-to-end: the app's RemoteManager talking to a real running server over HTTP."""
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DOORSTEP_NO_AUTOSTART"] = "1"

from werkzeug.serving import make_server

from api_client import ApiError, RemoteManager, SessionExpired
from backend.app import create_app
from storage import SqliteStore


class QuietNotifier:
    def sms(self, phone, text):
        return True

    def email(self, to, subject, text):
        return True


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        app = create_app(SqliteStore(os.path.join(cls.dir.name, "c.db")), QuietNotifier(), sync_notify=True)
        cls.server = make_server("127.0.0.1", 0, app, threaded=True)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.dir.cleanup()

    def test_two_devices_one_delivery(self):
        clinic, phone = RemoteManager(self.url), RemoteManager(self.url)
        clinic.login("clinic1", "1234")
        phone.login("thabo", "1111")
        clinic.sync()
        patient = clinic.add_patient("Mpho Z", "Lekubu", "3 Hill Rd", "0831234567")
        pin, sms = clinic.create_delivery(patient.patient_id, "Bag A")
        self.assertTrue(sms)
        phone.sync()
        self.assertEqual(len(phone.deliveries), 2)
        mine = next(d for d in phone.deliveries if d.patient_id == patient.patient_id)
        phone.collect(mine.delivery_id)
        with self.assertRaises(ApiError):
            phone.confirm_delivery(mine.delivery_id, "wrong")
        phone.confirm_delivery(mine.delivery_id, pin)
        clinic.sync()
        self.assertEqual(clinic.counts()["Delivered"], 1)
        phone.sync()
        self.assertEqual(phone.delivered_count, 1)

    def test_errors_are_friendly(self):
        m = RemoteManager(self.url)
        with self.assertRaises(ApiError) as ctx:
            m.login("thabo", "bad")
        self.assertIn("Wrong", str(ctx.exception))
        offline = RemoteManager("http://127.0.0.1:1")
        with self.assertRaises(ApiError) as ctx:
            offline.login("a", "b")
        self.assertIn("Cannot reach", str(ctx.exception))

    def test_expired_session(self):
        m = RemoteManager(self.url)
        m.login("clinic1", "1234")
        m.logout()
        m.token = "stale"
        with self.assertRaises(SessionExpired):
            m.sync()
        self.assertIsNone(m.me)

    def test_register_approve_message_flow(self):
        newcomer, clinic = RemoteManager(self.url), RemoteManager(self.url)
        self.assertEqual(newcomer.register("messenger", "zodwa", "Zodwa M", "7777", "Lekubu",
                                           "zodwa@example.com", "0821230000"), "pending")
        with self.assertRaises(ApiError) as ctx:
            newcomer.login("zodwa", "7777")
        self.assertIn("approval", str(ctx.exception))
        clinic.login("clinic1", "1234")
        clinic.sync()
        self.assertIn("zodwa", [u["username"] for u in clinic.pending])
        clinic.approve("zodwa")
        newcomer.login("zodwa", "7777")
        newcomer.send_message("@clinic", "Hello, I am ready to start", by_email=True)
        clinic.sync()
        self.assertEqual(clinic.unread, 1)
        inbox = clinic.load_messages()
        self.assertEqual(inbox[0]["sender_name"], "Zodwa M")
        self.assertEqual(clinic.unread, 0)
        # invite flow
        code = clinic.create_invite()
        self.assertEqual(RemoteManager(self.url).register("clinic", "nurse9", "Nurse Nine", "8888",
                                                          invite_code=code), "active")
        # profile
        newcomer.change_pin("7777", "9999")
        newcomer.update_contact("new@example.com", "0821239999")
        self.assertEqual(newcomer.me.email, "new@example.com")
        RemoteManager(self.url).login("zodwa", "9999")
        self.assertIn("sms_sent", clinic.message_patient("P001", "See you soon", "sms"))

    def test_add_messenger_then_login(self):
        clinic = RemoteManager(self.url)
        clinic.login("clinic1", "1234")
        clinic.add_messenger("Neo", "Neo M", "4321", "Zeerust")
        self.assertEqual(RemoteManager(self.url).login("neo", "4321").village, "Zeerust")


if __name__ == "__main__":
    unittest.main()
