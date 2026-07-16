"""data/snapshots.json の読込・最新値選択・日付整形の共有ヘルパー。

generate_ogp.py（OGP 画像）と build_site.py（HTML 焼き込み, Issue #93）の
両方が同じ「最新スナップショット」の解釈を使うため、ここに一元化する。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io import read_json


@dataclass(frozen=True)
class Snapshot:
    published: str
    as_of: str
    total: int
    national: int
    private_: int
    joint: int


def load_snapshots(path: Path) -> list[dict]:
    data = read_json(path)
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} is empty or invalid")
    return data


def pick_latest_snapshot(rows: list[dict]) -> Snapshot:
    """asOf 昇順で末尾を最新とする。"""
    if not rows:
        raise ValueError("snapshots is empty")
    # ソートキー (asOf) を含む必須キーをソート前に全行で検証する。
    # ソートを先に行うと asOf 欠落行が不透明な KeyError を投げ、
    # 下のドキュメント化された ValueError 経路に到達しない。
    required = ("published", "asOf", "total", "national", "private", "joint")
    for row in rows:
        for k in required:
            if k not in row:
                raise ValueError(f"snapshot is missing key: {k}")
    r = sorted(rows, key=lambda row: row["asOf"])[-1]
    return Snapshot(
        published=r["published"],
        as_of=r["asOf"],
        total=int(r["total"]),
        national=int(r["national"]),
        private_=int(r["private"]),
        joint=int(r["joint"]),
    )


def format_jst_date(iso: str) -> str:
    """'2026-04-28' → '2026年4月28日'。"""
    parts = iso.split("-")
    if len(parts) != 3:
        return iso
    y, m, d = parts
    try:
        return f"{int(y)}年{int(m)}月{int(d)}日"
    except ValueError:
        return iso
