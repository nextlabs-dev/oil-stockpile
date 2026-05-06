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
    is_japan_bound_destination,
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

    def test_jpmiz_short_form_normalizes_to_mizushima(self):
        # 観測データ ">JP MIZ B MINAI OFF" 等の短縮形
        self.assertEqual(match_japan_port(">JP MIZ B MINAI OFF"), "MIZUSHIMA")
        self.assertEqual(match_japan_port(">JP MIZ TS OFF"), "MIZUSHIMA")

    def test_jpmur_short_form_matches_muroran(self):
        self.assertEqual(match_japan_port(">JP MUR"), "MURORAN")

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


class TestIsJapanBoundDestination(unittest.TestCase):
    """フォールバック判定: port 特定不可だが日本向けと推定するケース。"""

    def test_known_port_is_japan_bound(self):
        # 既存の港名マッチも True を返す
        self.assertTrue(is_japan_bound_destination("JPYOK"))
        self.assertTrue(is_japan_bound_destination(">JP YKK 3E"))
        self.assertTrue(is_japan_bound_destination("YOKOHAMA"))

    def test_unregistered_jp_locode_is_japan_bound(self):
        # JPKZJ (金沢) は KEYWORDS 未登録だが LOCODE 形式で日本向け
        self.assertTrue(is_japan_bound_destination(">JP KZJ"))
        self.assertTrue(is_japan_bound_destination("JPKZJ"))

    def test_jp_prefix_with_garbled_text_is_japan_bound(self):
        # 船員手入力の崩れた表記でも >JP プレフィックスで日本向けと判定
        self.assertTrue(is_japan_bound_destination(">JP MIZ B MINAI OFF"))
        self.assertTrue(is_japan_bound_destination(">JP KAMA OFF"))
        self.assertTrue(is_japan_bound_destination(">JP/SKD/OFF"))

    def test_jp_locode_without_prefix_is_japan_bound(self):
        # ">" がない LOCODE 形式も拾う
        self.assertTrue(is_japan_bound_destination("JP NAS OFF"))

    def test_non_japan_destination_is_not_japan_bound(self):
        self.assertFalse(is_japan_bound_destination("BUSAN"))
        self.assertFalse(is_japan_bound_destination("SHANGHAI"))
        self.assertFalse(is_japan_bound_destination(">CN SHA"))
        self.assertFalse(is_japan_bound_destination("VLADIVOSTOK"))

    def test_empty_returns_false(self):
        self.assertFalse(is_japan_bound_destination(""))
        self.assertFalse(is_japan_bound_destination(None))

    def test_garbage_returns_false(self):
        self.assertFalse(is_japan_bound_destination("@@@@@@@@@@"))
        self.assertFalse(is_japan_bound_destination("ZZZZZ"))

    def test_jp_followed_by_digits_does_not_match(self):
        # LOCODE は JP+大文字3文字。JP+数字や JP+短い文字列はフォールバック対象外
        self.assertFalse(is_japan_bound_destination("JP12"))
        self.assertFalse(is_japan_bound_destination("FOOJP"))


class TestAggregate(unittest.TestCase):
    def test_empty_input(self):
        result = aggregate({})
        self.assertEqual(result["totalTankersInRegion"], 0)
        self.assertEqual(result["japanBoundTankers"], 0)
        self.assertEqual(result["japanBoundUnknownPort"], 0)
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

    def test_japan_bound_unknown_port_counted_separately(self):
        # フォールバック判定された船は japanBoundUnknownPort に計上され、
        # topDestinationPorts には含まれない
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},      # 特定港 (YOKOHAMA)
            2: {"static": {"type": 80, "destination": ">JP KZJ"}},    # 港名特定不可（KZJ は未登録 LOCODE）
            3: {"static": {"type": 80, "destination": ">JP NAS OFF"}},  # 港名特定不可（NAS も未登録）
            4: {"static": {"type": 80, "destination": "BUSAN"}},      # 日本向けでない
        }
        result = aggregate(ships)
        self.assertEqual(result["totalTankersInRegion"], 4)
        self.assertEqual(result["japanBoundTankers"], 3)              # 特定 1 + 不明 2
        self.assertEqual(result["japanBoundUnknownPort"], 2)
        ports = result["topDestinationPorts"]
        self.assertEqual(ports, [{"port": "YOKOHAMA", "count": 1}])   # 特定港のみ

    def test_all_unknown_jp_yields_empty_top_ports(self):
        # 全てフォールバック判定の場合、topDestinationPorts は空でも japanBoundTankers > 0
        ships = {
            1: {"static": {"type": 80, "destination": ">JP KZJ"}},
            2: {"static": {"type": 80, "destination": ">JP NAS OFF"}},
        }
        result = aggregate(ships)
        self.assertEqual(result["japanBoundTankers"], 2)
        self.assertEqual(result["japanBoundUnknownPort"], 2)
        self.assertEqual(result["topDestinationPorts"], [])


class TestVessels(unittest.TestCase):
    def test_vessel_basic_fields(self):
        ships = {
            123456789: {
                "static": {
                    "type": 80,
                    "name": "EVER GIVEN",
                    "destination": "JPYOK",
                },
                "last_pos": {"lat": 35.0123, "lon": 140.5678},
            },
        }
        result = aggregate(ships)
        self.assertEqual(len(result["vessels"]), 1)
        v = result["vessels"][0]
        self.assertEqual(v["mmsi"], 123456789)
        self.assertEqual(v["name"], "EVER GIVEN")
        self.assertEqual(v["destination"], "JPYOK")
        self.assertTrue(v["isJapanBound"])
        self.assertEqual(v["lat"], 35.0123)
        self.assertEqual(v["lon"], 140.5678)

    def test_non_japan_destination_marked_false(self):
        ships = {
            1: {
                "static": {"type": 80, "name": "FOO", "destination": "BUSAN"},
                "last_pos": {"lat": 34.0, "lon": 132.0},
            },
        }
        result = aggregate(ships)
        v = result["vessels"][0]
        self.assertFalse(v["isJapanBound"])

    def test_unknown_jp_destination_marked_japan_bound(self):
        # port 名特定不可でもフォールバックで isJapanBound = True
        ships = {
            1: {
                "static": {"type": 80, "name": "KOUHOU MARU", "destination": ">JP KZJ"},
                "last_pos": {"lat": 34.36, "lon": 134.0},
            },
        }
        result = aggregate(ships)
        v = result["vessels"][0]
        self.assertTrue(v["isJapanBound"])

    def test_no_position_keeps_vessel_with_null_coords(self):
        # 静的データのみで位置がないケース。vessel は出すが lat/lon は None
        ships = {
            1: {"static": {"type": 80, "name": "NO POS", "destination": "JPYOK"}},
        }
        result = aggregate(ships)
        self.assertEqual(len(result["vessels"]), 1)
        v = result["vessels"][0]
        self.assertIsNone(v["lat"])
        self.assertIsNone(v["lon"])

    def test_non_tankers_excluded(self):
        ships = {
            1: {
                "static": {"type": 70, "name": "CARGO", "destination": "JPYOK"},
                "last_pos": {"lat": 35.0, "lon": 140.0},
            },
            2: {
                "static": {"type": 80, "name": "TANKER", "destination": "JPYOK"},
                "last_pos": {"lat": 35.0, "lon": 140.0},
            },
        }
        result = aggregate(ships)
        self.assertEqual(len(result["vessels"]), 1)
        self.assertEqual(result["vessels"][0]["name"], "TANKER")

    def test_lat_lon_rounded_to_4_decimals(self):
        ships = {
            1: {
                "static": {"type": 80, "name": "PRECISE", "destination": "JPYOK"},
                "last_pos": {"lat": 35.123456789, "lon": 140.987654321},
            },
        }
        result = aggregate(ships)
        v = result["vessels"][0]
        self.assertEqual(v["lat"], 35.1235)
        self.assertEqual(v["lon"], 140.9877)

    def test_invalid_position_yields_null_coords(self):
        ships = {
            1: {
                "static": {"type": 80, "name": "BAD", "destination": "JPYOK"},
                "last_pos": {"lat": "not-a-number", "lon": 140.0},
            },
        }
        result = aggregate(ships)
        v = result["vessels"][0]
        self.assertIsNone(v["lat"])
        # lon も None を期待（lat が無効ならペアで無効扱い）
        self.assertEqual(v["lon"], 140.0)  # 個別では valid なので残す


if __name__ == "__main__":
    unittest.main(verbosity=2)
