"""不连接微信，检查案例里的判断和文件输出。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cases.accept_user_request import handle as accept_friend  # noqa: E402
from cases.enter_room_tip import handle as welcome  # noqa: E402
from cases.room_message_guard import handle as guard  # noqa: E402
from wxrobot import (  # noqa: E402
    Client,
    State,
    append_label,
    duplicate_members,
    friend_request,
    keyword_matches,
    message_kind,
    payment_amount,
    removal_plan,
    render_welcome,
    resource_types,
    sns_permission,
    vmq_sign,
    write_table,
)


def main() -> int:
    assert message_kind({"local_type": 1}) == "text"
    assert message_kind({"local_type": 37}) == "friend_request"
    assert message_kind({"local_type": 10000}) == "system"
    assert message_kind({"local_type": 0x600000031}) == "file"
    assert message_kind({"msg_type": 49, "content": "<msg><appmsg><type>5</type></appmsg></msg>"}) == "link"
    request = friend_request(
        '<msg fromusername="wxid_a" fromnickname="甲" encryptusername="v3_user" ticket="v4ticket" scene="6" content="合作"/>'
    )
    assert request == {
        "username": "wxid_a",
        "nickname": "甲",
        "validation": "合作",
        "wxid": "v3_user",
        "v4": "v4ticket",
        "scene": 6,
    }
    text, atlist = render_welcome("欢迎 @{nick_name}（{nick_name}）", [{"username": "wxid_a", "nick_name": "甲"}])
    assert text == "欢迎 @甲\u2005（甲）"
    assert atlist == "wxid_a"
    assert keyword_matches("学习", "学习,测试", "exact") == "学习"
    assert keyword_matches("我想学习", "学习", "contains") == "学习"
    assert keyword_matches("学习群", "学习", "exact") is None
    assert append_label("1,11", "2") == "1,11,2"
    assert append_label("1,11", "1") == "1,11"
    assert sns_permission("仅聊天") == 8
    assert resource_types("图片&&文件") == {"图片", "文件"}
    duplicates = duplicate_members(
        [
            ("1@chatroom", [{"username": "wxid_a", "nick_name": "甲"}, {"username": "wxid_owner", "is_owner": True}]),
            ("2@chatroom", [{"username": "wxid_a", "nick_name": "甲"}]),
        ]
    )
    assert removal_plan(duplicates, {"wxid_a"}) == [("2@chatroom", "wxid_a")]
    assert payment_amount("微信支付收款0.10元") == "0.1"
    assert vmq_sign("sample") == "5e8ff9bf55ba3508199d22e984129be6"
    with tempfile.TemporaryDirectory() as directory:
        path = write_table(Path(directory) / "rows.csv", [{"wxid": "wxid_a", "nickname": "甲"}])
        assert "wxid_a" in path.read_text(encoding="utf-8-sig")
        state = State(Path(directory) / "state.json")
        assert state.already("demo", "9") is False
        state.remember("demo", "9")
        state.save()
        assert State(Path(directory) / "state.json").already("demo", "9")
    preview = Client("http://127.0.0.1:9", apply=False).post("/send/text", {"wxid": "filehelper", "content": "预览"}, write=True)
    assert preview["preview"] is True and preview["path"] == "/send/text"
    _handlers()
    print(json.dumps({"ok": True}, ensure_ascii=False))


class _Fake:
    apply = True

    def __init__(self):
        self.calls = []
        self.member_reads = 0

    def post(self, path, body=None, write=False):
        self.calls.append((path, body, write))
        if path == "/label/get":
            return {"合作": "11"}
        if path == "/room/getmembers":
            self.member_reads += 1
            rows = [
                {"username": "self", "nick_name": "我", "is_owner": True},
                {"username": "wxid_a", "nick_name": "甲"},
            ]
            if self.member_reads > 1:
                rows.append({"username": "wxid_b", "nick_name": "乙"})
            return rows
        return {"ret": 0}

    def account(self):
        return {"wxid": "self"}


def _handlers() -> None:
    fake = _Fake()
    with tempfile.TemporaryDirectory() as directory:
        state = State(Path(directory) / "state.json")
        request = {
            "local_type": 37,
            "sender": "wxid_a",
            "content": '<msg fromusername="wxid_a" fromnickname="甲" encryptusername="v3" ticket="v4" scene="3" content="合作"/>',
        }
        settings = {
            "keywords": ["合作"],
            "keywords_only": True,
            "classify_label": True,
            "sns_permission": "仅聊天",
            "greetings": "你好",
            "disturb": True,
        }
        accept_friend(fake, request, settings, state)
        accept_friend(
            fake,
            {"local_type": 10000, "sender": "wxid_a", "content": "现在可以开始聊天了"},
            settings,
            state,
        )
        plain = {
            "local_type": 37,
            "sender": "wxid_c",
            "content": '<msg fromusername="wxid_c" fromnickname="丙" encryptusername="v3c" ticket="v4c" scene="1" content="我是丙"/>',
        }
        accept_friend(fake, plain, {"greetings": "你好", "keywords_only": False}, state)
        accept_friend(
            fake,
            {"local_type": 10000, "sender": "wxid_c", "content": "现在可以开始聊天了"},
            {"greetings": "你好"},
            state,
        )
        room = "9@chatroom"
        welcome_config = {"welcome_messages": {room: "欢迎 @{nick_name}"}}
        welcome(fake, {"local_type": 10000, "sender": room, "content": '邀请"甲"加入了群聊'}, welcome_config, state)
        welcome(fake, {"local_type": 10000, "sender": room, "content": '邀请"乙"加入了群聊'}, welcome_config, state)
        guard(
            fake,
            {"local_type": 3, "sender": room, "room_sender": "wxid_a", "msgid": "8", "content": ""},
            {
                "kick_after_warning": False,
                "warning_template": "@{user_name} 停",
                "room_rules": [{"roomid": room, "mode": "allow_selected", "message_types": ["text"]}],
            },
            state,
        )
    agree = fake.calls[1][1]
    assert agree["labels"] == "11" and agree["sns_permissions"] == 8 and agree["add_type"] == 3
    assert fake.calls[2][1]["notify"] is True
    assert any(
        path == "/send/text" and body == {"wxid": "wxid_c", "content": "你好", "atlist": ""}
        for path, body, _write in fake.calls
    )
    assert any(path == "/send/text" and body["content"] == "欢迎 @乙\u2005" for path, body, _write in fake.calls)
    assert any(path == "/send/text" and body["atlist"] == "wxid_a" and "停" in body["content"] for path, body, _write in fake.calls)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
