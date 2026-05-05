"""
aisstream.io WebSocket から日本周辺のタンカーをサンプリングし、
data/tankers.json を更新する。

使い方:
    AISSTREAM_API_KEY=xxx python scripts/fetch_tankers.py [--duration 480]

設計:
    - WebSocket で 5-8 分間サンプル → ShipStaticData / PositionReport を集める
    - vessel type 80-89 (Tanker) のみ集計対象
    - destination を日本港名/UN-LOCODE と部分一致で「日本向け」判定
    - 出力は集計値のみ（隻数 + 上位港）。船舶識別情報 (MMSI / 船名) は出さない

出力 (data/tankers.json):
    {
      "fetchedAt": "ISO 8601 UTC",
      "samplingDurationSec": 480,
      "totalTankersInRegion": 87,
      "japanBoundTankers": 32,
      "topDestinationPorts": [{"port": "YOKOHAMA", "count": 8}, ...],
      "boundingBox": "24-46N / 122-146E",
      "source": "aisstream.io",
      "vessels": [
        {
          "mmsi": 123456789,
          "name": "EVER GIVEN",
          "destination": "JPYOK",
          "isJapanBound": true,
          "lat": 35.0123,
          "lon": 140.5678
        },
        ...
      ]
    }

注意事項:
    - aisstream.io は BETA で SLA 非保証
    - aisstream.io は明示的な ToS / Acceptable Use Policy を公開していないが、
      MarineTraffic / VesselFinder 等が同種データを公開している業界慣行に従い
      個別船舶情報 (MMSI / 船名 / destination / 位置) を出力する
    - destination は船員手入力で精度に限界がある（正確な「日本入港」ではない）
    - 対象は AIS の船種コード 80-89 (Tanker) のみ
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "data" / "tankers.json"

WS_URL = "wss://stream.aisstream.io/v0/stream"

# 日本周辺海域 (大雑把)。緯度範囲: 沖縄〜北海道、経度範囲: 東シナ海〜西太平洋
DEFAULT_BBOX = [[24.0, 122.0], [46.0, 146.0]]
DEFAULT_DURATION_SEC = 480  # 8分: AIS Type 5 が約6分間隔のため大半をカバー

# 日本の主要原油受入港のキーワード集合
# 値は表示用の正規化された港名（複数別名→同じ canonical に集約）
JAPAN_PORT_KEYWORDS = {
    # UN/LOCODE (5-letter)
    "JPYOK": "YOKOHAMA",
    "JPCHB": "CHIBA",
    "JPKWS": "KAWASAKI",
    "JPYKK": "YOKKAICHI",
    "JPSKT": "SAKAI",
    "JPKII": "KIIRE",
    "JPMSU": "MIZUSHIMA",
    "JPKSM": "KASHIMA",
    "JPTMK": "TOMAKOMAI",
    "JPOIT": "OITA",
    "JPSDJ": "SENDAI",
    "JPMTY": "MATSUYAMA",
    "JPSBS": "SHIBUSHI",
    "JPNGS": "NEGISHI",
    # 英語の港・地名（destination に頻出）
    "YOKOHAMA": "YOKOHAMA",
    "NEGISHI": "YOKOHAMA",  # 根岸製油所（横浜）
    "KEIYO": "CHIBA",        # 京葉シーバース（千葉）
    "CHIBA": "CHIBA",
    "KAWASAKI": "KAWASAKI",
    "YOKKAICHI": "YOKKAICHI",
    "SAKAI": "SAKAI",
    "SENBOKU": "SAKAI",
    "KIIRE": "KIIRE",
    "MIZUSHIMA": "MIZUSHIMA",
    "KASHIMA": "KASHIMA",
    "TOMAKOMAI": "TOMAKOMAI",
    "OITA": "OITA",
    "SENDAI": "SENDAI",
    "MATSUYAMA": "MATSUYAMA",
    "SHIBUSHI": "SHIBUSHI",
    "KUSHIKINO": "KUSHIKINO",
    "MURORAN": "MURORAN",
    "TOKYO": "TOKYO",
}


def is_tanker_type(t):
    """AIS vessel type 80-89 = Tanker。"""
    return isinstance(t, int) and 80 <= t <= 89


def normalize_destination(dest):
    """destination 文字列を正規化。@パディング、空白、記号を除去して大文字化。"""
    if not dest:
        return ""
    s = dest.upper().strip()
    s = s.replace("@", "")
    s = re.sub(r"[\s\-_/.,;:]+", "", s)
    return s


def match_japan_port(dest):
    """destination が日本港なら canonical name を返す。マッチしなければ None。"""
    if not dest:
        return None
    norm = normalize_destination(dest)
    if not norm:
        return None
    for kw, canonical in JAPAN_PORT_KEYWORDS.items():
        if kw in norm:
            return canonical
    return None


def _round_coord(value):
    """緯度経度を 4 桁 (~11m 精度) に丸める。"""
    if not isinstance(value, (int, float)):
        return None
    return round(float(value), 4)


def aggregate(ships_seen):
    """
    ships_seen: { mmsi: { 'static': {type, name, destination}, 'last_pos': {lat, lon} | None } }
    戻り値: 集計値 + 個別タンカーリスト (vessels) を含む dict
    """
    vessels = []
    for mmsi, info in ships_seen.items():
        static = info.get("static") or {}
        if not is_tanker_type(static.get("type")):
            continue
        destination = (static.get("destination") or "").strip()
        japan_port = match_japan_port(destination)
        last_pos = info.get("last_pos")
        if not isinstance(last_pos, dict):
            last_pos = None
        vessel = {
            "mmsi": int(mmsi) if isinstance(mmsi, (int, str)) and str(mmsi).isdigit() else mmsi,
            "name": (static.get("name") or "").strip(),
            "destination": destination,
            "isJapanBound": japan_port is not None,
            "lat": _round_coord(last_pos.get("lat")) if last_pos else None,
            "lon": _round_coord(last_pos.get("lon")) if last_pos else None,
        }
        vessels.append(vessel)

    japan_bound_ports = []
    for v in vessels:
        port = match_japan_port(v["destination"])
        if port is not None:
            japan_bound_ports.append(port)

    counter = Counter(japan_bound_ports)
    top = [
        {"port": port, "count": count}
        for port, count in counter.most_common(10)
    ]

    return {
        "totalTankersInRegion": len(vessels),
        "japanBoundTankers": sum(1 for v in vessels if v["isJapanBound"]),
        "topDestinationPorts": top,
        "vessels": vessels,
    }


async def sample(api_key, duration_sec, bbox):
    """WebSocket で duration_sec 秒間サンプリングして ships_seen を返す。"""
    import websockets  # ローカル import（テストでは不要）

    sub = {
        "APIKey": api_key,
        "BoundingBoxes": [bbox],
        "FilterMessageTypes": ["ShipStaticData", "PositionReport"],
    }

    ships_seen: dict = {}

    loop = asyncio.get_event_loop()
    deadline = loop.time() + duration_sec

    async with websockets.connect(WS_URL, ping_interval=30) as ws:
        await ws.send(json.dumps(sub))

        while loop.time() < deadline:
            timeout = max(1.0, deadline - loop.time())
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                break

            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue

            mmsi = msg.get("MetaData", {}).get("MMSI")
            if not mmsi:
                continue

            mt = msg.get("MessageType")
            if mt == "ShipStaticData":
                payload = msg.get("Message", {}).get("ShipStaticData", {})
                ships_seen.setdefault(mmsi, {})["static"] = {
                    "type": payload.get("Type"),
                    "name": (payload.get("Name") or "").strip(),
                    "destination": (payload.get("Destination") or "").strip(),
                }
            elif mt == "PositionReport":
                payload = msg.get("Message", {}).get("PositionReport", {})
                lat = payload.get("Latitude")
                lon = payload.get("Longitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    ships_seen.setdefault(mmsi, {})["last_pos"] = {
                        "lat": float(lat),
                        "lon": float(lon),
                    }

    return ships_seen


def write_output(summary, duration_sec, bbox):
    bbox_str = (
        f"{bbox[0][0]:g}-{bbox[1][0]:g}N / "
        f"{bbox[0][1]:g}-{bbox[1][1]:g}E"
    )
    out = {
        "fetchedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "samplingDurationSec": duration_sec,
        **summary,
        "boundingBox": bbox_str,
        "source": "aisstream.io",
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return out


async def main_async(args):
    api_key = os.environ.get("AISSTREAM_API_KEY")
    if not api_key:
        print(
            "[tankers] AISSTREAM_API_KEY env var not set",
            file=sys.stderr,
        )
        return 1

    print(f"[tankers] sampling for {args.duration}s ...", flush=True)
    try:
        ships = await sample(api_key, args.duration, DEFAULT_BBOX)
    except Exception as e:
        print(
            f"[tankers] sampling failed: {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 1

    print(f"[tankers] saw {len(ships)} unique vessels (all types)")

    summary = aggregate(ships)
    print(f"[tankers] tankers in region: {summary['totalTankersInRegion']}")
    print(f"[tankers] japan-bound: {summary['japanBoundTankers']}")
    print(f"[tankers] top: {summary['topDestinationPorts'][:5]}")

    if args.dry_run:
        print("[tankers] dry-run; not writing tankers.json")
        return 0

    write_output(summary, args.duration, DEFAULT_BBOX)
    print(f"[tankers] wrote {OUTPUT_PATH}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--duration",
        type=int,
        default=DEFAULT_DURATION_SEC,
        help=f"Sampling duration in seconds (default: {DEFAULT_DURATION_SEC})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Sample and aggregate but don't write tankers.json",
    )
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
