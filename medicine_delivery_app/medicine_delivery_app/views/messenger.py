import flet as ft

from models import COLLECTED, READY
from views.common import app_bar, body, heading, nav_row, padded, page_body, status_badge, status_guide


def messenger_view(ctx):
    manager = ctx.manager
    user = ctx.current_user()

    def collect(delivery_id):
        def handler(e):
            try:
                manager.collect(delivery_id)
            except ValueError as err:
                ctx.toast(str(err))
            ctx.refresh()
        return handler

    def returned(delivery_id):
        def handler(e):
            def confirm_return(event):
                try:
                    manager.mark_returned(delivery_id)
                    ctx.close_dialog()
                    ctx.toast("Marked as returned to the clinic. Clinic staff can queue it again.")
                    ctx.refresh()
                except ValueError as err:
                    ctx.toast(str(err))
                    ctx.close_dialog()
                    ctx.refresh()

            ctx.page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Return parcel to clinic?"),
                content=body(
                    "Use this when the patient or caregiver is unavailable or the handover "
                    "cannot be completed. The parcel will be marked as returned, and clinic "
                    "staff can review it and queue it again."
                ),
                actions=[
                    ft.TextButton("Cancel", on_click=ctx.close_dialog),
                    ft.Button("Confirm return", on_click=confirm_return),
                ],
            ))
        return handler

    def open_confirm(delivery_id):
        def handler(e):
            pin = ft.TextField(label="PIN from the patient", keyboard_type=ft.KeyboardType.NUMBER,
                               autofocus=True)

            def confirm(e):
                try:
                    manager.confirm_delivery(delivery_id, pin.value)
                except ValueError as err:
                    pin.error_text = str(err)
                    ctx.page.update()
                    return
                ctx.close_dialog()
                ctx.toast("Delivery confirmed. Thank you!")
                ctx.refresh()

            ctx.page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text("Confirm handover"),
                content=ft.Column([body("Ask the patient or caregiver for their 4-digit PIN."), pin],
                                  tight=True, width=320),
                actions=[ft.TextButton("Cancel", on_click=ctx.close_dialog),
                         ft.Button("Confirm", on_click=confirm)],
            ))
        return handler

    cards = []
    for d in manager.deliveries:
        patient = manager.get_patient(d.patient_id)
        if patient is None:
            continue
        lines = [
            ft.Row([ft.Text(patient.name, size=18, weight=ft.FontWeight.BOLD, expand=True),
                    status_badge(d.status)]),
            body(f"Address: {patient.address}, {patient.village}"),
            body(f"Phone: {patient.contact}"),
        ]
        if d.locked:
            lines.append(ft.Text("PIN locked. Ask the clinic to send a new PIN.",
                                 color=ft.Colors.RED, size=14))
        if d.status == READY:
            lines.append(body("Next step: collect this parcel from the clinic, then deliver it to the patient or caregiver."))
        elif d.status == COLLECTED:
            lines.append(body("Next step: complete the handover and ask the patient or caregiver for their 4-digit PIN. "
                              "If the handover cannot be completed, return the parcel to the clinic."))
        if d.status == READY:
            lines.append(ft.Button("Collect from clinic", icon=ft.Icons.INVENTORY,
                                   on_click=collect(d.delivery_id)))
        elif d.status == COLLECTED:
            lines.append(ft.Row([
                ft.Button("Confirm delivery", icon=ft.Icons.CHECK_CIRCLE,
                          on_click=open_confirm(d.delivery_id)),
                ft.OutlinedButton("Return to clinic", on_click=returned(d.delivery_id)),
            ], wrap=True))
        cards.append(ft.Card(content=ft.Container(ft.Column(lines, spacing=6), padding=14)))
    if not cards:
        cards.append(body("No parcels waiting in your village right now."))

    done = manager.delivered_count

    return ft.View(
        route="/messenger",
        appbar=app_bar(ctx, f"Messenger: {user.village}"),
        controls=[padded(page_body(
            heading(f"Hello, {user.full_name}"),
            nav_row(ctx),
            body(f"Delivered by you so far: {done}"),
            ft.Divider(),
            ft.Container(
                content=ft.Column([
                    heading("Your delivery steps"),
                    body("1. Collect a parcel marked Ready. "
                         "2. Take it to the patient or caregiver. "
                         "3. Ask them for the 4-digit handover PIN and confirm delivery. "
                         "If the handover cannot be completed, choose 'Return to clinic' "
                         "and explain the situation to clinic staff."),
                ], spacing=6),
                padding=12, border_radius=10,
                bgcolor=ft.Colors.BLUE_GREY_50,
            ),
            status_guide(),
            heading("Parcels to deliver"),
            *cards,
        ))],
    )
