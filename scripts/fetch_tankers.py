"""
aisstream.io WebSocket から日本周辺のタンカーをサンプリングし、
data/tankers.json を更新する。

使い方:
    AISSTREAM_API_KEY=xxx python scripts/fetch_tankers.py [--duration 480]

設計:
    - WebSocket で 5-8 分間サンプル → ShipStaticData / PositionReport を集める
    - vessel type 80-89 (Tanker) のみ集計対象
    - destination をトークン分割し日本港名/UN-LOCODE とトークン一致で「日本向け」判定
    - 出力は集計値（隻数 + 上位港）に加え、個別タンカー情報（MMSI/船名/destination/
      位置）も出力する。位置は緯度経度を4桁(~11m)に丸める（aggregate 参照）

出力 (data/tankers.json):
    {
      "fetchedAt": "ISO 8601 UTC",
      "samplingDurationSec": 480,
      "totalTankersInRegion": 87,
      "japanBoundTankers": 32,                  # 特定港 + port 不明の日本向け の合計
      "japanBoundUnknownPort": 5,               # 日本向けだが港名特定不可
      "topDestinationPorts": [{"port": "YOKOHAMA", "count": 8}, ...],  # 特定港のみ
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

from lib.io import write_json
from lib.paths import TANKERS_PATH

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
    # 観測された短縮形（船員手入力で頻出するパターン）。JP プレフィックス必須の
    # 部分一致なので、独立した英単語との誤マッチは起こらない
    "JPMIZ": "MIZUSHIMA",  # ">JP MIZ B MINAI OFF" や ">JP MIZ TS OFF" 形式
    "JPMUR": "MURORAN",    # 室蘭製油所・原油受入港
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


def _tokenize(dest):
    """destination を英数字トークン列に分割する（大文字化）。

    空白・記号・@ パディング等の非英数字をすべて区切りとして扱う。トークン境界を
    保持することで、隣接トークンが連結されて生じる誤マッチ（'BANGKOK JP AGENT'
    → 'BANGKOKJPAGENT' → 'JPAGE' 等）を防ぐ。
    """
    if not dest:
        return []
    return re.findall(r"[A-Z0-9]+", dest.upper())


# 5 文字 UN/LOCODE トークン「JP」+3文字（例: JPYOK）のパターン。
_JP_LOCODE_RE = re.compile(r"JP[A-Z]{3}")


def _jp_locodes(tokens):
    """トークン列から 5 文字の JP LOCODE 候補を抽出する。

    対象は以下の 2 形態:
      - 単独 5 文字トークン（'JPYOK'）
      - 先頭が 'JP' で次が独立した 3 文字トークンの分割形（'JP YOK' → 'JPYOK'）
    船員手入力では LOCODE が先頭に置かれるため、分割の再結合は先頭位置のみ対象とし、
    中間の 'JP' + 任意トークンを誤って LOCODE 化しない。
    """
    codes = [t for t in tokens if _JP_LOCODE_RE.fullmatch(t)]
    if (
        len(tokens) >= 2
        and tokens[0] == "JP"
        and re.fullmatch(r"[A-Z]{3}", tokens[1])
    ):
        codes.append("JP" + tokens[1])
    return codes


def match_japan_port(dest):
    """destination が日本港なら canonical name を返す。マッチしなければ None。

    港キーワードは独立トークンと完全一致でマッチする（部分一致しない）。
    'OSAKA INTL' が 'SAKAI' を含み大阪→堺と誤帰属する類の問題を避けるため。
    """
    tokens = _tokenize(dest)
    if not tokens:
        return None
    for candidate in tokens + _jp_locodes(tokens):
        canonical = JAPAN_PORT_KEYWORDS.get(candidate)
        if canonical:
            return canonical
    return None


def is_japan_bound_destination(dest):
    """destination が日本向けを示すか（特定港マッチに加えて、port 不明の日本向けも True）。

    判定（いずれもトークン境界にアンカーし、連結による誤マッチを防ぐ）:
      1. JAPAN_PORT_KEYWORDS にマッチ（特定可能な日本港）
      2. 'JAPAN' トークンを含む（港名特定不可だが文字どおり日本向け）
      3. 先頭トークンが 'JP'（'>JP ...' 国コード慣行。先頭以外の 'JP' は対象外）
      4. 独立した 'JP[A-Z]{3}' LOCODE トークンを含む（リスト未登録の日本港）
    """
    if match_japan_port(dest) is not None:
        return True
    tokens = _tokenize(dest)
    if not tokens:
        return False
    if "JAPAN" in tokens:
        return True
    if tokens[0] == "JP":
        return True
    if _jp_locodes(tokens):
        return True
    return False


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
        last_pos = info.get("last_pos")
        if not isinstance(last_pos, dict):
            last_pos = None
        vessel = {
            "mmsi": int(mmsi) if isinstance(mmsi, (int, str)) and str(mmsi).isdigit() else mmsi,
            "name": (static.get("name") or "").strip(),
            "destination": destination,
            "isJapanBound": is_japan_bound_destination(destination),
            "lat": _round_coord(last_pos.get("lat")) if last_pos else None,
            "lon": _round_coord(last_pos.get("lon")) if last_pos else None,
        }
        vessels.append(vessel)

    japan_bound_ports = []
    japan_bound_unknown_port = 0
    for v in vessels:
        if not v["isJapanBound"]:
            continue
        port = match_japan_port(v["destination"])
        if port is not None:
            japan_bound_ports.append(port)
        else:
            japan_bound_unknown_port += 1

    counter = Counter(japan_bound_ports)
    top = [
        {"port": port, "count": count}
        for port, count in counter.most_common(10)
    ]

    return {
        "totalTankersInRegion": len(vessels),
        "japanBoundTankers": sum(1 for v in vessels if v["isJapanBound"]),
        "japanBoundUnknownPort": japan_bound_unknown_port,
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
    write_json(TANKERS_PATH, out)
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
    print(f"[tankers] wrote {TANKERS_PATH}")
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
