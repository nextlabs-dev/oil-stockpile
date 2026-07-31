"""
ＬＰガス備蓄の現況（月次PDF）をダウンロード・パースし、
data/lpg_snapshots.json を更新するスクリプト。

石油版 (scripts/fetch_pdf.py) の姉妹スクリプト。相違点は2つ:

    1. LPG は「毎月」公表で、PDF URL が毎回変わる（例:
       pl002/pdf/2026/20260715lp.pdf）。命名も不統一（lp / LP / 無印）。
       → results.html の統計表一覧から最新PDFのURLを毎回スクレイプする。
    2. LPG データは公表の約2ヶ月前時点（前々月）を指す。石油の日次速報と違い
       秒読み向きではないため、フロントは「公表値そのまま（静的）」で表示する。
       本スクリプトは日数を丸めず float のまま保存する。

抽出する値（最新の完全行）:
    民間備蓄 保有量（日数） / 国家備蓄 保有量（日数） / 合計日数

    ※ 国家備蓄の「日数」は PDF 上、最新月の行にしか併記されない
       （保有量[千トン]は各月に載る）。よって国家日数が入っている
       最も新しい行を「カウンター基準行」とみなす。

出口コード:
    0 — 成功（変更あり / 変更なしの両方とも0）
    1 — 失敗（ダウンロード/パース/検証エラー）

使い方:
    python scripts/fetch_lpg.py [--dry-run] [--pdf-path path/to/lp.pdf]
"""

from __future__ import annotations

import argparse
import calendar
import contextlib
import datetime
import re
import sys
import time
from pathlib import Path

import pdfplumber
from curl_cffi import requests as crequests

from lib.io import read_json, write_json
from lib.paths import DATA_DIR

LPG_SNAPSHOTS_PATH = DATA_DIR / "lpg_snapshots.json"

RESULTS_URL = "https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl002/results.html"
SITE_ORIGIN = "https://www.enecho.meti.go.jp"

TMP_PDF_PATH = DATA_DIR / ".lpg_monthly.pdf"

# 全角→半角（数字・括弧・小数点・カンマ・コロン・全角スペース）
ZEN_TO_HAN = str.maketrans(
    "０１２３４５６７８９（）．，－：　",
    "0123456789().,-: ",
)

# 経産省サイトの WAF は TLS フィンガープリント (JA3) / HTTP/2 SETTINGS まで見る。
# curl-cffi の impersonate で実ブラウザ fingerprint を模倣する（石油版と同条件）。
IMPERSONATE_BROWSER = "chrome"

# results.html 内の LPG 月次PDFリンク。日付部分(YYYYMMDD / YYMMDD)を捕捉する。
PDF_LINK_RE = re.compile(
    r'href="(?P<href>[^"]*?/pl002/pdf/\d{4}/(?P<date>\d{6,8})[a-zA-Z]*\.pdf)"',
    re.IGNORECASE,
)

# 推移テーブルの1行。
# 例: "令和8年 5月 979 1,520(62.1) 1,392(53.0)"
#     "6月 1,087 1,420 (52.3) 1,392"（国家日数なし・年は前行から継承）
ROW_RE = re.compile(
    r"(?:令\s*和\s*(?P<ry>\d+)\s*年\s*)?"
    r"(?P<mo>\d{1,2})月\s+"
    r"(?P<pk>[\d,]+)\s+"  # 民間 基準備蓄量
    r"(?P<ph>[\d,]+)\s*\((?P<pd>\d+\.\d)\)\s+"  # 民間 保有量(日数)
    r"(?P<nh>[\d,]+)"  # 国家 保有量
    r"(?:\s*\((?P<nd>\d+\.\d)\))?"  # 国家 日数（最新行のみ）
)


def reiwa_to_gregorian(reiwa_year: int) -> int:
    """令和N年 → 西暦。令和元年=2019。"""
    return 2018 + reiwa_year


def _num(s: str) -> int:
    return int(s.replace(",", ""))


def _date_from_filename(token: str) -> datetime.date:
    """PDF ファイル名の日付トークン(YYYYMMDD or YYMMDD)を date に変換。"""
    if len(token) == 8:
        y, m, d = int(token[0:4]), int(token[4:6]), int(token[6:8])
    elif len(token) == 6:
        y, m, d = 2000 + int(token[0:2]), int(token[2:4]), int(token[4:6])
    else:  # pragma: no cover - 正規表現で 6/8 桁に限定済み
        raise ValueError(f"unexpected date token: {token!r}")
    return datetime.date(y, m, d)


def resolve_latest_pdf_url(
    *, timeout: int = 60, retries: int = 3, backoff: float = 5.0
) -> tuple[str, datetime.date]:
    """results.html を取得し、最新（ファイル名日付が最大）の月次PDFのURLを返す。"""
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = crequests.get(
                RESULTS_URL, impersonate=IMPERSONATE_BROWSER, timeout=timeout
            )
            resp.raise_for_status()
            html = resp.text
            candidates: list[tuple[datetime.date, str]] = []
            for m in PDF_LINK_RE.finditer(html):
                href = m.group("href")
                pub = _date_from_filename(m.group("date"))
                url = href if href.startswith("http") else SITE_ORIGIN + href
                candidates.append((pub, url))
            if not candidates:
                raise RuntimeError("no LPG PDF link found in results.html")
            pub, url = max(candidates, key=lambda t: t[0])
            return url, pub
        except Exception as e:  # noqa: BLE001 - リトライして最終的に abort
            last_err = e
            print(
                f"[lpg] resolve attempt {attempt}/{retries} failed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"all {retries} resolve attempts failed") from last_err


def download_pdf(
    url: str,
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
            resp = crequests.get(url, impersonate=IMPERSONATE_BROWSER, timeout=timeout)
            resp.raise_for_status()
            data = resp.content
            if not data.startswith(b"%PDF"):
                raise RuntimeError("downloaded file is not a PDF")
            dest.write_bytes(data)
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(
                f"[lpg] download attempt {attempt}/{retries} failed: {type(e).__name__}: {e}",
                file=sys.stderr,
            )
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"all {retries} download attempts failed") from last_err


def extract_text(pdf_path: Path) -> str:
    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            chunks.append(page.extract_text() or "")
    return "\n".join(chunks).translate(ZEN_TO_HAN)


def parse_rows(text: str) -> list[dict]:
    """推移テーブルを月次行のリストに変換（asOf 昇順）。"""
    rows: list[dict] = []
    cur_year: int | None = None
    for m in ROW_RE.finditer(text):
        if m.group("ry"):
            ry = int(m.group("ry"))
            if not (1 <= ry <= 30):
                raise RuntimeError(f"implausible Reiwa year {ry}: {m.group(0)!r}")
            cur_year = reiwa_to_gregorian(ry)
        if cur_year is None:
            # 年が一度も現れる前の行は文脈不明なのでスキップ
            continue
        mo = int(m.group("mo"))
        if not (1 <= mo <= 12):
            raise RuntimeError(f"implausible month {mo}: {m.group(0)!r}")
        last_day = calendar.monthrange(cur_year, mo)[1]
        national_days = float(m.group("nd")) if m.group("nd") else None
        private_days = float(m.group("pd"))
        row = {
            "month": f"{cur_year:04d}-{mo:02d}",
            "asOf": f"{cur_year:04d}-{mo:02d}-{last_day:02d}",
            "privateKijun": _num(m.group("pk")),
            "privateHold": _num(m.group("ph")),
            "privateDays": private_days,
            "nationalHold": _num(m.group("nh")),
            "nationalDays": national_days,
            "totalDays": (
                round(private_days + national_days, 1)
                if national_days is not None
                else None
            ),
        }
        rows.append(row)
    if not rows:
        raise RuntimeError("no data rows matched; PDF format may have changed")
    return rows


def basis_row(rows: list[dict]) -> dict:
    """カウンター基準行 = 国家日数が入っている最も新しい行。"""
    complete = [r for r in rows if r["nationalDays"] is not None]
    if not complete:
        raise RuntimeError("no row with national reserve days found")
    return complete[-1]


def validate(row: dict) -> None:
    try:
        datetime.date.fromisoformat(row["asOf"])
    except ValueError as e:
        raise RuntimeError(f"invalid asOf date: {e}") from e
    pd, nd, td = row["privateDays"], row["nationalDays"], row["totalDays"]
    # 制度上、民間40日義務・国家50日目標。実績は上振れするが妥当域で遮断する。
    if not (20 <= pd <= 150):
        raise RuntimeError(f"privateDays out of plausible range: {pd}")
    if not (20 <= nd <= 150):
        raise RuntimeError(f"nationalDays out of plausible range: {nd}")
    if abs((pd + nd) - td) > 0.15:
        raise RuntimeError(f"totalDays {td} != private {pd} + national {nd}")
    if not (40 <= td <= 300):
        raise RuntimeError(f"totalDays out of plausible range: {td}")


def load_existing() -> list[dict]:
    if not LPG_SNAPSHOTS_PATH.exists():
        return []
    return read_json(LPG_SNAPSHOTS_PATH)


def merge(existing: list[dict], new: list[dict]) -> tuple[list[dict], int, int]:
    """month キーで統合。新規PDFの値を正典として上書き。"""
    by_month: dict[str, dict] = {r["month"]: r for r in existing}
    added = updated = 0
    for r in new:
        key = r["month"]
        if key not in by_month:
            by_month[key] = r
            added += 1
        elif by_month[key] != r:
            by_month[key] = r
            updated += 1
    merged = sorted(by_month.values(), key=lambda x: x["month"])
    return merged, added, updated


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--keep-pdf", action="store_true")
    parser.add_argument(
        "--pdf-path",
        type=Path,
        default=None,
        help="ローカルPDFを使う（テスト用。指定時はダウンロードしない）",
    )
    parser.add_argument(
        "--published",
        default=None,
        help="--pdf-path 併用時に公表日(YYYY-MM-DD)を明示",
    )
    args = parser.parse_args(argv)

    published: str | None = args.published
    if args.pdf_path is None:
        try:
            url, pub_date = resolve_latest_pdf_url()
            print(f"[lpg] latest PDF: {url} (published {pub_date})")
            download_pdf(url, TMP_PDF_PATH)
            published = pub_date.isoformat()
        except Exception as e:  # noqa: BLE001
            print(f"[lpg] fetch failed: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        pdf_path = TMP_PDF_PATH
    else:
        pdf_path = args.pdf_path
        print(f"[lpg] using local PDF: {pdf_path}")
        if not pdf_path.exists():
            print(f"[lpg] file not found: {pdf_path}", file=sys.stderr)
            return 1

    try:
        text = extract_text(pdf_path)
        rows = parse_rows(text)
    except Exception as e:  # noqa: BLE001
        print(f"[lpg] parse failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    finally:
        if not args.keep_pdf and args.pdf_path is None:
            with contextlib.suppress(FileNotFoundError):
                TMP_PDF_PATH.unlink()

    basis = basis_row(rows)
    if published:
        basis = {**basis, "published": published}
    try:
        validate(basis)
    except Exception as e:  # noqa: BLE001
        print(f"[lpg] validation failed: {e}", file=sys.stderr)
        return 1

    print(f"[lpg] parsed {len(rows)} months; basis row: {basis}")

    existing = load_existing()
    merged, added, updated = merge(existing, rows)
    # published は基準行にだけ持たせる（history 行には不要）
    for r in merged:
        if r["month"] == basis["month"] and published:
            r["published"] = published
    print(f"[lpg] existing: {len(existing)}, added: {added}, updated: {updated}")

    if added == 0 and updated == 0:
        print("[lpg] no changes")
        return 0

    if args.dry_run:
        print("[lpg] dry-run; not writing lpg_snapshots.json")
        return 0

    write_json(LPG_SNAPSHOTS_PATH, merged)
    print(f"[lpg] wrote {LPG_SNAPSHOTS_PATH} with {len(merged)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
