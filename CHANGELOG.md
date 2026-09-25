# Changelog

## Unreleased

- README Quick Start is now skill-install plus base deps only; extra commands and config are marked skippable.
- README: document `npx skills add gyfy368/video-to-card` as the primary Agent Skill install path; keep manual copy as the fallback without Node.js.
- README: put Quick Start first; `config.yaml` is optional and no longer a step before install.

## v1.3.2 — 2026-09-12

- Decouple `python main.py --help` from config / PyYAML loading.
- Empty `preferred_ups` in `config.example.yaml` (commented examples only).
- Network calls catch `URLError` with retry/backoff; `argparse` for `--out`.
- Platform `.srt`/`.vtt` used for draft outline scaffolding; distinguish `--skip-comments`.
- `find_up` prints usage and exits 2 with no args; ASR temp WAV cleaned in `finally`.
- README: Python 3.10–3.12 badge, local-only `jar.txt` note, GitHub Description/Topics snippet.
- SKILL frontmatter: Chinese triggers first; version/license moved to body.

## v1.3.1 — 2026-09-11

- Legal / compliance: `NOTICE.md`, README Legal section; WBI reverse-engineering disclaimer.
- Split dependencies: `requirements-base.txt` / `requirements-asr.txt`.
- Cross-platform ffmpeg / Python probing; fix `fetch_comments` import path.
- Empty default `preferred_ups` in code; `--strict` on `main.py process`.
- Basic `unittest` suite under `tests/`.
- `SECURITY.md`; Skill frontmatter version/license; portable media paths.

## v1.3 — 2026-09-07

- Logic-relation weaving after duplicate checks; open-source dual-mode CLI + Skill.

## v1.2 — 2026-09-06

- Hot comments, name search + preferred UP list, literature-card comment section.

## v1.1 — 2026-09-03

- Char-level timestamp → SRT; subtitle/audio extension whitelist; ASR proofreading notes.
