---
name: video-to-card
description: 视频转卡片工作流：用户提供B站等平台的视频链接、UP主空间链接，或只给"UP主+视频名称"时使用——按优先UP主清单搜索定位视频，抓取视频音频与评论区热评，用 ffmpeg + FunASR(Paraformer) 本地转写得到字幕，整理成 Obsidian 音视频文献卡，并提炼候选永久卡片与用户讨论。只要用户提到"视频转写""爬视频做卡片""B站视频整理成笔记""提取这个视频的字幕""把这个视频变成卡片""Obsidian 文献卡"等，即使没明说"转卡片"，也应加载本技能。Also for Bilibili/YouTube links → Obsidian Zettelkasten literature cards via fetch, comments, and FunASR.
---

# 视频转卡片（Video → 字幕 → 文献卡 → 永久卡片讨论）

把用户给的视频变成三层产物：**原始转写稿 → 音视频文献卡（入知识库）→ 候选永久卡片（仅讨论，批准后才建卡）**。

本仓库同时是 **CLI 工具**（`python main.py`）与 **Agent Skill**（本文件）。

**版本 / Version**：1.3.2　|　**许可 / License**：MIT

## Obsidian × Zettelkasten：核心定位（先读）

本工作流**专为 Obsidian 与卡片盒笔记法（Zettelkasten）构建**，不是「视频爬取 + 转写」的薄封装。

| 普通转写 / 摘要工具 | video-to-card |
|---------------------|---------------|
| 堆砌原始字幕或浅层摘要 | 产出可入库的**结构化文献卡**与**原子永久卡候选** |
| 与笔记库脱节 | YAML Frontmatter、Dataview 标签、Callouts、`[[Wikilinks]]`，直接织入图谱 |
| 一次导出即结束 | 查重纪律 + 双向类型化关系编织，卡片可生长 |

**卡片设计原则（撰写时必须遵守）：**

1. **三层分流**：转写稿 = 证据；文献卡 = 一视频一整理；永久卡 = 一事一认知（须用户批准）。
2. **原子与大白话**：候选论点用普通人一听就懂的表述；做不到就说明尚未提炼到位。
3. **时间戳大纲**：核心逻辑用 `` `MM:SS` ``，来自 SRT；重组讲述，禁止大段照抄字幕。
4. **查重先于立卡**：区分**良性关联**（可各自成卡 + 互链）与**重复**（并入 / 补链，不新建）。
5. **关系双向落地**：互补 / 对照 / 深化 / 修正 / 冲突辩证等，类型 + 一句话理由；新卡与旧卡成对回链。
6. **Obsidian 原生排版**：Frontmatter（`type` / `tags` / `source_url` 等）、Callouts、评论脱敏摘录、个人反思 checklist；模板见 `references/文献卡模板.md`。

Vault 连接：在 `config.yaml` 设置 `obsidian_vault`（见 `config.example.yaml`）。未配置则草案只留在 `media_dir`。

### 路径铁律（Agent CWD 不可靠）

- 设 `$SKILL_DIR` = 本 Skill / 仓库根目录的**绝对路径**（含 `SKILL.md`、`main.py`、`scripts/` 的那一层）。
- **禁止**依赖 Agent 当前工作目录写相对路径 `./output`。
- 媒体与草案目录 = `config.yaml` 的 `media_dir`（由 `config.py` 相对 `$SKILL_DIR` 解析为绝对路径）。未配置时默认为 `$SKILL_DIR/output`。
- 所有脚本调用优先：`python $SKILL_DIR/main.py … --out <绝对路径>`，或先 `cd $SKILL_DIR` 再跑命令。
- 合规与 Cookie：见仓库根 `NOTICE.md` / `SECURITY.md`。

## 铁律（先于一切）

1. **知识库路径由用户配置，禁止写死个人盘符。** 在 `config.yaml` 设置 `obsidian_vault`（复制自 `config.example.yaml`）。若已配置 vault：音视频文献卡建议写入 vault 内的文献/参考资料区（常见为 `30-参考资料与文献库/音视频文献卡/`）；永久卡片写入永久卡区（常见为 `10-永久卡片(核心认知库)/`）。若未配置 vault，草案只保留在 `media_dir`，由用户自行入库。
2. **严禁未经用户探讨并明确批准就新建永久卡片。** 必须先提炼 1~3 个候选论点（大白话表述）→ 用户挑选、改写 → 明确批准后才建卡。批准前，文献卡的「提炼观点」区只能写「候选（未建卡）」状态。
3. 凡创建/修改用户知识库文件，登记《AI-修改留痕.md》（格式：时间 | 位置 | 修改者 | 内容）——若用户库中有该文件；没有则按用户习惯记录。
4. 生成内容末尾注明「生成时间 + 模型名称」。
5. 用户当场指示 > 本技能。若用户只想拿字幕不想建卡，直接跳到第 3 步交付转写稿即可。
6. **版权**：只处理用户有观看权限的内容；转写/评论勿提交公开仓库；评论摘录示例脱敏（`@用户A`）。

## 第 0 步：按名称找视频（用户只给「UP主 + 标题」时）

优先用统一入口（在 `$SKILL_DIR` 下执行）：

```bash
python "$SKILL_DIR/main.py" search "<UP主> <标题关键词>" --limit 10
```

或底层脚本 / yt-dlp：

```bash
# 多数公开内容可不需要 Cookie；仅登录可见内容才加 --cookies
yt-dlp --flat-playlist --print "%(id)s %(title)s" "bilisearch8:<UP主> <标题关键词>"
# 可选：yt-dlp --cookies "$SKILL_DIR/scripts/jar.txt" ...

python "$SKILL_DIR/scripts/search_bili.py" "<关键词>" 10
```

- 结果人工核对 UP 主名与标题是否吻合（标题常带标点差异，关键词取 2~3 个），再取 BV 号走第 1 步。
- 搜不到时：去掉标点换关键词、只搜标题主短语，或用 `python "$SKILL_DIR/main.py" space <mid>` / `scripts/bili_space.py` 拉 UP 主空间列表定位。
- **兜底链**：① `search_bili.py`；② `archive/related` 相关视频接口；③ 用户搜索拿 mid 后走空间列表（注意风控）；④ 网络搜索引擎找标题；⑤ 仍找不到 → 向用户要 BV 号，不要恋战。

### 优先UP主清单

默认见本地 `config.yaml` 的 `preferred_ups`（代码与 `config.example.yaml` 默认为空列表；示例注释见该文件）。搜索结果出现相似标题/搬运号时以上 UP 优先；用户认可的新 UP 追加进**本地** `config.yaml`，勿写死在对话记忆之外。

## 第 1 步：抓取（一条命令，自动带 cookie 与风控退避）

**推荐一站式（含评论、ASR、草案）：**

```bash
python "$SKILL_DIR/main.py" process <BV号或URL> --out "<media_dir绝对路径>" [--skip-asr] [--skip-comments] [--strict]
```

- `--strict`：评论或 ASR 失败则非零退出，**不**生成空/残缺草案（入库前建议开启）。

仅抓取媒体时：

```bash
python "$SKILL_DIR/scripts/fetch_bili.py" <BV号或URL> --out "<media_dir绝对路径>"
```

脚本自动完成：元信息（view API，限流时降级 yt-dlp info.json）→ 尝试平台字幕 → 无字幕则下载音频（yt-dlp，bestaudio）→ ffmpeg 转 16k 单声道 wav。产物都在 `--out` 目录下，前缀为 BV 号。风控期可改用 `scripts/fetch_bili_api.py`（`main.py process` 在主通道失败时会自动尝试）。

Cookie：将 `scripts/jar.txt.example` 复制为 `scripts/jar.txt`（已 gitignore）。无文件时抓取脚本可尝试引导匿名 buvid。详见 `SECURITY.md`。

## 第 1.5 步：评论区摘取（默认执行）

```bash
python "$SKILL_DIR/scripts/fetch_comments.py" <BV号> --out "<media_dir绝对路径>" [--limit 30]
```

- 产出 `<bvid>_comments.txt`：按热度排序的热评（点赞数 | 用户 | 内容）。写入文献卡时**脱敏展示**（文档示例用 `@用户A`）。
- 评论只作理解与讨论素材：挑 5~10 条有信息量的进草案「💬 高赞评论摘录」节（保留点赞数），用来观察听众的共鸣点与质疑点；**不把评论当讲者观点引证**。
- 接口被限流或视频无评论时：非 `--strict` 下草案记「评论区未取到」并继续；显式 `--skip-comments` 时记「已跳过（--skip-comments）」；`--strict` 下失败即退出。

## 第 2 步：转写（FunASR/Paraformer，CPU 可跑）

```bash
# 若当前环境无 funasr，会探测 python3 / py -3.12 等；仍失败则提示 pip install -r requirements-asr.txt
python "$SKILL_DIR/scripts/run_asr.py" "<media_dir绝对路径>" <bvid1> [bvid2 ...]
```

- 产出 `<bvid>_转写.txt`（带标点全文）与 `<bvid>_转写.srt`（句级时间戳，来自 sentence_info；否则字级 timestamp 合成）。
- 若第 1 步已产出 `<bvid>_subtitle.txt`（平台自带字幕），跳过转写，直接用平台字幕；大纲时间戳亦会尝试读取平台 `<bvid>*.srt` / `*.vtt`。
- 参考速度：CPU 上约为音频时长的 0.2~0.5 倍；长视频批量转写时按顺序跑，别并行开多个 FunASR 进程。
- 用户指定其他平台（YouTube 等）时：直接用 yt-dlp 下载音频，其余步骤不变。
- ASR 模型名可在 `config.yaml` 的 `asr` 段覆盖。依赖说明见 README（base vs asr、CPU/GPU）。

## 第 3 步：整理与讨论稿

1. 读 `<bvid>_转写.txt`（+ `.srt` 拿时间戳）、`<bvid>_meta.json` 与 `<bvid>_comments.txt`（若有）。`main.py process` 已生成的 `<bvid>_文献卡草案.md` 可作为骨架继续完善。
2. 按模板写文献卡草案：`references/文献卡模板.md`（先读它）。核心逻辑大纲必须带时间戳（格式 `` `MM:SS` ``），来源于 SRT；含「💬 高赞评论摘录」节。
3. 「提炼出的原子永久卡片」区写 **1~3 个候选论点**：大白话表述 + 一句话解释 + 与现有永久卡片的关系。
4. 草案先放 `media_dir` 给用户看；**用户批准入库后**才写入 vault 文献卡目录，并登记留痕。
5. 与用户的探讨话术：「提炼出的候选观点为：[A] 与 [B]。你对哪一个有共鸣？打算如何用你的大白话表述它？」

## 查重纪律：区分「重复」与「良性关联」（务必保留）

提交候选清单**之前**，必须把新视频的候选论点与知识库现有永久卡片（含本工作流此前各轮已建的卡——库在长大，每轮都要重扫）逐张对照，并在草案中落一个「查重与链接建议」小节。判别标准：

1. **良性关联（可以各自成卡）**：只**部分**相似——两张卡的核心机制不同、各自独立成立、放在一起能对比分析或辅助记忆。典型：姊妹机制、同一策略的前后半程、同一家族的不同场景。处理：各自成卡 + **双向互链**，并写清关系（互补 / 对照 / 深化 / 修正）。
2. **重复（不立新卡）**：**大量**相似，或一方几乎完全包含另一方。三问：①核心机制是否同一件事？②删掉新卡，旧卡是否已覆盖全部行动指导？③两卡并列时能否一句话说清谁是谁？——命中两条以上即判重复。处理：**并入现有卡**或**补一条链接**，不新建文件。
3. **判决要显式交付**：同族/相邻候选必须逐条标注关系与「为何仍值得立」；重复项必须单独标出并给处理方式。不许把重复论点混进候选，也不许错杀良性关联。
4. 查重结论的执行（补链/并入）同样要登记《AI-修改留痕.md》（若用户库使用该文件）。

## 第 3.5 步：新旧卡片逻辑关系编织

查重决策完成、候选清单确定后（建卡前），把每张新卡与旧卡（含本轮其他新卡）**尽量在逻辑上挂上关系**——孤立知识点难记牢，挂进关系网才记得住。关系类型包括但不限于：互补、对照、深化、修正、冲突辩证、同族不同场景——**真实即可，禁止硬编**。

1. **关系必须显式标注**：类型 + 一句话理由；不许只丢 `[[双链]]` 不解释。
2. **允许冲突与张力**：观点打架时写「与 [[旧卡]] 冲突，需辩证看待」及各自成立条件。
3. **双向落地**：新卡「关联思考与双向链接」写 `[[旧卡]]（关系：XX —— 理由）`；旧卡对应节补回链。改旧卡只增不改并登记留痕。
4. **宁缺毋滥**：每张新卡至少 1 条强关系；找不到则写「暂未挂网」并说明原因。
5. **草案阶段先标**：在「🔍 查重与链接建议」或「🧩 逻辑关系编织」写出计划关系，批准建卡时一并落地。

## 第 4 步：用户批准后建卡

1. 按用户知识库现有永久卡片格式建卡，一事一记。路径以 `obsidian_vault` + 用户库结构为准。
2. 回填文献卡「提炼观点」区的 `[[双链]]`，把「候选」改为正式链接。
3. 登记留痕。绝不允许物理删除卡片（淘汰走 `status: deprecated` SOP）。

## 风控与故障（踩过的坑）

- **B站 412 限流**：停止请求静置 3~5 分钟 → 删除 `scripts/jar.txt` 重新生成 buvid → 重试；脚本已内置退避与元信息降级。宁可慢，不要并发轰炸。**禁止**并发跑多个 BV；`space --pages` 默认 1，需要翻页须先问用户；412 后必须停 3–5 分钟，不得擅自缩短 sleep 或改代码强刷。
- **ffmpeg 找不到**：PATH →（仅 Windows）winget Links → imageio-ffmpeg；都不在就 `pip install imageio-ffmpeg`。
- **转写质量**：专有名词可能错；交付前校对。
- **多P视频**：脚本只取 P1；整组时逐 P 调用。
- **funasr 环境**：探测当前解释器 / `python3` / `py -3.12` 等；仍失败则 `pip install -r requirements-asr.txt`（Python 3.10–3.12）。

## 维护记录（历史）

- 2026-09-03 v1.1：字级 timestamp 合成 SRT；字幕/音频扩展名白名单；ASR 校对附注。
- 2026-09-06 v1.2：新增评论区热评、按名称找视频与优先 UP 清单、文献卡「💬 高赞评论摘录」。
- 2026-09-07 v1.3：新旧卡片逻辑关系编织（查重后显式关系、双向落地、允许冲突）。
- 2026-09-11 Scheme B / v1.3.1：开源双模（CLI `main.py` + Skill）；配置解耦；合规 NOTICE/SECURITY；依赖拆分；`--strict`。
- 2026-09-12 v1.3.2：CLI `--help` 与配置解耦；网络 URLError 退避；平台字幕大纲；示例 UP 清单清空；Cookie 搜索示例改为可选。
