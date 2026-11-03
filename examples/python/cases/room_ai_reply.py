"""群内 AI 自动回复：把文本消息发给兼容 OpenAI 的接口，再用 /send/text 回群。"""

import json
import urllib.request

from wxrobot import WxError, message_kind


def handle(client, message, config, state):
    del state
    room = str(message.get("sender") or "")
    speaker = str(message.get("room_sender") or "")
    content = str(message.get("content") or "").strip()
    if message_kind(message) != "text" or not room.endswith("@chatroom") or not content:
        return
    self_id = str(client.account().get("wxid") or "")
    if speaker == self_id:
        return
    rule = next((item for item in config.get("room_configs") or [] if item.get("roomid") == room), None)
    if not rule or not rule.get("api_key"):
        return
    prompt = [
        {"role": "system", "content": str(rule.get("system_prompt") or "你是群聊助手，回答简短。")},
        {"role": "user", "content": content},
    ]
    if not client.apply:
        print(json.dumps({"preview": True, "room": room, "messages": prompt}, ensure_ascii=False))
        return
    answer = _complete(rule, prompt)
    if answer:
        client.post("/send/text", {"wxid": room, "content": answer, "atlist": speaker}, write=True)


def _complete(rule: dict, messages: list[dict]) -> str:
    base = str(rule.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    payload = json.dumps(
        {"model": rule.get("model") or "gpt-4o-mini", "messages": messages},
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(base + "/chat/completions", data=payload, method="POST")
    request.add_header("Content-Type", "application/json; charset=utf-8")
    request.add_header("Authorization", f"Bearer {rule['api_key']}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise WxError(f"模型接口调用失败：{exc}") from exc
    return str(body["choices"][0]["message"]["content"]).strip()
