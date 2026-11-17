import flet as ft

from views.common import app_bar, body, heading, padded, page_body


def register_view(ctx):
    full_name = ft.TextField(label="Full name")
    username = ft.TextField(label="Username (letters and numbers)")
    pin = ft.TextField(label="PIN (4+ digits)", password=True, can_reveal_password=True)
    pin2 = ft.TextField(label="Repeat PIN", password=True, can_reveal_password=True)
    email = ft.TextField(label="Email (optional)", keyboard_type=ft.KeyboardType.EMAIL)
    phone = ft.TextField(label="Cell number (optional)", keyboard_type=ft.KeyboardType.PHONE)
    village = ft.TextField(label="Village you will deliver in (messengers)")
    invite = ft.TextField(label="Invite code (clinic staff only)")
    error = ft.Text("", color=ft.Colors.RED, size=16)

    async def submit(role):
        error.value = ""
        if pin.value != pin2.value:
            error.value = "The two PINs do not match."
            ctx.page.update()
            return
        try:
            status = ctx.manager.register(role, username.value, full_name.value, pin.value,
                                          village.value or "", email.value or "", phone.value or "",
                                          invite.value or "")
        except ValueError as err:
            error.value = str(err)
            ctx.page.update()
            return
        ctx.notice = ("Registration sent. The clinic will approve it, and you can sign in after that."
                      if status == "pending" else "Account created. You can sign in now.")
        await ctx.go("/login")

    async def as_messenger(e):
        await submit("messenger")

    async def as_staff(e):
        await submit("clinic")

    async def cancel(e):
        await ctx.go("/login")

    return ft.View(
        route="/register",
        appbar=app_bar(ctx, "Create account", show_logout=False),
        controls=[padded(page_body(
            heading("Join Doorstep Meds"),
            body("Messengers are approved by the clinic and can sign in after approval. "
                 "Clinic staff can register with a one-use invite code from a colleague."),
            body("Complete the village field only for messenger registration. "
                 "Complete the invite code field only for clinic staff registration."),
            full_name, username, pin, pin2, email, phone, village, invite, error,
            ft.Button("Register as messenger", icon=ft.Icons.DIRECTIONS_WALK, on_click=as_messenger),
            ft.OutlinedButton("Register as clinic staff", icon=ft.Icons.LOCAL_HOSPITAL, on_click=as_staff),
            ft.TextButton("Back to sign in", on_click=cancel),
        ))],
    )
