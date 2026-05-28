"""
data/snapshots.json の最新値から OGP 画像 (assets/og-image.png, 1200x630) を生成する。

設計方針:
    - サイト本体（ブラウザ側）と数字のソースを共有する（snapshots.json 経由）
    - 真の動的生成ではなく、毎日の自動取得に追従して PNG を更新する事前生成方式
    - 失敗時は既存 og-image.png を維持し、abort（exit non-zero）して人間に通知
    - レイアウトは index.html のヒーローカード（カウンター + counter_top.png）を踏襲

入力:
    data/snapshots.json
出力:
    assets/og-image.png  (1200x630, PNG)

引数:
    --dry-run     画像を書き出さず終了（CI のスモーク確認用）
    --output PATH 出力先を上書き（既定: assets/og-image.png）

出口コード:
    0 — 成功
    1 — 失敗（snapshots.json 不在/不正、Pillow エラー、必須フォント不在 等）
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from lib.constants import PEAK_DAYS  # SSOT: src/constants.json
from lib.io import read_json
from lib.paths import ASSETS_DIR, REPO_ROOT, SNAPSHOTS_PATH

JST = timezone(timedelta(hours=9))
SECONDS_PER_DAY = 86_400.0

DEFAULT_OUTPUT = ASSETS_DIR / "og-image.png"

# OGP 推奨サイズ (Twitter/Facebook 共通)
WIDTH = 1200
HEIGHT = 630

# 色（assets/styles/pages/home.css と assets/styles/layout.css の :root 変数と一致）
BG_TOP = (227, 233, 245)            # #e3e9f5
BG_BOTTOM = (238, 242, 250)         # #eef2fa

HEADER_NAVY = (15, 21, 53)          # #0f1535
LOGO_NAVY = (37, 43, 74)            # #252b4a
HEADER_TITLE = (255, 255, 255)
HEADER_TAGLINE = (158, 167, 192)    # #9ea7c0
HEADER_META_VALUE = (207, 213, 230) # #cfd5e6

CARD_BG = (255, 255, 255)
CARD_BORDER = (232, 236, 245)       # #e8ecf5

BRAND_BLUE = (89, 131, 241)         # #5983f1
FG_STRONG = (15, 20, 48)            # #0f1430
FG_SUB = (81, 88, 122)              # #51587a
FG_MUTED = (130, 138, 166)          # #828aa6

GRADIENT_TOP = (124, 151, 248)      # #7c97f8
GRADIENT_MID = (59, 92, 240)        # #3b5cf0
GRADIENT_BOTTOM = (37, 65, 199)     # #2541c7
GRADIENT_MID_STOP = 0.55

# カード影 (CSS は rgba(44,64,120,0.06) blur=16 だが Pillow の Gaussian は CSS より散逸が速い
# ため、視認可能な α を実測ベースで強めに採る)
SHADOW_COLOR_RGBA = (44, 64, 120, 38)
SHADOW_BLUR = 14
SHADOW_OFFSET = (0, 4)

# 画像内アセット
ILLUSTRATION_PATH = ASSETS_DIR / "counter_top.png"
INTER_FONT_DIR = ASSETS_DIR / "fonts" / "inter"

# Inter フォント候補（必ずリポジトリ同梱の TTF を最優先）。
FONT_CANDIDATES_INTER_SEMIBOLD = [str(INTER_FONT_DIR / "Inter-SemiBold.ttf")]
FONT_CANDIDATES_INTER_BOLD = [str(INTER_FONT_DIR / "Inter-Bold.ttf")]
FONT_CANDIDATES_INTER_EXTRABOLD = [str(INTER_FONT_DIR / "Inter-ExtraBold.ttf")]

# CJK 用フォント候補（"日分", 日本語ラベル）。
# GitHub Actions Ubuntu には apt で fonts-noto-cjk を入れている前提。
FONT_CANDIDATES_CJK_REGULAR = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/yugothm.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]
FONT_CANDIDATES_CJK_BOLD = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/yugothb.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]


@dataclass(frozen=True)
class Snapshot:
    published: str
    as_of: str
    total: int
    national: int
    private_: int
    joint: int


# ─────────────────────────────────────────────────────────────────────────────
# データ読込・計算（サイト側 js/core/data.js と同じ式）
# ─────────────────────────────────────────────────────────────────────────────


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


def compute_current_days(snapshot: Snapshot, now: datetime | None = None) -> float:
    """
    サイト本体 (js/core/data.js:computeCurrentDays) と同じ式で「いま時点」の備蓄日数を返す。
    モデル: 「1 日経過 = 1 日分減る」（asOf を JST 0:00 として now との差分日数を減算）。
    OG 画像は事前生成のため、cron 実行時刻の値で固定される（次の実行までは更新されない）。
    """
    if now is None:
        now = datetime.now(timezone.utc)
    as_of_jst = datetime.fromisoformat(f"{snapshot.as_of}T00:00:00+09:00")
    elapsed_days = (now - as_of_jst).total_seconds() / SECONDS_PER_DAY
    days = snapshot.total - elapsed_days
    return max(0.0, min(float(snapshot.total), days))


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


# ─────────────────────────────────────────────────────────────────────────────
# フォント解決
# ─────────────────────────────────────────────────────────────────────────────


def _find_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont | None:
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return None


def resolve_inter(
    weight: Literal["semibold", "bold", "extrabold"],
    size: int,
) -> ImageFont.FreeTypeFont:
    """Inter のリポジトリ同梱 TTF を解決する。失敗は致命（OGP の見た目が壊れる）。"""
    candidates = {
        "semibold": FONT_CANDIDATES_INTER_SEMIBOLD,
        "bold": FONT_CANDIDATES_INTER_BOLD,
        "extrabold": FONT_CANDIDATES_INTER_EXTRABOLD,
    }[weight]
    font = _find_font(candidates, size)
    if font is None:
        raise RuntimeError(
            f"Inter {weight} TTF not found. Expected at: {candidates[0]}. "
            "Bundle the font in assets/fonts/inter/ (see plan)."
        )
    return font


def resolve_cjk(
    weight: Literal["regular", "bold"],
    size: int,
) -> ImageFont.FreeTypeFont:
    """日本語グリフ用フォント。Linux/Windows/macOS のシステムフォントに依存する。"""
    candidates = (
        FONT_CANDIDATES_CJK_BOLD if weight == "bold" else FONT_CANDIDATES_CJK_REGULAR
    )
    font = _find_font(candidates, size)
    if font is None:
        raise RuntimeError(
            "No CJK font found. On CI install fonts-noto-cjk; "
            "locally rely on system Yu Gothic / Noto Sans CJK."
        )
    return font


# ─────────────────────────────────────────────────────────────────────────────
# 描画プリミティブ
# ─────────────────────────────────────────────────────────────────────────────


def _interpolate(
    c1: tuple[int, int, int],
    c2: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    return (
        int(round(c1[0] + (c2[0] - c1[0]) * t)),
        int(round(c1[1] + (c2[1] - c1[1]) * t)),
        int(round(c1[2] + (c2[2] - c1[2]) * t)),
    )


def make_vertical_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    mid: tuple[int, int, int] | None = None,
    mid_stop: float = 0.5,
) -> Image.Image:
    """1×H ストリップを補間で作り (W, H) に拡大して返す。3 stop 対応。"""
    w, h = size
    strip = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        if mid is None:
            color = _interpolate(top, bottom, t)
        else:
            if t <= mid_stop:
                color = _interpolate(top, mid, t / mid_stop if mid_stop > 0 else 0.0)
            else:
                color = _interpolate(
                    mid, bottom, (t - mid_stop) / (1.0 - mid_stop) if mid_stop < 1 else 0.0
                )
        strip.putpixel((0, y), color)
    return strip.resize((w, h), Image.Resampling.BILINEAR)


def make_rounded_rect_mask(size: tuple[int, int], radius: int) -> Image.Image:
    """角丸長方形の "L" マスクを返す。"""
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [(0, 0), (size[0] - 1, size[1] - 1)], radius=radius, fill=255
    )
    return mask


def draw_soft_shadow(
    base: Image.Image,
    *,
    rect: tuple[int, int, int, int],  # (left, top, right, bottom)
    radius: int,
    blur: int,
    offset: tuple[int, int],
    color_rgba: tuple[int, int, int, int],
) -> None:
    """rounded_rect のソフトシャドウをベース画像にアルファ合成で焼き込む。"""
    pad = blur * 3
    left, top, right, bottom = rect
    w = right - left
    h = bottom - top
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [(pad, pad), (pad + w - 1, pad + h - 1)],
        radius=radius,
        fill=color_rgba,
    )
    layer = layer.filter(ImageFilter.GaussianBlur(radius=blur))

    paste_x = left - pad + offset[0]
    paste_y = top - pad + offset[1]
    if base.mode != "RGBA":
        rgba = base.convert("RGBA")
        rgba.alpha_composite(layer, dest=(paste_x, paste_y))
        composited = rgba.convert(base.mode)
        base.paste(composited, (0, 0))
    else:
        base.alpha_composite(layer, dest=(paste_x, paste_y))


def draw_gradient_text(
    base: Image.Image,
    text: str,
    *,
    font: ImageFont.FreeTypeFont,
    xy: tuple[int, int],
    anchor: str,
    gradient_top: tuple[int, int, int],
    gradient_mid: tuple[int, int, int],
    gradient_bottom: tuple[int, int, int],
    mid_stop: float = 0.5,
) -> tuple[int, int, int, int]:
    """
    指定位置に縦 3 stop グラデーションでテキストを描く。
    マスク合成方式: L モードでテキストを白で焼き、同サイズの RGB グラデーションタイルを
    マスク経由で base に貼る。返値は描画 bbox (left, top, right, bottom)。
    """
    draw = ImageDraw.Draw(base)
    bbox = draw.textbbox(xy, text, font=font, anchor=anchor)
    left, top, right, bottom = bbox

    pad = 8  # AA の端を取りこぼさないための余白
    tile_w = right - left + pad * 2
    tile_h = bottom - top + pad * 2

    # マスク: L モードに textbbox 起点 (anchor='lt') で白文字を焼く
    mask = Image.new("L", (tile_w, tile_h), 0)
    mdraw = ImageDraw.Draw(mask)
    # base 側 xy から bbox を取った時点で baseline 等が解決済み。
    # マスク側はそれを原点 (pad, pad) にオフセットして描き直す。
    mdraw.text((xy[0] - left + pad, xy[1] - top + pad), text, font=font, fill=255, anchor=anchor)

    grad = make_vertical_gradient(
        (tile_w, tile_h),
        gradient_top,
        gradient_bottom,
        mid=gradient_mid,
        mid_stop=mid_stop,
    )

    base.paste(grad, (left - pad, top - pad), mask=mask)
    return bbox


def draw_text_letter_spaced(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
    em_spacing: float,
    anchor: str = "lt",
) -> int:
    """
    1 文字ずつ前進量に em_spacing(em) を足して描く。
    対応 anchor: "lt"（左上）/ "ls"（左ベースライン）。返値は最終 x（右端）。
    """
    x, y = xy
    # 1em ≒ font.size
    extra = em_spacing * font.size
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill, anchor=anchor)
        adv = font.getlength(ch)
        x += int(round(adv + extra))
    return x


# ─────────────────────────────────────────────────────────────────────────────
# 描画リージョン
# ─────────────────────────────────────────────────────────────────────────────


HEADER_H = 76
PAD_X = 64


def draw_header_band(base: Image.Image, *, published_iso: str) -> None:
    """上部の濃紺ヘッダ帯（site.layout の .site-header と同一トーン）。"""
    draw = ImageDraw.Draw(base)
    draw.rectangle([(0, 0), (WIDTH, HEADER_H)], fill=HEADER_NAVY)

    # ロゴ箱 (28×28, radius 6, inner inset 6 highlight)
    logo_size = 28
    logo_x = PAD_X
    logo_y = (HEADER_H - logo_size) // 2
    draw.rounded_rectangle(
        [(logo_x, logo_y), (logo_x + logo_size, logo_y + logo_size)],
        radius=6,
        fill=LOGO_NAVY,
    )
    inner_inset = 6
    inner = (255, 255, 255, 15)  # rgba(255,255,255,0.06) ≒ alpha 15
    inner_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(inner_layer).rounded_rectangle(
        [
            (logo_x + inner_inset, logo_y + inner_inset),
            (logo_x + logo_size - inner_inset, logo_y + logo_size - inner_inset),
        ],
        radius=3,
        fill=inner,
    )
    rgba = base.convert("RGBA")
    rgba.alpha_composite(inner_layer)
    base.paste(rgba.convert(base.mode), (0, 0))

    # 再構築後の draw を取り直す
    draw = ImageDraw.Draw(base)

    text_x = logo_x + logo_size + 12

    # JAPAN OIL STOCKPILE (Inter Bold 14, letter-spacing 0.1em, 白)
    title_font = resolve_inter("bold", 17)  # OGP は 14px より少し大きめに（視認性確保）
    title_text = "JAPAN OIL STOCKPILE"
    em_spacing = 0.1
    title_y = logo_y + 1
    draw_text_letter_spaced(
        draw,
        (text_x, title_y),
        title_text,
        title_font,
        HEADER_TITLE,
        em_spacing,
        anchor="lt",
    )

    # タグライン (Noto Regular 13)
    tagline_font = resolve_cjk("regular", 13)
    tagline_y = title_y + 22
    draw.text(
        (text_x, tagline_y),
        "あと何日、日本は持つのか。",
        font=tagline_font,
        fill=HEADER_TAGLINE,
        anchor="lt",
    )

    # 右側: 最終更新 YYYY年M月D日
    meta_label_font = resolve_cjk("regular", 12)
    right_x = WIDTH - PAD_X
    label_text = "最終更新"
    value_text = format_jst_date(published_iso)

    label_y = logo_y + 3
    value_y = label_y + 20

    draw.text(
        (right_x, label_y),
        label_text,
        font=meta_label_font,
        fill=HEADER_TAGLINE,
        anchor="rt",
    )
    # value は CJK 混在（"年/月/日" を含む）なので CJK Bold で描く
    value_font = resolve_cjk("bold", 14)
    draw.text(
        (right_x, value_y),
        value_text,
        font=value_font,
        fill=HEADER_META_VALUE,
        anchor="rt",
    )


def _load_illustration(width: int) -> Image.Image:
    img = Image.open(ILLUSTRATION_PATH).convert("RGBA")
    if img.width == 0:
        raise RuntimeError(f"illustration has zero width: {ILLUSTRATION_PATH}")
    ratio = width / img.width
    new_h = max(1, int(round(img.height * ratio)))
    return img.resize((width, new_h), Image.Resampling.LANCZOS)


def draw_hero_card(
    base: Image.Image,
    *,
    snapshot: Snapshot,
    current_days: float,
    ratio: float,
    peak: int,
) -> None:
    """中央の白いヒーローカード（カウンター + counter_top.png イラスト）。"""
    card_left = 60
    card_right = WIDTH - 60
    card_top = HEADER_H + 28
    card_bottom = HEADER_H + 28 + 388
    card_w = card_right - card_left
    card_h = card_bottom - card_top
    radius = 14

    # 影
    draw_soft_shadow(
        base,
        rect=(card_left, card_top, card_right, card_bottom),
        radius=radius,
        blur=SHADOW_BLUR,
        offset=SHADOW_OFFSET,
        color_rgba=SHADOW_COLOR_RGBA,
    )

    # カード塗り (rounded rect, マスク経由)
    card_layer = Image.new("RGB", (card_w, card_h), CARD_BG)
    mask = make_rounded_rect_mask((card_w, card_h), radius)
    base.paste(card_layer, (card_left, card_top), mask=mask)

    # 1px ボーダー
    draw = ImageDraw.Draw(base)
    draw.rounded_rectangle(
        [(card_left, card_top), (card_right - 1, card_bottom - 1)],
        radius=radius,
        outline=CARD_BORDER,
        width=1,
    )

    # ─── 右側: イラスト ──────────────────────────────────────────────
    illu = _load_illustration(width=290)
    illu_x = card_right - 32 - illu.width
    illu_y = card_top + (card_h - illu.height) // 2
    # alpha を mask に流して合成
    if base.mode == "RGB":
        rgba = base.convert("RGBA")
        rgba.alpha_composite(illu, dest=(illu_x, illu_y))
        base.paste(rgba.convert("RGB"), (0, 0))
    else:
        base.alpha_composite(illu, dest=(illu_x, illu_y))

    # 描画後の draw を取り直す
    draw = ImageDraw.Draw(base)

    # ─── 左側: カウンター ────────────────────────────────────────────
    left_x = card_left + 44

    # eyebrow: 今、日本の石油備蓄は
    eyebrow_font = resolve_cjk("bold", 22)
    eyebrow_y = card_top + 36
    draw.text(
        (left_x, eyebrow_y),
        "今、日本の石油備蓄は",
        font=eyebrow_font,
        fill=BRAND_BLUE,
        anchor="lt",
    )

    # 大きな数字: Inter ExtraBold + 3 stop gradient
    days_int = int(current_days)
    days_str = str(days_int)
    num_font_size = 220
    num_font = resolve_inter("extrabold", num_font_size)

    # 数字の baseline 位置を決める（card 下端から逆算）
    baseline_y = card_top + card_h - 110
    num_bbox = draw_gradient_text(
        base,
        days_str,
        font=num_font,
        xy=(left_x, baseline_y),
        anchor="ls",
        gradient_top=GRADIENT_TOP,
        gradient_mid=GRADIENT_MID,
        gradient_bottom=GRADIENT_BOTTOM,
        mid_stop=GRADIENT_MID_STOP,
    )
    # base.paste 後、再度 draw 取得
    draw = ImageDraw.Draw(base)
    num_right = num_bbox[2]

    # 「日分」（Noto Bold） + 「DAYS LEFT」（Inter Bold, letter-spaced）スタック
    unit_x = num_right + 14
    unit_font = resolve_cjk("bold", 44)
    sublabel_font = resolve_inter("bold", 13)

    # CSS 上のスタック: 上=「日分」, 下=「DAYS LEFT」(flex column)。
    # 親 row の align-items: flex-end + padding-bottom:10px により、
    # 「DAYS LEFT」の下端が数字のベースラインから ~10px 上に来る。
    days_left_baseline_y = baseline_y - 6
    unit_baseline_y = days_left_baseline_y - 22  # DAYS LEFT のキャップハイト + 余白
    draw.text(
        (unit_x, unit_baseline_y),
        "日分",
        font=unit_font,
        fill=FG_STRONG,
        anchor="ls",
    )
    draw_text_letter_spaced(
        draw,
        (unit_x, days_left_baseline_y),
        "DAYS LEFT",
        sublabel_font,
        FG_MUTED,
        em_spacing=0.1,
        anchor="ls",
    )

    # 「基準 247 日比 XX%」サブテキスト
    sub_font = resolve_cjk("regular", 17)
    sub_text = f"基準 {peak} 日比 {ratio * 100:.0f}%"
    draw.text(
        (left_x, card_top + card_h - 56),
        sub_text,
        font=sub_font,
        fill=FG_SUB,
        anchor="lt",
    )


def draw_footer_line(base: Image.Image, *, as_of_iso: str) -> None:
    """カードの下、出典 + データ時点。"""
    draw = ImageDraw.Draw(base)
    src_font = resolve_cjk("regular", 16)
    asof_font = resolve_cjk("regular", 16)
    y = HEIGHT - 32
    draw.text(
        (PAD_X, y),
        "経済産業省「石油備蓄の現況」速報値より",
        font=src_font,
        fill=FG_MUTED,
        anchor="ls",
    )
    asof_text = f"データ時点 {format_jst_date(as_of_iso)}"
    draw.text(
        (WIDTH - PAD_X, y),
        asof_text,
        font=asof_font,
        fill=FG_SUB,
        anchor="rs",
    )


# ─────────────────────────────────────────────────────────────────────────────
# オーケストレータ
# ─────────────────────────────────────────────────────────────────────────────


def render_image(
    snapshot: Snapshot,
    *,
    current_days: float,
    peak: int = PEAK_DAYS,
) -> Image.Image:
    """OGP 画像本体。1200×630 RGB を返す。"""
    bg = make_vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM)
    base = bg.copy()

    draw_header_band(base, published_iso=snapshot.published)

    ratio = compute_fill_ratio(current_days, peak)
    draw_hero_card(
        base,
        snapshot=snapshot,
        current_days=current_days,
        ratio=ratio,
        peak=peak,
    )

    draw_footer_line(base, as_of_iso=snapshot.as_of)

    return base


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

    current_days = compute_current_days(snapshot)
    days_int = int(current_days)

    try:
        img = render_image(snapshot, current_days=current_days)
    except Exception as e:
        print(f"::error::Failed to render OGP image: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(
            f"::notice::dry-run: would write {args.output} "
            f"(latest asOf={snapshot.as_of}, total={snapshot.total}, "
            f"currentDays={days_int})",
        )
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        img.save(args.output, format="PNG", optimize=True)
    except Exception as e:
        print(f"::error::Failed to write {args.output}: {e}", file=sys.stderr)
        return 1

    try:
        out_label = str(args.output.relative_to(REPO_ROOT))
    except ValueError:
        out_label = str(args.output)
    print(
        f"::notice::Wrote {out_label} "
        f"(asOf={snapshot.as_of}, total={snapshot.total}, currentDays={days_int})",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
