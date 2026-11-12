import flet as ft

from views.common import app_bar, body, heading, padded, page_body


def add_messenger_view(ctx):
    full_name = ft.TextField(label="Full name")
    username = ft.TextField(label="Username (letters and numbers)")
    pin = ft.TextField(label="Starting PIN (4+ digits)", password=True, can_reveal_password=True)
    village = ft.TextField(label="Village they cover")
    email = ft.TextField(label="Email (optional)", keyboard_type=ft.KeyboardType.EMAIL)
    phone = ft.TextField(label="Cell number (optional)", keyboard_type=ft.KeyboardType.PHONE)
    error = ft.Text("", color=ft.Colors.RED, size=16)

    async def save(e):
        try:
            m = ctx.manager.add_messenger(username.value, full_name.value, pin.value, village.value,
                                         email.value or "", phone.value or "")
        except ValueError as err:
            error.value = str(err)
            ctx.page.update()
            return
        ctx.toast(f"Added messenger {m['full_name']} for {m['village']}")
        await ctx.go("/clinic")

    async def cancel(e):
        await ctx.go("/clinic")

    return ft.View(
        route="/add-messenger",
        appbar=app_bar(ctx, "Add messenger"),
        controls=[padded(page_body(
            heading("New messenger"),
            body("Choose someone the village already trusts."),
            full_name, username, pin, village, email, phone, error,
            ft.Row([ft.Button("Save", icon=ft.Icons.SAVE, on_click=save),
                    ft.TextButton("Cancel", on_click=cancel)]),
        ))],
    )
