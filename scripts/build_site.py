"""Build static HTML pages from shared templates.

The deployed URLs stay as plain GitHub Pages files:
  - index.html
  - tankers/index.html
  - scale/index.html
  - about/index.html

Source HTML lives under src/pages and only contains the page-specific main
content. Shared head/header/footer markup is generated here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from string import Template


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PAGES_DIR = SRC / "pages"
TEMPLATES_DIR = SRC / "templates"
BASE_TEMPLATE = TEMPLATES_DIR / "base.html"

SITE_URL = "https://tkysi-mi.github.io/oil-stockpile"
OG_IMAGE = f"{SITE_URL}/assets/og-image.png"
OG_IMAGE_ALT = "日本の石油備蓄カウンターと充填率タンクゲージ"
FONT_HREF = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@200;300;400;500;700&"
    "family=Noto+Sans+JP:wght@200;300;400;500;700&display=swap"
)


@dataclass(frozen=True)
class Page:
    key: str
    source: str
    output: str
    title: str
    description: str
    canonical_path: str
    og_title: str
    og_description: str
    twitter_title: str
    twitter_description: str
    active_nav: str
    script_tags: str = ""
    extra_head: str = ""
    footer_source: str = ""
    footer_disclaimer: str = ""
    root_path: str = "./"
    nav: dict[str, str] = field(default_factory=dict)


EXTERNAL_NOTE = '<span class="visually-hidden">（外部サイト・別タブで開きます）</span>'

PAGES = [
    Page(
        key="home",
        source="home.html",
        output="index.html",
        title="あと何日？｜日本の石油備蓄",
        description="日本の石油備蓄、いまこれだけ。経済産業省「石油備蓄の現況」速報値を分かりやすく可視化する非公式カウンター。",
        canonical_path="/",
        og_title="あと何日？｜日本の石油備蓄",
        og_description="経済産業省の速報値から、日本の石油備蓄日数を静かに可視化します。",
        twitter_title="あと何日？｜日本の石油備蓄",
        twitter_description="経済産業省の速報値から、日本の石油備蓄日数を静かに可視化します。",
        active_nav="home",
        script_tags='<script type="module" src="js/pages/home.js"></script>',
        footer_source=(
            '<strong>データ出典:</strong>\n'
            '    経済産業省「<a href="https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/" '
            f'target="_blank" rel="noopener noreferrer">石油備蓄の現況{EXTERNAL_NOTE}</a>」速報PDF\n'
            '    ／ データ時点 <span id="footer-as-of">—</span>\n'
            '    ／ 公表 <span id="footer-published">—</span>'
        ),
        footer_disclaimer=(
            "本サイトは経産省公表の速報（推計値）を可視化する非公式の情報サイトです。"
            "確報値とは差が生じる場合があります。トップの「現在値」は端末時刻に基づく秒按分の推計表示で、"
            "実数を秒単位で観測するものではありません。"
        ),
        root_path="./",
        nav={
            "home": "./",
            "tankers": "./tankers/",
            "scale": "./scale/",
            "about": "./about/",
        },
    ),
    Page(
        key="tankers",
        source="tankers.html",
        output="tankers/index.html",
        title="日本周辺のタンカー｜日本の石油備蓄",
        description="いま、日本周辺の海域に何隻のタンカーが航行中か。AIS データから集計した隻数のみを表示する非公式の可視化サイト。",
        canonical_path="/tankers/",
        og_title="日本周辺のタンカー｜日本の石油備蓄",
        og_description="AIS データから日本周辺のタンカー隻数を集計。aisstream.io 提供。",
        twitter_title="日本周辺のタンカー",
        twitter_description="AIS データから日本周辺のタンカー隻数を集計。",
        active_nav="tankers",
        extra_head=(
            '<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"\n'
            '      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="\n'
            '      crossorigin="anonymous">'
        ),
        script_tags=(
            '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"\n'
            '        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="\n'
            '        crossorigin="anonymous"></script>\n'
            '<script type="module" src="../js/pages/tankers.js"></script>'
        ),
        footer_source=(
            '<strong>データソース:</strong>\n'
            f'    <a href="https://aisstream.io/" target="_blank" rel="noopener noreferrer"><span lang="en">aisstream.io</span>{EXTERNAL_NOTE}</a>'
            '（<span lang="en">BETA</span>）の AIS リアルタイムストリーム'
        ),
        footer_disclaimer=(
            "本サイトは AIS データに基づく非公式の集計です。AIS は IMO 規定により公開放送される情報で、"
            "地図には個別船舶の名称・destination・位置を表示しています。実流入量は財務省貿易統計をご参照ください。"
        ),
        root_path="../",
        nav={
            "home": "../",
            "tankers": "./",
            "scale": "../scale/",
            "about": "../about/",
        },
    ),
    Page(
        key="scale",
        source="scale.html",
        output="scale/index.html",
        title="石油のものさし｜日本の石油備蓄",
        description="日本の石油備蓄を「N 日」だけでなく、kL・バレル・VLCC隻数・年間消費比に換算して提示する非公式の可視化サイト。",
        canonical_path="/scale/",
        og_title="石油のものさし｜日本の石油備蓄",
        og_description="備蓄日数を kL・バレル・VLCC隻数・年間消費比に換算して、肌感覚を補強します。",
        twitter_title="石油のものさし｜日本の石油備蓄",
        twitter_description="備蓄日数を kL・バレル・VLCC隻数・年間消費比に換算して、肌感覚を補強します。",
        active_nav="scale",
        script_tags='<script type="module" src="../js/pages/scale.js"></script>',
        footer_source=(
            '<strong>データ出典:</strong>\n'
            '    経済産業省「<a href="https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/" '
            f'target="_blank" rel="noopener noreferrer">石油備蓄の現況{EXTERNAL_NOTE}</a>」速報PDF\n'
            '    ／ 換算根拠: 経産省「資源・エネルギー統計」、IEA「<span lang="en">Oil Stocks of IEA Countries</span>」、JOGMEC 公開情報'
        ),
        footer_disclaimer=(
            "本ページの換算値は概算です。1 日あたり消費量・VLCC 積載量・年間消費量は公開統計の代表的な値を採用しており、"
            "実値とは数%程度の誤差が生じます。引用時は元データの出典に当たってください。"
        ),
        root_path="../",
        nav={
            "home": "../",
            "tankers": "../tankers/",
            "scale": "./",
            "about": "../about/",
        },
    ),
    Page(
        key="about",
        source="about.html",
        output="about/index.html",
        title="このサイトについて｜日本の石油備蓄",
        description="「あと何日？日本の石油備蓄」サイトの目的・データ出典・計算方法・運営会社の情報を 1 ページに集約しています。",
        canonical_path="/about/",
        og_title="このサイトについて｜日本の石油備蓄",
        og_description="サイトの目的・データ出典・計算方法・運営会社情報。",
        twitter_title="このサイトについて｜日本の石油備蓄",
        twitter_description="サイトの目的・データ出典・計算方法・運営会社情報。",
        active_nav="about",
        footer_source=(
            '<strong>主要データ出典:</strong>\n'
            '    経済産業省「<a href="https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/" '
            f'target="_blank" rel="noopener noreferrer">石油備蓄の現況{EXTERNAL_NOTE}</a>」速報 PDF\n'
            '    ／\n'
            f'    <a href="https://aisstream.io/" target="_blank" rel="noopener noreferrer"><span lang="en">aisstream.io</span>{EXTERNAL_NOTE}</a>'
            '（<span lang="en">BETA</span>）'
        ),
        footer_disclaimer="本サイトは経産省公表の速報（推計値）と AIS データを可視化する非公式の情報サイトです。確報値・実測値とは差が生じる場合があります。",
        root_path="../",
        nav={
            "home": "../",
            "tankers": "../tankers/",
            "scale": "../scale/",
            "about": "./",
        },
    ),
]


def render_nav(page: Page) -> str:
    labels = {
        "home": "カウンター",
        "tankers": "タンカー",
        "scale": "石油のものさし",
        "about": "about",
    }
    links = []
    for key in ("home", "tankers", "scale", "about"):
        classes = "tab tab--active" if key == page.active_nav else "tab"
        current = ' aria-current="page"' if key == page.active_nav else ""
        links.append(f'      <a class="{classes}" href="{page.nav[key]}"{current}>{labels[key]}</a>')
    return "\n".join(links)


def render_page(template: Template, page: Page) -> str:
    content = (PAGES_DIR / page.source).read_text(encoding="utf-8").strip()
    canonical = SITE_URL + page.canonical_path
    asset_root = "" if page.root_path == "./" else page.root_path
    favicon = asset_root + "assets/favicon.svg"
    stylesheet = asset_root + "assets/styles.css"
    extra_head = f"{page.extra_head}\n" if page.extra_head else ""
    script_tags = f"{page.script_tags}\n" if page.script_tags else ""
    return template.substitute(
        title=page.title,
        description=page.description,
        canonical=canonical,
        og_title=page.og_title,
        og_description=page.og_description,
        og_image=OG_IMAGE,
        og_image_alt=OG_IMAGE_ALT,
        twitter_title=page.twitter_title,
        twitter_description=page.twitter_description,
        favicon=favicon,
        font_href=FONT_HREF,
        extra_head=extra_head,
        stylesheet=stylesheet,
        home_href=page.root_path,
        nav=render_nav(page),
        content=content,
        footer_source=page.footer_source,
        footer_disclaimer=page.footer_disclaimer,
        script_tags=script_tags,
    )


def main() -> int:
    template = Template(BASE_TEMPLATE.read_text(encoding="utf-8"))
    for page in PAGES:
        output = ROOT / page.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_page(template, page), encoding="utf-8", newline="\n")
        print(f"built {page.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
