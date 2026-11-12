import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import (COLLECTED, DELIVERED, READY, RETURNED, DeliveryManager,
                    Messenger, hash_pin)
from storage import JsonStore, SqliteStore, load_json, save_json


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "data.json")
        self.m = DeliveryManager(JsonStore(self.path))
        self.thabo = self.m.get_user("thabo")

    def tearDown(self):
        self.dir.cleanup()

    def test_seed_and_login(self):
        self.assertIsNotNone(self.m.authenticate("clinic1", "1234"))
        self.assertIsNone(self.m.authenticate("clinic1", "0000"))
        self.assertIsNone(self.m.authenticate("nobody", "1234"))
        self.assertNotEqual(self.m.get_user("thabo").pin_hash, "1111")

    def test_polymorphism(self):
        self.assertEqual(self.m.get_user("clinic1").home_route(), "/clinic")
        self.assertEqual(self.thabo.home_route(), "/messenger")
        self.assertIsInstance(self.thabo, Messenger)

    def test_add_patient_validation(self):
        with self.assertRaises(ValueError):
            self.m.add_patient("", "Lekubu", "1 Road", "0821234567")
        with self.assertRaises(ValueError):
            self.m.add_patient("A", "Lekubu", "1 Road", "12345")
        p = self.m.add_patient("Ann", "Lekubu", "1 Road", "082 123 4567")
        self.assertEqual(p.patient_id, "P004")
        self.assertEqual(p.contact, "0821234567")

    def test_full_delivery_flow(self):
        d, pin = self.m.create_delivery("P003", "Bag", "clinic1")
        self.assertEqual(d.status, READY)
        self.assertNotIn(pin, str(d.to_dict()))  # the PIN itself is never stored
        self.m.collect(d.delivery_id, self.thabo)
        self.assertEqual(d.status, COLLECTED)
        wrong = "0000" if pin != "0000" else "1111"
        with self.assertRaises(ValueError):
            self.m.confirm_delivery(d.delivery_id, wrong, self.thabo)
        self.m.confirm_delivery(d.delivery_id, pin, self.thabo)
        self.assertEqual(d.status, DELIVERED)
        self.assertEqual([h["status"] for h in d.history], [READY, COLLECTED, DELIVERED])

    def test_messenger_only_sees_own_village(self):
        d, _ = self.m.create_delivery("P002", "Bag", "clinic1")  # Dinokana
        lerato = self.m.get_user("lerato")
        self.assertIn(d, self.m.active_for_messenger(lerato))
        self.assertNotIn(d, self.m.active_for_messenger(self.thabo))
        with self.assertRaises(ValueError):
            self.m.collect(d.delivery_id, self.thabo)

    def test_no_duplicate_active_delivery(self):
        with self.assertRaises(ValueError):  # P001 seeded with one
            self.m.create_delivery("P001", "Another", "clinic1")

    def test_return_and_requeue(self):
        d = self.m.get_delivery("D001")
        self.m.collect("D001", self.thabo)
        self.m.mark_returned("D001", self.thabo)
        self.assertEqual(d.status, RETURNED)
        _, pin = self.m.requeue("D001", "clinic1")
        self.assertEqual(d.status, READY)
        self.assertTrue(d.check_pin(pin))

    def test_pin_locks_after_five_wrong_tries(self):
        d, pin = self.m.create_delivery("P003", "Bag", "clinic1")
        self.m.collect(d.delivery_id, self.thabo)
        wrong = "0000" if pin != "0000" else "1111"
        for _ in range(5):
            with self.assertRaises(ValueError):
                self.m.confirm_delivery(d.delivery_id, wrong, self.thabo)
        with self.assertRaises(ValueError):  # even the right PIN is refused now
            self.m.confirm_delivery(d.delivery_id, pin, self.thabo)
        new = self.m.reissue_pin(d.delivery_id)
        self.m.confirm_delivery(d.delivery_id, new, self.thabo)
        self.assertEqual(d.status, DELIVERED)

    def test_add_messenger(self):
        m = self.m.add_messenger("Sipho", "Sipho K", "5555", "Zeerust")
        self.assertEqual(m.username, "sipho")
        self.assertIsNotNone(self.m.authenticate("sipho", "5555"))
        with self.assertRaises(ValueError):
            self.m.add_messenger("sipho", "Again", "5555", "Zeerust")
        with self.assertRaises(ValueError):
            self.m.add_messenger("x", "X", "12", "Zeerust")

    def test_sqlite_round_trip(self):
        store = SqliteStore(os.path.join(self.dir.name, "x.db"))
        m = DeliveryManager(store)
        m.add_patient("Ann", "Lekubu", "1 Road", "0821234567")
        d, _ = m.create_delivery("P004", "Bag", "clinic1")
        again = DeliveryManager(SqliteStore(os.path.join(self.dir.name, "x.db")))
        self.assertEqual(len(again.patients), 4)
        self.assertEqual(len(again.deliveries), 2)
        self.assertTrue(again.get_delivery(d.delivery_id).check_pin(_))
        self.assertIsNotNone(again.authenticate("thabo", "1111"))

    def test_persistence_round_trip(self):
        self.m.add_patient("Ann", "Lekubu", "1 Road", "0821234567")
        again = DeliveryManager(JsonStore(self.path))
        self.assertEqual(len(again.patients), 4)
        self.assertEqual(len(again.deliveries), 1)

    def test_damaged_file_recovers(self):
        with open(self.path, "w") as f:
            f.write("{not json")
        fresh = DeliveryManager(JsonStore(self.path))
        self.assertEqual(len(fresh.patients), 3)
        self.assertTrue(os.path.exists(self.path + ".bak"))


class MigrationTests(unittest.TestCase):
    def test_old_database_is_upgraded_in_place(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "old.db")
            db = sqlite3.connect(path)
            db.executescript("""
                CREATE TABLE users(username TEXT PRIMARY KEY, role TEXT NOT NULL, full_name TEXT NOT NULL,
                                   pin_hash TEXT NOT NULL, village TEXT);
                CREATE TABLE patients(patient_id TEXT PRIMARY KEY, name TEXT NOT NULL, village TEXT NOT NULL,
                                      address TEXT NOT NULL, contact TEXT NOT NULL);
                INSERT INTO users VALUES('thabo','messenger','Thabo','x','Lekubu');
            """)
            db.commit(); db.close()
            store = SqliteStore(path)
            data = store.load()
            self.assertEqual(data["users"][0]["status"], "active")
            self.assertEqual(data["users"][0]["email"], "")


class RegistrationModelTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.m = DeliveryManager(JsonStore(os.path.join(self.dir.name, "r.json")))

    def tearDown(self):
        self.dir.cleanup()

    def test_pending_user_cannot_authenticate_until_approved(self):
        self.m.register_messenger("Sipho", "Sipho K", "5555", "Zeerust")
        with self.assertRaises(ValueError):
            self.m.authenticate("sipho", "5555")
        self.assertIsNone(self.m.authenticate("sipho", "0000"))      # wrong PIN looks the same as always
        self.assertEqual(self.m.find_messenger("Zeerust"), None)     # not active yet
        self.m.approve_user("sipho")
        self.assertIsNotNone(self.m.authenticate("sipho", "5555"))
        self.assertIsNotNone(self.m.find_messenger("Zeerust"))

    def test_messages_do_not_show_as_unread_for_new_users(self):
        self.m.send_message(self.m.get_user("clinic1"), "@messengers", "hello all")
        self.m.add_messenger("late", "Late Joiner", "4444", "Lekubu")
        self.assertEqual(self.m.unread_count(self.m.get_user("late")), 0)


class ProductionSeedTests(unittest.TestCase):
    def test_production_has_only_admin(self):
        with tempfile.TemporaryDirectory() as d:
            m = DeliveryManager(JsonStore(os.path.join(d, "p.json")), demo=False, admin_pin="s3cret-pin")
            self.assertEqual([u.username for u in m.users], ["admin"])
            self.assertEqual(m.patients, [])
            self.assertIsNotNone(m.authenticate("admin", "s3cret-pin"))
            with self.assertRaises(RuntimeError):
                DeliveryManager(JsonStore(os.path.join(d, "q.json")), demo=False, admin_pin="123")


class StorageTests(unittest.TestCase):
    def test_missing_returns_default(self):
        self.assertEqual(load_json("/no/such/file.json", {"a": 1}), {"a": 1})

    def test_save_then_load(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "x.json")
            self.assertTrue(save_json(path, {"k": [1, 2]}))
            self.assertEqual(load_json(path), {"k": [1, 2]})


if __name__ == "__main__":
    unittest.main()
