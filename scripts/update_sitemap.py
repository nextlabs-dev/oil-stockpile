"""Update sitemap lastmod values from the latest published data snapshots."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITEMAP_PATH = ROOT / "sitemap.xml"
SNAPSHOTS_PATH = ROOT / "data" / "snapshots.json"
TANKERS_PATH = ROOT / "data" / "tankers.json"

LOC_BLOCK_RE = re.compile(
    r"(?P<indent>\s*)<loc>(?P<url>[^<]+)</loc>(?P<rest>.*?)(?P<close>\s*</url>)",
    re.DOTALL,
)
LASTMOD_RE = re.compile(r"\s*<lastmod>[^<]+</lastmod>")


def latest_oil_date() -> str:
    rows = json.loads(SNAPSHOTS_PATH.read_text(encoding="utf-8"))
    dates = [row["published"] for row in rows if isinstance(row.get("published"), str)]
    if not dates:
        raise ValueError("snapshots.json has no published dates")
    return max(dates)


def latest_tanker_date() -> str:
    data = json.loads(TANKERS_PATH.read_text(encoding="utf-8"))
    fetched_at = data.get("fetchedAt")
    if not isinstance(fetched_at, str) or len(fetched_at) < 10:
        raise ValueError("tankers.json has no valid fetchedAt")
    return fetched_at[:10]


def update_lastmod(xml: str, url_to_date: dict[str, str]) -> str:
    def replace_block(match: re.Match[str]) -> str:
        url = match.group("url")
        if url not in url_to_date:
            return match.group(0)
        raw_indent = match.group("indent")
        # LOC_BLOCK_RE の \s* は直前の改行も捕捉するため、改行と行頭空白を分離する。
        line_break = "\n" if "\n" in raw_indent else ""
        indent = raw_indent.rsplit("\n", 1)[-1]
        rest = LASTMOD_RE.sub("", match.group("rest"))
        lastmod = f"{indent}  <lastmod>{url_to_date[url]}</lastmod>"
        return f"{line_break}{indent}<loc>{url}</loc>{rest}\n{lastmod}{match.group('close')}"

    return LOC_BLOCK_RE.sub(replace_block, xml)


def main() -> int:
    oil_date = latest_oil_date()
    tanker_date = latest_tanker_date()
    url_to_date = {
        "https://oilstock.nextlabs.jp/": oil_date,
        "https://oilstock.nextlabs.jp/tankers/": tanker_date,
    }
    original = SITEMAP_PATH.read_text(encoding="utf-8")
    updated = update_lastmod(original, url_to_date)
    if updated == original:
        print("sitemap.xml already up to date")
        return 0
    SITEMAP_PATH.write_text(updated, encoding="utf-8")
    print(f"updated sitemap.xml: oil={oil_date}, tankers={tanker_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
