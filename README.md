# video-to-card

[![Python 3.10–3.12](https://img.shields.io/badge/python-3.10%E2%80%933.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![FunASR](https://img.shields.io/badge/ASR-FunASR%20Paraformer-orange.svg)](https://github.com/modelscope/FunASR)
[![yt-dlp](https://img.shields.io/badge/download-yt--dlp-green.svg)](https://github.com/yt-dlp/yt-dlp)

把 B 站视频变成可织入 **Obsidian** 的音视频文献卡草案。命令行能直接跑，也能装成 Cursor / Claude Code / Codex 的 Agent Skill。

只处理你有权观看的视频。约束见 [NOTICE.md](NOTICE.md)。

---

## 快速开始 Quick Start

### 1. 安装 Agent 技能

需要 Node.js（自带 `npx`）：

```bash
npx skills add gyfy368/video-to-card -g -a cursor -y
```

### 2. 安装基础依赖，把视频交给 Agent

在技能目录里执行：

```bash
pip install -r requirements-base.txt
```

然后把 BV 号交给 Agent 即可，例如：「帮我把 BV1xxxxxxxx 整理成文献卡」。

已有字幕的视频不需要本地语音转写。本地 ASR（`pip install -r requirements-asr.txt`）可选，可跳过；ffmpeg 已由 `imageio-ffmpeg` 一并带上，不必单独安装。

---

## 亮点 Highlights

- 🧠 **Obsidian × Zettelkasten 原生** — YAML Frontmatter、Callouts、Wikilinks、Dataview 标签；产物直接织入图谱与查询流
- ⚡ **B站防风控抓取** — 裸 UA / 退避重试 / wbi 签名；view API 失败时降级 yt-dlp `info.json`
- 🎙️ **离线高精度转写** — 阿里 Paraformer（FunASR），输出带句级时间戳的 SRT
- 💬 **评论区精选** — 热评采集，辅助共鸣点与质疑点分析（不当讲者引证）
- 🗂️ **三层卡片纪律** — 转写稿 → 文献卡 → 永久认知卡；查重 + 双向逻辑关系编织
- 🤖 **双模设计** — `python main.py …` 一站式流水线 + `SKILL.md` Agent 工作流

---

## Obsidian & Zettelkasten 原生集成

> **这不是又一个「视频转文字」工具。**  
> 普通爬取 / 转写器留下的是死掉的原始字幕或浅层 AI 摘要——难检索、难关联、难复用。  
> **video-to-card** 把视频整理成**结构化、原子化、可生长**的 Obsidian 卡片：带 YAML Frontmatter 与 Dataview 友好标签，用 Callouts 与 `[[双链]]` 织进你的图谱（Graph View），并进入你已有的 Dataview 工作流。转写只是原料；**卡片盒方法论才是产品本身**。

### 三层 Zettelkasten 架构

```text
Raw Transcripts（原始转写稿）
        ↓  重组、时间戳大纲、证据留存
Literature Note（文献卡 / 音视频文献卡）
        ↓  查重 → 用户批准 → 原子提炼
Permanent Cognitive Cards（永久卡片 / 核心认知）
```

| 层级 | 角色 | 典型落点 |
|------|------|----------|
| **原始转写稿** | 带标点全文 + 句级 SRT；证据底稿，校对时回查原句 | `media_dir` 工作缓存 |
| **文献卡** | 一视频一卡：元信息、时间戳大纲、评论摘录、候选论点、查重与关系编织 | Vault 内文献区（常见 `30-参考资料与文献库/音视频文献卡/`） |
| **永久卡片** | 一事一记的独立认知；须经讨论与明确批准后才建卡 | Vault 内永久卡区（常见 `10-永久卡片(核心认知库)/`） |

### 查重纪律：良性关联 vs 重复

提交候选永久卡**之前**，必须对照库内已有永久卡逐张核查：

1. **良性关联（可各自成卡）** — 仅部分相似：核心机制不同、各自独立成立、并列后可对照或互补。处理：各自成卡 + **双向互链**，并写清关系类型。
2. **重复（不立新卡）** — 大量相似，或一方几乎包含另一方。处理：并入现有卡作补充，或在现有卡关联节补链，**不新建文件**。
3. **判决须显式交付** — 相邻项标注「与哪张卡、何种关系、为何仍值得立」；重复项单独标出并给出并入 / 补链方案。关联是资产，重复才是负债。

### 双向类型化关系编织

查重之后、建卡之前，为每张新卡与旧卡（含本轮其他新卡）挂上**真实**逻辑关系，双向落地：

| 关系类型 | 含义（简述） |
|----------|----------------|
| **互补** | 各覆盖机制的一面，合起来更完整 |
| **对照** | 相近场景下的不同策略或条件 |
| **深化** | 新卡在旧卡之上推进一层机制或边界 |
| **修正** | 新卡限定或修正旧卡的适用范围 |
| **冲突辩证** | 观点张力保留；写清各自成立条件 |

规则：每条关系写清「类型 + 一句话理由」；新卡关联节与旧卡回链成对出现；宁缺毋滥，禁止硬编。

### 文献卡在 Obsidian 中的样子

下面是一份贴近真实产物的文献卡示意（YAML、Callouts、时间戳大纲、Wikilinks、评论摘录与反思区）：

````markdown
---
type: literature
media: video
title: 剂量决定毒与补——刺激与恢复的边界
source_url: "https://www.bilibili.com/video/BVxxxxxxxx"
speaker_author: 示例UP
tags:
  - literature-note
  - 学习方法
  - 身心节律
created: 2026-09-12
---

# 🎙️ 音视频文献卡：剂量决定毒与补

> [!abstract] 一句话总评
> 讲清「同一刺激可成补也可成毒」——关键变量是剂量与恢复窗口，而不是意志力口号。

* **讲者/UP主**：示例UP
* **一句话总评/收获**：把「努力」拆成可调节的刺激强度与必留的恢复期。

---

## 🎯 核心逻辑大纲

* `00:42` - **问题重述**：为什么同样的训练，有人变强、有人崩溃
* `03:15` - **剂量曲线**：刺激不足无效，过量则损伤；中间带才是「补」
* `07:08` - **恢复窗口**：刺激之后必须留出修复时间，否则剂量在账面上叠加成毒
* `11:30` - **可迁移例子**：学习、运动、社交曝光共用同一套边界感

---

## 💬 高赞评论摘录

* [1280赞] @用户A：终于有人把「休息也是训练」讲成机制，而不是鸡汤
* [456赞] @用户B：想对照一下和「刺激之后要有恢复期」那张卡的边界
* *小结：共鸣在「可操作的剂量」；质疑在「如何量化个人阈值」。*

---

## 💡 提炼出的原子永久卡片

* 候选：「剂量决定毒与补」——同一刺激的效果由强度与间隔决定；与 [[刺激之后要有恢复期]] 互补（待探讨，未建卡）

---

## 🔍 查重与链接建议

* 与 [[刺激之后要有恢复期]]：**良性关联（互补）**——一侧重剂量边界，一侧重恢复节奏；建议各自成卡并双向互链。
* 与 [[只要努力就有回报]]：**重复风险**——若新表述无法增加可执行边界，建议并入或仅补链，不新建。

---

## 🧩 逻辑关系编织

* 「剂量决定毒与补」 ↔ [[刺激之后要有恢复期]]（关系：互补 —— 剂量与恢复是同一机制的两半）
* 「剂量决定毒与补」 ↔ [[比较优势]]（关系：对照 —— 前者谈身心负荷边界，后者谈资源投放选择）

---

## 📝 个人反思

- [ ] 本周把一项学习任务标出「刺激量」与「恢复窗」，记录主观疲劳是否下降

---

> 🤖 由 video-to-card 转写整理 · 生成时间 2026-09-12 11:20 · 模型 <你的模型名>
````

权威字段与撰写规则见 [`references/文献卡模板.md`](references/文献卡模板.md)。

### 连接 Obsidian Vault

在「可选配置（可跳过）」里填写 `obsidian_vault` 后，Agent 在你批准入库时把文献卡写入库内文献区，永久卡写入永久卡区。不填则草案留在 `output/`，自己移进 Obsidian。

---

## 进阶（可跳过）

命令行、搜索、自测与输出文件说明都不是入门必做。需要 Python 3.10–3.12。

没有 Node.js 时，把本仓库复制或软链到 `~/.cursor/skills/video-to-card/`。

技能包不含 Python 依赖，也不含 FunASR 或 Cookie。CPU 直接装 `requirements-asr.txt` 即可；GPU 请先按 [pytorch.org](https://pytorch.org) 的 CUDA 版本安装 `torch` / `torchaudio`，再装其余包。

### 更多命令

```bash
python main.py process BV1xxxxxxxx
python main.py process https://www.bilibili.com/video/BVxxx --out ./output
python main.py process BVxxx --skip-asr --skip-comments
python main.py process BVxxx --strict
python main.py search "关键词" --limit 5
python main.py space 12345678 --pages 1
python main.py --help
python -m unittest discover tests
```

产物在 `output/`（或你传入的 `--out`）：

- `<bvid>_meta.json`
- `<bvid>_audio16k.wav` / `<bvid>_subtitle.txt`（若有）
- `<bvid>_转写.txt` + `<bvid>_转写.srt`
- `<bvid>_comments.txt`
- **`<bvid>_文献卡草案.md`**

### 可选配置（可跳过）

没有 `config.yaml` 时，草案写到 `output/`。只有你想改默认行为时再做。

复制模板：

```bash
copy config.example.yaml config.yaml          # Windows
# cp config.example.yaml config.yaml         # macOS / Linux
```

| 字段 | 作用 |
|------|------|
| `media_dir` | 默认输出目录。不写则用 `./output`（相对仓库根） |
| `preferred_ups` | 按标题搜索时优先核对的 UP 主。不写则为空 |
| `obsidian_vault` | 你的 Obsidian 库路径。不写则草案留在 `output/`，自己移入库 |
| `asr.*` | FunASR 模型名 |

`config.yaml` 已被 gitignore，不要把个人库路径提交到公开仓库。CLI 的 `--out` 相对当前终端目录；Agent 请传绝对路径。

公开视频一般不用 Cookie。只有登录才可见的内容，才把 `scripts/jar.txt.example` 复制为 `scripts/jar.txt`。说明见 [SECURITY.md](SECURITY.md)。

---

## 目录结构

```text
video-to-card/
├── main.py                 # 统一 CLI 入口
├── config.py               # 配置加载（config.yaml → 默认值）
├── config.example.yaml     # 配置模板
├── requirements-base.txt   # 必装
├── requirements-asr.txt    # 可选 ASR
├── requirements.txt        # 包含上述二者
├── NOTICE.md               # 法律与合规说明
├── SECURITY.md             # Cookie / 密钥处理
├── LICENSE                 # MIT
├── README.md
├── CHANGELOG.md
├── SKILL.md                # Agent Skill 说明与工作流
├── tests/
│   └── test_core.py
├── references/
│   └── 文献卡模板.md
└── scripts/
    ├── fetch_bili.py       # yt-dlp 主抓取通道
    ├── fetch_bili_api.py   # 直连 API 备用通道
    ├── fetch_comments.py   # 热评
    ├── run_asr.py          # FunASR 转写
    ├── search_bili.py      # 关键词搜索
    ├── bili_space.py       # UP 空间列表
    ├── find_up.py
    └── jar.txt.example     # Cookie 模板；复制为本地 jar.txt（不在仓库）
```

---

## 合规

本项目仅供学习与个人知识整理。只下载你有合法观看权限的内容。转写稿与评论不要提交到公开仓库。评论示例须脱敏。WBI 签名可能随平台更新失效。完整说明见 [NOTICE.md](NOTICE.md)，Cookie 见 [SECURITY.md](SECURITY.md)。

---

## License

[MIT](LICENSE) © 2026 [gyfy368](https://github.com/gyfy368)
