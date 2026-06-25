"""
Unit tests for scripts/fetch_pdf.py

Run from project root:
    python scripts/test_fetch_pdf.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

Network/PDF I/O は意図的にカバーしない（pdfplumber/urllib のラッパに過ぎない部分は
壊れる粒度が違うため）。本テストは「ロジック」を持つ関数だけを集中的に守る:
    - parse_snapshots  : テキスト → 構造化 snapshot 配列
    - validate         : 値域・整合性チェック
    - merge            : 既存と新規の統合
    - reiwa_to_gregorian
    - ZEN_TO_HAN translate table
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_pdf import (  # noqa: E402
    HEADER_RE,
    ZEN_TO_HAN,
    merge,
    parse_snapshots,
    reiwa_to_gregorian,
    validate,
)


def make_block(reiwa_y, mp, dp, ma, da, *, total, national, priv, joint, extra_space=False):
    """ZEN→HAN 後のテキスト1ブロックを作る。"""
    sep = " " if extra_space else ""
    return (
        f"令和{reiwa_y}年{mp}月{dp}日（{ma}月{sep}{da}日時点）\n"
        "備蓄日数\n"
        f"国家備蓄 {national}日分\n"
        f"民間備蓄 {priv}日分\n"
        f"産油国共同備蓄 {joint}日分\n"
        f"合計 {total}日分\n"
    )


class TestReiwaToGregorian(unittest.TestCase):
    def test_reiwa_first_year(self):
        self.assertEqual(reiwa_to_gregorian(1), 2019)

    def test_reiwa_eighth_year(self):
        self.assertEqual(reiwa_to_gregorian(8), 2026)

    def test_reiwa_tenth_year(self):
        self.assertEqual(reiwa_to_gregorian(10), 2028)


class TestNormalize(unittest.TestCase):
    def test_full_to_half_width_digits(self):
        self.assertEqual(
            "０１２３４５６７８９".translate(ZEN_TO_HAN),
            "0123456789",
        )

    def test_mixed_with_kanji(self):
        self.assertEqual(
            "合計 ２１１日分".translate(ZEN_TO_HAN),
            "合計 211日分",
        )

    def test_no_change_for_already_halfwidth(self):
        self.assertEqual("123日分".translate(ZEN_TO_HAN), "123日分")


class TestHeaderRegex(unittest.TestCase):
    """ヘッダ正規表現自体の挙動を確認（パース失敗の根本原因切り分け用）。"""

    def test_matches_basic(self):
        m = HEADER_RE.search("令和8年5月1日（4月28日時点）")
        self.assertIsNotNone(m)
        self.assertEqual(m.groups(), ("8", "5", "1", "4", "28"))

    def test_matches_with_internal_space(self):
        # 実 PDF に存在: 「４月 27日時点」「令和８年４月 30日」
        m = HEADER_RE.search("令和8年4月 30日（4月 27日時点）")
        self.assertIsNotNone(m)
        self.assertEqual(m.groups(), ("8", "4", "30", "4", "27"))

    def test_does_not_match_random_text(self):
        self.assertIsNone(HEADER_RE.search("石油備蓄の状況（推計値の速報）"))


class TestParseSnapshots(unittest.TestCase):
    def test_single_well_formed_block(self):
        text = make_block(8, 5, 1, 4, 28, total=211, national=128, priv=81, joint=2)
        result = parse_snapshots(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(
            result[0],
            {
                "published": "2026-05-01",
                "asOf": "2026-04-28",
                "total": 211,
                "national": 128,
                "private": 81,
                "joint": 2,
            },
        )

    def test_multiple_blocks_preserve_doc_order(self):
        text = (
            make_block(8, 5, 1, 4, 28, total=211, national=128, priv=81, joint=2)
            + make_block(8, 4, 30, 4, 27, total=211, national=128, priv=81, joint=2)
            + make_block(8, 4, 29, 4, 26, total=210, national=128, priv=81, joint=2)
        )
        result = parse_snapshots(text)
        self.assertEqual(len(result), 3)
        self.assertEqual([r["asOf"] for r in result], ["2026-04-28", "2026-04-27", "2026-04-26"])

    def test_year_wrap_jan_publish_dec_asof(self):
        # 公表 = 令和9年1月5日 (2027-01-05)、asOf = 12月28日 → 2026-12-28
        text = make_block(9, 1, 5, 12, 28, total=200, national=120, priv=78, joint=2)
        result = parse_snapshots(text)
        self.assertEqual(result[0]["published"], "2027-01-05")
        self.assertEqual(result[0]["asOf"], "2026-12-28")

    def test_empty_text_raises(self):
        with self.assertRaises(RuntimeError):
            parse_snapshots("")

    def test_no_header_raises(self):
        text = "これは関係ない文章です。備蓄日数 国家備蓄 100日分"
        with self.assertRaises(RuntimeError):
            parse_snapshots(text)

    def test_partial_block_is_skipped_others_kept(self):
        # 1個目: 合計が欠落 → スキップされるべき
        partial = (
            "令和8年5月1日（4月28日時点）\n"
            "備蓄日数\n"
            "国家備蓄 128日分\n"
            "民間備蓄 81日分\n"
            "産油国共同備蓄 2日分\n"
            # 合計 行がない
        )
        full = make_block(8, 4, 30, 4, 27, total=210, national=128, priv=80, joint=2)
        result = parse_snapshots(partial + full)
        # partial はスキップ、full のみ採用
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asOf"], "2026-04-27")

    def test_extra_whitespace_in_header(self):
        # 実PDF想定: 「４月 27日時点」のような半角スペース混入
        text = make_block(
            8, 5, 1, 4, 28, total=211, national=128, priv=81, joint=2, extra_space=True
        )
        result = parse_snapshots(text)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["asOf"], "2026-04-28")

    def test_only_garbage_blocks_returns_empty(self):
        # ヘッダはあるが本文が一切ない → ループは回るが snapshots は空のまま、
        # その場合 parse_snapshots は空リストを返す（呼び出し側で 0件 abort 判断）
        text = "令和8年5月1日（4月28日時点）\nまったく無関係な文章\n"
        result = parse_snapshots(text)
        self.assertEqual(result, [])


class TestValidate(unittest.TestCase):
    def _ok_snap(self, **overrides):
        s = {
            "published": "2026-05-01",
            "asOf": "2026-04-28",
            "total": 211,
            "national": 128,
            "private": 81,
            "joint": 2,
        }
        s.update(overrides)
        return s

    def test_in_range_no_raise(self):
        validate(self._ok_snap())

    def test_total_too_low_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._ok_snap(total=49, national=20, private=20, joint=9))

    def test_total_at_lower_bound_ok(self):
        validate(self._ok_snap(total=50, national=25, private=20, joint=5))

    def test_total_at_upper_bound_ok(self):
        validate(self._ok_snap(total=500, national=300, private=180, joint=20))

    def test_total_too_high_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._ok_snap(total=501, national=300, private=180, joint=21))

    def test_breakdown_off_by_2_ok(self):
        # 128+81+2=211. total=213 → 差2 → OK
        validate(self._ok_snap(total=213))

    def test_breakdown_off_by_3_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._ok_snap(total=214))

    def test_prev_total_none_skips_change_check(self):
        # 大きく差があっても prev_total=None なら検査されない
        validate(self._ok_snap(total=211), prev_total=None)

    def test_normal_daily_change_ok(self):
        validate(self._ok_snap(total=211), prev_total=210)

    def test_change_at_threshold_ok(self):
        # abs(210 - 180) = 30 → 30 > 30 が False → OK
        validate(self._ok_snap(total=210, national=128, private=80, joint=2), prev_total=180)

    def test_change_above_threshold_raises(self):
        # abs(211 - 180) = 31 → fail
        with self.assertRaises(RuntimeError):
            validate(self._ok_snap(total=211), prev_total=180)


class TestMerge(unittest.TestCase):
    def _row(self, asof, total=200):
        return {
            "published": asof,
            "asOf": asof,
            "total": total,
            "national": 100,
            "private": 80,
            "joint": total - 180,
        }

    def test_all_new_added(self):
        merged, added, updated = merge(
            existing=[],
            new=[self._row("2026-04-26"), self._row("2026-04-27"), self._row("2026-04-28")],
        )
        self.assertEqual(len(merged), 3)
        self.assertEqual(added, 3)
        self.assertEqual(updated, 0)

    def test_idempotent_when_input_matches(self):
        rows = [self._row("2026-04-26"), self._row("2026-04-27")]
        merged, added, updated = merge(rows, list(rows))
        self.assertEqual(added, 0)
        self.assertEqual(updated, 0)

    def test_mixed_add_and_existing(self):
        existing = [self._row("2026-04-26"), self._row("2026-04-27")]
        new = [self._row("2026-04-27"), self._row("2026-04-28")]
        merged, added, updated = merge(existing, new)
        self.assertEqual(len(merged), 3)
        self.assertEqual(added, 1)
        self.assertEqual(updated, 0)

    def test_value_change_counts_as_update(self):
        existing = [self._row("2026-04-27", total=200)]
        new = [self._row("2026-04-27", total=201)]
        merged, added, updated = merge(existing, new)
        self.assertEqual(added, 0)
        self.assertEqual(updated, 1)
        # 上書き値が反映される
        self.assertEqual(merged[0]["total"], 201)

    def test_output_sorted_by_asOf(self):
        # わざと逆順で渡す
        existing = [self._row("2026-04-28"), self._row("2026-04-26")]
        merged, _, _ = merge(existing, [])
        self.assertEqual([r["asOf"] for r in merged], ["2026-04-26", "2026-04-28"])

    def test_pdf_wins_on_conflict(self):
        # 既存と新規で値が違う場合、新規（PDF由来）が優先
        existing = [self._row("2026-04-27", total=200)]
        new = [self._row("2026-04-27", total=205)]
        merged, _, _ = merge(existing, new)
        self.assertEqual(merged[0]["total"], 205)


if __name__ == "__main__":
    unittest.main(verbosity=2)
