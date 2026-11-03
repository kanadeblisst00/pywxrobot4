"""好友聊天记录导出：按好友调用 /other/chatmsgs，保存为 jsonl 或 csv。"""

import argparse
from pathlib import Path

from wxrobot import rows_of, stamp, write_table


RANGES = {"2h": 7200, "6h": 21600, "12h": 43200, "1d": 86400, "3d": 259200, "1y": 31536000}


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="user_msg_summary", description="导出好友聊天记录")
    parser.add_argument("--users", help="逗号分隔的 wxid，默认读取配置 users")
    parser.add_argument("--range", choices=tuple(RANGES), default="2h")
    parser.add_argument("--max-count", type=int, default=500)
    parser.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    options = parser.parse_args(args)
    wanted = [item.strip() for item in (options.users or ",".join(config.get("users") or [])).split(",") if item.strip()]
    if not wanted or not 1 <= options.max_count <= 10000:
        raise SystemExit("请提供要导出的好友，数量范围为 1 到 10000")
    contacts = rows_of(client.post("/user/list", {}))
    selected = []
    for item in wanted:
        matches = [row for row in contacts if item in {row.get("wxid"), row.get("wxh")}]
        if len(matches) != 1 or not matches[0].get("wxid"):
            raise SystemExit(f"好友不存在或微信号不唯一：{item}")
        selected.append(matches[0]["wxid"])
    now = stamp()
    start = now - RANGES[options.range]
    account = client.account().get("wxid") or "account"
    directory = Path(config.get("directory") or "out") / str(account)
    written = []
    for wxid in dict.fromkeys(selected):
        rows = rows_of(
            client.post(
                "/other/chatmsgs",
                {"wxid": wxid, "start_time": start, "end_time": now, "max_count": options.max_count},
            )
        )
        path = write_table(directory / f"{wxid}_{now}.{options.format}", rows, options.format)
        written.append({"wxid": wxid, "path": str(path), "count": len(rows)})
    print({"start_time": start, "end_time": now, "users": written})
    return 0
