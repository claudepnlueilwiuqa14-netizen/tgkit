#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tgkit.server —— 把 Telegram 完全控制包成 HTTP API（纯标准库）

  GET  /health                     存活 + 登录态
  GET  /api/dialogs?limit=200      所有对话
  GET  /api/export?target=xxx&limit=2000&media=0   全量导出
  GET  /api/search?q=关键词&limit=50              全局搜索
  GET  /api/lsearch?q=关键词                       本地已抓数据检索
  GET  /api/monitor_hits                          实时监控命中记录
  POST /api/send                 {"target":"...","text":"..."}
  POST /api/admin                {"target":"...","action":"kick|mute|unmute|pin|title","user":"...","arg":"..."}
"""
import argparse, asyncio, json, os, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config as C
import tg as T


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _j(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        p, q = u.path, urllib.parse.parse_qs(u.query)
        g = lambda k, d=None: (q.get(k) or [d])[0]
        try:
            if p == "/health":
                cl = T.client()
                cl.connect()
                ok = cl.is_user_authorized()
                me = None
                if ok:
                    me = T._name(asyncio.get_event_loop().run_until_complete(cl.get_me()))
                cl.disconnect()
                return self._j(200, {"ok": True, "logged_in": ok, "account": me})
            if p == "/api/dialogs":
                d = asyncio.run(T.a_dialogs(int(g("limit", "200")), g("unread") == "1"))
                return self._j(200, {"count": len(d), "dialogs": d})
            if p == "/api/export":
                t = g("target")
                if not t:
                    return self._j(400, {"error": "缺 target"})
                asyncio.run(T.a_export(t, int(g("limit", "2000")), g("media") == "1"))
                return self._j(200, {"ok": True, "target": t})
            if p == "/api/search":
                r = asyncio.run(T.a_search(g("q") or "", int(g("limit", "50"))))
                return self._j(200, {"q": g("q"), "count": len(r), "results": r})
            if p == "/api/lsearch":
                r = T.local_search(g("q") or "")
                return self._j(200, {"count": len(r), "results": r[:200]})
            if p == "/api/monitor_hits":
                p2 = os.path.join(C.HERE, "tg.out", "monitor_hits.jsonl")
                lines = open(p2, encoding="utf-8").read().strip().split("\n") if os.path.exists(p2) else []
                recs = [json.loads(x) for x in lines if x.strip()]
                return self._j(200, {"count": len(recs), "hits": recs[-200:]})
            return self._j(404, {"error": "not found", "path": p})
        except Exception as e:
            return self._j(500, {"error": str(e)[:300]})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return self._j(400, {"error": "bad json"})
        try:
            if u.path == "/api/send":
                asyncio.run(T.a_send(body.get("target"), body.get("text") or ""))
                return self._j(200, {"ok": True})
            if u.path == "/api/admin":
                asyncio.run(T.a_admin(body.get("target"), body.get("action"),
                                      body.get("user"), body.get("arg")))
                return self._j(200, {"ok": True})
            return self._j(404, {"error": "not found"})
        except Exception as e:
            return self._j(500, {"error": str(e)[:300]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8810)
    a = ap.parse_args()
    print("[i] tgkit http://127.0.0.1:%d" % a.port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
