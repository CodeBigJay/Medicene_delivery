import flet as ft

from views.common import app_bar, back_button, body, heading, padded, page_body


def profile_view(ctx):
    user = ctx.current_user()
    email = ft.TextField(label="Email", value=user.email, keyboard_type=ft.KeyboardType.EMAIL)
    phone = ft.TextField(label="Cell number", value=user.phone, keyboard_type=ft.KeyboardType.PHONE)
    contact_msg = ft.Text("", size=16)
    old = ft.TextField(label="Current PIN", password=True, can_reveal_password=True)
    new = ft.TextField(label="New PIN (4+ digits)", password=True, can_reveal_password=True)
    new2 = ft.TextField(label="Repeat new PIN", password=True, can_reveal_password=True)
    pin_msg = ft.Text("", size=16)

    def save_contact(e):
        try:
            ctx.manager.update_contact(email.value or "", phone.value or "")
            contact_msg.value, contact_msg.color = "Saved.", ft.Colors.GREEN
        except ValueError as err:
            contact_msg.value, contact_msg.color = str(err), ft.Colors.RED
        ctx.page.update()

    def save_pin(e):
        if new.value != new2.value:
            pin_msg.value, pin_msg.color = "The two new PINs do not match.", ft.Colors.RED
        else:
            try:
                ctx.manager.change_pin(old.value or "", new.value or "")
                pin_msg.value, pin_msg.color = "PIN changed.", ft.Colors.GREEN
                old.value = new.value = new2.value = ""
            except ValueError as err:
                pin_msg.value, pin_msg.color = str(err), ft.Colors.RED
        ctx.page.update()

    role = "Clinic staff" if user.role == "clinic" else f"Messenger, {user.village}"
    return ft.View(
        route="/profile",
        appbar=app_bar(ctx, "Profile"),
        controls=[padded(page_body(
            back_button(ctx),
            heading(user.full_name),
            body(f"{role} · username: {user.username}"),
            ft.Divider(),
            heading("Contact details"),
            body("Used for notifications (new parcels, messages, approvals)."),
            email, phone, contact_msg,
            ft.Button("Save contact details", icon=ft.Icons.SAVE, on_click=save_contact),
            ft.Divider(),
            heading("Change PIN"),
            old, new, new2, pin_msg,
            ft.Button("Change PIN", icon=ft.Icons.LOCK, on_click=save_pin),
        ))],
    )
