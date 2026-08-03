"""
Unit tests for scripts/fetch_gasoline.py

Run from project root:
    python scripts/test_fetch_gasoline.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

ネットワーク / xlsx I/O はカバーしない（curl_cffi / openpyxl ラッパ部分）。
「ロジック」を持つ関数だけを守る:
    - find_national_col : ヘッダから「全国」列を見つける
    - parse_grid        : 行タプル列 → 週次レコード（asOf ごとにピボット）
    - validate          : 値域・日付・油種存在チェック
    - merge             : 既存と新規の統合
    - _date_from_filename / XLSX_LINK_RE : 最新 xlsx URL 解決

グリッドは実シート（公表資料（経済産業局別））のレイアウトを模した合成データ。
実値は 260729.xlsx（2026-07-29 公表, 直近6週）の全国参考値を用いる。
"""

import datetime
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_gasoline import (  # noqa: E402
    XLSX_LINK_RE,
    _date_from_filename,
    find_national_col,
    merge,
    parse_grid,
    validate,
)

NCOL = 15  # 合成グリッドで「全国」列を置くインデックス


def _dt(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s)


def _row(*, label=None, date=None, national=None, filler=170):
    """1行分のタプルを組み立てる。label は col1、date は col3、national は NCOL。"""
    row = [None] * (NCOL + 1)
    if label is not None:
        row[1] = label
    if date is not None:
        row[3] = _dt(date)
        # 地域列（col4..13）にそれっぽい数値を詰める（national とは別値）。
        for ci in range(4, 14):
            row[ci] = filler
    if national is not None:
        row[NCOL] = national
    return tuple(row)


# 実シートを模したグリッド。ヘッダ2行 + タイトル日付 + 3油種×6週 + 無視すべき灯油。
SAMPLE_GRID = [
    (None, "石油製品小売市況調査", None, None),
    tuple([None] * 3 + [_dt("2026-07-29")]),  # タイトル日付（油種前 → 無視）
    tuple([None] * NCOL + ["全国（円／ﾘｯﾄﾙ）"]),  # ヘッダ（全国列）
    # ハイオク
    _row(label="ハイオク", date="2026-06-22", national=180.6),
    _row(date="2026-06-29", national=180.6),
    _row(date="2026-07-06", national=180.7),
    _row(date="2026-07-13", national=180.8),
    _row(date="2026-07-21", national=180.8),
    _row(date="2026-07-27", national=180.9),
    # レギュラー
    _row(label="レギュラー", date="2026-06-22", national=169.8),
    _row(date="2026-06-29", national=169.8),
    _row(date="2026-07-06", national=169.9),
    _row(date="2026-07-13", national=169.9),
    _row(date="2026-07-21", national=170.0),
    _row(date="2026-07-27", national=170.1),
    # 軽油
    _row(label="軽油", date="2026-06-22", national=159.0),
    _row(date="2026-06-29", national=159.2),
    _row(date="2026-07-06", national=159.2),
    _row(date="2026-07-13", national=159.3),
    _row(date="2026-07-21", national=159.4),
    _row(date="2026-07-27", national=159.4),
    # 灯油（PRODUCTS 外 & 全国参考値=0）→ 完全に無視されるべき
    _row(label="灯油", date="2026-06-22", national=0),
    _row(date="2026-07-27", national=0),
]


class TestFindNationalCol(unittest.TestCase):
    def test_finds_national_column(self):
        self.assertEqual(find_national_col(SAMPLE_GRID), NCOL)

    def test_raises_when_absent(self):
        with self.assertRaises(RuntimeError):
            find_national_col([(None, "北海道", "東北")])


class TestParseGrid(unittest.TestCase):
    def setUp(self):
        self.rows = parse_grid(SAMPLE_GRID)

    def test_one_record_per_week(self):
        self.assertEqual(len(self.rows), 6)

    def test_sorted_by_date(self):
        dates = [r["asOf"] for r in self.rows]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(dates[0], "2026-06-22")
        self.assertEqual(dates[-1], "2026-07-27")

    def test_label_carries_across_block(self):
        # ラベルは各ブロック先頭行だけ。以降の行にも同じ油種が付くこと。
        latest = self.rows[-1]
        self.assertAlmostEqual(latest["regular"], 170.1)
        self.assertAlmostEqual(latest["highOctane"], 180.9)
        self.assertAlmostEqual(latest["diesel"], 159.4)

    def test_all_three_products_present(self):
        for r in self.rows:
            self.assertIn("regular", r)
            self.assertIn("highOctane", r)
            self.assertIn("diesel", r)

    def test_kerosene_ignored(self):
        # 灯油キーは一切現れない。
        for r in self.rows:
            self.assertNotIn("kerosene", r)

    def test_title_date_before_label_ignored(self):
        # 2026-07-29（タイトル日付）はレコード化されない。
        self.assertNotIn("2026-07-29", [r["asOf"] for r in self.rows])

    def test_raises_when_no_rows(self):
        with self.assertRaises(RuntimeError):
            parse_grid([tuple([None] * NCOL + ["全国"])])  # ヘッダのみ


class TestValidate(unittest.TestCase):
    def test_ok(self):
        validate([{"asOf": "2026-07-27", "regular": 170.1, "highOctane": 180.9, "diesel": 159.4}])

    def test_partial_products_ok(self):
        # 一部油種が欠けても、1つでもあれば通す。
        validate([{"asOf": "2026-07-27", "regular": 170.1}])

    def test_no_products_raises(self):
        with self.assertRaises(RuntimeError):
            validate([{"asOf": "2026-07-27"}])

    def test_out_of_range_raises(self):
        with self.assertRaises(RuntimeError):
            validate([{"asOf": "2026-07-27", "regular": 17.0}])  # 円/L としてあり得ない
        with self.assertRaises(RuntimeError):
            validate([{"asOf": "2026-07-27", "regular": 999.0}])

    def test_bad_date_raises(self):
        with self.assertRaises(RuntimeError):
            validate([{"asOf": "2026-13-40", "regular": 170.1}])


class TestMerge(unittest.TestCase):
    def test_add_and_no_change(self):
        existing = [{"asOf": "2026-07-21", "regular": 170.0}]
        new = [
            {"asOf": "2026-07-21", "regular": 170.0},  # 同一→変化なし
            {"asOf": "2026-07-27", "regular": 170.1},  # 新規
        ]
        merged, added, updated = merge(existing, new)
        self.assertEqual((added, updated), (1, 0))
        self.assertEqual([r["asOf"] for r in merged], ["2026-07-21", "2026-07-27"])

    def test_overwrite_on_change(self):
        existing = [{"asOf": "2026-07-27", "regular": 169.9}]
        new = [{"asOf": "2026-07-27", "regular": 170.1}]
        merged, added, updated = merge(existing, new)
        self.assertEqual((added, updated), (0, 1))
        self.assertAlmostEqual(merged[0]["regular"], 170.1)


class TestXlsxUrlResolution(unittest.TestCase):
    def test_date_from_filename(self):
        self.assertEqual(str(_date_from_filename("260729")), "2026-07-29")
        self.assertEqual(str(_date_from_filename("250106")), "2025-01-06")

    def test_link_regex_only_matches_unsuffixed_weekly(self):
        html = (
            '<a href="/statistics/petroleum_and_lpgas/pl007/xlsx/260729.xlsx">週次</a>'
            '<a href="/statistics/petroleum_and_lpgas/pl007/xlsx/260722.xlsx">週次</a>'
            # 以下はサフィックス付き別調査 → マッチしないこと
            '<a href="/statistics/petroleum_and_lpgas/pl007/xlsx/260731k.xlsx">軽油ｲﾝﾀﾝｸ</a>'
            '<a href="/statistics/petroleum_and_lpgas/pl007/xlsx/260729s5.xlsx">別</a>'
        )
        dates = sorted(
            _date_from_filename(m.group("date")) for m in XLSX_LINK_RE.finditer(html)
        )
        self.assertEqual(len(dates), 2)
        self.assertEqual(str(dates[-1]), "2026-07-29")  # newest


if __name__ == "__main__":
    unittest.main(verbosity=2)
