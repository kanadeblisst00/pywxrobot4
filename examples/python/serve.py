"""接收服务配置里的消息回调，并按已启用的案例处理。"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from cases import MESSAGE, TITLES  # noqa: E402
from wxrobot import State, WxError, client_from, load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="用 HTTP 回调运行消息插件案例")
    parser.add_argument("--config", default="config.json", help="由 config.example.json 复制而来")
    parser.add_argument("--apply", action="store_true", help="真正调用会发送、同意、邀请、下载或移出成员的接口")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    client = client_from(config, True if args.apply else None)
    state = State(Path(config.get("state_file") or "out/cases-state.json"))
    listen = str(config.get("listen") or "127.0.0.1:8787")
    host, port_text = listen.rsplit(":", 1)
    path = str(config.get("callback_path") or "/messages")
    if not path.startswith("/"):
        path = "/" + path
    lock = threading.Lock()
    enabled = [name for name, item in (config.get("cases") or {}).items() if isinstance(item, dict) and item.get("enabled")]

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path.split("?", 1)[0].rstrip("/") != path.rstrip("/"):
                self._reply(404, {"detail": "not_found"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                message = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError):
                self._reply(400, {"detail": "invalid_json"})
                return
            if not isinstance(message, dict):
                self._reply(422, {"detail": "invalid_message"})
                return
            errors = dispatch(client, state, config, message, lock)
            self._reply(200, {"accepted": True, "errors": errors})

        def log_message(self, fmt: str, *values) -> None:
            print(f"[callback] {self.address_string()} {fmt % values}")

        def _reply(self, status: int, body: dict) -> None:
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer((host, int(port_text)), Handler)
    print(f"回调地址：http://{host}:{port_text}{path}")
    print("请把这个地址填到“系统管理 → 服务配置”的消息回调。")
    print("已启用：" + ("、".join(TITLES.get(name, name) for name in enabled) or "无"))
    print("写操作：" + ("执行" if client.apply else "只预览"))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("已停止")
    finally:
        server.server_close()
    return 0


def dispatch(client, state: State, config: dict, message: dict, lock: threading.Lock) -> list[str]:
    errors = []
    msgid = str(message.get("msgid") or "")
    with lock:
        for case_id, handler in MESSAGE.items():
            case = (config.get("cases") or {}).get(case_id) or {}
            if not case.get("enabled") or state.already(case_id, msgid):
                continue
            try:
                handler(client, message, case, state)
            except (WxError, OSError, ValueError, RuntimeError) as exc:
                errors.append(f"{case_id}: {exc}")
                print(f"[{case_id}] {exc}")
            else:
                state.remember(case_id, msgid)
        state.save()
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
