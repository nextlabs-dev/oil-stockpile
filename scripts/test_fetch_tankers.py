"""
Unit tests for scripts/fetch_tankers.py

Run from project root:
    python scripts/test_fetch_tankers.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

WebSocket I/O は意図しないでカバーしない（websockets ライブラリのラッパに過ぎないため）。
本テストはロジック関数のみ:
    - is_tanker_type
    - normalize_destination
    - match_japan_port
    - aggregate
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_tankers import (  # noqa: E402
    aggregate,
    is_tanker_type,
    match_japan_port,
    normalize_destination,
)


class TestIsTankerType(unittest.TestCase):
    def test_80_through_89_are_tankers(self):
        for t in range(80, 90):
            self.assertTrue(is_tanker_type(t), f"type {t} should be tanker")

    def test_other_codes_are_not_tankers(self):
        for t in [0, 30, 70, 79, 90, 99, 100]:
            self.assertFalse(is_tanker_type(t), f"type {t} should not be tanker")

    def test_none_handled(self):
        self.assertFalse(is_tanker_type(None))

    def test_string_handled(self):
        self.assertFalse(is_tanker_type("80"))


class TestNormalizeDestination(unittest.TestCase):
    def test_at_padding_removed(self):
        self.assertEqual(normalize_destination("YOKOHAMA@@@"), "YOKOHAMA")

    def test_lowercase_uppercased(self):
        self.assertEqual(normalize_destination("yokohama"), "YOKOHAMA")

    def test_internal_whitespace_removed(self):
        self.assertEqual(normalize_destination("JP YOK"), "JPYOK")

    def test_punctuation_removed(self):
        self.assertEqual(normalize_destination("CHIBA-1"), "CHIBA1")
        self.assertEqual(normalize_destination("KIIRE/JP"), "KIIREJP")

    def test_empty_string(self):
        self.assertEqual(normalize_destination(""), "")

    def test_none_returns_empty(self):
        self.assertEqual(normalize_destination(None), "")

    def test_only_at_signs(self):
        self.assertEqual(normalize_destination("@@@@@@@@@@"), "")

    def test_real_padded_format(self):
        # 実 AIS で見られる 20文字パディング
        self.assertEqual(
            normalize_destination("JP HKT              "),
            "JPHKT",
        )


class TestMatchJapanPort(unittest.TestCase):
    def test_unloc_yokohama(self):
        self.assertEqual(match_japan_port("JPYOK"), "YOKOHAMA")

    def test_unloc_chiba(self):
        self.assertEqual(match_japan_port("JPCHB"), "CHIBA")

    def test_unloc_kiire(self):
        self.assertEqual(match_japan_port("JPKII"), "KIIRE")

    def test_yokohama_lowercase(self):
        self.assertEqual(match_japan_port("yokohama"), "YOKOHAMA")

    def test_negishi_normalizes_to_yokohama(self):
        # 根岸製油所は横浜に集約
        self.assertEqual(match_japan_port("NEGISHI"), "YOKOHAMA")

    def test_keiyo_normalizes_to_chiba(self):
        # 京葉シーバースは千葉に集約
        self.assertEqual(match_japan_port("KEIYO"), "CHIBA")

    def test_with_at_padding(self):
        self.assertEqual(match_japan_port("KIIRE@@@@@@@@@@@@@@@"), "KIIRE")

    def test_with_internal_space(self):
        self.assertEqual(match_japan_port("JP YOK"), "YOKOHAMA")

    def test_busan_not_japan(self):
        self.assertIsNone(match_japan_port("BUSAN"))

    def test_shanghai_not_japan(self):
        self.assertIsNone(match_japan_port("SHANGHAI"))

    def test_vladivostok_not_japan(self):
        self.assertIsNone(match_japan_port("VLADIVOSTOK"))

    def test_garbage_returns_none(self):
        self.assertIsNone(match_japan_port("@@@@@@@@@@"))
        self.assertIsNone(match_japan_port("ZZZZZ"))

    def test_empty_returns_none(self):
        self.assertIsNone(match_japan_port(""))
        self.assertIsNone(match_japan_port(None))


class TestAggregate(unittest.TestCase):
    def test_empty_input(self):
        result = aggregate({})
        self.assertEqual(result["totalTankersInRegion"], 0)
        self.assertEqual(result["japanBoundTankers"], 0)
        self.assertEqual(result["topDestinationPorts"], [])

    def test_filters_non_tanker_types(self):
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},  # Tanker
            2: {"static": {"type": 70, "destination": "JPYOK"}},  # Cargo, excluded
            3: {"static": {"type": 60, "destination": "JPYOK"}},  # Passenger, excluded
        }
        result = aggregate(ships)
        self.assertEqual(result["totalTankersInRegion"], 1)
        self.assertEqual(result["japanBoundTankers"], 1)

    def test_filters_japan_bound_correctly(self):
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},
            2: {"static": {"type": 80, "destination": "BUSAN"}},
            3: {"static": {"type": 80, "destination": "SHANGHAI"}},
            4: {"static": {"type": 80, "destination": "CHIBA"}},
        }
        result = aggregate(ships)
        self.assertEqual(result["totalTankersInRegion"], 4)
        self.assertEqual(result["japanBoundTankers"], 2)

    def test_top_destinations_sorted_by_count(self):
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},
            2: {"static": {"type": 80, "destination": "JPYOK"}},
            3: {"static": {"type": 80, "destination": "JPYOK"}},
            4: {"static": {"type": 80, "destination": "CHIBA"}},
            5: {"static": {"type": 80, "destination": "KIIRE"}},
        }
        result = aggregate(ships)
        ports = result["topDestinationPorts"]
        self.assertEqual(ports[0], {"port": "YOKOHAMA", "count": 3})
        # CHIBA and KIIRE both have 1, ordering of equal counts not strictly defined
        names = [p["port"] for p in ports]
        self.assertEqual(set(names), {"YOKOHAMA", "CHIBA", "KIIRE"})

    def test_ships_without_static_skipped(self):
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},
            2: {"last_pos": True},  # PositionReport only, no ShipStaticData
            3: {},  # nothing
        }
        result = aggregate(ships)
        self.assertEqual(result["totalTankersInRegion"], 1)

    def test_empty_destination_excluded_from_japan_bound(self):
        ships = {
            1: {"static": {"type": 80, "destination": ""}},
            2: {"static": {"type": 80, "destination": None}},
            3: {"static": {"type": 80, "destination": "JPYOK"}},
        }
        result = aggregate(ships)
        self.assertEqual(result["totalTankersInRegion"], 3)
        self.assertEqual(result["japanBoundTankers"], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
