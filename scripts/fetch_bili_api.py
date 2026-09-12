# -*- coding: utf-8 -*-
"""B站直连 API 抓取（风控期备用通道，单请求+慢节奏，绕开 yt-dlp）。
用法: python fetch_bili_api.py <BV号或URL> [--out <媒体目录>]
流程: view(元信息+cid) -> playurl(免签名优先,失败转 wbi 签名) -> 下载 dash 音频 -> ffmpeg 16k wav
设计要点: 每个 HTTP 阶段只发一次请求；遇 412 静默 60s 仅重试一次——重试风暴会延长限流。
产物: <out>/<bvid>_meta.json / <bvid>_audio16k.wav （幂等：wav 已存在则跳过）
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from shutil import which
from urllib.parse import urlencode

sys.stdout.reconfigure(encoding="utf-8")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SKILL_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
from config import get_media_dir  # noqa: E402

JAR = os.path.join(SKILL_DIR, "jar.txt")
DEFAULT_OUT = get_media_dir()

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


def http_json(url: str, headers: dict) -> dict:
    """单请求；412 / 网络错误时静默 60s 仅重试一次。"""
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_err = e
            if isinstance(e, urllib.error.HTTPError) and e.code == 412 and attempt == 0:
                print("[api] 412，静默 60s 后单次重试...", flush=True)
                time.sleep(60)
            elif isinstance(e, urllib.error.URLError) and attempt == 0:
                print(f"[api] 网络错误 {e}，静默 60s 后单次重试...", flush=True)
                time.sleep(60)
            else:
                raise
    raise SystemExit(f"请求失败: {url} ({last_err})")


def wbi_sign(params: dict) -> dict:
    nav = http_json("https://api.bilibili.com/x/web-interface/nav", {"User-Agent": UA})
    img = nav["data"]["wbi_img"]["img_url"]
    sub = nav["data"]["wbi_img"]["sub_url"]
    raw = (img.rsplit("/", 1)[1].split(".")[0]) + (sub.rsplit("/", 1)[1].split(".")[0])
    mixin = "".join(raw[i] for i in MIXIN_TAB)[:32]
    params = dict(params)
    params["wts"] = int(time.time())
    params = {k: "".join(ch for ch in str(v) if ch not in "!'()*")
              for k, v in sorted(params.items())}
    params["w_rid"] = hashlib.md5((urlencode(params) + mixin).encode()).hexdigest()
    return params


def ffmpeg_exe() -> str | None:
    p = which("ffmpeg")
    if p:
        return p
    if sys.platform == "win32":
        cand = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe")
        if os.path.exists(cand):
            return cand
    # Probe current interpreter and common alternates for imageio-ffmpeg
    probe_cmds: list[list[str]] = [
        [sys.executable, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"],
    ]
    if sys.platform == "win32" and which("py"):
        probe_cmds.append(
            ["py", "-3.12", "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"]
        )
    for name in ("python3", "python"):
        exe = which(name)
        if exe and os.path.normcase(exe) != os.path.normcase(sys.executable):
            probe_cmds.append(
                [exe, "-c", "import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())"]
            )
    for cmd in probe_cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and r.stdout.strip():
                path = r.stdout.strip().splitlines()[-1]
                if os.path.exists(path):
                    return path
        except Exception:
            pass
    return None


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stderr[-800:])
        raise SystemExit(f"命令失败: {cmd[0]}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="B站直连 API 抓取（风控期备用通道）",
    )
    ap.add_argument("src", help="BV号或完整视频 URL")
    ap.add_argument("--out", default=None, help="输出目录（默认 config media_dir 或 ./output）")
    ns = ap.parse_args()
    src = ns.src
    cli_out = ns.out
    outdir = get_media_dir(cli_out) if cli_out else DEFAULT_OUT
    os.makedirs(outdir, exist_ok=True)
    m = re.search(r"BV[0-9A-Za-z]{10}", src)
    if not m:
        raise SystemExit(f"无法解析 BV 号: {src}")
    bvid = m.group(0)
    wav = os.path.join(outdir, f"{bvid}_audio16k.wav")
    meta_path = os.path.join(outdir, f"{bvid}_meta.json")
    # 实测（2026-09-03 风控期）：view/nav 带 Referer 会被 412，裸 UA 通过；
    # playurl/CDN 带 Referer 正常。请求头组合勿改动。
    view_headers = {"User-Agent": UA}
    dl_headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/"}

    # 1) view：元信息 + cid
    v = http_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", view_headers)
    if v.get("code") != 0:
        raise SystemExit(f"view API code={v.get('code')} {v.get('message')}")
    data = v["data"]
    meta = {"bvid": bvid, "url": f"https://www.bilibili.com/video/{bvid}",
            "title": data["title"], "desc": data.get("desc", ""),
            "owner": data["owner"]["name"], "owner_mid": data["owner"]["mid"],
            "duration_sec": data["duration"], "pubdate": data.get("pubdate"),
            "view": data["stat"]["view"], "like": data["stat"]["like"]}
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    cid = data["cid"]
    print(f"[meta] {meta['title']} | {meta['duration_sec']}s | cid={cid}", flush=True)

    if os.path.exists(wav):
        print(f"[skip] {wav} 已存在", flush=True)
        return
    time.sleep(3)

    # 2) playurl：先免签名，失败转 wbi 签名
    params = {"bvid": bvid, "cid": cid, "qn": 0, "fnval": 16, "fnver": 0, "fourk": 1}
    pj = http_json("https://api.bilibili.com/x/player/playurl?" + urlencode(params), dl_headers)
    if pj.get("code") != 0 or not (pj.get("data") or {}).get("dash"):
        print(f"[playurl] 免签名失败(code={pj.get('code')})，转 wbi 签名...", flush=True)
        time.sleep(5)
        pj = http_json("https://api.bilibili.com/x/player/wbi/playurl?" + urlencode(wbi_sign(params)),
                       dl_headers)
        if pj.get("code") != 0 or not (pj.get("data") or {}).get("dash"):
            raise SystemExit(f"playurl 仍失败: code={pj.get('code')} {pj.get('message')}")
    audios = pj["data"]["dash"]["audio"]
    best = max(audios, key=lambda a: a.get("bandwidth", 0))
    audio_url = (best.get("baseUrl") or best.get("base_url"))
    print(f"[playurl] 音频流 {best.get('bandwidth')}bps", flush=True)

    # 3) 从 CDN 下载（单流直下，CDN 不受 API 风控影响）
    m4s = os.path.join(outdir, f"{bvid}.m4s")
    req = urllib.request.Request(audio_url, headers=dl_headers)
    with urllib.request.urlopen(req, timeout=120) as r, open(m4s, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"[audio] {m4s} ({os.path.getsize(m4s)//1024} KB)", flush=True)

    # 4) ffmpeg 转 16k wav
    ff = ffmpeg_exe()
    if not ff:
        raise SystemExit("找不到 ffmpeg（可 pip install imageio-ffmpeg）")
    run([ff, "-y", "-i", m4s, "-ac", "1", "-ar", "16000", wav])
    os.remove(m4s)
    print(f"[wav] {wav} ({os.path.getsize(wav)//1024} KB)", flush=True)


if __name__ == "__main__":
    main()
