import flet as ft

from models import ALL_STATUSES, RETURNED
from theme import STATUS_COLORS
from views.common import (DropdownOption, app_bar, body, heading, nav_row, padded,
                          page_body, status_badge)


def clinic_view(ctx):
    manager = ctx.manager
    user = ctx.current_user()

    # ---- new delivery dialog ----------------------------------------
    def open_new_delivery(e):
        waiting = [p for p in manager.patients if not manager.has_active_delivery(p.patient_id)]
        if not waiting:
            ctx.toast("Every patient already has a delivery in progress.")
            return
        patient = ft.Dropdown(
            label="Patient",
            options=[DropdownOption(key=p.patient_id, text=f"{p.name} ({p.village})") for p in waiting],
        )
        note = ft.TextField(label="Parcel label (e.g. Monthly repeat, bag 1)")
        error = ft.Text("", color=ft.Colors.RED)

        def create(e):
            try:
                pin, sms_sent = manager.create_delivery(patient.value, note.value)
            except ValueError as err:
                error.value = str(err)
                ctx.page.update()
                return
            ctx.close_dialog()
            ctx.show_pin("Parcel ready: patient PIN", pin, sms_sent)
            ctx.refresh()

        ctx.page.show_dialog(ft.AlertDialog(
            modal=True,
            title=ft.Text("Mark parcel ready"),
            content=ft.Column([patient, note, error], tight=True, width=320),
            actions=[ft.TextButton("Cancel", on_click=ctx.close_dialog),
                     ft.Button("Create", on_click=create)],
        ))

    def pin_action(action, title):
        def make(delivery_id):
            def handler(e):
                try:
                    pin, sms_sent = action(delivery_id)
                except ValueError as err:
                    ctx.toast(str(err))
                    return
                ctx.show_pin(title, pin, sms_sent)
                ctx.refresh()
            return handler
        return make

    requeue = pin_action(manager.requeue, "Queued again: new patient PIN")
    reissue = pin_action(manager.reissue_pin, "New patient PIN")

    def decide(action, username, done):
        def handler(e):
            try:
                action(username)
                ctx.toast(done)
            except ValueError as err:
                ctx.toast(str(err))
            ctx.refresh()
        return handler

    def make_invite(e):
        try:
            code = manager.create_invite()
        except ValueError as err:
            ctx.toast(str(err))
            return
        ctx.show_code("Staff invite code", code,
                      "Give this code to a colleague. They choose 'Create account' and register as clinic staff.",
                      "It works once.")

    def reset_messenger_pin(username):
        def handler(e):
            try:
                pin = manager.reset_pin(username)
            except ValueError as err:
                ctx.toast(str(err))
                return
            ctx.show_code("Temporary PIN", pin,
                          "It was sent by SMS or email if they have contact details saved.",
                          "Tell them to change it under Profile.")
        return handler

    def open_message_patient(patient):
        def handler(e):
            text = ft.TextField(label="Message", multiline=True, min_lines=2, max_length=300)
            channel = ft.Dropdown(label="Send by", value="sms", options=[
                DropdownOption(key="sms", text="SMS"),
                DropdownOption(key="email", text="Email"),
                DropdownOption(key="both", text="SMS and email")])
            error = ft.Text("", color=ft.Colors.RED)

            def send(e):
                try:
                    result = manager.message_patient(patient.patient_id, text.value, channel.value)
                except ValueError as err:
                    error.value = str(err)
                    ctx.page.update()
                    return
                ctx.close_dialog()
                failed = [k for k in ("sms_sent", "email_sent") if result.get(k) is False]
                ctx.toast("Message sent." if not failed else "Could not send every message. Try again.")

            ctx.page.show_dialog(ft.AlertDialog(
                modal=True,
                title=ft.Text(f"Message {patient.name}"),
                content=ft.Column([text, channel, error], tight=True, width=320),
                actions=[ft.TextButton("Cancel", on_click=ctx.close_dialog),
                         ft.Button("Send", on_click=send)],
            ))
        return handler

    async def to_add_patient(e):
        await ctx.go("/add-patient")

    async def to_add_messenger(e):
        await ctx.go("/add-messenger")

    # ---- summary row -------------------------------------------------
    counts = manager.counts()
    summary = ft.Row(
        [ft.Container(
            content=ft.Column([ft.Text(str(counts[s]), size=28, weight=ft.FontWeight.BOLD,
                                       color=STATUS_COLORS[s]),
                               ft.Text(s, size=14)],
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=10, expand=True)
         for s in ALL_STATUSES],
    )

    # ---- delivery cards ---------------------------------------------
    cards = []
    for d in reversed(manager.deliveries):
        patient = manager.get_patient(d.patient_id)
        last = d.history[-1] if d.history else {}
        lines = [
            ft.Row([ft.Text(patient.name if patient else d.patient_id, size=18,
                            weight=ft.FontWeight.BOLD, expand=True),
                    status_badge(d.status)]),
            body(f"{d.delivery_id} \u00b7 {patient.village if patient else ''} \u00b7 {d.parcel_note}"),
            ft.Text(f"Last update: {last.get('time', '')} by {last.get('by', '')}", size=14),
        ]
        if d.locked:
            lines.append(ft.Text("Locked after too many wrong PINs. Send a new PIN.",
                                 color=ft.Colors.RED, size=14))
        buttons = []
        if patient is not None:
            buttons.append(ft.OutlinedButton("Message patient", icon=ft.Icons.SMS,
                                             on_click=open_message_patient(patient)))
        if d.is_active():
            buttons.append(ft.OutlinedButton("Send new PIN", icon=ft.Icons.PIN,
                                             on_click=reissue(d.delivery_id)))
        if d.status == RETURNED:
            buttons.append(ft.Button("Queue again", icon=ft.Icons.REPLAY,
                                     on_click=requeue(d.delivery_id)))
        if buttons:
            lines.append(ft.Row(buttons, wrap=True))
        cards.append(ft.Card(content=ft.Container(ft.Column(lines, spacing=6), padding=14)))
    if not cards:
        cards.append(body("No deliveries yet. Tap 'New delivery' to start."))

    pending = []
    for u in manager.pending:
        pending.append(ft.Card(content=ft.Container(ft.Column([
            ft.Text(u["full_name"], size=18, weight=ft.FontWeight.BOLD),
            body(f"Username: {u['username']} \u00b7 Village: {u.get('village', '')}"),
            body(f"Contact: {u.get('phone') or '-'} \u00b7 {u.get('email') or '-'}"),
            ft.Row([ft.Button("Approve", icon=ft.Icons.CHECK,
                              on_click=decide(manager.approve, u["username"], "Approved.")),
                    ft.OutlinedButton("Decline", icon=ft.Icons.CLOSE,
                                      on_click=decide(manager.reject, u["username"], "Declined."))],
                   wrap=True),
        ], spacing=6), padding=14)))
    pending_section = ([heading(f"Waiting for approval ({len(pending)})"), *pending, ft.Divider()]
                       if pending else [])

    team = []
    for m in manager.messengers:
        team.append(ft.Row([
            ft.Column([ft.Text(m["full_name"], size=16, weight=ft.FontWeight.BOLD),
                       ft.Text(f"{m.get('village', '')} \u00b7 {m.get('phone') or 'no phone'}", size=14)],
                      expand=True, spacing=0),
            ft.OutlinedButton("Reset PIN", on_click=reset_messenger_pin(m["username"])),
        ]))

    return ft.View(
        route="/clinic",
        appbar=app_bar(ctx, "Clinic dashboard"),
        controls=[padded(page_body(
            heading(f"Hello, {user.full_name}"),
            nav_row(ctx),
            *pending_section,
            ft.Row([
                ft.Button("New delivery", icon=ft.Icons.LOCAL_SHIPPING, on_click=open_new_delivery),
                ft.OutlinedButton("Add patient", icon=ft.Icons.PERSON_ADD, on_click=to_add_patient),
                ft.OutlinedButton("Add messenger", icon=ft.Icons.DIRECTIONS_WALK, on_click=to_add_messenger),
                ft.OutlinedButton("Invite staff", icon=ft.Icons.GROUP_ADD, on_click=make_invite),
            ], wrap=True),
            summary,
            ft.Divider(),
            heading("Deliveries"),
            *cards,
            ft.Divider(),
            heading("Messengers"),
            *team,
        ))],
    )
