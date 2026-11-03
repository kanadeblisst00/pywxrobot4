"""运行一次性插件案例，例如导出、防撤回、标签分类和群成员去重。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cases import MANUAL, MESSAGE, TITLES  # noqa: E402
from wxrobot import WxError, client_from, load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="调用 HTTP 接口运行一个插件案例")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--apply", action="store_true", help="执行会修改微信数据的请求")
    parser.add_argument("case", nargs="?", help="案例 ID；用 list 查看全部")
    parser.add_argument("case_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.case in (None, "list"):
        print("消息回调案例：")
        for case_id in MESSAGE:
            print(f"  {case_id}  {TITLES[case_id]}")
        print("一次性案例：")
        for case_id in MANUAL:
            print(f"  {case_id}  {TITLES[case_id]}")
        return 0
    if args.case not in MANUAL:
        print(f"没有名为 {args.case} 的一次性案例。消息案例请运行 serve.py。", file=sys.stderr)
        return 2
    config = load_config(Path(args.config))
    client = client_from(config, True if args.apply else None)
    case_config = (config.get("cases") or {}).get(args.case) or {}
    case_args = list(args.case_args)
    if case_args[:1] == ["--"]:
        case_args = case_args[1:]
    try:
        return int(MANUAL[args.case](client, case_config, case_args) or 0)
    except (WxError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
