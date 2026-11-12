import flet as ft

from views.common import (DropdownOption, app_bar, back_button, body, heading,
                          padded, page_body)


def messages_view(ctx):
    manager = ctx.manager
    user = ctx.current_user()
    try:
        inbox = manager.load_messages()
    except ValueError as err:
        ctx.toast(str(err))
        inbox = []

    if user.role == "clinic":
        options = [DropdownOption(key=m["username"], text=f"{m['full_name']} ({m.get('village', '')})")
                   for m in manager.messengers]
        options += [DropdownOption(key=f"@village:{v}", text=f"Everyone in {v}") for v in manager.villages()]
        options.append(DropdownOption(key="@messengers", text="All messengers"))
        to = ft.Dropdown(label="To", options=options)
    else:
        to = ft.Dropdown(label="To", options=[DropdownOption(key="@clinic", text="The clinic")],
                         value="@clinic")
    text = ft.TextField(label="Message", multiline=True, min_lines=2, max_lines=5, max_length=500)
    by_email = ft.Checkbox(label="Also send by email", value=False)
    by_sms = ft.Checkbox(label="Also send by SMS", value=False)
    error = ft.Text("", color=ft.Colors.RED, size=16)

    def send(e):
        try:
            manager.send_message(to.value, text.value, bool(by_email.value), bool(by_sms.value))
        except ValueError as err:
            error.value = str(err)
            ctx.page.update()
            return
        ctx.toast("Message sent.")
        ctx.refresh()

    cards = []
    for m in inbox:
        who = f"To {m['to_name']}" if m["mine"] else f"From {m['sender_name']}"
        cards.append(ft.Card(content=ft.Container(ft.Column([
            ft.Text(who, size=14, weight=ft.FontWeight.BOLD if m["unread"] else ft.FontWeight.NORMAL),
            body(m["text"]),
            ft.Text(m["time"], size=12),
        ], spacing=4), padding=14)))
    if not cards:
        cards.append(body("No messages yet."))

    return ft.View(
        route="/messages",
        appbar=app_bar(ctx, "Messages"),
        controls=[padded(page_body(
            back_button(ctx),
            heading("New message"),
            to, text,
            ft.Row([by_email, by_sms], wrap=True),
            error,
            ft.Button("Send", icon=ft.Icons.SEND, on_click=send),
            ft.Divider(),
            heading("Inbox"),
            *cards,
        ))],
    )
