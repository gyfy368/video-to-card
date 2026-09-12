# -*- coding: utf-8 -*-
"""抓取B站视频：元信息 + 字幕(若有) + 音频 + 16k wav。（video-to-card skill 版）
用法: python fetch_bili.py <BV号或URL> [--out <媒体目录>]
产物: <out>/<bvid>_meta.json / <bvid>_subtitle.txt(若有平台字幕) / <bvid>_audio16k.wav
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from shutil import which

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


def load_jar_pairs(jar_path: str) -> list[tuple[str, str]]:
    pairs = []
    with open(jar_path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                pairs.append((parts[5], parts[6].strip()))
    return pairs


def ensure_jar(jar_path: str) -> str:
    """有 jar 用 jar；没有就访问B站首页引导 buvid 并落盘。返回 Cookie 头字符串。"""
    if not os.path.exists(jar_path):
        pairs = []
        lines = ["# Netscape HTTP Cookie File"]
        req = urllib.request.Request("https://www.bilibili.com/", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            set_cookies = r.headers.get_all("Set-Cookie") or []
        exp = str(int(time.time()) + 365 * 86400)
        for sc in set_cookies:
            kv = sc.split(";", 1)[0]
            if "=" in kv:
                name, val = kv.split("=", 1)
                name, val = name.strip(), val.strip()
                if name and all(name != p[0] for p in pairs):
                    pairs.append((name, val))
                    lines.append(f".bilibili.com\tTRUE\t/\tFALSE\t{exp}\t{name}\t{val}")
        os.makedirs(os.path.dirname(jar_path) or ".", exist_ok=True)
        with open(jar_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    return "; ".join(f"{k}={v}" for k, v in load_jar_pairs(jar_path))


def ytdlp_cmd() -> list[str]:
    p = which("yt-dlp")
    if p:
        return [p]
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        return ["py", "-3.12", "-m", "yt_dlp"]


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


def api_json(url: str, cookie: str) -> dict:
    headers = {"User-Agent": UA, "Referer": "https://www.bilibili.com/", "Cookie": cookie}
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            last_err = e
            if isinstance(e, urllib.error.HTTPError):
                if e.code in (412, 429) or e.code >= 500:
                    wait = 15 * (attempt + 1)
                    print(f"[api] HTTP {e.code}，退避 {wait}s 后重试({attempt + 1}/4)...", flush=True)
                    time.sleep(wait)
                else:
                    raise
            else:
                wait = 15 * (attempt + 1)
                print(f"[api] 网络错误 {e}，退避 {wait}s 后重试({attempt + 1}/4)...", flush=True)
                time.sleep(wait)
    raise SystemExit(f"API 重试仍失败: {url} ({last_err})")


def run(cmd: list[str]) -> None:
    print(">>", " ".join(os.path.basename(c) if os.sep in c else c for c in cmd[:3]), "...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(r.stdout[-1500:])
        print(r.stderr[-1500:])
        raise SystemExit(f"命令失败: {cmd[0]}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="抓取B站视频：元信息 + 字幕(若有) + 音频 + 16k wav",
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
        raise SystemExit(f"无法从参数解析 BV 号: {src}")
    bvid = m.group(0)
    url = f"https://www.bilibili.com/video/{bvid}"
    cookie = ensure_jar(JAR)

    # 1) 元信息（view API 被限流时降级，稍后从 yt-dlp info.json 补全）
    meta = {"bvid": bvid, "url": url}
    try:
        d = api_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", cookie)
        if d.get("code") == 0:
            v = d["data"]
            meta = {
                "bvid": bvid, "url": url,
                "title": v["title"], "desc": v.get("desc", ""),
                "owner": v["owner"]["name"], "owner_mid": v["owner"]["mid"],
                "duration_sec": v["duration"], "pubdate": v.get("pubdate"),
                "view": v["stat"]["view"], "like": v["stat"]["like"],
            }
            with open(os.path.join(outdir, f"{bvid}_meta.json"), "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            print(f"[meta] {meta['title']} | {meta['duration_sec']}s | 播放{meta['view']}")
        else:
            print(f"[meta] view API code={d.get('code')}，降级为 yt-dlp info.json")
    except SystemExit as e:
        print(f"[meta] {e}，降级为 yt-dlp info.json")

    # 2) 平台字幕（有就省去 ASR）+ info.json（元信息兜底）
    run(ytdlp_cmd() + ["--cookies", JAR, "--skip-download", "--no-playlist", "--playlist-items", "1",
                       "--write-subs", "--write-auto-subs", "--write-info-json", "--sleep-requests", "1",
                       "--sub-langs", ".*", "--sub-format", "srt/best",
                       "-o", os.path.join(outdir, bvid), url])
    info_file = os.path.join(outdir, f"{bvid}.info.json")
    if "title" not in meta and os.path.exists(info_file):
        with open(info_file, encoding="utf-8") as f:
            info = json.load(f)
        meta.update({
            "title": info.get("title"), "desc": (info.get("description") or "")[:2000],
            "owner": info.get("uploader"), "owner_mid": info.get("uploader_id"),
            "duration_sec": info.get("duration"), "view": info.get("view_count"),
            "like": info.get("like_count"),
        })
        with open(os.path.join(outdir, f"{bvid}_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        print(f"[meta] 从 info.json 补全: {meta['title']}")

    sub_txt = os.path.join(outdir, f"{bvid}_subtitle.txt")
    sub_file = next((f for f in os.listdir(outdir)
                     if f.startswith(bvid) and f.endswith((".srt", ".vtt"))), None)
    if sub_file:
        with open(os.path.join(outdir, sub_file), encoding="utf-8") as f:
            raw = f.read()
        lines = []
        for ln in raw.splitlines():
            if ("-->" in ln or re.fullmatch(r"\d+", ln.strip())
                    or ln.strip() in ("WEBVTT", "") or ln.startswith(("Kind:", "Language:", "NOTE"))):
                continue
            t = re.sub(r"</?c[^>]*>", "", ln).strip()
            if t and (not lines or t != lines[-1]):
                lines.append(t)
        with open(sub_txt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"[sub] 使用平台字幕 {sub_file}，无需 ASR")
        return
    print("[sub] 平台无字幕，走 ASR")

    # 3) 下载音频
    run(ytdlp_cmd() + ["--cookies", JAR, "--no-playlist", "--playlist-items", "1",
                       "-f", "ba/best", "--retries", "3", "--sleep-requests", "1",
                       "-o", os.path.join(outdir, bvid + ".%(ext)s"), url])
    audio = next((os.path.join(outdir, f) for f in os.listdir(outdir)
                  if f.startswith(bvid + ".")
                  and f.rsplit(".", 1)[1].lower() in ("m4s", "m4a", "mp4", "webm", "aac", "mp3", "opus")), None)
    if not audio:
        raise SystemExit("未找到下载的音频文件")
    print(f"[audio] {audio} ({os.path.getsize(audio)//1024} KB)")

    # 4) ffmpeg 转 16k 单声道 wav
    ff = ffmpeg_exe()
    if not ff:
        raise SystemExit("找不到 ffmpeg（可 pip install imageio-ffmpeg 解决）")
    wav = os.path.join(outdir, f"{bvid}_audio16k.wav")
    run([ff, "-y", "-i", audio, "-ac", "1", "-ar", "16000", wav])
    print(f"[wav] {wav} ({os.path.getsize(wav)//1024} KB)")


if __name__ == "__main__":
    main()
