# -*- coding: utf-8 -*-
"""B站空间视频列表（wbi 签名版）。（video-to-card skill 版）
用法: python bili_space.py <mid> [页数=1]
输出: bvid | 播放量 | 标题
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
JAR = os.path.join(SKILL_DIR, "jar.txt")

MIXIN_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62,
    11, 36, 20, 34, 44, 52,
]


def load_cookies(jar_path: str) -> str:
    if not os.path.exists(jar_path):
        return ""
    pairs = []
    with open(jar_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                pairs.append(f"{parts[5]}={parts[6].strip()}")
    return "; ".join(pairs)


def http_get(url: str, headers: dict, retries: int = 3) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (412, 429) or e.code >= 500:
                time.sleep(15 * (attempt + 1))
            else:
                raise
    raise last


def get_mixin_key(jar: str) -> str:
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Cookie": jar}
    d = json.loads(http_get("https://api.bilibili.com/x/web-interface/nav", headers))
    img = d["data"]["wbi_img"]["img_url"]
    sub = d["data"]["wbi_img"]["sub_url"]
    raw = (img.rsplit("/", 1)[1].split(".")[0]) + (sub.rsplit("/", 1)[1].split(".")[0])
    return "".join(raw[i] for i in MIXIN_TAB)[:32]


def sign(params: dict, mixin_key: str) -> dict:
    params = dict(params)
    params["wts"] = int(time.time())
    params = {k: "".join(ch for ch in str(v) if ch not in "!'()*")
              for k, v in sorted(params.items())}
    query = urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


def main() -> None:
    mid = sys.argv[1]
    pages = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    jar = load_cookies(JAR)
    mixin_key = get_mixin_key(jar)
    # 2026-09-06 实测：space arc 接口带 Referer/Origin 易 412，改裸 UA + cookie（2026-09-04 教训同源）
    headers = {
        "User-Agent": UA,
        "Cookie": jar,
    }
    for pn in range(1, pages + 1):
        params = sign({"mid": mid, "ps": 30, "pn": pn, "order": "pubdate"}, mixin_key)
        url = "https://api.bilibili.com/x/space/wbi/arc/search?" + urlencode(params)
        d = json.loads(http_get(url, headers))
        if d.get("code") != 0:
            print(f"page {pn}: code={d.get('code')} {d.get('message')}")
            break
        vlist = d["data"]["list"]["vlist"]
        if not vlist:
            break
        for v in vlist:
            print(f"{v['bvid']} | 播放{v.get('play')} | {v['title']}")
        time.sleep(2)


if __name__ == "__main__":
    main()
