"""导出群列表：调用 /room/list，保存为 CSV。"""

from pathlib import Path

from wxrobot import rows_of, write_table


def run(client, config, args):
    if args:
        raise SystemExit("export_room_list 不需要额外参数")
    wxid = client.account().get("wxid") or "account"
    rows = rows_of(client.post("/room/list", {}))
    path = write_table(Path(config.get("directory") or "out") / f"{wxid}_room_list.csv", rows)
    print({"path": str(path), "count": len(rows)})
    return 0
