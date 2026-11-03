"""自动同意好友申请：解析验证消息，调用 /user/agreefriend，再按配置问候或免打扰。"""

from wxrobot import friend_request, message_kind, sns_permission


def handle(client, message, config, state):
    kind = message_kind(message)
    content = str(message.get("content") or "")
    sender = str(message.get("sender") or "")
    pending = state.bucket("friend_requests")
    if kind == "friend_request":
        request = friend_request(content)
        if request is None or request["username"] in pending:
            return
        keywords = [str(item) for item in config.get("keywords") or []]
        validation = request["validation"]
        if config.get("keywords_only") and not any(word and word in validation for word in keywords):
            return
        label = ""
        if config.get("classify_label"):
            matched = next((word for word in keywords if word and word in validation), "")
            labels = client.post("/label/get", {})
            if matched and isinstance(labels, dict) and labels.get(matched) not in (None, "", 0, False):
                label = str(labels[matched])
        client.post(
            "/user/agreefriend",
            {
                "wxid": request["wxid"],
                "v4": request["v4"],
                "remarks": "",
                "labels": label,
                "sns_permissions": sns_permission(str(config.get("sns_permission") or "默认")),
                "add_type": request["scene"],
            },
            write=True,
        )
        pending[request["username"]] = {
            "greeting": not validation or validation == f"我是{request['nickname']}",
            "wxid": request["wxid"],
            "v4": request["v4"],
            "scene": request["scene"],
            "label": label,
        }
        return
    if kind == "system" and "现在可以开始聊天了" in content:
        record = pending.pop(sender, None)
        if not record:
            return
        greeting = str(config.get("greetings") or "").strip()
        if record["greeting"] and greeting:
            client.post("/send/text", {"wxid": sender, "content": greeting, "atlist": ""}, write=True)
        if config.get("disturb"):
            # 与内置插件一致：开启免打扰时向 /user/receivenotify 传入 notify=true。
            client.post("/user/receivenotify", {"wxid": sender, "notify": True}, write=True)
