"""进群欢迎：系统通知到来后读取群成员，给新出现的成员发送欢迎语。"""

from wxrobot import message_kind, render_welcome, rows_of


def handle(client, message, config, state):
    room = str(message.get("sender") or "")
    content = str(message.get("content") or "")
    template = (config.get("welcome_messages") or {}).get(room)
    if (
        message_kind(message) != "system"
        or "加入了群聊" not in content
        or not room.endswith("@chatroom")
        or not template
    ):
        return
    members = rows_of(client.post("/room/getmembers", {"roomid": room}))
    current = {str(member.get("username") or "") for member in members}
    current.discard("")
    known = state.bucket("welcome_members")
    previous = set(known.get(room) or [])
    known[room] = sorted(current)
    if not previous:
        return
    added = [member for member in members if str(member.get("username") or "") not in previous]
    if not added:
        return
    text, atlist = render_welcome(str(template), added)
    for line in str(text).splitlines():
        image = line.removeprefix("image:").strip() if line.startswith("image:") else ""
        if image:
            client.post("/send/image", {"wxid": room, "path": image}, write=True)
        elif line.strip():
            client.post("/send/text", {"wxid": room, "content": line, "atlist": atlist}, write=True)
