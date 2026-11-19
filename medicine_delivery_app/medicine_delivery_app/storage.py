"""Persistence (no UI code here).

Two interchangeable stores with the same two methods, load() and save(data):
  * JsonStore    - a single JSON file (simple, used for tests and quick demos)
  * SqliteStore  - a real database file (used by the backend server)
`data` is always {"users": [...], "patients": [...], "deliveries": [...]}.
"""
import json
import shutil
from contextlib import contextmanager
import sqlite3
from pathlib import Path


# ----------------------------------------------------------------------
# JSON helpers
# ----------------------------------------------------------------------
def load_json(path, default=None):
    """Read JSON from `path`. Return `default` if the file is missing or damaged."""
    path = Path(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError:
        print(f"Warning: {path.name} is damaged. A copy was kept as {path.name}.bak")
        try:
            shutil.copy(path, path.with_name(path.name + ".bak"))
        except OSError:
            pass
        return default


def save_json(path, data):
    """Write `data` to `path` as readable JSON. Return True if it worked."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp.replace(path)  # atomic: a crash can never leave half a file
        return True
    except OSError as err:
        print(f"Could not save data: {err}")
        return False


class JsonStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        return load_json(self.path, None)

    def save(self, data):
        return save_json(self.path, data)


# ----------------------------------------------------------------------
# SQLite store
# ----------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
    username TEXT PRIMARY KEY, role TEXT NOT NULL, full_name TEXT NOT NULL,
    pin_hash TEXT NOT NULL, village TEXT, email TEXT DEFAULT '', phone TEXT DEFAULT '',
    status TEXT DEFAULT 'active', last_read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS patients(
    patient_id TEXT PRIMARY KEY, name TEXT NOT NULL, village TEXT NOT NULL,
    address TEXT NOT NULL, contact TEXT NOT NULL, email TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS deliveries(
    delivery_id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, parcel_note TEXT NOT NULL,
    pin_hash TEXT NOT NULL, status TEXT NOT NULL, messenger TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0, history TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(
    message_id INTEGER PRIMARY KEY, sender TEXT NOT NULL, recipient TEXT NOT NULL,
    text TEXT NOT NULL, time TEXT NOT NULL, delivery_id TEXT);
CREATE TABLE IF NOT EXISTS invites(
    code TEXT PRIMARY KEY, created_by TEXT NOT NULL, used_by TEXT);
CREATE TABLE IF NOT EXISTS sessions(
    token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
"""

# Columns added after the first release: older database files are upgraded in place.
NEW_COLUMNS = {
    "users": [("email", "TEXT DEFAULT ''"), ("phone", "TEXT DEFAULT ''"),
              ("status", "TEXT DEFAULT 'active'"), ("last_read", "INTEGER DEFAULT 0")],
    "patients": [("email", "TEXT DEFAULT ''")],
}


class SqliteStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)
            for table, columns in NEW_COLUMNS.items():
                have = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
                for name, definition in columns:
                    if name not in have:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    @contextmanager
    def _connect(self):
        """Open, commit (or roll back on error) and always close the connection."""
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def load(self):
        with self._connect() as db:
            users = [dict(r) for r in db.execute("SELECT * FROM users ORDER BY rowid")]
            if not users:
                return None  # empty database: caller seeds it
            patients = [dict(r) for r in db.execute("SELECT * FROM patients ORDER BY rowid")]
            deliveries = []
            for r in db.execute("SELECT * FROM deliveries ORDER BY rowid"):
                d = dict(r)
                d["history"] = json.loads(d["history"])
                deliveries.append(d)
            messages = []
            for r in db.execute("SELECT * FROM messages ORDER BY message_id"):
                m = dict(r)
                m["to"] = m.pop("recipient")
                messages.append(m)
            invites = [dict(r) for r in db.execute("SELECT * FROM invites ORDER BY rowid")]
        return {"users": users, "patients": patients, "deliveries": deliveries,
                "messages": messages, "invites": invites}

    def save(self, data):
        try:
            with self._connect() as db:  # one transaction: all or nothing
                for table in ("users", "patients", "deliveries", "messages", "invites"):
                    db.execute(f"DELETE FROM {table}")
                db.executemany(
                    "INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?)",
                    [(u["username"], u["role"], u["full_name"], u["pin_hash"], u.get("village"),
                      u.get("email", ""), u.get("phone", ""), u.get("status", "active"),
                      u.get("last_read", 0)) for u in data["users"]])
                db.executemany(
                    "INSERT INTO patients VALUES(?,?,?,?,?,?)",
                    [(p["patient_id"], p["name"], p["village"], p["address"], p["contact"],
                      p.get("email", "")) for p in data["patients"]])
                db.executemany(
                    "INSERT INTO deliveries VALUES(?,?,?,?,?,?,?,?)",
                    [(d["delivery_id"], d["patient_id"], d["parcel_note"], d["pin_hash"],
                      d["status"], d.get("messenger"), d.get("failed_attempts", 0),
                      json.dumps(d["history"])) for d in data["deliveries"]])
                db.executemany(
                    "INSERT INTO messages VALUES(?,?,?,?,?,?)",
                    [(m["message_id"], m["sender"], m["to"], m["text"], m["time"],
                      m.get("delivery_id")) for m in data.get("messages", [])])
                db.executemany(
                    "INSERT INTO invites VALUES(?,?,?)",
                    [(i["code"], i["created_by"], i.get("used_by")) for i in data.get("invites", [])])
            return True
        except sqlite3.Error as err:
            print(f"Could not save data: {err}")
            return False

    # ---- login sessions (kept apart from the business data) ----------
    def add_session(self, token, username, expires):
        with self._connect() as db:
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (token, username, expires))

    def get_session(self, token, now):
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE expires < ?", (now,))
            row = db.execute("SELECT username FROM sessions WHERE token=?", (token,)).fetchone()
        return row["username"] if row else None

    def delete_session(self, token):
        with self._connect() as db:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
