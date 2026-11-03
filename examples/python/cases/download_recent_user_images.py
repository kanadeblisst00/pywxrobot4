"""历史图片补下载：从 /other/chatmsgs 找出图片消息，再调用 /cdn/image。"""

import argparse

from wxrobot import rows_of, stamp


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="download_recent_user_images", description="补下载好友最近图片")
    parser.add_argument("--users", help="逗号分隔的 wxid，默认读取配置 users")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--max-count", type=int, default=500)
    parser.add_argument("--flag", type=int, choices=(1, 2, 3), default=3, help="1 缩略图，2 压缩图，3 原图")
    options = parser.parse_args(args)
    users = [item.strip() for item in (options.users or ",".join(config.get("users") or [])).split(",") if item.strip()]
    if not users or options.hours < 1 or not 1 <= options.max_count <= 10000:
        raise SystemExit("请提供好友、正整数小时数，以及 1 到 10000 的数量")
    now = stamp()
    downloaded = []
    for wxid in users:
        rows = rows_of(
            client.post(
                "/other/chatmsgs",
                {
                    "wxid": wxid,
                    "start_time": now - options.hours * 3600,
                    "end_time": now,
                    "max_count": options.max_count,
                },
            )
        )
        for row in rows:
            if not _image(row):
                continue
            msgid = str(row.get("server_id") or "")
            if not msgid.isdigit():
                continue
            result = client.post(
                "/cdn/image",
                {"msgid": msgid, "wxid": wxid, "flag": options.flag, "wait": True, "timeout": 30},
                write=True,
            )
            downloaded.append({"wxid": wxid, "msgid": msgid, "result": result})
    print({"downloaded": len(downloaded), "items": downloaded})
    return 0


def _image(row: dict) -> bool:
    kind = str(row.get("message_type") or "")
    content = str(row.get("message_content") or "")
    return "图片" in kind or kind.lower() == "image" or "<img" in content.lower()
