import flet as ft

from views.common import DropdownOption, app_bar, heading, padded, page_body


def add_patient_view(ctx):
    name = ft.TextField(label="Full name")
    village = ft.Dropdown(
        label="Village",
        options=[DropdownOption(v) for v in ctx.manager.villages()],
    )
    address = ft.TextField(label="Street address / landmark")
    contact = ft.TextField(label="Contact number (10 digits)", keyboard_type=ft.KeyboardType.PHONE)
    email = ft.TextField(label="Email (optional)", keyboard_type=ft.KeyboardType.EMAIL)

    async def save(e):
        try:
            patient = ctx.manager.add_patient(name.value, village.value, address.value, contact.value, email.value or "")
        except ValueError as err:
            contact.error_text = str(err)
            ctx.page.update()
            return
        ctx.toast(f"Added {patient.name} ({patient.patient_id})")
        await ctx.go("/clinic")

    async def cancel(e):
        await ctx.go("/clinic")

    return ft.View(
        route="/add-patient",
        appbar=app_bar(ctx, "Add patient"),
        controls=[padded(page_body(
            heading("New patient"),
            name, village, address, contact, email,
            ft.Row([
                ft.Button("Save", icon=ft.Icons.SAVE, on_click=save),
                ft.TextButton("Cancel", on_click=cancel),
            ]),
        ))],
    )
