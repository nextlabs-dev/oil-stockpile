"""
Unit tests for scripts/generate_ogp.py

Run from project root:
    python scripts/test_generate_ogp.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

Pillow 描画の出力ピクセルはテストしない（フォント可用性で結果が変わるため）。
本テストは「ロジック」を持つ関数だけを集中的に守る:
    - pick_latest_snapshot : asOf 昇順末尾を最新として返す
    - compute_fill_ratio   : 0..1 にクランプ・peak<=0 を 0 で扱う
    - color_for_ratio      : 閾値 0.4 / 0.8 の境界
    - format_jst_date      : '2026-04-28' → '2026年4月28日'
    - render_image (smoke) : 例外を投げず Image を返す
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_ogp import (  # noqa: E402
    PEAK_DAYS,
    TANK_MID,
    TANK_OK,
    TANK_WARN,
    Snapshot,
    color_for_ratio,
    compute_fill_ratio,
    format_jst_date,
    pick_latest_snapshot,
    render_image,
)


class PickLatestTest(unittest.TestCase):
    def test_returns_max_as_of(self):
        rows = [
            {"published": "2026-04-30", "asOf": "2026-04-27",
             "total": 210, "national": 128, "private": 80, "joint": 2},
            {"published": "2026-05-01", "asOf": "2026-04-28",
             "total": 211, "national": 128, "private": 81, "joint": 2},
            {"published": "2026-04-29", "asOf": "2026-04-26",
             "total": 209, "national": 127, "private": 80, "joint": 2},
        ]
        s = pick_latest_snapshot(rows)
        self.assertEqual(s.as_of, "2026-04-28")
        self.assertEqual(s.total, 211)
        self.assertEqual(s.private_, 81)

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            pick_latest_snapshot([])

    def test_missing_key_raises(self):
        rows = [{"published": "2026-05-01", "asOf": "2026-04-28", "total": 211}]
        with self.assertRaises(ValueError):
            pick_latest_snapshot(rows)


class FillRatioTest(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(compute_fill_ratio(200, 247), 200 / 247)

    def test_clamped_low(self):
        self.assertEqual(compute_fill_ratio(-10, 247), 0.0)

    def test_clamped_high(self):
        self.assertEqual(compute_fill_ratio(500, 247), 1.0)

    def test_zero_peak(self):
        self.assertEqual(compute_fill_ratio(100, 0), 0.0)

    def test_negative_peak(self):
        self.assertEqual(compute_fill_ratio(100, -1), 0.0)


class ColorForRatioTest(unittest.TestCase):
    def test_high(self):
        self.assertEqual(color_for_ratio(1.0), TANK_OK)
        self.assertEqual(color_for_ratio(0.8), TANK_OK)

    def test_mid(self):
        self.assertEqual(color_for_ratio(0.79), TANK_MID)
        self.assertEqual(color_for_ratio(0.4), TANK_MID)

    def test_low(self):
        self.assertEqual(color_for_ratio(0.39), TANK_WARN)
        self.assertEqual(color_for_ratio(0.0), TANK_WARN)


class FormatJstDateTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(format_jst_date("2026-04-28"), "2026年4月28日")

    def test_zero_padded(self):
        self.assertEqual(format_jst_date("2026-01-05"), "2026年1月5日")

    def test_invalid_returns_original(self):
        self.assertEqual(format_jst_date("not-a-date"), "not-a-date")
        self.assertEqual(format_jst_date(""), "")


class RenderSmokeTest(unittest.TestCase):
    """例外を投げずに 1200x630 の Image を返すことだけ確認する。"""

    def test_renders(self):
        s = Snapshot(
            published="2026-05-01",
            as_of="2026-04-28",
            total=211,
            national=128,
            private_=81,
            joint=2,
        )
        img = render_image(s, peak=PEAK_DAYS)
        self.assertEqual(img.size, (1200, 630))
        self.assertEqual(img.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
