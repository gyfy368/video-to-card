# -*- coding: utf-8 -*-
"""FunASR(Paraformer) 批量转写：wav -> txt + srt。（video-to-card）
用法: python run_asr.py <媒体目录> <bvid1> [bvid2 ...]
输入: <媒体目录>/<bvid>_audio16k.wav
输出: <媒体目录>/<bvid>_转写.txt / <bvid>_转写.srt(句级时间戳)

若当前解释器无 funasr，会依次探测当前 python / python3 / py -3.12 等；
仍找不到则打印 pip install -r requirements-asr.txt 指引。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _probe_python_candidates() -> list[list[str]]:
    """Candidate interpreter launch prefixes that might have funasr installed.

    Order: Windows `py -3.12` / `py -3.11` / `py -3.10` (if available), then
    python3.12 / python3.11 / python3.10 / python3 / python on PATH — skipping
    the interpreter we are already running.
    """
    candidates: list[list[str]] = []
    seen: set[str] = set()

    def add(cmd: list[str]) -> None:
        key = " ".join(cmd).lower()
        if key not in seen:
            seen.add(key)
            candidates.append(cmd)

    if sys.platform == "win32":
        py_launcher = shutil.which("py")
        if py_launcher:
            for ver in ("-3.12", "-3.11", "-3.10"):
                add([py_launcher, ver])

    for name in (
        "python3.12",
        "python3.11",
        "python3.10",
        "python3",
        "python",
    ):
        exe = shutil.which(name)
        if not exe:
            continue
        try:
            same = os.path.samefile(exe, sys.executable)
        except OSError:
            same = os.path.normcase(os.path.abspath(exe)) == os.path.normcase(
                os.path.abspath(sys.executable)
            )
        if not same:
            add([exe])
    return candidates


def _has_funasr(cmd_prefix: list[str]) -> bool:
    try:
        r = subprocess.run(
            cmd_prefix + ["-c", "import funasr"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _install_hint() -> str:
    req_asr = os.path.join(_ROOT, "requirements-asr.txt")
    req_base = os.path.join(_ROOT, "requirements-base.txt")
    return (
        "未找到可用的 funasr 环境。\n"
        "请先安装基础依赖，再安装 ASR 依赖（建议 Python 3.10–3.12）：\n"
        f"  pip install -r \"{req_base}\"\n"
        f"  pip install -r \"{req_asr}\"\n"
        "GPU 用户请先按 https://pytorch.org 安装匹配 CUDA 的 torch/torchaudio，\n"
        "再安装 requirements-asr.txt 中的其余包。\n"
        "No funasr found. Install: pip install -r requirements-asr.txt "
        "(Python 3.10–3.12)."
    )


def _reexec_with_funasr() -> None:
    """Try alternate Pythons that have funasr; otherwise exit with clear instructions."""
    for prefix in _probe_python_candidates():
        if _has_funasr(prefix):
            print(f"[asr] 当前 Python 无 funasr，切换到 {' '.join(prefix)} ...", flush=True)
            r = subprocess.run(prefix + [os.path.abspath(__file__)] + sys.argv[1:])
            sys.exit(r.returncode)
    raise SystemExit(_install_hint())


# Import-time: never re-exec (would steal unittest/main argv). Defer to main().
try:
    from funasr import AutoModel
except ImportError:  # pragma: no cover - env dependent
    AutoModel = None  # type: ignore[misc, assignment]


def ms2srt(t: int) -> str:
    h, rem = divmod(int(t), 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


PUNCT = set("，。！？；：、,.!?;:…—·（）()《》“\"'“”‘’ \t")
STRONG = set("。！？；!?;")


def build_srt(text: str, timestamp) -> str | None:
    """funasr 1.4.x 返回字级 timestamp（毫秒），无 sentence_info。
    将带标点文本与字级时间戳对齐，按强标点切句合成 SRT。"""
    if not timestamp:
        return None
    raw = [ch for ch in text if ch not in PUNCT]
    n_ts = len(timestamp)
    if not raw or not n_ts:
        return None
    sents, cur = [], []
    for ch in text:
        if ch in PUNCT:
            if ch in STRONG and cur:
                cur.append(ch)
                sents.append(cur)
                cur = []
            elif cur and ch not in STRONG:
                cur.append(ch)
        else:
            cur.append(ch)
    if cur:
        sents.append(cur)
    blocks, consumed = [], 0
    for i, sent in enumerate(sents, 1):
        n = sum(1 for ch in sent if ch not in PUNCT)
        if n == 0:
            continue
        a = min(consumed * n_ts // max(len(raw), 1), n_ts - 1)
        b = max(a + 1, min((consumed + n) * n_ts // max(len(raw), 1), n_ts))
        start, end = timestamp[a][0], timestamp[b - 1][1]
        blocks.append(f"{i}\n{ms2srt(start)} --> {ms2srt(end)}\n{''.join(sent).strip()}\n")
        consumed += n
    return "\n".join(blocks) if blocks else None


def main() -> None:
    if AutoModel is None:
        _reexec_with_funasr()
        raise SystemExit(_install_hint())  # pragma: no cover
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    d, bvids = sys.argv[1], sys.argv[2:]
    try:
        from config import get_asr_models
        asr = get_asr_models()
    except Exception:
        asr = {"model": "paraformer-zh", "vad_model": "fsmn-vad", "punc_model": "ct-punc"}

    print(
        f"加载 FunASR 模型({asr['model']} + {asr['vad_model']} + {asr['punc_model']})...",
        flush=True,
    )
    model = AutoModel(
        model=asr["model"],
        vad_model=asr["vad_model"],
        punc_model=asr["punc_model"],
        disable_update=True,
    )
    for bvid in bvids:
        wav = os.path.join(d, f"{bvid}_audio16k.wav")
        if not os.path.exists(wav):
            print(f"[{bvid}] 找不到 {wav}，跳过", flush=True)
            continue
        # 复制到纯 ASCII 临时路径，规避音频库对中文路径的兼容问题
        tmp = os.path.join(tempfile.gettempdir(), "bili2card", bvid + ".wav")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        shutil.copyfile(wav, tmp)
        try:
            print(f"[{bvid}] ASR 开始...", flush=True)
            res = model.generate(input=tmp, batch_size_s=300, hotword="")
            r = res[0]
            text = r.get("text", "")
            with open(os.path.join(d, f"{bvid}_转写.txt"), "w", encoding="utf-8") as f:
                f.write(text)
            sents = r.get("sentence_info") or []
            srt_path = os.path.join(d, f"{bvid}_转写.srt")
            srt_src = ""
            if sents:
                blocks = []
                for i, s in enumerate(sents, 1):
                    blocks.append(f"{i}\n{ms2srt(s['start'])} --> {ms2srt(s['end'])}\n{s['text']}\n")
                with open(srt_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(blocks))
                srt_src = "句级时间戳"
            else:
                srt = build_srt(text, r.get("timestamp"))
                if srt:
                    with open(srt_path, "w", encoding="utf-8") as f:
                        f.write(srt)
                    srt_src = "字级时间戳合成"
                    print(f"[{bvid}] SRT 由字级时间戳合成", flush=True)
                else:
                    print(f"[{bvid}] 无法合成 SRT（时间戳缺失或无法对齐），仅输出 txt", flush=True)
            print(f"[{bvid}] 完成：{len(text)} 字，SRT={srt_src or '无'}", flush=True)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


if __name__ == "__main__":
    main()
