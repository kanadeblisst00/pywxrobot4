"""收款消息与 VMQ 集成：按 VMQ 的心跳和收款推送规则计算签名并请求服务。"""

import json
import time
import urllib.parse
import urllib.request

from wxrobot import payment_amount, vmq_sign

PAY_ACCOUNTS = {"gh_3dfda90e39d6", "gh_f0a92aa7146c"}


def handle(client, message, config, state):
    host = str(config.get("host") or "").strip().rstrip("/")
    key = str(config.get("key") or "")
    if not host or not key:
        return
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    sender = str(message.get("sender") or "")
    if sender not in PAY_ACCOUNTS:
        return
    amount = payment_amount(str(message.get("content") or ""))
    if amount is None:
        return
    moment = str(int(time.time() * 1000))
    sign = vmq_sign(f"1{amount}{moment}{key}")
    _get(client, host + "/appPush", {"t": moment, "type": "1", "price": amount, "sign": sign})
    beats = state.bucket("vmq")
    last = int(beats.get("heartbeat_ms") or 0)
    interval = int(config.get("heartbeat_seconds") or 60) * 1000
    now = int(moment)
    if now - last < interval:
        return
    heart = vmq_sign(f"{moment}{key}")
    _get(client, host + "/appHeart", {"t": moment, "type": "1", "sign": heart})
    if client.apply:
        beats["heartbeat_ms"] = now


def _get(client, url: str, params: dict) -> None:
    target = url + "?" + urllib.parse.urlencode(params)
    if not client.apply:
        print(json.dumps({"preview": True, "url": target}, ensure_ascii=False))
        return
    request = urllib.request.Request(target, method="GET")
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"VMQ 返回 HTTP {response.status}")
