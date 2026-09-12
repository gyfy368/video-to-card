# -*- coding: utf-8 -*-
"""Project configuration loader for video-to-card.

Loads config.yaml from the project root if present; otherwise falls back to
sensible defaults (media_dir=./output, empty preferred_ups, FunASR model names).
"""
from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS: dict[str, Any] = {
    "media_dir": "./output",
    # Keep empty in code; put personal UP lists only in config.yaml / config.example.yaml
    "preferred_ups": [],
    "obsidian_vault": "",
    "asr": {
        "model": "paraformer-zh",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, val in (override or {}).items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def _resolve_path(path: str) -> str:
    if not path:
        return path
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.normpath(os.path.join(ROOT_DIR, path))
    return path


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load YAML config merged over defaults.

    Search order when config_path is None:
      1. config.yaml (project root)
      2. config.local.yaml (project root, overrides config.yaml)
    Missing files are fine — defaults are used.
    """
    cfg = deepcopy(DEFAULTS)
    files_to_load: list[str] = []
    if config_path:
        if os.path.isfile(config_path):
            files_to_load.append(config_path)
    else:
        base_cfg = os.path.join(ROOT_DIR, "config.yaml")
        local_cfg = os.path.join(ROOT_DIR, "config.local.yaml")
        if os.path.isfile(base_cfg):
            files_to_load.append(base_cfg)
        if os.path.isfile(local_cfg):
            files_to_load.append(local_cfg)

    for path in files_to_load:
        try:
            import yaml  # lazy: only needed when a file exists
        except ImportError as e:
            raise SystemExit(
                "找到配置文件但未安装 PyYAML。请运行: pip install pyyaml\n"
                f"Config file found but PyYAML is missing: {e}"
            ) from e
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if not isinstance(loaded, dict):
            raise SystemExit(f"配置文件格式错误（需要 YAML 映射）: {path}")
        cfg = _deep_merge(cfg, loaded)

    cfg["media_dir"] = _resolve_path(str(cfg.get("media_dir") or DEFAULTS["media_dir"]))
    vault = cfg.get("obsidian_vault") or ""
    cfg["obsidian_vault"] = _resolve_path(str(vault)) if vault else ""
    if not isinstance(cfg.get("preferred_ups"), list):
        cfg["preferred_ups"] = list(DEFAULTS["preferred_ups"])
    if not isinstance(cfg.get("asr"), dict):
        cfg["asr"] = dict(DEFAULTS["asr"])
    return cfg


def get_media_dir(cli_out: str | None = None) -> str:
    """Resolve output directory: CLI --out wins, else config media_dir."""
    if cli_out:
        path = os.path.expanduser(cli_out)
        if not os.path.isabs(path):
            path = os.path.normpath(os.path.join(os.getcwd(), path))
        return path
    return load_config()["media_dir"]


def get_asr_models() -> dict[str, str]:
    asr = load_config().get("asr") or DEFAULTS["asr"]
    return {
        "model": asr.get("model", "paraformer-zh"),
        "vad_model": asr.get("vad_model", "fsmn-vad"),
        "punc_model": asr.get("punc_model", "ct-punc"),
    }


def get_preferred_ups() -> list[str]:
    return list(load_config().get("preferred_ups") or DEFAULTS["preferred_ups"])
