# -*- coding: utf-8 -*-
"""video-to-card — unified CLI entry point.

One-stop pipeline: fetch → comments → ASR → literature-card draft.
Also exposes search / space helpers.

用法 / Usage:
  python main.py process <BV号/URL> [--skip-asr] [--skip-comments] [--strict] [--out <dir>]
  python main.py search "<关键词/UP+标题>" [--limit 10]
  python main.py space <mid> [--pages 1]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import get_media_dir, get_preferred_ups, load_config  # noqa: E402


def _run_script(script_name: str, args: list[str]) -> int:
    script = SCRIPTS / script_name
    cmd = [sys.executable, str(script)] + args
    print(f">> {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd)
    return r.returncode


def _parse_bvid(src: str) -> str:
    m = re.search(r"BV[0-9A-Za-z]{10}", src)
    if not m:
        raise SystemExit(f"无法从参数解析 BV 号 / Cannot parse BV id: {src}")
    return m.group(0)


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _load_meta(outdir: Path, bvid: str) -> dict:
    meta_path = outdir / f"{bvid}_meta.json"
    if meta_path.is_file():
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    return {"bvid": bvid, "title": bvid, "owner": "", "url": f"https://www.bilibili.com/video/{bvid}"}


def _pick_transcript(outdir: Path, bvid: str) -> tuple[str, str]:
    """Return (source_label, text). Prefer platform subtitle, else ASR."""
    sub = outdir / f"{bvid}_subtitle.txt"
    asr = outdir / f"{bvid}_转写.txt"
    if sub.is_file() and sub.stat().st_size > 0:
        return "platform_subtitle", _read_text(sub)
    if asr.is_file() and asr.stat().st_size > 0:
        return "asr", _read_text(asr)
    return "none", ""


def _excerpt_comments(outdir: Path, bvid: str, limit: int = 10) -> list[str]:
    path = outdir / f"{bvid}_comments.txt"
    if not path.is_file():
        return []
    lines = []
    for ln in _read_text(path).splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        lines.append(ln.strip())
        if len(lines) >= limit:
            break
    return lines


def _srt_outline_hints(outdir: Path, bvid: str, max_items: int = 8) -> list[str]:
    """Pull a few timestamped lines from SRT for draft outline scaffolding."""
    for name in (f"{bvid}_转写.srt",):
        path = outdir / name
        if not path.is_file():
            continue
        blocks = _read_text(path).strip().split("\n\n")
        hints = []
        for block in blocks:
            parts = block.strip().splitlines()
            if len(parts) < 3:
                continue
            timing = parts[1]
            text = " ".join(parts[2:]).strip()
            m = re.match(r"(\d{2}):(\d{2}):(\d{2})", timing)
            if not m:
                continue
            h, mi, s = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
            mmss = f"{h * 60 + mi:02d}:{s:02d}"
            hints.append(f"* `{mmss}` - **…**：{text[:80]}{'…' if len(text) > 80 else ''}")
            if len(hints) >= max_items:
                break
        return hints
    return []


def _yaml_escape(val: str) -> str:
    """Safely escape a string for single-line YAML frontmatter value."""
    return json.dumps(val or "", ensure_ascii=False)


def _write_draft_card(outdir: Path, bvid: str) -> Path:
    meta = _load_meta(outdir, bvid)
    title = meta.get("title") or bvid
    owner = meta.get("owner") or "未知UP"
    url = meta.get("url") or f"https://www.bilibili.com/video/{bvid}"
    src_label, transcript = _pick_transcript(outdir, bvid)
    comments = _excerpt_comments(outdir, bvid)
    outline = _srt_outline_hints(outdir, bvid)
    if not outline:
        outline = ["* `00:00` - **待整理**：请根据转写稿填写核心逻辑大纲（带时间戳）"]

    comment_block = "\n".join(f"* {c}" for c in comments) if comments else "* 评论区未取到"
    preview = (transcript[:1200] + ("…" if len(transcript) > 1200 else "")) if transcript else "（暂无转写稿）"
    today = date.today().isoformat()

    md = f"""---
type: literature
media: video
title: {_yaml_escape(title)}
source_url: "{url}"
speaker_author: {_yaml_escape(owner)}
tags:
  - literature-note
created: {today}
status: draft
---

# 🎙️ 音视频文献卡：{title}

* **讲者/UP主**：{owner}
* **一句话总评/收获**：（待填写）
* **转写来源**：{src_label}
* **BV**：{bvid}

---

## 🎯 核心逻辑大纲
{chr(10).join(outline)}

---

## 💬 高赞评论摘录（评论区热评，选 5~10 条有信息量的）

{comment_block}

---

## 💡 提炼出的原子永久卡片（由此抽出的独立思考）
* 候选观点 1：「…」——（待与用户探讨，未建卡）

---

## 🔍 查重与链接建议
* （Agent / 人工）：对照知识库永久卡片后填写。

---

## 🧩 逻辑关系编织
* （待填写）

---

## 📝 转写预览（前约 1200 字）

{preview}

---

> 草案由 `python main.py process` 自动生成。请按 `references/文献卡模板.md` 完善后入库。
> Draft auto-generated. Refine using the literature card template before filing into your vault.
"""
    out_path = outdir / f"{bvid}_文献卡草案.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def cmd_process(args: argparse.Namespace) -> int:
    bvid = _parse_bvid(args.src)
    outdir = Path(get_media_dir(args.out))
    outdir.mkdir(parents=True, exist_ok=True)
    strict = bool(getattr(args, "strict", False))
    print(f"[process] bvid={bvid} out={outdir} strict={strict}", flush=True)

    rc = _run_script("fetch_bili.py", [bvid, "--out", str(outdir)])
    if rc != 0:
        print("[process] fetch_bili 失败，尝试 API 备用通道 fetch_bili_api ...", flush=True)
        rc = _run_script("fetch_bili_api.py", [bvid, "--out", str(outdir)])
        if rc != 0:
            return rc

    if not args.skip_comments:
        crc = _run_script("fetch_comments.py", [bvid, "--out", str(outdir)])
        if crc != 0:
            if strict:
                print("[process] 评论抓取失败（--strict），中止", flush=True)
                return crc or 1
            print("[process] 评论抓取失败或无评论，继续主流程...", flush=True)

    sub = outdir / f"{bvid}_subtitle.txt"
    asr_txt = outdir / f"{bvid}_转写.txt"
    has_transcript = (
        (sub.is_file() and sub.stat().st_size > 0)
        or (asr_txt.is_file() and asr_txt.stat().st_size > 0)
    )
    need_asr = not args.skip_asr and not has_transcript
    if need_asr:
        wav = outdir / f"{bvid}_audio16k.wav"
        if not wav.is_file():
            msg = f"[process] 无平台字幕且缺少 {wav.name}，无法 ASR"
            if strict:
                print(msg + "（--strict），中止", flush=True)
                return 1
            print(msg, flush=True)
        else:
            arc = _run_script("run_asr.py", [str(outdir), bvid])
            if arc != 0:
                if strict:
                    print("[process] ASR 失败（--strict），中止", flush=True)
                    return arc or 1
                print("[process] ASR 失败，仍将生成草案骨架", flush=True)
            elif strict:
                # Re-check after ASR
                asr_txt = outdir / f"{bvid}_转写.txt"
                if not (asr_txt.is_file() and asr_txt.stat().st_size > 0):
                    print("[process] ASR 未产出转写稿（--strict），中止", flush=True)
                    return 1
    elif args.skip_asr:
        print("[process] 已跳过 ASR (--skip-asr)", flush=True)
    else:
        print("[process] 已有字幕/转写，跳过 ASR", flush=True)

    draft = _write_draft_card(outdir, bvid)
    print(f"[process] 文献卡草案已写入: {draft}", flush=True)
    ups = get_preferred_ups()
    if ups:
        print(f"[hint] preferred_ups={', '.join(ups[:3])}{'…' if len(ups) > 3 else ''}（见 config）", flush=True)
    else:
        print("[hint] preferred_ups 为空；可在 config.yaml 填写优先 UP 列表", flush=True)
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    return _run_script("search_bili.py", [args.keyword, str(args.limit)])


def cmd_space(args: argparse.Namespace) -> int:
    return _run_script("bili_space.py", [str(args.mid), str(args.pages)])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "video-to-card：B站视频 → 转写/评论 → 文献卡草案（CLI + Agent Skill）\n"
            "Bilibili video → transcript/comments → literature-card draft."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例 / Examples:\n"
            "  python main.py process BV1xxxxxxxx [--out ./output]\n"
            "  python main.py process https://www.bilibili.com/video/BVxxx --skip-asr\n"
            "  python main.py process BVxxx --strict\n"
            "  python main.py search \"关键词\" --limit 5\n"
            "  python main.py space 12345678 --pages 2\n"
            "\n"
            "配置 / Config: 复制 config.example.yaml → config.yaml\n"
            "Cookie: 复制 scripts/jar.txt.example → scripts/jar.txt（可选）"
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    pp = sub.add_parser(
        "process",
        help="一站式处理：抓取+评论+ASR+文献卡草案 / Full pipeline",
        description=(
            "抓取元信息与音频/字幕，采集热评，必要时本地 ASR，并生成 "
            "<out>/<bvid>_文献卡草案.md"
        ),
    )
    pp.add_argument("src", help="BV 号或完整视频 URL / BV id or video URL")
    pp.add_argument("--out", default=None, help="输出目录（默认 ./output 或 config media_dir）")
    pp.add_argument("--skip-asr", action="store_true", help="跳过本地语音转写")
    pp.add_argument("--skip-comments", action="store_true", help="跳过评论区抓取")
    pp.add_argument(
        "--strict",
        action="store_true",
        help="严格模式：评论或 ASR 失败则退出，不生成空/残缺草案",
    )
    pp.set_defaults(func=cmd_process)

    ps = sub.add_parser(
        "search",
        help="按关键词搜索视频 / Search videos by keyword",
        description="搜索 B站视频（优先配合 preferred_ups 人工核对）",
    )
    ps.add_argument("keyword", help="关键词或「UP主 + 标题」")
    ps.add_argument("--limit", type=int, default=10, help="返回条数（默认 10）")
    ps.set_defaults(func=cmd_search)

    psp = sub.add_parser(
        "space",
        help="列出 UP 主空间视频 / List videos in a user space",
        description="按 mid 拉取 UP 主投稿列表",
    )
    psp.add_argument("mid", help="UP 主 mid（数字）")
    psp.add_argument("--pages", type=int, default=1, help="拉取页数（默认 1）")
    psp.set_defaults(func=cmd_space)

    return p


def main(argv: list[str] | None = None) -> int:
    load_config()  # warm defaults; validates pyyaml only if config file present
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
