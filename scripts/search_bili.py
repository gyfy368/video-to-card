# -*- coding: utf-8 -*-
"""B站视频搜索（wbi 签名 + 裸 UA 无 Referer 版）。（video-to-card skill 版）
用途: 用户只给"UP主+视频名称"时定位 BV 号（第 0 步）。
用法: python search_bili.py <关键词> [条数=10]
输出: bvid | UP主 | 播放 | 时长 | 标题
注意: 2026-09-04 实测 web-interface 系接口带 Referer 即 412、裸 UA 通过，故本脚本全程无 Referer；
      yt-dlp 的 bilisearch 会 412 时改用本脚本。
"""
import html
import json
import re
import sys
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8")

from bili_space import JAR, UA, get_mixin_key, http_get, load_cookies, sign  # noqa: E402


def clean_title(t: str) -> str:
    t = re.sub(r"<em class=\"keyword\">(.*?)</em>", r"\1", t)
    return html.unescape(t)


def main() -> None:
    keyword = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    jar = load_cookies(JAR)
    mixin_key = get_mixin_key(jar)
    headers = {"User-Agent": UA, "Cookie": jar}  # 无 Referer
    params = sign({"search_type": "video", "keyword": keyword,
                   "page": 1, "page_size": min(max(n, 1), 50)}, mixin_key)
    url = "https://api.bilibili.com/x/web-interface/wbi/search/type?" + urlencode(params)
    d = json.loads(http_get(url, headers))
    if d.get("code") != 0:
        raise SystemExit(f"搜索失败 code={d.get('code')} msg={d.get('message')}"
                         f"{'（可能被限流，静置几分钟或删 jar.txt 换 buvid）' if d.get('code') == -412 else ''}")
    results = d.get("data", {}).get("result") or []
    if not results:
        raise SystemExit("无搜索结果，试试去掉标点/换关键词")
    for r in results[:n]:
        if r.get("type") not in (None, "video", ""+"video"):
            continue
        print(f"{r.get('bvid')} | {r.get('author')} | 播放{r.get('play')} | {r.get('duration')} | {clean_title(r.get('title',''))}")


if __name__ == "__main__":
    main()
