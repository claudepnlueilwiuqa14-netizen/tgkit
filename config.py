#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgkit.config —— 本地配置（api_id / api_hash / 手机号）

⚠️ 这些是个人的，只放本机 `tg.local.json`，**绝不进 GitHub**（.gitignore 已排除）。
申请入口：https://my.telegram.org → API development tools
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "tg.local.json")
SESSION = os.path.join(HERE, "tg_session")     # telethon 会话文件（含登录态，同样不进 Git）

DEFAULT = {
    "_说明": "把 api_id / api_hash / phone 填进来，然后跑 python tg.py login",
    "_申请入口": "https://my.telegram.org → API development tools（用自己的号登录就能申请，免费）",
    "api_id": 0,
    "api_hash": "",
    "phone": "",
    "twofa_password": "",
    "_monitor_keywords": ["关键词1", "关键词2"],
    "_push": {"bus_file": "C:/Users/qq/SharedKB/_bus/radar_latest.txt"}
}


def load():
    if not os.path.exists(CFG):
        json.dump(DEFAULT, open(CFG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        raise SystemExit("[!] 已生成模板 %s\n    请填入 api_id / api_hash / phone（在 https://my.telegram.org 申请）" % CFG)
    d = json.load(open(CFG, encoding="utf-8"))
    if not d.get("api_id") or not d.get("api_hash") or not d.get("phone"):
        raise SystemExit("[!] %s 里 api_id / api_hash / phone 还没填" % CFG)
    return d


def keywords():
    try:
        d = json.load(open(CFG, encoding="utf-8"))
        return [k for k in d.get("_monitor_keywords", []) if k]
    except Exception:
        return []
