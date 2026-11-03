"""群消息记录整理与导出：调用 /other/chatmsgs，写成 txt 或 csv。"""

import argparse
from pathlib import Path

from wxrobot import rows_of, stamp, write_table


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="room_msg_summary", description="导出一个群的聊天记录")
    parser.add_argument("--room", required=True)
    parser.add_argument("--start", type=int, default=0, help="开始时间，Unix 秒；0 表示两小时前")
    parser.add_argument("--end", type=int, default=0, help="结束时间，Unix 秒；0 表示现在")
    parser.add_argument("--max-count", type=int, default=500)
    parser.add_argument("--format", choices=("txt", "csv"), default="txt")
    options = parser.parse_args(args)
    now = stamp()
    start = options.start or now - 7200
    end = options.end or now
    if not 1 <= options.max_count <= 2000 or start > end:
        raise SystemExit("数量需在 1 到 2000 之间，且开始时间不能晚于结束时间")
    rows = rows_of(
        client.post(
            "/other/chatmsgs",
            {"wxid": options.room, "start_time": start, "end_time": end, "max_count": options.max_count},
        )
    )
    directory = Path(config.get("directory") or "out")
    path = write_table(directory / f"{options.room}_{now}.{options.format}", rows, options.format)
    print({"path": str(path), "count": len(rows)})
    return 0
