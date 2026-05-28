"""
Unit tests for scripts/generate_ogp.py

Run from project root:
    python scripts/test_generate_ogp.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

Pillow 描画の出力ピクセルはテストしない（フォント可用性で結果が変わるため）。
本テストは「ロジック」を持つ関数と、リデザイン後の必須前提条件だけを守る:
    - pick_latest_snapshot : asOf 昇順末尾を最新として返す
    - compute_current_days : サイト側と同じ式で「いま時点」の日数を返す
    - compute_fill_ratio   : 0..1 にクランプ・peak<=0 を 0 で扱う
    - format_jst_date      : '2026-04-28' → '2026年4月28日'
    - resolve_inter        : リポジトリ同梱 Inter TTF が解決できる
    - counter_top.png      : OGP の右側ビジュアル素材が存在する
    - render_image (smoke) : 例外を投げず 1200x630 Image を返す
"""

import os
import sys
import unittest
from datetime import datetime, timezone

from PIL import Image, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_ogp import (  # noqa: E402
    ILLUSTRATION_PATH,
    PEAK_DAYS,
    Snapshot,
    compute_current_days,
    compute_fill_ratio,
    format_jst_date,
    pick_latest_snapshot,
    render_image,
    resolve_inter,
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


class ComputeCurrentDaysTest(unittest.TestCase):
    def _snap(self, as_of: str, total: int) -> Snapshot:
        return Snapshot(
            published="2026-05-01",
            as_of=as_of,
            total=total,
            national=128,
            private_=81,
            joint=2,
        )

    def test_at_as_of_returns_total(self):
        s = self._snap("2026-04-28", 211)
        # asOf 当日 00:00 JST = 前日 15:00 UTC
        now = datetime(2026, 4, 27, 15, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(compute_current_days(s, now), 211.0)

    def test_one_day_later_minus_one(self):
        s = self._snap("2026-04-28", 211)
        now = datetime(2026, 4, 28, 15, 0, 0, tzinfo=timezone.utc)  # asOf+1日 00:00 JST
        self.assertAlmostEqual(compute_current_days(s, now), 210.0)

    def test_partial_day(self):
        s = self._snap("2026-04-28", 211)
        # asOf 翌日 12:00 JST = asOf から 1.5 日経過
        now = datetime(2026, 4, 29, 3, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(compute_current_days(s, now), 209.5)

    def test_before_as_of_caps_at_total(self):
        s = self._snap("2026-04-28", 211)
        # 端末時計が asOf より過去のケース。total で頭打ち。
        now = datetime(2026, 4, 26, 0, 0, 0, tzinfo=timezone.utc)
        self.assertAlmostEqual(compute_current_days(s, now), 211.0)

    def test_floor_below_zero(self):
        s = self._snap("2026-04-28", 3)
        # total を大幅に超える経過。0 で下限。
        now = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(compute_current_days(s, now), 0.0)


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


class FormatJstDateTest(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(format_jst_date("2026-04-28"), "2026年4月28日")

    def test_zero_padded(self):
        self.assertEqual(format_jst_date("2026-01-05"), "2026年1月5日")

    def test_invalid_returns_original(self):
        self.assertEqual(format_jst_date("not-a-date"), "not-a-date")
        self.assertEqual(format_jst_date(""), "")


class InterFontResolvesTest(unittest.TestCase):
    """リポジトリ同梱 Inter TTF が読めることを確認。
    OGP の見た目はこの 3 ファイルに依存する。"""

    def test_extrabold_resolves(self):
        font = resolve_inter("extrabold", 220)
        self.assertIsInstance(font, ImageFont.FreeTypeFont)
        self.assertEqual(font.getname()[0], "Inter")

    def test_bold_resolves(self):
        font = resolve_inter("bold", 17)
        self.assertIsInstance(font, ImageFont.FreeTypeFont)
        self.assertEqual(font.getname()[0], "Inter")

    def test_semibold_resolves(self):
        font = resolve_inter("semibold", 14)
        self.assertIsInstance(font, ImageFont.FreeTypeFont)
        self.assertEqual(font.getname()[0], "Inter")


class CounterTopExistsTest(unittest.TestCase):
    """OGP のヒーローカード右側に貼るイラストが残っていることを確認する安全装置。"""

    def test_file_present_and_openable(self):
        self.assertTrue(ILLUSTRATION_PATH.exists(), f"{ILLUSTRATION_PATH} missing")
        with Image.open(ILLUSTRATION_PATH) as img:
            img.verify()


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
        img = render_image(s, current_days=float(s.total), peak=PEAK_DAYS)
        self.assertEqual(img.size, (1200, 630))
        self.assertEqual(img.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
