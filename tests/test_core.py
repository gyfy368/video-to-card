# -*- coding: utf-8 -*-
"""Core unit tests for video-to-card (stdlib unittest; no pytest required)."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import config as cfg  # noqa: E402
import main as app  # noqa: E402
import run_asr  # noqa: E402


class TestParseBvid(unittest.TestCase):
    def test_plain_bvid(self) -> None:
        self.assertEqual(app._parse_bvid("BV1xx411c7mD"), "BV1xx411c7mD")

    def test_url(self) -> None:
        url = "https://www.bilibili.com/video/BV1GJ411x7h7?spm_id_from=333.337"
        self.assertEqual(app._parse_bvid(url), "BV1GJ411x7h7")

    def test_embedded_in_text(self) -> None:
        self.assertEqual(
            app._parse_bvid("请看 BV1xx411c7mD 这个视频"),
            "BV1xx411c7mD",
        )

    def test_invalid(self) -> None:
        with self.assertRaises(SystemExit):
            app._parse_bvid("not-a-bvid")


class TestConfig(unittest.TestCase):
    def test_deep_merge_nested(self) -> None:
        base = {"a": 1, "asr": {"model": "x", "vad_model": "y"}, "preferred_ups": []}
        override = {"asr": {"model": "z"}, "preferred_ups": ["UP1"]}
        out = cfg._deep_merge(base, override)
        self.assertEqual(out["a"], 1)
        self.assertEqual(out["asr"]["model"], "z")
        self.assertEqual(out["asr"]["vad_model"], "y")
        self.assertEqual(out["preferred_ups"], ["UP1"])
        # base must not be mutated
        self.assertEqual(base["asr"]["model"], "x")

    def test_defaults_empty_preferred_ups(self) -> None:
        self.assertEqual(cfg.DEFAULTS["preferred_ups"], [])

    def test_load_config_fallback_without_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing = os.path.join(td, "nope.yaml")
            with mock.patch.object(cfg, "ROOT_DIR", td):
                loaded = cfg.load_config(missing)
            self.assertEqual(loaded["preferred_ups"], [])
            self.assertTrue(os.path.isabs(loaded["media_dir"]))
            self.assertEqual(loaded["asr"]["model"], "paraformer-zh")

    def test_load_config_from_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "config.yaml")
            with open(path, "w", encoding="utf-8") as f:
                f.write("media_dir: ./media\n")  # file must exist for loader branch
            fake_yaml = mock.MagicMock()
            fake_yaml.safe_load.return_value = {
                "media_dir": "./media",
                "preferred_ups": ["Alpha"],
                "asr": {"model": "custom-model"},
            }
            with mock.patch.object(cfg, "ROOT_DIR", td):
                with mock.patch.dict(sys.modules, {"yaml": fake_yaml}):
                    loaded = cfg.load_config(path)
            self.assertEqual(loaded["preferred_ups"], ["Alpha"])
            self.assertEqual(loaded["asr"]["model"], "custom-model")
            self.assertIn("media", loaded["media_dir"])
            fake_yaml.safe_load.assert_called_once()


class TestBuildSrt(unittest.TestCase):
    def test_build_srt_alignment(self) -> None:
        # timestamps are [start_ms, end_ms] per character (excluding punctuation)
        text = "你好。世界！"
        # 4 content chars: 你 好 世 界
        timestamp = [
            [0, 200],
            [200, 400],
            [500, 700],
            [700, 900],
        ]
        srt = run_asr.build_srt(text, timestamp)
        self.assertIsNotNone(srt)
        assert srt is not None
        self.assertIn("00:00:00,000 --> 00:00:00,400", srt)
        self.assertIn("你好。", srt)
        self.assertIn("世界！", srt)
        blocks = [b for b in srt.strip().split("\n\n") if b.strip()]
        self.assertEqual(len(blocks), 2)

    def test_build_srt_empty_timestamp(self) -> None:
        self.assertIsNone(run_asr.build_srt("你好。", None))
        self.assertIsNone(run_asr.build_srt("你好。", []))

    def test_ms2srt(self) -> None:
        self.assertEqual(run_asr.ms2srt(3661001), "01:01:01,001")


class TestStrictFlag(unittest.TestCase):
    def test_parser_has_strict(self) -> None:
        p = app.build_parser()
        args = p.parse_args(["process", "BV1xx411c7mD", "--strict"])
        self.assertTrue(args.strict)


class TestEnhancements(unittest.TestCase):
    def test_yaml_escape(self) -> None:
        raw = '深度解读：为什么 "这样" 做？'
        escaped = app._yaml_escape(raw)
        self.assertTrue(escaped.startswith('"'))
        self.assertTrue(escaped.endswith('"'))
        self.assertIn('\\"这样\\"', escaped)

    def test_missing_jar_returns_empty(self) -> None:
        import bili_space
        res = bili_space.load_cookies("non_existent_file_12345.txt")
        self.assertEqual(res, "")

    def test_config_local_yaml_overrides_base(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base_file = os.path.join(td, "config.yaml")
            local_file = os.path.join(td, "config.local.yaml")
            with open(base_file, "w", encoding="utf-8") as f:
                f.write("dummy base")
            with open(local_file, "w", encoding="utf-8") as f:
                f.write("dummy local")

            def fake_safe_load(f):
                content = f.read()
                if "base" in content:
                    return {"media_dir": "./base_out", "preferred_ups": ["UP1"]}
                return {"preferred_ups": ["UP1", "UP2"]}

            fake_yaml = mock.MagicMock()
            fake_yaml.safe_load.side_effect = fake_safe_load

            with mock.patch.object(cfg, "ROOT_DIR", td):
                with mock.patch.dict(sys.modules, {"yaml": fake_yaml}):
                    loaded = cfg.load_config()
                    self.assertEqual(loaded["preferred_ups"], ["UP1", "UP2"])
                    self.assertIn("base_out", loaded["media_dir"])


class TestCliRobustness(unittest.TestCase):
    def test_help_does_not_load_config(self) -> None:
        with mock.patch.object(app, "load_config") as lc:
            with self.assertRaises(SystemExit) as cm:
                app.main(["--help"])
            self.assertEqual(cm.exception.code, 0)
            lc.assert_not_called()

    def test_find_up_no_args_exits_2(self) -> None:
        import find_up

        with mock.patch.object(sys, "argv", ["find_up.py"]):
            with self.assertRaises(SystemExit) as cm:
                find_up.main()
            self.assertEqual(cm.exception.code, 2)

    def test_srt_outline_hints_platform_srt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td)
            bvid = "BV1xx411c7mD"
            srt = outdir / f"{bvid}.zh-CN.srt"
            srt.write_text(
                "1\n00:01:05,000 --> 00:01:08,000\n平台字幕第一句\n\n"
                "2\n00:02:00,000 --> 00:02:03,000\n平台字幕第二句\n",
                encoding="utf-8",
            )
            hints = app._srt_outline_hints(outdir, bvid)
            self.assertTrue(hints)
            self.assertIn("01:05", hints[0])
            self.assertIn("平台字幕第一句", hints[0])

    def test_skip_comments_note_in_draft(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            outdir = Path(td)
            bvid = "BV1xx411c7mD"
            (outdir / f"{bvid}_meta.json").write_text(
                '{"bvid":"%s","title":"t","owner":"u","url":"https://x"}' % bvid,
                encoding="utf-8",
            )
            path = app._write_draft_card(outdir, bvid, skip_comments=True)
            text = path.read_text(encoding="utf-8")
            self.assertIn("已跳过（--skip-comments）", text)
            self.assertNotIn("评论区未取到", text)


if __name__ == "__main__":
    unittest.main()
