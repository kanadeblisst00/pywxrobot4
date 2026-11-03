"""二维码检测与群治理：下载图片，交给本机检测命令，命中后提醒并可移出成员。"""

import subprocess
from pathlib import Path

from wxrobot import message_kind

from .room_message_guard import _moderate


def handle(client, message, config, state):
    room = str(message.get("sender") or "")
    user = str(message.get("room_sender") or "")
    msgid = str(message.get("msgid") or "")
    rooms = set(config.get("rooms") or [])
    if message_kind(message) != "image" or room not in rooms or not user or not msgid.isdigit():
        return
    downloaded = client.post(
        "/cdn/image",
        {"msgid": msgid, "wxid": room, "flag": 2, "wait": True, "timeout": 30},
        write=True,
    )
    path = ""
    if isinstance(downloaded, dict):
        path = str(downloaded.get("path") or "")
    if path.lower().endswith(".dat"):
        output = str(Path(path).with_suffix(".jpg"))
        client.post("/other/mmdecrypt", {"input_path": path, "output_path": output}, write=True)
        path = output
    if not _detected(path, str(config.get("detector") or "")):
        return
    name = _moderate(client, room, user)
    if name is None:
        return
    template = str(config.get("warning_template") or "本群不允许发送二维码。")
    mention = f"@{name}\u2005"
    text = template.replace("@{user_name}", mention).replace("{user_name}", name)
    if mention not in text:
        text = f"{mention} {text}"
    client.post("/send/text", {"wxid": room, "content": text, "atlist": user}, write=True)
    key = f"{room}:{msgid}"
    if key in state.bucket("qr_warned"):
        return
    state.bucket("qr_warned")[key] = True
    if config.get("kick_after_warning", True):
        client.post("/room/deletemembers", {"roomid": room, "wxids": user}, write=True)


def _detected(path: str, detector: str) -> bool:
    if not path or not detector or "{path}" not in detector:
        print({"qrcode": "skipped", "path": path, "reason": "未配置检测命令"})
        return False
    completed = subprocess.run(detector.replace("{path}", path), shell=True, check=False)
    return completed.returncode == 0
