"""群成员去重：比较多个群的成员，预览重复项；确认后从较后的群移除。"""

import argparse

from wxrobot import duplicate_members, removal_plan, rows_of


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="room_members_deduplication", description="比较群成员并可选移除重复成员")
    parser.add_argument("--rooms", help="逗号分隔的群 ID，默认读取配置 rooms")
    parser.add_argument("--selected", default="", help="要处理的成员 wxid，逗号分隔；省略则只预览")
    options = parser.parse_args(args)
    rooms = [item.strip() for item in (options.rooms or ",".join(config.get("rooms") or [])).split(",") if item.strip()]
    if len(rooms) < 2:
        raise SystemExit("请在配置 rooms 或 --rooms 中提供至少两个群")
    snapshots = [(room, rows_of(client.post("/room/getmembers", {"roomid": room}))) for room in rooms]
    duplicates = duplicate_members(snapshots)
    print({"preview": True, "duplicates": duplicates})
    selected = {item.strip() for item in options.selected.split(",") if item.strip()}
    if not selected:
        return 0
    self_id = str(client.account().get("wxid") or "")
    for room, username in removal_plan(duplicates, selected):
        members = rows_of(client.post("/room/getmembers", {"roomid": room}))
        managed = any(
            member.get("username") == self_id and (member.get("is_owner") or member.get("is_admin"))
            for member in members
        )
        if not managed:
            raise SystemExit(f"当前账号不是 {room} 的管理员，已停止移除")
        client.post("/room/deletemembers", {"roomid": room, "wxids": username}, write=True)
    return 0
