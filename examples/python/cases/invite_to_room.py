"""自动邀请好友进群：私聊关键词或好友验证内容命中后，调用 /room/invitemembers。"""

import time

from wxrobot import friend_request, keyword_matches, message_kind, rows_of

COOLDOWN_MS = 600_000


def handle(client, message, config, state):
    kind = message_kind(message)
    content = str(message.get("content") or "")
    sender = str(message.get("sender") or "")
    requests = state.bucket("invite_requests")
    if kind == "friend_request":
        request = friend_request(content)
        if request and request["validation"] and request["validation"] != f"我是{request['nickname']}":
            requests[request["username"]] = request["validation"]
        return
    trigger = content
    if kind == "system" and "现在可以开始聊天了" in content:
        trigger = requests.pop(sender, "")
        if not trigger:
            return
    elif kind != "text" or "@chatroom" in sender:
        return
    now = int(message.get("timestamp") or time.time())
    if now < 10_000_000_000:
        now *= 1000
    self_id = ""
    invited = state.bucket("invitations")
    for room, rule in (config.get("keywords") or {}).items():
        if not isinstance(rule, dict):
            continue
        keyword = keyword_matches(trigger, str(rule.get("keywords") or ""), str(rule.get("match_mode") or "exact"))
        if not keyword:
            continue
        if not self_id:
            self_id = str(client.account().get("wxid") or "")
        members = rows_of(client.post("/room/getmembers", {"roomid": room}))
        managed = any(
            (member.get("username") == self_id) and (member.get("is_owner") or member.get("is_admin"))
            for member in members
        )
        if not managed:
            continue
        last = int(invited.get(sender) or 0)
        if now and now - last < COOLDOWN_MS:
            client.post(
                "/send/text",
                {"wxid": sender, "content": f"你已被邀请进群({keyword}), 请勿重复发送", "atlist": ""},
                write=True,
            )
            return
        if any(member.get("username") == sender for member in members):
            client.post(
                "/send/text",
                {"wxid": sender, "content": f"你已是{keyword}中的成员,无需邀请", "atlist": ""},
                write=True,
            )
            return
        result = client.post("/room/invitemembers", {"roomid": room, "wxids": sender}, write=True)
        if not (isinstance(result, dict) and result.get("preview")):
            invited[sender] = now or last
        return
