"""Builds every screen with a stand-in for Flet (Flet is not needed) against a real server.
Catches wiring mistakes: wrong routes, role guards, attribute errors in the views.
Run:  python tests/smoke_ui.py
"""
import asyncio, os, sys, tempfile, threading, types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["DOORSTEP_NO_AUTOSTART"] = "1"

class Any:
    def __init__(s, *a, **k): s.args, s.kw = a, k
class Ns:
    def __getattr__(s, n): return n
ft = types.ModuleType("flet")
for n in ("View AppBar Text TextButton TextField Button OutlinedButton Row Column Container Card "
          "Divider Dropdown AlertDialog SnackBar Theme DropdownOption Page Icon IconButton Alignment Checkbox").split():
    setattr(ft, n, type(n, (Any,), {}))
for n in "Colors Icons FontWeight ScrollMode KeyboardType CrossAxisAlignment ThemeMode TextAlign MainAxisAlignment".split():
    setattr(ft, n, Ns())
ft.run = lambda *a, **k: None
sys.modules["flet"] = ft

from werkzeug.serving import make_server
from backend.app import create_app
from storage import SqliteStore
class Q:
    def sms(self, p, t): return True
    def email(self, to, s, t): return True
srv = make_server("127.0.0.1", 0, create_app(SqliteStore(os.path.join(tempfile.mkdtemp(), "s.db")), Q(), sync_notify=True))
threading.Thread(target=srv.serve_forever, daemon=True).start()
os.environ["DOORSTEP_API_URL"] = f"http://127.0.0.1:{srv.server_port}"
import main as app

class Page:
    def __init__(s): s.views, s.route, s.shown = [], "/", []
    def update(s): pass
    def show_dialog(s, d): s.shown.append(d)
    def pop_dialog(s): s.shown.pop()
    async def push_route(s, r): s.route = r; s.on_route_change()
def route(p): return p.views[-1].kw["route"]

p = Page(); app.main(p)
assert route(p) == "/login"
p.route = "/clinic"; p.on_route_change(); assert route(p) == "/login"      # guard: not signed in
mgr = None
def sign_in(user, pin):
    # use the real login view's own click handler path
    from api_client import RemoteManager
    m = p_mgr(); m.login(user, pin)
def p_mgr():
    return app_ctx.manager
# grab the context the app created
import gc
app_ctx = next(o for o in gc.get_objects() if type(o).__name__ == "AppContext")
for user, pin, home in [("clinic1", "1234", "/clinic"), ("thabo", "1111", "/messenger")]:
    app_ctx.manager.logout(); sign_in(user, pin)
    asyncio.run(p.push_route(home)); assert route(p) == home, (user, route(p))
p.route = "/clinic"; p.on_route_change(); assert route(p) == "/messenger"    # guard: wrong role
app_ctx.manager.logout(); sign_in("clinic1", "1234")
for r in ("/add-patient", "/add-messenger"):
    p.route = r; p.on_route_change(); assert route(p) == r, r
# new screens
app_ctx.manager.logout()
p.route = "/register"; p.on_route_change(); assert route(p) == "/register"
p.route = "/messages"; p.on_route_change(); assert route(p) == "/login"       # guard: not signed in
for user, pin in [("clinic1", "1234"), ("thabo", "1111")]:
    app_ctx.manager.logout(); sign_in(user, pin)
    for r in ("/messages", "/profile"):
        p.route = r; p.on_route_change(); assert route(p) == r, (user, r)
app_ctx.manager.logout(); sign_in("clinic1", "1234")
p.route = "/clinic"; p.on_route_change(); assert route(p) == "/clinic"        # shows Nomsa's pending card
assert len(app_ctx.manager.pending) == 1
app_ctx.manager.token = "stale"; p.route = "/clinic"; p.on_route_change()
assert route(p) == "/login" and app_ctx.notice == "" , "expired session returns to login"
print("smoke ok")
