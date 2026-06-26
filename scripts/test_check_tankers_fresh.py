"""
Unit tests for scripts/check_tankers_fresh.py

Run from project root:
    python scripts/test_check_tankers_fresh.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

判定ロジック evaluate() は now を注入する純粋関数として直接テストする。
main() はファイル読み取り (read_json) を境界としてモックし、終了コードのみ検証する。
"""

import os
import sys
import unittest
from datetime import UTC, datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check_tankers_fresh  # noqa: E402
from check_tankers_fresh import evaluate  # noqa: E402

# 全テスト共通の固定「現在時刻」。fetchedAt は ここからの相対で組む。
NOW = datetime(2026, 6, 26, 12, 0, 0, tzinfo=UTC)


def _iso(dt):
    return dt.isoformat(timespec="seconds")


class TestEvaluate(unittest.TestCase):
    def test_fresh_sample_returns_0(self):
        data = {"fetchedAt": _iso(NOW - timedelta(hours=1))}
        code, _ = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 0)

    def test_stale_sample_returns_1(self):
        data = {"fetchedAt": _iso(NOW - timedelta(hours=7))}
        code, msg = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 1)
        self.assertIn("stale", msg.lower())

    def test_exactly_at_threshold_is_fresh(self):
        # ちょうど max_age なら fresh（境界は strict greater-than で stale 判定）
        data = {"fetchedAt": _iso(NOW - timedelta(hours=6))}
        code, _ = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 0)

    def test_just_over_threshold_is_stale(self):
        data = {"fetchedAt": _iso(NOW - timedelta(hours=6, seconds=1))}
        code, _ = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 1)

    def test_missing_fetched_at_returns_1(self):
        code, msg = evaluate({}, NOW, max_age_hours=6)
        self.assertEqual(code, 1)
        self.assertIn("fetchedAt", msg)

    def test_empty_fetched_at_returns_1(self):
        code, _ = evaluate({"fetchedAt": ""}, NOW, max_age_hours=6)
        self.assertEqual(code, 1)

    def test_malformed_fetched_at_returns_1(self):
        code, msg = evaluate({"fetchedAt": "not-a-timestamp"}, NOW, max_age_hours=6)
        self.assertEqual(code, 1)
        self.assertIn("fetchedAt", msg)

    def test_non_string_fetched_at_returns_1(self):
        # 数値など文字列でない fetchedAt も壊れ扱いで fail（沈黙の劣化を避ける）
        code, _ = evaluate({"fetchedAt": 12345}, NOW, max_age_hours=6)
        self.assertEqual(code, 1)

    def test_naive_datetime_treated_as_utc(self):
        # tz 無しの fetchedAt は UTC とみなす（write_output は UTC を書くため）
        naive = (NOW - timedelta(hours=1)).replace(tzinfo=None)
        data = {"fetchedAt": naive.isoformat(timespec="seconds")}
        code, _ = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 0)

    def test_future_fetched_at_is_fresh(self):
        # クロックスキューで未来時刻になっても age 負 → fresh（安全側）
        data = {"fetchedAt": _iso(NOW + timedelta(hours=1))}
        code, _ = evaluate(data, NOW, max_age_hours=6)
        self.assertEqual(code, 0)


class TestMain(unittest.TestCase):
    """main() はファイル読み取りを境界としてモックし終了コードを検証する。"""

    def test_missing_file_returns_1(self):
        with mock.patch.object(check_tankers_fresh, "read_json", side_effect=FileNotFoundError):
            rc = check_tankers_fresh.main(["--max-age-hours", "6"])
        self.assertEqual(rc, 1)

    def test_fresh_file_returns_0(self):
        # 遠未来の fetchedAt は実時刻 now に対して必ず fresh
        with mock.patch.object(
            check_tankers_fresh,
            "read_json",
            return_value={"fetchedAt": "2999-01-01T00:00:00+00:00"},
        ):
            rc = check_tankers_fresh.main(["--max-age-hours", "6"])
        self.assertEqual(rc, 0)

    def test_stale_file_returns_1(self):
        # 遠過去の fetchedAt は実時刻 now に対して必ず stale
        with mock.patch.object(
            check_tankers_fresh,
            "read_json",
            return_value={"fetchedAt": "2000-01-01T00:00:00+00:00"},
        ):
            rc = check_tankers_fresh.main(["--max-age-hours", "6"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
