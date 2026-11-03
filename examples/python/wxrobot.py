"""调用 rswxrobot HTTP 接口的小客户端，以及案例共用的消息判断。"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


class WxError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


class Client:
    """业务 REST 客户端。写接口在 apply 为假时只打印请求，不发到微信。"""

    def __init__(self, base_url: str, token: str = "", wxpid: int | None = None, apply: bool = False, timeout: float = 35):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self.wxpid = wxpid
        self.apply = apply
        self.timeout = timeout
        self._account: dict | None = None

    def get(self, path: str):
        return self._send("GET", path, None, write=False)

    def post(self, path: str, body: dict | None = None, *, write: bool = False):
        payload = dict(body or {})
        if self.wxpid is not None and "wxpid" not in payload:
            payload["wxpid"] = self.wxpid
        return self._send("POST", path, payload, write=write)

    def account(self) -> dict:
        if self._account is not None:
            return self._account
        users = self.get("/getusers")
        if not isinstance(users, list) or not users:
            raise WxError("没有已登录的微信账号")
        if self.wxpid is None:
            if len(users) != 1:
                raise WxError("存在多个微信进程，请在配置里填写 wxpid")
            self._account = users[0]
            return self._account
        for user in users:
            if user.get("wxpid") == self.wxpid or user.get("pid") == self.wxpid:
                self._account = user
                return user
        raise WxError(f"未找到 wxpid={self.wxpid} 的登录账号")

    def _send(self, method: str, path: str, body: dict | None, *, write: bool):
        if write and not self.apply:
            preview = {"preview": True, "method": method, "path": path, "body": body}
            print(json.dumps(preview, ensure_ascii=False))
            return preview
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json; charset=utf-8")
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise WxError(f"{method} {path} 返回 HTTP {exc.code}", exc.code, detail) from exc
        except urllib.error.URLError as exc:
            raise WxError(f"{method} {path} 连接失败：{exc.reason}") from exc
        if not raw:
            return None
        return json.loads(raw)


class State:
    """案例自己的本地状态。只记录已处理消息、欢迎基线和邀请冷却，不代替微信数据。"""

    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    def bucket(self, name: str) -> dict:
        value = self.data.setdefault(name, {})
        if not isinstance(value, dict):
            value = {}
            self.data[name] = value
        return value

    def already(self, case_id: str, msgid: str) -> bool:
        if not msgid or msgid == "0":
            return False
        return msgid in self.bucket("seen").get(case_id, [])

    def remember(self, case_id: str, msgid: str) -> None:
        if not msgid or msgid == "0":
            return
        seen = self.bucket("seen").setdefault(case_id, [])
        if msgid not in seen:
            seen.append(msgid)
            del seen[:-10000]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or not str(config.get("base_url", "")).strip():
        raise WxError("配置需要包含 base_url")
    return config


def client_from(config: dict, apply: bool | None = None) -> Client:
    wxpid = config.get("wxpid")
    return Client(
        str(config["base_url"]),
        str(config.get("token") or ""),
        None if wxpid in (None, "", 0) else int(wxpid),
        apply if apply is not None else bool(config.get("apply")),
    )


def local_type(message: dict) -> int:
    value = message.get("local_type", message.get("msg_type", 0))
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def message_kind(message: dict) -> str:
    """与软件里消息类型筛选使用同一套 local_type 划分。"""
    value = local_type(message)
    low = value & 0xFFFFFFFF
    if low == 1:
        return "text"
    if low == 3:
        return "image"
    if low == 34:
        return "voice"
    if low in (43, 62):
        return "video"
    if low == 47:
        return "emoji"
    if low == 48:
        return "location"
    if low == 42:
        return "card"
    if low == 37:
        return "friend_request"
    if low in (10000, 10002):
        return "system"
    if low != 49:
        return "other"
    subtype = value >> 32 or _app_subtype(str(message.get("content") or "")) or 0
    return {
        5: "link",
        6: "file",
        19: "forwarded",
        33: "mini_program",
        36: "mini_program",
        57: "quote",
        2000: "transfer",
        2001: "red_packet",
    }.get(subtype, "other")


def _app_subtype(content: str) -> int | None:
    root = xml_root(content)
    if root is None:
        return None
    app = root if _tag(root) == "appmsg" else next((node for node in root.iter() if _tag(node) == "appmsg"), None)
    if app is None:
        return None
    for child in list(app):
        if _tag(child) == "type" and (child.text or "").strip().isdigit():
            return int(child.text.strip())
    return None


def xml_root(content: str) -> ET.Element | None:
    start = content.find("<")
    if start < 0:
        return None
    try:
        return ET.fromstring(content[start:])
    except ET.ParseError:
        return None


def _tag(node) -> str:
    if node is None:
        return ""
    tag = getattr(node, "tag", "")
    return tag.rsplit("}", 1)[-1]


def friend_request(content: str) -> dict | None:
    root = xml_root(content)
    if root is None:
        return None
    node = root if _tag(root) == "msg" else next((item for item in root.iter() if _tag(item) == "msg"), None)
    if node is None:
        return None
    wxid = node.attrib.get("encryptusername") or ""
    ticket = node.attrib.get("ticket") or ""
    username = node.attrib.get("fromusername") or ""
    if not wxid or not ticket or not username:
        return None
    scene = node.attrib.get("scene") or "1"
    return {
        "username": username,
        "nickname": node.attrib.get("fromnickname") or "",
        "validation": node.attrib.get("content") or "",
        "wxid": wxid,
        "v4": ticket,
        "scene": int(scene) if scene.isdigit() else 1,
    }


def sns_permission(name: str) -> int:
    return {"不让他看": 1, "不看他": 2, "不让他看|不看他": 3, "仅聊天": 8}.get(name, 0)


def render_welcome(template: str, members: list[dict]) -> tuple[str, str]:
    names = " ".join(str(member.get("nick_name") or "") for member in members)
    mentions = "".join(f"@{member.get('nick_name') or ''}\u2005" for member in members)
    ids = ",".join(str(member.get("username") or "") for member in members if member.get("username"))
    text = template.replace("@{nick_name}", mentions).replace("{nick_name}", names)
    atlist = ids if "@{nick_name}" in template else ""
    return text, atlist


def keyword_matches(content: str, keywords: str, mode: str) -> str | None:
    for keyword in (item.strip() for item in keywords.split(",")):
        if not keyword:
            continue
        if mode == "exact" and content == keyword:
            return keyword
        if mode != "exact" and keyword in content:
            return keyword
    return None


def label_ids(value) -> list[str]:
    if isinstance(value, list):
        raw = [str(item) for item in value]
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        raw = [str(int(value))]
    else:
        raw = str(value or "").split(",")
    seen: list[str] = []
    for item in raw:
        item = item.strip()
        if item and item not in seen:
            seen.append(item)
    return seen


def append_label(existing, label: str) -> str:
    ids = label_ids(existing)
    if label not in ids:
        ids.append(label)
    return ",".join(ids)


def resource_types(rule: str) -> set[str]:
    return {item.strip() for item in str(rule or "").split("&&") if item.strip()}


def duplicate_members(rooms: list[tuple[str, list[dict]]]) -> list[dict]:
    people: dict[str, dict] = {}
    for room, members in rooms:
        seen: set[str] = set()
        for member in members:
            if member.get("is_owner") or member.get("is_admin"):
                continue
            username = str(member.get("username") or "")
            if not username or username in seen:
                continue
            seen.add(username)
            entry = people.setdefault(username, {"username": username, "member": member, "rooms": []})
            entry["rooms"].append(room)
    return [entry for entry in people.values() if len(entry["rooms"]) > 1]


def removal_plan(duplicates: list[dict], selected: set[str]) -> list[tuple[str, str]]:
    """保留成员最早出现的群，从后面的群里移除。"""
    actions = []
    for row in duplicates:
        username = row["username"]
        if username not in selected:
            continue
        for room in reversed(row["rooms"][1:]):
            actions.append((room, username))
    return actions


def vmq_sign(parts: str) -> str:
    return hashlib.md5(parts.encode("utf-8")).hexdigest()


def payment_amount(content: str) -> str | None:
    match = re.search(r"(?:微信支付收款\s*|收款金额\s*[￥¥]?\s*)([\d.]+)", content)
    if not match:
        return None
    try:
        amount = float(match.group(1))
    except ValueError:
        return None
    if amount <= 0:
        return None
    text = format(amount, "f").rstrip("0").rstrip(".")
    return text if "." in text else text + ".0"


def write_table(path: Path, rows: list[dict], kind: str = "csv") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if kind == "jsonl":
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return path
    if kind == "txt":
        lines = []
        for row in rows:
            stamp = row.get("create_time") or row.get("timestamp") or ""
            speaker = row.get("room_sender_nickname") or row.get("sender_nickname") or row.get("sender") or ""
            content = str(row.get("message_content") or row.get("content") or "").replace("\r", " ").replace("\n", " ")
            lines.append(f"[{stamp}] {speaker}: {content}")
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        return path
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _cell(row.get(key)) for key in fields})
    return path


def _cell(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def rows_of(value) -> list[dict]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        return [row for row in value["data"] if isinstance(row, dict)]
    raise WxError("接口返回的列表格式无法识别")


def stamp() -> int:
    return int(time.time())
