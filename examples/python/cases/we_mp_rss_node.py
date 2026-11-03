"""公众号文章转发：收到公众号消息后，把原文投递到自己的接收地址。

这是给自有系统用的精简案例。软件内置的公众号文章消息监听使用独立采集协议，
案例不代替节点 Token、关注清单和自动关注。
"""

import json
import urllib.request

from wxrobot import message_kind


def handle(client, message, config, state):
    del state
    sender = str(message.get("sender") or "")
    allowed = set(config.get("whitelist") or [])
    if not sender.startswith("gh_"):
        return
    if config.get("upload_mode", "selected") != "all" and sender not in allowed:
        return
    if message_kind(message) not in {"link", "text", "other"}:
        return
    payload = {
        "wxpid": message.get("wxpid"),
        "account": sender,
        "msgid": str(message.get("msgid") or ""),
        "timestamp": message.get("timestamp"),
        "content": message.get("content") or "",
    }
    target = str(config.get("forward_url") or "").strip()
    if not target:
        print(json.dumps({"preview": True, "article": payload}, ensure_ascii=False))
        return
    if not client.apply:
        print(json.dumps({"preview": True, "url": target, "article": payload}, ensure_ascii=False))
        return
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(target, data=data, method="POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    token = str(config.get("token") or "")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()
