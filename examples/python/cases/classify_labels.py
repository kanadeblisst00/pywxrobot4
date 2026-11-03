"""好友标签分类：把指定群里已是好友的成员追加到同名已有标签。"""

import argparse

from wxrobot import append_label, label_ids, rows_of


def run(client, config, args):
    parser = argparse.ArgumentParser(prog="classify_labels", description="按群为好友追加已有标签")
    parser.parse_args(args)
    rules = config.get("labels") or {}
    labels = client.post("/label/get", {})
    if not isinstance(labels, dict):
        raise SystemExit("标签列表不是对象")
    contacts = {item.get("wxid"): item for item in rows_of(client.post("/user/list", {}))}
    self_id = str(client.account().get("wxid") or "")
    changes = []
    for room, name in rules.items():
        label = labels.get(name)
        if label in (None, "", 0, False):
            print(f"跳过 {room}：标签“{name}”尚不存在")
            continue
        label = str(label)
        for member in rows_of(client.post("/room/getmembers", {"roomid": room})):
            wxid = str(member.get("username") or "")
            if not wxid or wxid == self_id or member.get("is_admin") or member.get("is_owner"):
                continue
            contact = contacts.get(wxid)
            if contact is None:
                continue
            current = label_ids(contact.get("labels"))
            if label in current:
                continue
            merged = append_label(contact.get("labels"), label)
            contact["labels"] = merged
            changes.append({"wxid": wxid, "room": room, "labels": merged})
            client.post("/label/set", {"wxid": wxid, "labels": merged}, write=True)
    print({"count": len(changes), "changes": changes, "applied": client.apply})
    return 0
