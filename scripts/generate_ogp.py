"""
data/snapshots.json の最新値から OGP 画像 (assets/og-image.png, 1200x630) を生成する。

設計方針:
    - サイト本体（ブラウザ側）と数字のソースを共有する（snapshots.json 経由）
    - 真の動的生成ではなく、毎日の自動取得に追従して PNG を更新する事前生成方式
    - 失敗時は既存 og-image.png を維持し、abort（exit non-zero）して人間に通知
    - レイアウトは index.html のカウンター + タンクゲージのミニチュアを目指す

入力:
    data/snapshots.json
出力:
    assets/og-image.png  (1200x630, PNG)

引数:
    --dry-run     画像を書き出さず終了（CI のスモーク確認用）
    --output PATH 出力先を上書き（既定: assets/og-image.png）

出口コード:
    0 — 成功
    1 — 失敗（snapshots.json 不在/不正、Pillow エラー等）
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from lib.constants import PEAK_DAYS  # SSOT: src/constants.json
from lib.io import read_json
from lib.paths import ASSETS_DIR, REPO_ROOT, SNAPSHOTS_PATH

DEFAULT_OUTPUT = ASSETS_DIR / "og-image.png"

# OGP 推奨サイズ (Twitter/Facebook 共通)
WIDTH = 1200
HEIGHT = 630

# 色（assets/styles.css の :root 変数と一致）
BG = (250, 250, 250)              # --bg
CARD_BG = (255, 255, 255)         # --bg-card
FG = (17, 17, 17)                 # --fg
FG_SUB = (89, 89, 89)             # --fg-sub
FG_MUTED = (107, 107, 107)        # --fg-muted
RULE = (229, 229, 229)            # --rule
TANK_OK = (26, 26, 26)            # ratio>=0.8
TANK_MID = (119, 119, 119)        # 0.4<=ratio<0.8
TANK_WARN = (192, 57, 43)         # ratio<0.4

# フォント候補（先に見つかった順に採用）。
# GitHub Actions Ubuntu には apt で fonts-noto-cjk を入れる前提。
FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/yugothm.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]
FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/yugothb.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]
FONT_CANDIDATES_LIGHT = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Light.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Light.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Light.otf",
    *FONT_CANDIDATES_REGULAR,  # Light がなければ Regular にフォールバック
]


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
    sorted_rows = sorted(rows, key=lambda r: r["asOf"])
    r = sorted_rows[-1]
    required = ("published", "asOf", "total", "national", "private", "joint")
    for k in required:
        if k not in r:
            raise ValueError(f"snapshot is missing key: {k}")
    return Snapshot(
        published=r["published"],
        as_of=r["asOf"],
        total=int(r["total"]),
        national=int(r["national"]),
        private_=int(r["private"]),
        joint=int(r["joint"]),
    )


def compute_fill_ratio(days: float, peak: int = PEAK_DAYS) -> float:
    """0..1 にクランプした充填率。peak<=0 は 0 を返す。"""
    if peak <= 0:
        return 0.0
    r = days / peak
    if r < 0:
        return 0.0
    if r > 1:
        return 1.0
    return r


def color_for_ratio(r: float) -> tuple[int, int, int]:
    if r >= 0.8:
        return TANK_OK
    if r >= 0.4:
        return TANK_MID
    return TANK_WARN


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


def find_font(candidates: list[str], size: int) -> ImageFont.ImageFont:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    # 最終フォールバック: Pillow デフォルト（日本語は描画できない）
    print(
        "::warning::No CJK font found; falling back to Pillow default. "
        "Japanese characters will render as boxes.",
        file=sys.stderr,
    )
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    """anchor='lt' 基準のテキスト寸法 (w, h)。"""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_tank_gauge(
    draw: ImageDraw.ImageDraw,
    *,
    cx: int,
    cy: int,
    width: int,
    height: int,
    ratio: float,
    peak: int,
) -> None:
    """中心 (cx, cy) を基準にタンクゲージを描く。tank-gauge.js のミニチュア。"""
    half_w = width // 2
    half_h = height // 2
    left = cx - half_w
    right = cx + half_w
    top = cy - half_h
    bottom = cy + half_h

    stroke = 3
    inset_top = top + stroke
    inset_bottom = bottom - stroke
    inset_left = left + stroke
    inset_right = right - stroke
    inset_h = inset_bottom - inset_top

    # 背景パネル（凡そカードに収まる感）
    fill_h = int(inset_h * ratio)
    fill_top = inset_bottom - fill_h
    color = color_for_ratio(ratio)

    # フィル（角丸クリップは Pillow の単純実装で省略。長方形で十分視認できる）
    if fill_h > 0:
        draw.rectangle(
            [(inset_left, fill_top), (inset_right, inset_bottom)],
            fill=color,
        )

    # 枠
    draw.rectangle(
        [(left, top), (right, bottom)],
        outline=FG,
        width=stroke,
    )

    # 上部パイプ（演出）
    pipe_w = max(20, width // 5)
    pipe_h = max(8, height // 30)
    draw.rectangle(
        [(cx - pipe_w // 2, top - pipe_h), (cx + pipe_w // 2, top)],
        fill=FG,
    )

    # 右側目盛りラベル: peak / half / 0
    tick_x = right + 12
    half_y = inset_bottom - inset_h // 2
    label_font = find_font(FONT_CANDIDATES_REGULAR, 22)
    for label, y in (
        (str(peak), inset_top),
        (str(peak // 2), half_y),
        ("0", inset_bottom),
    ):
        draw.text((tick_x, y), label, font=label_font, fill=FG_MUTED, anchor="lm")


def render_image(snapshot: Snapshot, *, peak: int = PEAK_DAYS) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    # フォント
    f_lead = find_font(FONT_CANDIDATES_REGULAR, 36)
    f_days_num = find_font(FONT_CANDIDATES_LIGHT, 320)
    f_days_unit = find_font(FONT_CANDIDATES_REGULAR, 64)
    f_meta = find_font(FONT_CANDIDATES_REGULAR, 22)
    f_brand = find_font(FONT_CANDIDATES_BOLD, 26)
    f_gauge_caption = find_font(FONT_CANDIDATES_REGULAR, 20)

    # ── ヘッダ（左上）: ブランド
    pad_x = 64
    pad_y = 56
    draw.text((pad_x, pad_y), "あと何日？", font=f_brand, fill=FG, anchor="lt")
    draw.text(
        (pad_x, pad_y + 38),
        "日本の石油備蓄",
        font=f_meta,
        fill=FG_SUB,
        anchor="lt",
    )

    # ── 中央左: 「いま、日本の石油備蓄は」
    lead_y = 200
    draw.text(
        (pad_x, lead_y),
        "いま、日本の石油備蓄は",
        font=f_lead,
        fill=FG_SUB,
        anchor="lt",
    )

    # ── メインカウンター: N 日
    days_str = str(snapshot.total)
    days_y = lead_y + 60
    days_w, _ = _text_size(draw, days_str, f_days_num)
    draw.text((pad_x, days_y), days_str, font=f_days_num, fill=FG, anchor="lt")
    # 「日分」
    unit_x = pad_x + days_w + 28
    unit_y = days_y + 230
    draw.text((unit_x, unit_y), "日分", font=f_days_unit, fill=FG_SUB, anchor="ls")

    # ── 右側: タンクゲージ（数字なしの視覚アクセントとして配置）
    ratio = compute_fill_ratio(snapshot.total, peak)
    gauge_cx = WIDTH - 200
    gauge_cy = HEIGHT // 2 + 30
    gauge_w = 160
    gauge_h = 360
    draw_tank_gauge(
        draw,
        cx=gauge_cx,
        cy=gauge_cy,
        width=gauge_w,
        height=gauge_h,
        ratio=ratio,
        peak=peak,
    )

    # ゲージのキャプション（タンク真上、ピプの上）
    caption = f"備蓄日数（基準 {peak} 日比 {ratio * 100:.0f}%）"
    cap_w, _ = _text_size(draw, caption, f_gauge_caption)
    draw.text(
        (gauge_cx, gauge_cy - gauge_h // 2 - 38),
        caption,
        font=f_gauge_caption,
        fill=FG_SUB,
        anchor="mb",
    )

    # ── フッタ: 出典 + データ時点
    footer_y = HEIGHT - 56
    draw.line(
        [(pad_x, footer_y - 28), (WIDTH - pad_x, footer_y - 28)],
        fill=RULE,
        width=1,
    )
    src_text = "経済産業省「石油備蓄の現況」速報値より"
    asof_text = f"データ時点 {format_jst_date(snapshot.as_of)}"
    draw.text((pad_x, footer_y), src_text, font=f_meta, fill=FG_MUTED, anchor="ls")
    draw.text(
        (WIDTH - pad_x, footer_y),
        asof_text,
        font=f_meta,
        fill=FG_MUTED,
        anchor="rs",
    )

    return img


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="画像を生成して破棄する（出力ファイルを書かない）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"出力先パス（既定: {DEFAULT_OUTPUT.relative_to(REPO_ROOT)})",
    )
    args = parser.parse_args()

    try:
        rows = load_snapshots(SNAPSHOTS_PATH)
        snapshot = pick_latest_snapshot(rows)
    except Exception as e:
        print(f"::error::Failed to load snapshots: {e}", file=sys.stderr)
        return 1

    try:
        img = render_image(snapshot)
    except Exception as e:
        print(f"::error::Failed to render OGP image: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(
            f"::notice::dry-run: would write {args.output} "
            f"(latest asOf={snapshot.as_of}, total={snapshot.total})",
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        img.save(args.output, format="PNG", optimize=True)
    except Exception as e:
        print(f"::error::Failed to write {args.output}: {e}", file=sys.stderr)
        return 1

    print(
        f"::notice::Wrote {args.output.relative_to(REPO_ROOT)} "
        f"(asOf={snapshot.as_of}, total={snapshot.total})",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
