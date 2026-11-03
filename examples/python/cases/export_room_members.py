"""导出群成员：调用 /room/getmembers，保存为 CSV。"""

import argparse
from pathlib import Path

from wxrobot import rows_of, write_table


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="export_room_members", description="导出一个群的成员")
    parser.add_argument("--room", required=True)
    options = parser.parse_args(args)
    rows = rows_of(client.post("/room/getmembers", {"roomid": options.room}))
    path = write_table(Path(config.get("directory") or "out") / f"{options.room}_members.csv", rows)
    print({"path": str(path), "count": len(rows)})
    return 0
