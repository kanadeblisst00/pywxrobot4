"""自动下载资源：按群或好友标签规则调用 /cdn/image、/cdn/video、/cdn/file。"""

from wxrobot import local_type, resource_types, rows_of

IMAGE = 3
VIDEO = 0x2B
FILE = 0x600000031


def handle(client, message, config, state):
    del state
    kind = local_type(message)
    sender = str(message.get("sender") or "")
    msgid = str(message.get("msgid") or "")
    if not msgid or not sender:
        return
    allowed = _allowed(client, sender, config)
    if kind == IMAGE and "图片" in allowed:
        client.post("/cdn/image", {"msgid": msgid, "wxid": sender, "flag": 2, "wait": True}, write=True)
    elif kind == VIDEO and "视频" in allowed:
        client.post("/cdn/video", {"msgid": msgid, "wxid": sender, "wait": True}, write=True)
    elif kind == FILE and "文件" in allowed:
        client.post("/cdn/file", {"msgid": msgid, "wxid": sender, "wait": True}, write=True)


def _allowed(client, sender: str, config: dict) -> set[str]:
    if sender.endswith("@chatroom"):
        return resource_types((config.get("save_resource_type") or {}).get(sender, ""))
    rules = config.get("user_label_resource_type") or {}
    if not rules:
        return set()
    contacts = rows_of(client.post("/user/list", {}))
    contact = next((item for item in contacts if item.get("wxid") == sender), None)
    if contact is None:
        return set()
    matched: set[str] = set()
    for label in str(contact.get("labels") or "").split(","):
        label = label.strip()
        if label in rules:
            matched.update(resource_types(rules[label]))
    return matched
