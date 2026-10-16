#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgkit —— Telegram 完全控制套件（你自己的号）

能力（全部按键级）：
  login      手机号 + 验证码 + 两步验证登录，session 持久化（之后免登录）
  me         当前登录账号信息
  dialogs    列出所有对话（群/频道/私聊）+ 未读数
  export     全量导出：消息历史 / 群成员 / 频道帖子 / 媒体文件
  search     全局搜索（Telegram 官方全局搜）+ 本地已抓数据全文检索
  monitor    实时关键词监控（新消息命中即推送到总线）
  send       发消息 / 转发 / 编辑 / 删除 / 置顶 / 回复
  admin      群管理：踢人 / 禁言 / 解禁 / 置顶 / 改标题 / 邀人
  media      批量下载媒体
  serve      把以上全部包成 HTTP API

用法：
  python tg.py login
  python tg.py dialogs
  python tg.py search "关键词"
  python tg.py monitor
"""
import argparse, asyncio, json, os, sys, time, re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C

from telethon import TelegramClient, events, functions, types
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import User, Chat, Channel


def client():
    cfg = C.load()
    return TelegramClient(C.SESSION, cfg["api_id"], cfg["api_hash"])


async def _login():
    cfg = C.load()
    cl = client()
    await cl.connect()
    if await cl.is_user_authorized():
        me = await cl.get_me()
        print("[✓] 已登录：%s (id=%s)" % (_name(me), me.id))
        await cl.disconnect(); return
    phone = cfg["phone"]
    try:
        await cl.send_code_request(phone)
    except FloodWaitError as e:
        print("[x] Telegram 限流，需等 %d 秒" % e.seconds); await cl.disconnect(); return
    code = input("请输入 Telegram 验证码：").strip()
    try:
        await cl.sign_in(phone, code)
    except SessionPasswordNeededError:
        pwd = cfg.get("twofa_password") or input("两步验证密码：").strip()
        await cl.sign_in(password=pwd)
    me = await cl.get_me()
    print("[✓] 登录成功：%s (id=%s)" % (_name(me), me.id))
    print("    session 已存 %s，下次免登录" % C.SESSION)
    await cl.disconnect()


def _name(e):
    if e is None:
        return "?"
    if isinstance(e, User):
        return " ".join(x for x in [e.first_name, e.last_name] if x) or e.username or str(e.id)
    return getattr(e, "title", None) or getattr(e, "username", None) or str(e.id)


def _peer(e):
    return "@" + e.username if getattr(e, "username", None) else str(e.id)


def _dump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    return path


# ---------------------------------------------------------------- 列出对话
async def a_dialogs(limit=200, unread_only=False):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录，先跑 python tg.py login"); await cl.disconnect(); return []
    out = []
    async for d in cl.iter_dialogs(limit=limit):
        if unread_only and not d.unread_count:
            continue
        out.append({
            "name": _name(d.entity), "id": d.entity.id,
            "username": getattr(d.entity, "username", None),
            "type": "user" if isinstance(d.entity, User) else ("channel" if getattr(d.entity, "broadcast", False) else "group"),
            "unread": d.unread_count, "participants": getattr(d.entity, "participants_count", None),
            "last_msg": (d.message.message or "")[:80] if d.message else "",
            "date": str(d.date)[:19] if d.date else "",
        })
    await cl.disconnect()
    print("\n%-38s %-10s %-6s %-6s %s" % ("名称", "类型", "未读", "人数", "最近消息"))
    print("-" * 110)
    for d in out:
        print("%-38s %-10s %-6s %-6s %s" % (d["name"][:36], d["type"], d["unread"],
                                            d["participants"] or "-", d["last_msg"][:40]))
    print("\n[✓] 共 %d 个对话 → tg.out/dialogs.json" % len(out))
    _dump(out, os.path.join(C.HERE, "tg.out", "dialogs.json"))
    return out


# ---------------------------------------------------------------- 全量导出
async def a_export(target, limit=2000, with_media=False, outdir=None):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    ent = await cl.get_entity(target)
    name = re.sub(r"[^\w\-]", "_", _name(ent))[:40]
    base = outdir or os.path.join(C.HERE, "tg.out", "export", name)
    os.makedirs(base, exist_ok=True)

    msgs = []
    n = 0
    async for m in cl.iter_messages(ent, limit=limit):
        n += 1
        msgs.append({
            "id": m.id, "date": str(m.date)[:19],
            "from": _name(m.sender) if m.sender else "",
            "from_id": m.sender_id,
            "text": m.message or "",
            "reply_to": m.reply_to_msg_id if m.reply_to else None,
            "forwards": m.forwards, "views": getattr(m, "views", None),
            "media": bool(m.media),
            "media_type": type(m.media).__name__ if m.media else None,
            "url": getattr(m, "url", None),
        })
    _dump(msgs, os.path.join(base, "messages.json"))
    print("[✓] 消息导出 %d 条 → %s" % (len(msgs), os.path.join(base, "messages.json")))

    # 群成员
    members = []
    try:
        async for u in cl.iter_participants(ent, limit=10000):
            members.append({"id": u.id, "name": _name(u), "username": u.username,
                            "bot": u.bot, "deleted": u.deleted})
        _dump(members, os.path.join(base, "members.json"))
        print("[✓] 成员导出 %d 人 → %s" % (len(members), os.path.join(base, "members.json")))
    except Exception as e:
        print("[!] 成员导出失败（可能是频道或权限不足）：%s" % str(e)[:120])

    if with_media:
        cnt = 0
        for m in msgs:
            pass
        print("[i] 开始下载媒体…")
        async for m in cl.iter_messages(ent, limit=limit):
            if m.media:
                try:
                    p = await cl.download_media(m, file=os.path.join(base, "media"))
                    cnt += 1
                    if cnt % 20 == 0:
                        print("    已下载 %d 个媒体" % cnt)
                except Exception:
                    pass
        print("[✓] 媒体下载 %d 个 → %s/media/" % (cnt, base))
    await cl.disconnect()


# ---------------------------------------------------------------- 全局搜索
async def a_search(q, limit=50):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    res = []
    try:
        async for d in cl.iter_dialogs():
            try:
                async for m in cl.iter_messages(d.entity, search=q, limit=5):
                    res.append({"chat": _name(d.entity), "chat_id": d.entity.id,
                                "msg_id": m.id, "date": str(m.date)[:19],
                                "from": _name(m.sender) if m.sender else "",
                                "text": (m.message or "")[:300], "url": getattr(m, "url", None)})
            except Exception:
                continue
            if len(res) >= limit:
                break
    except Exception as e:
        print("[!] 搜索出错：%s" % str(e)[:150])
    await cl.disconnect()
    print("\n=== 全局搜索「%s」命中 %d 条 ===" % (q, len(res)))
    for r in res[:limit]:
        print("  [%s] %s · %s\n      %s" % (r["date"], r["chat"], r["from"], r["text"][:90].replace("\n", " ")))
    _dump(res, os.path.join(C.HERE, "tg.out", "search_%s.json" % re.sub(r"[^\w]", "", q)[:20]))
    print("\n[✓] 已存 tg.out/search_*.json")
    return res


# ---------------------------------------------------------------- 本地检索（对已抓数据全文搜）
def local_search(q, root=None):
    root = root or os.path.join(C.HERE, "tg.out")
    hits = []
    for dp, dns, fns in os.walk(root):
        for f in fns:
            if not f.endswith(".json"):
                continue
            p = os.path.join(dp, f)
            try:
                data = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                data = [data]
            for item in data:
                if not isinstance(item, dict):
                    continue
                blob = json.dumps(item, ensure_ascii=False)
                if q.lower() in blob.lower():
                    hits.append({"file": os.path.relpath(p, root), "item": item})
    print("本地检索「%s」命中 %d 条（范围 %s）" % (q, len(hits), root))
    for h in hits[:40]:
        t = (h["item"].get("text") or h["item"].get("title") or h["item"].get("word") or "")[:100]
        print("  [%s] %s" % (h["file"], t.replace("\n", " ")))
    return hits


# ---------------------------------------------------------------- 实时监控
async def a_monitor(keywords=None, push_bus=True):
    kws = keywords or C.keywords()
    if not kws:
        print("[!] config 里 _monitor_keywords 为空，先把关键词填进去")
        return
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    me = await cl.get_me()
    print("[✓] 监控启动：%s" % ", ".join(kws))
    print("    命中即写入 tg.out/monitor_hits.jsonl（Ctrl+C 停止）")

    @cl.on(events.NewMessage)
    async def handler(event):
        try:
            txt = event.message.message or ""
        except Exception:
            return
        for k in kws:
            if k and k.lower() in txt.lower():
                chat = await event.get_chat()
                rec = {"ts": str(datetime.now())[:19], "keyword": k,
                       "chat": _name(chat), "chat_id": chat.id,
                       "from": _name(event.sender) if event.sender else "",
                       "text": txt[:500], "msg_id": event.message.id}
                p = os.path.join(C.HERE, "tg.out", "monitor_hits.jsonl")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                print("  [命中:%s] %s · %s | %s" % (k, rec["chat"], rec["from"], txt[:70].replace("\n", " ")))
                break
    await cl.run_until_disconnected()


# ---------------------------------------------------------------- 发送/操作
async def a_send(target, text):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    m = await cl.send_message(target, text)
    print("[✓] 已发送到 %s (msg_id=%s)" % (target, m.id))
    await cl.disconnect()


async def a_admin(target, action, user=None, arg=None):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    ent = await cl.get_entity(target)
    if action == "kick" and user:
        u = await cl.get_entity(user)
        await cl.kick_participant(ent, u); print("[✓] 已踢出 %s" % _name(u))
    elif action == "mute" and user:
        u = await cl.get_entity(user)
        await cl.edit_permissions(ent, u, until_date=0, send_messages=False)
        print("[✓] 已禁言 %s（永久）" % _name(u))
    elif action == "unmute" and user:
        u = await cl.get_entity(user)
        await cl.edit_permissions(ent, u, send_messages=True)
        print("[✓] 已解禁 %s" % _name(u))
    elif action == "pin" and arg:
        m = await cl.get_messages(ent, ids=int(arg))
        await cl.pin_message(ent, m); print("[✓] 已置顶 msg %s" % arg)
    elif action == "title" and arg:
        await cl(functions.channels.EditTitleRequest(channel=ent, title=arg))
        print("[✓] 标题改为 %s" % arg)
    else:
        print("[x] 未知操作 %s（支持 kick/mute/unmute/pin/title）" % action)
    await cl.disconnect()


# ---------------------------------------------------------------- 媒体下载
async def a_media(target, limit=200, outdir=None):
    cl = client(); await cl.connect()
    if not await cl.is_user_authorized():
        print("[x] 未登录"); await cl.disconnect(); return
    ent = await cl.get_entity(target)
    name = re.sub(r"[^\w\-]", "_", _name(ent))[:40]
    base = outdir or os.path.join(C.HERE, "tg.out", "export", name, "media")
    os.makedirs(base, exist_ok=True)
    cnt = 0
    async for m in cl.iter_messages(ent, limit=limit):
        if m.media:
            try:
                await cl.download_media(m, file=base); cnt += 1
                if cnt % 20 == 0:
                    print("    已下载 %d" % cnt)
            except Exception:
                pass
    print("[✓] 媒体下载 %d 个 → %s" % (cnt, base))
    await cl.disconnect()


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(description="tgkit —— Telegram 完全控制")
    ap.add_argument("cmd", choices=["login", "me", "dialogs", "export", "search",
                                    "lsearch", "monitor", "send", "admin", "media", "serve"])
    ap.add_argument("target", nargs="?", default=None)
    ap.add_argument("--limit", type=int, default=2000)
    ap.add_argument("--media", action="store_true")
    ap.add_argument("--text", default=None)
    ap.add_argument("--user", default=None)
    ap.add_argument("--arg", default=None)
    ap.add_argument("--unread", action="store_true")
    a = ap.parse_args()

    if a.cmd == "login":
        asyncio.run(_login())
    elif a.cmd == "me":
        cl = client(); cl.connect()
        if cl.is_user_authorized():
            import asyncio as _a
            me = _a.get_event_loop().run_until_complete(cl.get_me())
            print("已登录：%s (id=%s, phone=%s)" % (_name(me), me.id, me.phone))
        else:
            print("未登录")
        cl.disconnect()
    elif a.cmd == "dialogs":
        asyncio.run(a_dialogs(a.limit, a.unread))
    elif a.cmd == "export":
        if not a.target:
            print("用法：python tg.py export <群/频道/@用户名/id> [--limit 2000] [--media]"); return
        asyncio.run(a_export(a.target, a.limit, a.media))
    elif a.cmd == "search":
        if not a.target:
            print("用法：python tg.py search <关键词>"); return
        asyncio.run(a_search(a.target, a.limit or 50))
    elif a.cmd == "lsearch":
        local_search(a.target or "")
    elif a.cmd == "monitor":
        asyncio.run(a_monitor())
    elif a.cmd == "send":
        asyncio.run(a_send(a.target, a.text or ""))
    elif a.cmd == "admin":
        asyncio.run(a_admin(a.target, a.text or "", a.user, a.arg))
    elif a.cmd == "media":
        asyncio.run(a_media(a.target, a.limit))
    elif a.cmd == "serve":
        import server
        server.main()


if __name__ == "__main__":
    main()
