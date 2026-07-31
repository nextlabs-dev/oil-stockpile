"""
Unit tests for scripts/fetch_lpg.py

Run from project root:
    python scripts/test_fetch_lpg.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

ネットワーク / PDF I/O はカバーしない（curl_cffi / pdfplumber ラッパ部分）。
「ロジック」を持つ関数だけを守る:
    - parse_rows        : ZEN→HAN 後テキスト → 月次行配列
    - basis_row         : 国家日数入りの最新行を選ぶ
    - validate          : 値域・整合性チェック
    - merge             : 既存と新規の統合
    - _date_from_filename / PDF_LINK_RE : 最新PDF URL 解決
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_lpg import (  # noqa: E402
    PDF_LINK_RE,
    ZEN_TO_HAN,
    _date_from_filename,
    basis_row,
    merge,
    parse_rows,
    reiwa_to_gregorian,
    validate,
)

# 実PDF（令和8年7月公表, 20260715lp.pdf）の推移テーブルを ZEN→HAN 正規化した想定テキスト。
SAMPLE_TABLE = (
    "○ ＬＰガス備蓄の推移\n"
    "(単位:千トン)\n"
    "民間備蓄 国家備蓄\n"
    "基準備蓄量 保有量(日数) 保有量(日数)\n"
    "令和7年 5月 1,062 1,396(52.6) 1,392\n"
    "6月 1,087 1,420 (52.3) 1,392\n"
    "7月 1,065 1,489(55.9) 1,392\n"
    "令和8年 1月 1,092 1,420(52.0) 1,392\n"
    "4月 1,018 1,385 (54.4) 1,392\n"
    "5月 979 1,520(62.1) 1,392(53.0)\n"
)


class TestReiwa(unittest.TestCase):
    def test_reiwa(self):
        self.assertEqual(reiwa_to_gregorian(1), 2019)
        self.assertEqual(reiwa_to_gregorian(8), 2026)


class TestNormalize(unittest.TestCase):
    def test_full_to_half_width(self):
        self.assertEqual("１，５２０（６２．１）".translate(ZEN_TO_HAN), "1,520(62.1)")


class TestParseRows(unittest.TestCase):
    def setUp(self):
        self.rows = parse_rows(SAMPLE_TABLE)

    def test_row_count(self):
        self.assertEqual(len(self.rows), 6)

    def test_year_carries_across_rows(self):
        # 6月/7月は令和7年を継承、1月/4月/5月は令和8年
        months = [r["month"] for r in self.rows]
        self.assertEqual(
            months,
            ["2025-05", "2025-06", "2025-07", "2026-01", "2026-04", "2026-05"],
        )

    def test_as_of_is_month_end(self):
        self.assertEqual(self.rows[0]["asOf"], "2025-05-31")  # 5月=31日
        self.assertEqual(self.rows[3]["asOf"], "2026-01-31")

    def test_private_days_parsed_every_row(self):
        self.assertAlmostEqual(self.rows[0]["privateDays"], 52.6)
        self.assertAlmostEqual(self.rows[-1]["privateDays"], 62.1)

    def test_national_days_only_on_latest(self):
        self.assertIsNone(self.rows[0]["nationalDays"])
        self.assertIsNone(self.rows[0]["totalDays"])
        self.assertAlmostEqual(self.rows[-1]["nationalDays"], 53.0)
        self.assertAlmostEqual(self.rows[-1]["totalDays"], 115.1)

    def test_holdings_parsed(self):
        latest = self.rows[-1]
        self.assertEqual(latest["privateKijun"], 979)
        self.assertEqual(latest["privateHold"], 1520)
        self.assertEqual(latest["nationalHold"], 1392)

    def test_empty_text_raises(self):
        with self.assertRaises(RuntimeError):
            parse_rows("no table here")

    def test_implausible_reiwa_raises(self):
        with self.assertRaises(RuntimeError):
            parse_rows("令和99年 5月 979 1,520(62.1) 1,392(53.0)\n")


class TestBasisRow(unittest.TestCase):
    def test_picks_latest_row_with_national_days(self):
        rows = parse_rows(SAMPLE_TABLE)
        basis = basis_row(rows)
        self.assertEqual(basis["month"], "2026-05")
        self.assertAlmostEqual(basis["totalDays"], 115.1)

    def test_raises_when_no_national_days(self):
        rows = parse_rows(
            "令和8年 5月 979 1,520(62.1) 1,392\n"  # 国家日数なし
        )
        with self.assertRaises(RuntimeError):
            basis_row(rows)


class TestValidate(unittest.TestCase):
    def _row(self, **kw):
        base = {
            "asOf": "2026-05-31",
            "privateDays": 62.1,
            "nationalDays": 53.0,
            "totalDays": 115.1,
        }
        base.update(kw)
        return base

    def test_ok(self):
        validate(self._row())  # 例外なし

    def test_total_mismatch_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._row(totalDays=99.9))

    def test_out_of_range_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._row(privateDays=5.0, totalDays=58.0))

    def test_bad_date_raises(self):
        with self.assertRaises(RuntimeError):
            validate(self._row(asOf="2026-13-40"))


class TestMerge(unittest.TestCase):
    def test_add_and_update(self):
        existing = [{"month": "2026-04", "privateDays": 54.4}]
        new = [
            {"month": "2026-04", "privateDays": 54.4},  # 同一→変化なし
            {"month": "2026-05", "privateDays": 62.1},  # 新規
        ]
        merged, added, updated = merge(existing, new)
        self.assertEqual(added, 1)
        self.assertEqual(updated, 0)
        self.assertEqual([r["month"] for r in merged], ["2026-04", "2026-05"])

    def test_overwrite_on_change(self):
        existing = [{"month": "2026-05", "privateDays": 60.0}]
        new = [{"month": "2026-05", "privateDays": 62.1}]
        merged, added, updated = merge(existing, new)
        self.assertEqual((added, updated), (0, 1))
        self.assertAlmostEqual(merged[0]["privateDays"], 62.1)


class TestPdfUrlResolution(unittest.TestCase):
    def test_date_from_filename(self):
        self.assertEqual(str(_date_from_filename("20260715")), "2026-07-15")
        self.assertEqual(str(_date_from_filename("250815")), "2025-08-15")

    def test_link_regex_captures_various_namings(self):
        html = (
            '<a href="/statistics/petroleum_and_lpgas/pl002/pdf/2026/20260715lp.pdf">x</a>'
            '<a href="/statistics/petroleum_and_lpgas/pl002/pdf/2025/250815LP.pdf">x</a>'
            '<a href="/statistics/petroleum_and_lpgas/pl002/pdf/2023/230417.pdf">x</a>'
        )
        dates = sorted(
            _date_from_filename(m.group("date")) for m in PDF_LINK_RE.finditer(html)
        )
        self.assertEqual(len(dates), 3)
        self.assertEqual(str(dates[-1]), "2026-07-15")  # newest


if __name__ == "__main__":
    unittest.main(verbosity=2)
