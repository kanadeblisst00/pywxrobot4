"""群消息规则治理：按允许或禁止的消息类型提醒，并可在数秒后移出成员。"""

import time

from wxrobot import message_kind, rows_of


def handle(client, message, config, state):
    room = str(message.get("sender") or "")
    user = str(message.get("room_sender") or "")
    if not room.endswith("@chatroom") or not user:
        return
    rule = next((item for item in config.get("room_rules") or [] if item.get("roomid") == room), None)
    if rule is None:
        return
    kind = message_kind(message)
    selected = set(rule.get("message_types") or [])
    blocked = kind not in selected if rule.get("mode", "allow_selected") == "allow_selected" else kind in selected
    if not blocked:
        return
    warned = state.bucket("guard_warned")
    key = f"{room}:{message.get('msgid')}"
    if key in warned:
        return
    name = _moderate(client, room, user)
    if name is None:
        return
    template = str(config.get("warning_template") or "当前群不允许发送这类消息，请遵守群规。")
    mention = f"@{name}\u2005"
    text = template.replace("@{user_name}", mention).replace("{user_name}", name).replace("{room_name}", room)
    if mention not in text:
        text = f"{mention} {text}"
    client.post("/send/text", {"wxid": room, "content": text, "atlist": user}, write=True)
    warned[key] = True
    if config.get("kick_after_warning", True) and client.apply:
        time.sleep(3)
        _moderate(client, room, user)
        client.post("/room/deletemembers", {"roomid": room, "wxids": user}, write=True)


def _moderate(client, room: str, user: str) -> str | None:
    self_id = str(client.account().get("wxid") or "")
    members = rows_of(client.post("/room/getmembers", {"roomid": room}))
    me = next((member for member in members if member.get("username") == self_id), None)
    target = next((member for member in members if member.get("username") == user), None)
    if not me or not (me.get("is_owner") or me.get("is_admin")) or target is None:
        return None
    if target.get("is_owner") or target.get("is_admin"):
        return None
    return str(target.get("nick_name") or target.get("room_nick_name") or user)
