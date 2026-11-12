"""Shared pieces used by every view."""
import flet as ft

from theme import GAP, PAD, STATUS_COLORS, BODY_SIZE, TITLE_SIZE

# Flet renamed dropdown options in newer versions; support both.
DropdownOption = getattr(ft, "DropdownOption", None) or ft.dropdown.Option


class AppContext:
    """Bundles the page, the server connection and navigation for the views."""

    def __init__(self, page, manager):
        self.page = page
        self.manager = manager
        self.notice = ""                    # message shown on the login screen
        self.refresh = lambda e=None: None  # replaced by main.py

    # ---- session -----------------------------------------------------
    def current_user(self):
        return self.manager.me

    def logout(self):
        self.manager.logout()

    # ---- navigation and feedback ------------------------------------
    async def go(self, route):
        await self.page.push_route(route)

    def toast(self, text):
        self.page.show_dialog(ft.SnackBar(ft.Text(text)))

    def close_dialog(self, e=None):
        self.page.pop_dialog()

    def show_code(self, title, code, *notes):
        """Show a one-time code (PIN or invite) in big letters."""
        self.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text(title),
            content=ft.Column(
                [ft.Text(code, size=48, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER)]
                + [body(n) for n in notes],
                tight=True, width=320, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            actions=[ft.Button("Done", on_click=self.close_dialog)],
        ))

    def show_pin(self, title, pin, sms_sent):
        """Show a new handover PIN to the clinic (it is stored only as a hash)."""
        note = ("It was also sent to the patient by SMS." if sms_sent
                else "The SMS could not be sent. Give this PIN to the patient or caregiver.")
        self.show_code(title, pin, note, "This PIN will not be shown again.")


def app_bar(ctx, title, show_logout=True):
    async def do_logout(e):
        ctx.logout()
        await ctx.go("/login")

    actions = []
    if show_logout:
        actions.append(ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh",
                                     on_click=lambda e: ctx.refresh()))
        actions.append(ft.TextButton("Log out", on_click=do_logout))
    return ft.AppBar(title=ft.Text(title), actions=actions)


def nav_row(ctx):
    """Shortcuts shown at the top of each home screen."""
    def to(route):
        async def handler(e):
            await ctx.go(route)
        return handler

    unread = ctx.manager.unread
    label = f"Messages ({unread})" if unread else "Messages"
    return ft.Row([
        ft.OutlinedButton(label, icon=ft.Icons.MAIL, on_click=to("/messages")),
        ft.OutlinedButton("Profile", icon=ft.Icons.PERSON, on_click=to("/profile")),
    ], wrap=True)


def back_button(ctx):
    async def handler(e):
        await ctx.go(ctx.current_user().home_route())
    return ft.TextButton("Back", icon=ft.Icons.ARROW_BACK, on_click=handler)


def heading(text):
    return ft.Text(text, size=TITLE_SIZE, weight=ft.FontWeight.BOLD)


def body(text, **kw):
    return ft.Text(text, size=BODY_SIZE, **kw)


def status_badge(status):
    return ft.Container(
        content=ft.Text(status, color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.BOLD),
        bgcolor=STATUS_COLORS.get(status, ft.Colors.GREY),
        padding=6,
        border_radius=12,
    )


def page_body(*controls):
    """Standard padded, scrollable column for a screen."""
    return ft.Column(list(controls), spacing=GAP, scroll=ft.ScrollMode.AUTO, expand=True)


def padded(content):
    return ft.Container(content=content, padding=PAD, expand=True)
