"""导出好友列表：调用 /user/list，保存为 CSV。"""

from pathlib import Path

from wxrobot import rows_of, write_table


def run(client, config, args):
    if args:
        raise SystemExit("export_contacts 不需要额外参数")
    wxid = client.account().get("wxid") or "account"
    rows = rows_of(client.post("/user/list", {}))
    path = write_table(Path(config.get("directory") or "out") / f"{wxid}_contacts.csv", rows)
    print({"path": str(path), "count": len(rows)})
    return 0
