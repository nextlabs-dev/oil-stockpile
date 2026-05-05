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
      "densityGrid": {
        "cellSizeDeg": 0.5,
        "cells": [{"lat": 35.0, "lon": 140.0, "count": 2}, ...]
      }
    }

注意事項:
    - aisstream.io は BETA で SLA 非保証。ToS の詳細は要確認
    - destination は船員手入力で精度に限界がある（正確な「日本入港」ではない）
    - 個別船舶の MMSI / 船名 は出さない (規約・プライバシー上の保守的な判断)
    - 位置は 0.5°メッシュ (~55km) に丸めて隻数のみ出力。個別船舶を識別できない粒度
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
DENSITY_CELL_SIZE_DEG = 0.5  # ~55km メッシュ。個別船舶を識別できない粒度

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


def _quantize(value, step):
    """value を step 単位の代表値 (グリッドの中心) に丸める。"""
    if value is None:
        return None
    return round(round(value / step) * step, 4)


def aggregate(ships_seen, *, cell_size_deg=DENSITY_CELL_SIZE_DEG):
    """
    ships_seen: { mmsi: { 'static': {type, destination}, 'last_pos': {lat, lon} | None } }
    戻り値: 集計済みの dict（船舶識別情報は含まない）

    位置は cell_size_deg のメッシュに丸めて隻数のみ集計するため、
    出力から個別船舶を特定することはできない。
    """
    tankers = []
    for _mmsi, info in ships_seen.items():
        static = info.get("static")
        if not static:
            continue
        if not is_tanker_type(static.get("type")):
            continue
        last_pos = info.get("last_pos")
        if not isinstance(last_pos, dict):
            last_pos = None
        tankers.append({
            "destination": static.get("destination", ""),
            "lat": last_pos.get("lat") if last_pos else None,
            "lon": last_pos.get("lon") if last_pos else None,
        })

    japan_bound_ports = []
    for t in tankers:
        port = match_japan_port(t["destination"])
        if port is not None:
            japan_bound_ports.append(port)

    counter = Counter(japan_bound_ports)
    top = [
        {"port": port, "count": count}
        for port, count in counter.most_common(10)
    ]

    cell_counter: Counter = Counter()
    for t in tankers:
        if not isinstance(t["lat"], (int, float)) or not isinstance(
            t["lon"], (int, float)
        ):
            continue
        key = (
            _quantize(t["lat"], cell_size_deg),
            _quantize(t["lon"], cell_size_deg),
        )
        cell_counter[key] += 1
    cells = [
        {"lat": lat, "lon": lon, "count": count}
        for (lat, lon), count in sorted(cell_counter.items())
    ]

    return {
        "totalTankersInRegion": len(tankers),
        "japanBoundTankers": len(japan_bound_ports),
        "topDestinationPorts": top,
        "densityGrid": {
            "cellSizeDeg": cell_size_deg,
            "cells": cells,
        },
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
