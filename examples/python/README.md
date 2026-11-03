# 用 HTTP 接口实现插件案例

这些脚本用 Python 标准库调用 HTTP 插件的 REST 接口，把软件里的消息插件和其他插件做成可以阅读、可以改的案例。运行前先启用 HTTP 基础版或全功能版，并确认当前账号拥有案例用到的接口权限。

案例在软件外面运行，不替换内置插件。`apply` 为 `false` 时，发送、同意好友、邀请、下载、改标签、移出成员和外部推送只打印请求。把配置中的 `apply` 改为 `true`，或加上 `--apply`，才会真正调用这些写接口。

## 准备

1. 复制 `config.example.json` 为 `config.json`。
2. 填写服务配置里的连接地址、端口和 API 认证令牌。只有一个已登录微信时可以不填 `wxpid`；多开时填写目标微信进程 ID。
3. 把要用的案例设为 `"enabled": true`，并换成自己的群 ID、关键词和目录。

消息案例需要软件把新消息推过来。在“系统管理 → 服务配置”的消息回调中填写：

```text
http://127.0.0.1:8787/messages
```

地址要和配置里的 `listen`、`callback_path` 一致。回调需要当前账号具备 HTTP 套餐和消息订阅权限。

## 运行

在本目录执行：

```text
python selfcheck.py
python serve.py --config config.json
python run.py list
python run.py --config config.json export_contacts
python run.py --config config.json --apply dont_revoke --revoke true
```

`serve.py` 持续接收回调。`run.py` 执行一次导出、防撤回、标签分类或去重。导出类命令会立即请求接口并在 `out` 目录写文件。

## 案例与接口

| 案例 | 对应插件 | 调用 |
| --- | --- | --- |
| `accept_user_request` | 自动同意好友申请 | `/user/agreefriend`、`/label/get`、`/send/text`、`/user/receivenotify` |
| `enter_room_tip` | 进群欢迎 | `/room/getmembers`、`/send/text`、`/send/image` |
| `invite_to_room` | 自动邀请好友进群 | `/room/getmembers`、`/room/invitemembers`、`/send/text` |
| `auto_download_resources` | 自动下载资源 | `/user/list`、`/cdn/image`、`/cdn/video`、`/cdn/file` |
| `room_ai_reply` | 群内 AI 自动回复 | 自备的 `/chat/completions`，然后 `/send/text` |
| `room_message_guard` | 群消息规则治理 | `/room/getmembers`、`/send/text`、`/room/deletemembers` |
| `room_qrcode_guard` | 二维码检测与群治理 | `/cdn/image`、`/other/mmdecrypt`、`/send/text`、`/room/deletemembers` |
| `vmq_monitor` | 收款消息与 VMQ 集成 | VMQ 的 `/appPush`、`/appHeart` |
| `we_mp_rss_node` | 公众号文章转发 | 把公众号消息 POST 到自己的 `forward_url` |
| `dont_revoke` | 防撤回 | `/other/dontrevoke` |
| `classify_labels` | 好友标签分类 | `/label/get`、`/room/getmembers`、`/user/list`、`/label/set` |
| `room_members_deduplication` | 群成员去重 | `/room/getmembers`、`/room/deletemembers` |
| `room_msg_summary` | 群消息记录整理与导出 | `/other/chatmsgs` |
| `export_room_members` | 导出群成员 | `/room/getmembers` |
| `export_contacts` | 导出好友列表 | `/user/list` |
| `export_biz_list` | 导出公众号列表 | `/other/getbizlist` |
| `export_room_list` | 导出群列表 | `/room/list` |
| `user_msg_summary` | 好友聊天记录导出 | `/user/list`、`/other/chatmsgs` |
| `download_recent_user_images` | 历史图片补下载 | `/other/chatmsgs`、`/cdn/image` |

回调里的 `local_type` 用来区分文字、图片、好友申请和系统通知。群消息的 `sender` 是群 ID，`room_sender` 是发言成员。

## 和内置插件的差别

- 进群欢迎在第一次看到某个群时只记录当时的成员，之后的入群通知才发送欢迎语。欢迎语里的 `{nick_name}` 会换成新成员昵称，`@{nick_name}` 会同时 @ 他们。单独一行写成 `image:C:\图片.jpg` 时发送图片。
- 自动邀请要求当前账号是目标群的群主或管理员。同一个人十分钟内只邀请一次。
- 好友资源下载按 `/user/list` 返回的标签 ID 匹配；群资源下载按群 ID 匹配。类型用 `图片&&视频&&文件` 这种文本。
- 群规则里的 `allow_selected` 表示只允许列出的类型，`block_selected` 表示禁止列出的类型。群主和管理员不处理。
- 二维码案例下载图片后，运行配置中的 `detector`。命令里写 `{path}`，退出码 0 表示发现二维码。例如 `python detect_qr.py "{path}"`。
- 收款案例只处理微信支付和微信收款助手的消息，签名方式与内置 VMQ 插件相同。
- 公众号案例把 `gh_` 开头的消息转发到自己的地址。内置“公众号文章消息监听”使用单独的采集协议，这个案例不提交节点 Token，也不执行关注或取关。
- 历史图片补下载依赖 `/other/chatmsgs` 能返回图片消息。聊天记录接口若只返回文字、引用和语音，脚本不会伪造下载。

接口字段以 `tools/openapi-3.1.json` 和 [REST 接口参考](../../docs/api-reference.md) 为准。发送类请求不会自动重试；超时不代表微信没有执行。
