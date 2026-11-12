import flet as ft

from theme import SEED
from views.common import app_bar, body, heading, padded, page_body


def _logo():
    return ft.Container(
        content=ft.Icon(ft.Icons.LOCAL_PHARMACY, size=56, color=ft.Colors.WHITE),
        bgcolor=SEED, width=96, height=96, border_radius=48,
        alignment=ft.Alignment(0, 0) if hasattr(ft, "Alignment") else None,
    )


def login_view(ctx):
    username = ft.TextField(label="Username", autofocus=True)
    pin = ft.TextField(label="PIN", password=True, can_reveal_password=True)
    notice = ft.Text(ctx.notice, color=ft.Colors.TEAL_700, size=16, weight=ft.FontWeight.BOLD)
    ctx.notice = ""

    async def sign_in(e):
        username.error_text = None
        pin.error_text = None
        if not username.value or not pin.value:
            if not username.value:
                username.error_text = "Enter your username"
            if not pin.value:
                pin.error_text = "Enter your PIN"
            ctx.page.update()
            return
        try:
            user = ctx.manager.login(username.value, pin.value)
        except ValueError as err:   # wrong PIN, locked out, or server unreachable
            pin.error_text = str(err)
            ctx.page.update()
            return
        await ctx.go(user.home_route())

    async def to_register(e):
        await ctx.go("/register")

    def forgot(e):
        ctx.page.show_dialog(ft.AlertDialog(
            title=ft.Text("Forgot your PIN?"),
            content=body("Ask your clinic to reset it. They will send you a temporary PIN by SMS or "
                         "email. Sign in with it, then choose a new PIN under Profile."),
            actions=[ft.Button("OK", on_click=ctx.close_dialog)],
        ))

    return ft.View(
        route="/login",
        appbar=app_bar(ctx, "Doorstep Meds", show_logout=False),
        controls=[padded(page_body(
            ft.Row([_logo()], alignment=ft.MainAxisAlignment.CENTER),
            ft.Text("Doorstep Meds", size=30, weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER),
            body("Chronic medicine, delivered to the door by someone you know.",
                 text_align=ft.TextAlign.CENTER),
            notice,
            username,
            pin,
            ft.Button("Sign in", icon=ft.Icons.LOGIN, on_click=sign_in),
            ft.Row([ft.TextButton("Create account", on_click=to_register),
                    ft.TextButton("Forgot PIN?", on_click=forgot)], wrap=True),
        ))],
    )
