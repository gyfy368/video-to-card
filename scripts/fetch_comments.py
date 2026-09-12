# -*- coding: utf-8 -*-
"""抓取B站视频评论区热评。（video-to-card skill 版）
用法: python fetch_comments.py <BV号或URL> [--out <目录>] [--limit N]
产物: <out>/<bvid>_comments.txt（热评列表：点赞数 | UP/用户 | 内容）
接口链路: view 接口(裸UA)拿 aid → x/v2/reply/main(热度) → x/v2/reply(legacy) 兜底。
注意: 2026-09-04 实测 web-interface 系接口带 Referer 即 412，故全程裸 UA + Cookie、不带 Referer。
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_SCRIPT_DIR)
# Allow `python scripts/fetch_comments.py` from repo root (not only CWD=scripts/)
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fetch_bili import JAR, ensure_jar  # noqa: E402  同目录复用 cookie 引导
from config import get_media_dir  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

DEFAULT_OUT = get_media_dir()


def get_json(url: str, cookie: str = "") -> dict:
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def get_aid(bvid: str, cookie: str) -> int:
    # 2026-09-06 实测 archive/stat 已 404 下线；view 接口裸 UA 仍可用，作首选
    d = get_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    if d.get("code") == 0:
        return d["data"]["aid"]
    raise SystemExit(f"取 aid 失败 code={d.get('code')} msg={d.get('message')}")


def clean(text: str) -> str:
    return " ".join(text.replace("\r", " ").replace("\n", " ").split())


def fetch_replies(oid: int, limit: int) -> list[dict]:
    # 2026-09-06 实测：评论接口带匿名 cookie 会被风控降级只回 3 条，裸 UA 正常回 20 条，故全程不带 cookie
    out: list[dict] = []

    def collect(replies: list[dict]) -> None:
        for r in replies or []:
            if not r:
                continue
            out.append({
                "name": (r.get("member") or {}).get("uname", "?"),
                "like": r.get("like", 0),
                "msg": clean(r.get("content", {}).get("message", "")),
                "rcount": r.get("rcount", 0),
            })

    # 首选 reply/main（mode=3 热度），翻页直到够数或到底
    next_cur = ""
    for _ in range(10):
        url = ("https://api.bilibili.com/x/v2/reply/main?type=1&oid=" + str(oid)
               + "&mode=3" + (f"&next={next_cur}" if next_cur else ""))
        d = get_json(url)
        if d.get("code") != 0:
            break
        data = d.get("data") or {}
        collect(data.get("replies"))
        cur = data.get("cursor") or {}
        if cur.get("is_end") or len(out) >= limit or not cur.get("next"):
            break
        next_cur = str(cur["next"])
    if out:
        return out

    # 兜底 legacy 接口（sort=2 按点赞）
    for pn in range(1, 6):
        url = (f"https://api.bilibili.com/x/v2/reply?type=1&oid={oid}&pn={pn}&ps=30&sort=2")
        d = get_json(url)
        if d.get("code") != 0:
            break
        page = (d.get("data") or {}).get("replies") or []
        collect(page)
        if len(page) < 30 or len(out) >= limit:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", default=None, help="输出目录（默认 config media_dir 或 ./output）")
    ap.add_argument("--limit", type=int, default=30)
    args = ap.parse_args()

    import re
    m = re.search(r"BV[0-9A-Za-z]{10}", args.src)
    if not m:
        raise SystemExit(f"无法解析 BV 号: {args.src}")
    bvid = m.group(0)
    args.out = get_media_dir(args.out) if args.out else DEFAULT_OUT
    os.makedirs(args.out, exist_ok=True)
    cookie = ensure_jar(JAR)

    aid = get_aid(bvid, cookie)
    print(f"[aid] {bvid} -> {aid}")
    replies = fetch_replies(aid, args.limit)
    if not replies:
        raise SystemExit("未取到评论（可能无评论或接口被限流，稍后重试）")
    replies = replies[:args.limit]
    total = sum(1 for _ in replies)

    path = os.path.join(args.out, f"{bvid}_comments.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# 评论区摘录 {bvid}（按热度，取前 {total} 条）\n")
        for r in replies:
            tail = f"  └该评论下有{r['rcount']}条回复" if r["rcount"] else ""
            f.write(f"[{r['like']}赞] @{r['name']}：{r['msg']}{tail}\n")
    print(f"[comments] 写入 {path}（{total} 条）")


if __name__ == "__main__":
    main()
