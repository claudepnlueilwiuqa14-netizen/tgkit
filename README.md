# tgkit · Telegram 完全控制套件

你自己的 Telegram 号 / 机器人，**按键级完全控制 + 全站搜索爬取**。基于 Telethon（MTProto 官方协议），比 Bot API 强得多——Bot API 做不到的（读任意群历史、抓成员、全局搜、管理群）这里全都能做。

> 2026-10-16 · telethon 1.45.0 实测安装通过，三模块语法/导入全绿。
> ⚠️ 只用在你**自己有权限**的号和群上。爬别人私有群、批量加人、发垃圾信息会封号。

## 一、30 秒上手

```bash
pip install telethon

# 1. 申请 API 凭证（免费，用自己的号登录）
#    https://my.telegram.org → API development tools → 记下 api_id 和 api_hash

# 2. 填配置（首次运行会自动生成模板 tg.local.json）
python tg.py login
#    → 输入手机号收到的验证码 → 有两步验证就输密码
#    → session 落盘，之后永久免登录

# 3. 开始用
python tg.py dialogs                 # 所有对话
python tg.py search "关键词"          # 全局搜索
python tg.py export <目标> --media    # 全量导出 + 媒体
python tg.py monitor                 # 实时关键词监控
```

## 二、能力清单（按键级）

| 命令 | 干什么 |
|---|---|
| `login` | 手机号+验证码+两步验证登录，session 持久化 |
| `me` | 当前账号信息 |
| `dialogs [--unread]` | 所有群/频道/私聊 + 未读数 + 人数 + 最近消息 |
| `export <目标> [--limit N] [--media]` | 全量导出消息历史 + 群成员 + 媒体文件 |
| `search <关键词>` | **Telegram 全局搜索**（跨所有对话搜，官方接口） |
| `lsearch <关键词>` | 对**已抓到本地**的数据全文检索（离线秒出） |
| `monitor` | 实时关键词监控，命中即写 `monitor_hits.jsonl` |
| `send <目标> --text "..."` | 发消息 |
| `admin <目标> --text kick --user @xxx` | 群管理：kick / mute / unmute / pin / title |
| `media <目标> [--limit N]` | 批量下载媒体 |
| `serve [--port 8810]` | 全部能力包成 HTTP API |

`<目标>` 可以是 `@用户名`、`-100` 开头的频道 ID、或手机号。

## 三、HTTP API

```bash
python tg.py serve --port 8810

curl "http://127.0.0.1:8810/health"
curl "http://127.0.0.1:8810/api/dialogs?limit=200&unread=1"
curl "http://127.0.0.1:8810/api/search?q=关键词&limit=50"
curl "http://127.0.0.1:8810/api/lsearch?q=关键词"
curl "http://127.0.0.1:8810/api/monitor_hits"
curl -X POST "http://127.0.0.1:8810/api/send" -d '{"target":"@xxx","text":"hi"}'
curl -X POST "http://127.0.0.1:8810/api/admin" -d '{"target":"@group","action":"pin","arg":"123"}'
```

## 四、实时监控怎么用

改 `tg.local.json`：

```json
"_monitor_keywords": ["空投", "BTC", "招聘", "你的品牌词"]
```

```bash
python tg.py monitor
```

之后任何对话里出现这些词，立刻写入 `tg.out/monitor_hits.jsonl`，字段含
`ts / keyword / chat / chat_id / from / text / msg_id`。可配合已有的热点雷达做「热词出现即报警」。

## 五、导出产物结构

```
tg.out/
├── dialogs.json                    所有对话
├── search_<关键词>.json             全局搜索结果
├── monitor_hits.jsonl              实时监控命中（追加写）
└── export/<目标名>/
    ├── messages.json               消息历史（含 from/date/reply/views/media）
    ├── members.json                群成员（id/name/username/bot）
    └── media/                      下载的图片视频文件
```

`messages.json` 每条字段：`id / date / from / from_id / text / reply_to / forwards / views / media / media_type / url`

## 六、接你自己的系统

`lsearch` 直接读 `tg.out/` 下所有 JSON，所以你可以：
- 把导出的 `messages.json` 喂给本地 LLM 网关（`http://127.0.0.1:8787/v1`）做摘要/情感/实体抽取
- 用 `analyze` 那套共现词方法分析群聊热词
- 监控命中直接推到 `SharedKB/_bus/` 让五端都看到

## 七、注意事项

- **session 文件 = 你的登录态**，`tg_session*` 已在 `.gitignore` 里，不会误传 GitHub
- `api_id / api_hash / 手机号` 只在 `tg.local.json`，同样不进 Git
- Telegram 对高频调用会限流（`FloodWaitError`），代码已捕获并提示需等待秒数
- 频道导出成员需要你是管理员且群不太大；权限不足会明确报错而不是静默失败
- 全局搜索 `search` 是逐对话遍历实现的，对话多时会慢——**先 `export` 再 `lsearch` 更快**
