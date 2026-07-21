"""提言(/opinions/)専用の OGP 画像 (assets/og-opinions.png, 1200x630) を生成する。

カウンターの og-image.png と違い、ライブ数値に依存しない静的カード。
毎日の自動ビルド(fetch-daily)では再生成しない前提で、内容が変わったときだけ
手動で `python scripts/generate_opinions_og.py` を実行してコミットする。

配色・トンマナは assets/styles/pages/home.css / layout.css の :root と揃える。

出口コード: 0 成功 / 1 失敗（フォント不在・Pillow エラー等）。
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 630

REPO_ROOT = Path(__file__).resolve().parent.parent
INTER_DIR = REPO_ROOT / "assets" / "fonts" / "inter"
OUTPUT = REPO_ROOT / "assets" / "og-opinions.png"

# --- 色（サイトの :root 変数と一致） ---
BG_TOP = (227, 233, 245)
BG_BOTTOM = (238, 242, 250)
HEADER_NAVY = (15, 21, 53)
LOGO_NAVY = (37, 43, 74)
WHITE = (255, 255, 255)
TAGLINE = (158, 167, 192)
CARD_BG = (255, 255, 255)
CARD_BORDER = (232, 236, 245)
BRAND_BLUE = (89, 131, 241)
FG_STRONG = (15, 20, 48)
FG_SUB = (81, 88, 122)
# 論客カードのアクセント（amber / orange / sky）
DOTS = [(245, 158, 11), (249, 115, 22), (2, 132, 199)]

# CJK フォント候補（mac ローカル → CI Ubuntu の noto）
CJK_CANDIDATES = [
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W7.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf",
]


def load_cjk(size: int) -> ImageFont.FreeTypeFont:
    for path in CJK_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit("CJK フォントが見つかりません（mac の Hiragino か CI の noto-cjk が必要）")


def load_inter(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = INTER_DIR / name
    if not path.exists():
        raise SystemExit(f"Inter フォント不在: {path}")
    return ImageFont.truetype(str(path), size)


def vertical_gradient(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    w, h = size
    grad = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        grad.putpixel(
            (0, y),
            tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3)),
        )
    return grad.resize((w, h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=255)
    return mask


def main() -> int:
    img = vertical_gradient((WIDTH, HEIGHT), BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # --- ヘッダーバー ---
    header_h = 104
    draw.rectangle([0, 0, WIDTH, header_h], fill=HEADER_NAVY)
    draw.rounded_rectangle([48, 30, 92, 74], radius=10, fill=LOGO_NAVY)
    draw.text((108, 30), "JAPAN OIL STOCKPILE", font=load_inter("Inter-Bold.ttf", 30), fill=WHITE)
    draw.text((108, 66), "あと何日、日本は持つのか。", font=load_cjk(20), fill=TAGLINE)

    # --- カード ---
    cx0, cy0, cx1, cy1 = 64, 152, WIDTH - 64, HEIGHT - 64
    card = Image.new("RGBA", (cx1 - cx0, cy1 - cy0), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cw, ch = card.size
    # soft shadow
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([cx0, cy0 + 10, cx1, cy1 + 10], 28, fill=(44, 64, 120, 46))
    shadow = shadow.filter(__import__("PIL.ImageFilter", fromlist=["GaussianBlur"]).GaussianBlur(18))
    img.alpha_composite(shadow)
    cd.rounded_rectangle([0, 0, cw - 1, ch - 1], 28, fill=CARD_BG, outline=CARD_BORDER, width=2)

    pad = 64
    # eyebrow（"提言" は CJK、"/ OPINIONS" は Inter で描き分ける）
    cd.text((pad, 58), "提言", font=load_cjk(26), fill=BRAND_BLUE)
    eb_w = cd.textlength("提言", font=load_cjk(26))
    cd.text(
        (pad + eb_w + 12, 56),
        "/ OPINIONS",
        font=load_inter("Inter-SemiBold.ttf", 26),
        fill=BRAND_BLUE,
    )
    # title
    cd.text((pad, 104), "国会論客カード", font=load_cjk(96), fill=FG_STRONG)
    # subtitle
    cd.text(
        (pad, 232),
        "税・エネルギー負担をめぐる国会論戦アーカイブ",
        font=load_cjk(34),
        fill=FG_SUB,
    )
    # 論客アクセントの3ドット（右上）
    r = 26
    for i, color in enumerate(DOTS):
        x = cw - pad - (len(DOTS) - i) * (r * 2 + 14)
        cd.ellipse([x, 60, x + r * 2, 60 + r * 2], fill=color, outline=WHITE, width=3)
    # 下部 URL
    cd.text(
        (pad, ch - 66),
        "oilstock.nextlabs.jp  ・  非公式アーカイブ",
        font=load_cjk(26),
        fill=FG_SUB,
    )

    img.alpha_composite(card, (cx0, cy0))
    img.convert("RGB").save(OUTPUT, "PNG")
    print(f"wrote {OUTPUT} ({WIDTH}x{HEIGHT})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
