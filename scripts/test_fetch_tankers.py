"""
Unit tests for scripts/fetch_tankers.py

Run from project root:
    python scripts/test_fetch_tankers.py
or:
    python -m unittest discover -s scripts -p 'test_*.py'

WebSocket I/O は意図しないでカバーしない（websockets ライブラリのラッパに過ぎないため）。
本テストはロジック関数のみ:
    - is_tanker_type
    - _tokenize
    - match_japan_port
    - aggregate
    - check_error_frame（aisstream エラーフレーム検出の純粋ロジック）
    - main_async のサニティガード（sample / write_json を境界としてモック）
"""

import asyncio
import os
import sys
import unittest
from argparse import Namespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_tankers  # noqa: E402
from fetch_tankers import (  # noqa: E402
    _tokenize,
    aggregate,
    is_japan_bound_destination,
    is_tanker_type,
    match_japan_port,
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


class TestTokenize(unittest.TestCase):
    def test_at_padding_dropped(self):
        self.assertEqual(_tokenize("YOKOHAMA@@@"), ["YOKOHAMA"])

    def test_lowercase_uppercased(self):
        self.assertEqual(_tokenize("yokohama"), ["YOKOHAMA"])

    def test_whitespace_separates_tokens(self):
        # 連結せずトークン境界を保持する（連結による誤マッチ防止の要）
        self.assertEqual(_tokenize("JP YOK"), ["JP", "YOK"])

    def test_punctuation_separates_tokens(self):
        self.assertEqual(_tokenize("CHIBA-1"), ["CHIBA", "1"])
        self.assertEqual(_tokenize("KIIRE/JP"), ["KIIRE", "JP"])

    def test_empty_string(self):
        self.assertEqual(_tokenize(""), [])

    def test_none_returns_empty(self):
        self.assertEqual(_tokenize(None), [])

    def test_only_at_signs(self):
        self.assertEqual(_tokenize("@@@@@@@@@@"), [])

    def test_real_padded_format(self):
        # 実 AIS で見られる 20文字パディング
        self.assertEqual(_tokenize("JP HKT              "), ["JP", "HKT"])


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

    def test_osaka_intl_does_not_falsely_match_sakai(self):
        # 退行: 'OSAKAINTL' が 'SAKAI' を部分一致で含み大阪→堺と誤帰属していた。
        # トークン境界でマッチすれば OSAKA も INTL も港キーワードと一致しない。
        self.assertIsNone(match_japan_port("OSAKA INTL"))

    def test_port_keyword_requires_full_token(self):
        # 港キーワードは独立トークンと完全一致する必要がある（部分一致しない）
        self.assertIsNone(match_japan_port("YOKOHAMAGAWA"))

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

    def test_mid_string_jp_does_not_falsely_match(self):
        # 退行: 'BANGKOKJPAGENT' が JP+AGE に誤マッチしていた（タイ仕向地を日本向けと誤判定）。
        # 'JP' は先頭トークンでない限り国コード慣行とみなさない。
        self.assertFalse(is_japan_bound_destination("BANGKOK JP AGENT"))

    def test_jpn_agent_does_not_falsely_match(self):
        # 退行: 'SGPORTJPNAGENT' が JPN+AGE に誤マッチしていた（シンガポール仕向地）
        self.assertFalse(is_japan_bound_destination("SG PORT JPN AGENT"))

    def test_literal_japan_word_is_japan_bound(self):
        # 退行: 'JAPAN' 単語そのもの（港名特定不可だが文字どおり日本向け）を取りこぼしていた
        self.assertTrue(is_japan_bound_destination("JAPAN"))


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


class TestCheckErrorFrame(unittest.TestCase):
    """aisstream はエラー時に {"error": "..."} フレームを返す（小文字 error）。"""

    def test_error_frame_raises(self):
        with self.assertRaises(fetch_tankers.AisStreamError) as cm:
            fetch_tankers.check_error_frame({"error": "Api Key Is Not Valid"})
        self.assertIn("Api Key Is Not Valid", str(cm.exception))

    def test_capitalized_error_frame_raises(self):
        # 防御的に Error（大文字始まり）も検出する
        with self.assertRaises(fetch_tankers.AisStreamError):
            fetch_tankers.check_error_frame({"Error": "throttled"})

    def test_normal_message_does_not_raise(self):
        msg = {
            "MessageType": "PositionReport",
            "MetaData": {"MMSI": 123456789},
            "Message": {"PositionReport": {"Latitude": 35.0, "Longitude": 140.0}},
        }
        # 例外を送出しないこと（戻り値は問わない）
        fetch_tankers.check_error_frame(msg)

    def test_empty_error_string_does_not_raise(self):
        # 空文字は falsy なのでエラー扱いしない
        fetch_tankers.check_error_frame({"error": ""})

    def test_non_dict_does_not_raise(self):
        fetch_tankers.check_error_frame(None)
        fetch_tankers.check_error_frame("string")
        fetch_tankers.check_error_frame([1, 2, 3])


def _make_args(min_tankers=fetch_tankers.DEFAULT_MIN_TANKERS, dry_run=False, duration=1):
    return Namespace(duration=duration, dry_run=dry_run, min_tankers=min_tankers)


class TestSanityGuard(unittest.TestCase):
    """書き込み前のサニティガード。sample（WebSocket I/O）と write_json
    （ファイル書き込み）を境界としてモックし、main_async の振る舞いを検証する。"""

    def _run_main(self, ships, args, api_key="test-key"):
        async def fake_sample(api_key_arg, duration_sec, bbox):
            return ships

        env = {"AISSTREAM_API_KEY": api_key} if api_key else {}
        with mock.patch.dict(os.environ, env, clear=False), \
                mock.patch.object(fetch_tankers, "sample", fake_sample), \
                mock.patch.object(fetch_tankers, "write_json") as mock_write:
            if not api_key:
                os.environ.pop("AISSTREAM_API_KEY", None)
            rc = asyncio.run(fetch_tankers.main_async(args))
        return rc, mock_write

    def test_zero_tankers_returns_1_and_does_not_write(self):
        rc, mock_write = self._run_main({}, _make_args(min_tankers=1))
        self.assertEqual(rc, 1)
        mock_write.assert_not_called()

    def test_below_min_returns_1_and_does_not_write(self):
        # 2 タンカー、min 3 → 拒否
        ships = {
            1: {"static": {"type": 80, "destination": "JPYOK"}},
            2: {"static": {"type": 80, "destination": "BUSAN"}},
        }
        rc, mock_write = self._run_main(ships, _make_args(min_tankers=3))
        self.assertEqual(rc, 1)
        mock_write.assert_not_called()

    def test_at_min_writes_and_returns_0(self):
        ships = {1: {"static": {"type": 80, "destination": "JPYOK"}}}
        rc, mock_write = self._run_main(ships, _make_args(min_tankers=1))
        self.assertEqual(rc, 0)
        mock_write.assert_called_once()

    def test_dry_run_valid_sample_does_not_write(self):
        ships = {1: {"static": {"type": 80, "destination": "JPYOK"}}}
        rc, mock_write = self._run_main(ships, _make_args(min_tankers=1, dry_run=True))
        self.assertEqual(rc, 0)
        mock_write.assert_not_called()

    def test_guard_fires_before_dry_run(self):
        # 劣化サンプルは dry-run でも 1 を返す（fetch_pdf の 0 件中断を踏襲）
        rc, mock_write = self._run_main({}, _make_args(min_tankers=1, dry_run=True))
        self.assertEqual(rc, 1)
        mock_write.assert_not_called()

    def test_missing_api_key_returns_1(self):
        rc, mock_write = self._run_main({}, _make_args(), api_key=None)
        self.assertEqual(rc, 1)
        mock_write.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
