"""Doorstep Meds: clinic-to-doorstep medication delivery (Flet app).

The app talks to the backend server (see backend/app.py). Set the server address with
the environment variable DOORSTEP_API_URL (default http://127.0.0.1:8000).

Run with:  python main.py        (or: flet run main.py)
"""
import os

import flet as ft

from api_client import ApiError, RemoteManager, SessionExpired
from theme import make_theme
from views.add_messenger import add_messenger_view
from views.add_patient import add_patient_view
from views.clinic import clinic_view
from views.common import AppContext
from views.login import login_view
from views.messages import messages_view
from views.profile import profile_view
from views.register import register_view
from views.messenger import messenger_view

API_URL = os.environ.get("DOORSTEP_API_URL", "http://127.0.0.1:8000")


def main(page: ft.Page):
    page.title = "Doorstep Meds"
    page.theme = make_theme()
    page.theme_mode = ft.ThemeMode.LIGHT

    manager = RemoteManager(API_URL)
    ctx = AppContext(page, manager)

    def build_view():
        user = ctx.current_user()
        if user is not None:
            try:
                manager.sync()
            except SessionExpired as err:
                ctx.notice = str(err)
                user = None
            except ApiError as err:
                ctx.notice = str(err)
                user = None
                manager.me = manager.token = None
        route = page.route
        if user is not None and route == "/messages":
            return messages_view(ctx)
        if user is not None and route == "/profile":
            return profile_view(ctx)
        if user is None and route == "/register":
            return register_view(ctx)
        # Role guards: each screen is only for its own role.
        if user is not None and user.role == "clinic" and route == "/add-patient":
            return add_patient_view(ctx)
        if user is not None and user.role == "clinic" and route == "/add-messenger":
            return add_messenger_view(ctx)
        if user is not None and user.role == "clinic":
            return clinic_view(ctx)
        if user is not None and user.role == "messenger":
            return messenger_view(ctx)
        return login_view(ctx)

    def route_change(e=None):
        page.views.clear()
        page.views.append(build_view())
        page.update()

    ctx.refresh = route_change
    page.on_route_change = route_change
    route_change()


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
