"""
oil_daily.pdf をダウンロード・パースし、data/snapshots.json を更新するスクリプト。

使い方:
    python scripts/fetch_pdf.py [--dry-run]

設計方針:
    - PDF は毎日同一URLで上書き更新される。直近 ~38日分の履歴を含む
    - 失敗時は既存データを維持し、abort（exit non-zero）して人間に通知
    - 重複: 既存と同じ asOf があれば PDF 値で上書き（PDFが正典）
    - 抽出: pdfplumber でテキスト化、全角数字を半角化、regex で6フィールドを取る

出口コード:
    0 — 成功（変更あり / 変更なしの両方とも0）
    1 — 失敗（ダウンロード/パース/検証エラー）
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
import time
from pathlib import Path

import pdfplumber
from curl_cffi import requests as crequests
from lib.io import read_json, write_json
from lib.paths import DATA_DIR, SNAPSHOTS_PATH

PDF_URL = (
    "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/pdf-oil-res/oil_daily.pdf"
)

TMP_PDF_PATH = DATA_DIR / ".oil_daily.pdf"

# 全角→半角
ZEN_TO_HAN = str.maketrans("０１２３４５６７８９", "0123456789")

# 経産省サイトの WAF は単なるヘッダではなく TLS フィンガープリント (JA3) /
# HTTP/2 SETTINGS まで見て bot を判別する。curl-cffi の impersonate モードで
# 実ブラウザの fingerprint を完全模倣する。
IMPERSONATE_BROWSER = "chrome"

# パース対象の本文を見つけるためのヘッダ正規表現。
# 例: 令和8年5月1日（4月28日時点） / 令和８年４月 30日（４月 27日時点）
HEADER_RE = re.compile(
    r"令和\s*(\d+)\s*年\s*(\d+)\s*月\s*(\d+)\s*日"
    r"\s*[（(]\s*(\d+)\s*月\s*(\d+)\s*日時点\s*[)）]"
)


def reiwa_to_gregorian(reiwa_year: int) -> int:
    """令和N年 → 西暦。令和元年=2019。"""
    return 2018 + reiwa_year


def download_pdf(
    dest: Path,
    *,
    timeout: int = 60,
    retries: int = 3,
    backoff: float = 5.0,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = crequests.get(
                PDF_URL,
                impersonate=IMPERSONATE_BROWSER,
                timeout=timeout,
            )
            resp.raise_for_status()
            ct = resp.headers.get("Content-Type", "")
            if "pdf" not in ct.lower():
                raise RuntimeError(f"unexpected content-type: {ct!r}")
            data = resp.content
            if not data.startswith(b"%PDF"):
                raise RuntimeError("downloaded file is not a PDF")
            dest.write_bytes(data)
            return
        except Exception as e:
            last_err = e
            print(
                f"[fetch] download attempt {attempt}/{retries} failed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"all {retries} download attempts failed") from last_err


def extract_text(pdf_path: Path) -> str:
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            chunks.append(t)
    return "\n".join(chunks).translate(ZEN_TO_HAN)


def parse_snapshots(text: str) -> list[dict]:
    """全テキストから snapshots を抽出。"""
    matches = list(HEADER_RE.finditer(text))
    if not matches:
        raise RuntimeError("no header pattern matched; PDF format may have changed")

    snapshots: list[dict] = []

    def grab(block: str, label: str) -> int | None:
        mm = re.search(rf"{label}\s*(\d+)\s*日分", block)
        return int(mm.group(1)) if mm else None

    for i, m in enumerate(matches):
        ry, mp, dp, ma, da = (int(g) for g in m.groups())
        year_pub = reiwa_to_gregorian(ry)

        # asOf の年は通常 published と同じ。ただし「公表1月、データ時点12月」のような
        # 年跨ぎは asOf 年を1引く（防御的）
        year_asof = year_pub - 1 if ma > mp else year_pub

        published = f"{year_pub:04d}-{mp:02d}-{dp:02d}"
        as_of = f"{year_asof:04d}-{ma:02d}-{da:02d}"

        block_start = m.end()
        block_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[block_start:block_end]

        national = grab(block, "国家備蓄")
        priv = grab(block, "民間備蓄")
        joint = grab(block, "産油国共同備蓄")
        total = grab(block, "合計")

        if None in (national, priv, joint, total):
            # ヘッダだけ見つかって本文が続かない異常ケースはスキップ
            continue

        snapshots.append(
            {
                "published": published,
                "asOf": as_of,
                "total": total,
                "national": national,
                "private": priv,
                "joint": joint,
            }
        )

    return snapshots


def validate(snapshot: dict, prev_total: int | None = None) -> None:
    t = snapshot["total"]
    parts = snapshot["national"] + snapshot["private"] + snapshot["joint"]
    if not (50 <= t <= 500):
        raise RuntimeError(f"total out of plausible range: {t}")
    if abs(parts - t) > 2:
        raise RuntimeError(
            f"breakdown sum {parts} differs from total {t} by >2 ({snapshot['asOf']})"
        )
    if prev_total is not None and abs(t - prev_total) > 30:
        # 日次変動が30日超は通常起こらない
        raise RuntimeError(f"daily change too large: prev {prev_total} -> {t} ({snapshot['asOf']})")


def load_existing() -> list[dict]:
    if not SNAPSHOTS_PATH.exists():
        return []
    return read_json(SNAPSHOTS_PATH)


def save(snapshots: list[dict]) -> None:
    write_json(SNAPSHOTS_PATH, snapshots)


def merge(existing: list[dict], new: list[dict]) -> tuple[list[dict], int, int]:
    """
    既存と新規を asOf キーで統合。新規があれば値を上書き。
    戻り値: (merged_sorted, added_count, updated_count)
    """
    by_as_of: dict[str, dict] = {row["asOf"]: row for row in existing}
    added = 0
    updated = 0
    for r in new:
        key = r["asOf"]
        if key not in by_as_of:
            by_as_of[key] = r
            added += 1
        elif by_as_of[key] != r:
            by_as_of[key] = r
            updated += 1
    merged = sorted(by_as_of.values(), key=lambda x: x["asOf"])
    return merged, added, updated


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse PDF and report changes without writing snapshots.json",
    )
    parser.add_argument(
        "--keep-pdf",
        action="store_true",
        help="Do not delete the temporary PDF after parsing",
    )
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=None,
        help="Use a local PDF instead of downloading (for testing)",
    )
    args = parser.parse_args(argv)

    pdf_path = args.pdf_path
    if pdf_path is None:
        print(f"[fetch] downloading {PDF_URL}")
        try:
            download_pdf(TMP_PDF_PATH)
        except Exception as e:
            print(f"[fetch] download failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        pdf_path = TMP_PDF_PATH
    else:
        print(f"[fetch] using local PDF: {pdf_path}")
        if not pdf_path.exists():
            print(f"[fetch] file not found: {pdf_path}", file=sys.stderr)
            return 1

    try:
        text = extract_text(pdf_path)
        new_snapshots = parse_snapshots(text)
    except Exception as e:
        print(f"[fetch] parse failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_pdf and args.pdf_path is None:
            with contextlib.suppress(FileNotFoundError):
                TMP_PDF_PATH.unlink()

    if not new_snapshots:
        print("[fetch] no snapshots extracted (unexpected)", file=sys.stderr)
        return 1

    print(f"[fetch] extracted {len(new_snapshots)} snapshots")

    # 検証（最新だけでなく全件）
    new_sorted = sorted(new_snapshots, key=lambda r: r["asOf"])
    print(f"[fetch] PDF range: {new_sorted[0]['asOf']} .. {new_sorted[-1]['asOf']}")
    print(f"[fetch] newest in PDF: {new_sorted[-1]}")
    prev_total = None
    for s in new_sorted:
        try:
            validate(s, prev_total)
        except Exception as e:
            print(f"[fetch] validation failed: {e}", file=sys.stderr)
            return 1
        prev_total = s["total"]

    existing = load_existing()
    merged, added, updated = merge(existing, new_sorted)

    print(f"[fetch] existing rows: {len(existing)}, added: {added}, updated: {updated}")

    if added == 0 and updated == 0:
        print("[fetch] no changes")
        return 0

    if args.dry_run:
        print("[fetch] dry-run; not writing snapshots.json")
        return 0

    save(merged)
    print(f"[fetch] wrote {SNAPSHOTS_PATH} with {len(merged)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
