# -*- coding: utf-8 -*-
"""通过 aid 反查B站视频的 UP 主信息（用于按名字定位 UP 主的 mid）。
用法: python find_up.py <aid1> <aid2> ...
提示：先用 yt-dlp 拿搜索结果 id：yt-dlp --flat-playlist --print "%(id)s" "bilisearch10:关键词"
"""
import json
import sys
import time
import urllib.error
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
}


def get_json(url: str) -> dict:
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError):
                if e.code in (412, 429) or e.code >= 500:
                    wait = 10 * (attempt + 1)
                    print(f"[find_up] HTTP {e.code}，退避 {wait}s 后重试({attempt + 1}/3)...", flush=True)
                    time.sleep(wait)
                else:
                    raise
            else:
                wait = 10 * (attempt + 1)
                print(f"[find_up] 网络错误 {e}，退避 {wait}s 后重试({attempt + 1}/3)...", flush=True)
                time.sleep(wait)
    raise last


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python find_up.py <aid1> [aid2 ...]", file=sys.stderr)
        print("Usage: python find_up.py <aid1> [aid2 ...]", file=sys.stderr)
        raise SystemExit(2)
    for aid in sys.argv[1:]:
        try:
            d = get_json(f"https://api.bilibili.com/x/web-interface/view?aid={aid}")
            if d.get("code") == 0:
                v = d["data"]
                print(f"{aid} | UP主: {v['owner']['name']} (mid={v['owner']['mid']}) | 《{v['title']}》 | 时长{v['duration']}秒")
            else:
                print(f"{aid} | code={d.get('code')} {d.get('message')}")
        except Exception as e:  # noqa: BLE001
            print(f"{aid} | ERROR {e}")


if __name__ == "__main__":
    main()
