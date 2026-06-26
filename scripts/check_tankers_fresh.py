"""data/tankers.json の fetchedAt 鮮度ガード。

fetch-tankers.yml は上流 (aisstream.io は BETA で SLA 非保証) の一時障害で run 全体が
赤くなるのを避けるため 'Sample AIS stream' に continue-on-error を付けている。その副作用
として、AISSTREAM_API_KEY の失効/ローテートや aisstream の持続障害でもジョブはグリーンの
まま tankers.json が最後の良値で凍結し、保守者に何の通知も飛ばない（GitHub はジョブ失敗時
のみ通知するため）。

本スクリプトを continue-on-error なしの独立ステップで走らせ、tankers.json の fetchedAt が
--max-age-hours より古ければ exit 1 でジョブを赤くする。一時障害は次回成功で鮮度が回復する
ため発火せず、鍵失効・上流の持続障害・劣化サンプルといった「持続的失敗」だけを 1 つで捕捉
する。

使い方:
    python scripts/check_tankers_fresh.py [--max-age-hours 6]
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime

from lib.io import read_json
from lib.paths import TANKERS_PATH

# データ凍結とみなす鮮度しきい値。ワークフローは毎時実行なので 6h は約6回連続失敗に相当し、
# 単発の一時障害や Actions cron の遅延/スキップでは発火しない。クライアント側の 6h stale
# 警告とも整合する。運用調整は --max-age-hours で行う。
DEFAULT_MAX_AGE_HOURS = 6


def evaluate(data, now, max_age_hours):
    """tankers.json の dict と現在時刻から (exit_code, message) を返す純粋関数。

    exit_code: 0 = fresh、1 = stale もしくは壊れた状態（fetchedAt 欠落・不正）。
    壊れた状態をグリーンにしないため、解釈不能な fetchedAt は stale と同じく 1 を返す。
    """
    fetched_at = data.get("fetchedAt")
    if not fetched_at:
        return 1, "tankers.json has no fetchedAt; cannot verify freshness"

    try:
        fetched = datetime.fromisoformat(fetched_at)
    except (ValueError, TypeError):
        return 1, f"tankers.json has unparseable fetchedAt {fetched_at!r}"

    # write_output は UTC を書くが、tz 無し表記でも UTC とみなして比較する。
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=UTC)

    age_hours = (now - fetched).total_seconds() / 3600
    if age_hours > max_age_hours:
        return 1, (
            f"tankers.json is stale: fetchedAt {fetched_at} is {age_hours:.1f}h old "
            f"(> max {max_age_hours}h). AIS sampling has been failing persistently; "
            "check the AISSTREAM_API_KEY secret and aisstream.io status."
        )

    return 0, f"tankers.json is fresh: {age_hours:.1f}h old (max {max_age_hours}h)"


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=DEFAULT_MAX_AGE_HOURS,
        help=(
            "Fail (exit 1) if tankers.json fetchedAt is older than this many hours "
            f"(default: {DEFAULT_MAX_AGE_HOURS})"
        ),
    )
    args = parser.parse_args(argv)

    try:
        data = read_json(TANKERS_PATH)
    except FileNotFoundError:
        print(f"[fresh] {TANKERS_PATH} not found", file=sys.stderr)
        return 1

    code, message = evaluate(data, datetime.now(UTC), args.max_age_hours)
    print(f"[fresh] {message}", file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
