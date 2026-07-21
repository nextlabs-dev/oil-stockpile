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

import base64
import hashlib
import json
import re
from pathlib import Path
from string import Template
from typing import Any

from lib.constants import PEAK_DAYS, PEAK_SOURCE
from lib.io import read_json
from lib.paths import OG_IMAGE_PATH, REPO_ROOT, SITE_CONFIG_PATH, SNAPSHOTS_PATH, SRC_DIR
from lib.snapshots import Snapshot, format_jst_date, load_snapshots, pick_latest_snapshot

PAGES_DIR = SRC_DIR / "pages"
TEMPLATES_DIR = SRC_DIR / "templates"
BASE_TEMPLATE = TEMPLATES_DIR / "base.html"


def text_value(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(value)
    return value


def load_site_config() -> dict[str, Any]:
    return read_json(SITE_CONFIG_PATH)


def build_latest_vars(rows: list[dict]) -> dict[str, str]:
    """最新スナップショットから HTML 焼き込み用テンプレート変数を組み立てる（#93）。

    値は snapshots.json の公表値そのまま。実行時刻依存の値（compute_current_days）は
    使わない — test.yml の drift チェックがビルドの決定論性を前提にしているため。
    JS (counter.js) がロード後にリアルタイム推計値で上書きする。
    """
    latest = pick_latest_snapshot(rows)
    return {
        "latest_total_days": str(latest.total),
        "latest_published_dot": latest.published.replace("-", "."),
        "latest_asof_jp": format_jst_date(latest.as_of),
    }


def compute_og_image_version(path: Path) -> str:
    """og:image URL の cache-busting 用に og-image.png の SHA-256[:8] を返す。

    X は画像を URL 単位でキャッシュするため、画像内容が変わったらクエリも変わる
    ようにして再クロールを促す。必須アセット欠損時は FileNotFoundError で fail
    fast（クエリ無しで静かに継続して欠損を隠さない）。
    """
    if not path.exists():
        raise FileNotFoundError(f"required OGP asset not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


_DATA_JS_PATH = REPO_ROOT / "js" / "core" / "data.js"
_PEAK_REFERENCE_BLOCK_RE = re.compile(
    r"PEAK_REFERENCE\s*=\s*\{(?P<body>[^}]*)\}",
    re.DOTALL,
)
_PEAK_DAYS_FIELD_RE = re.compile(r"\bdays\s*:\s*(\d+)")
_PEAK_SOURCE_FIELD_RE = re.compile(r"\bsource\s*:\s*(['\"])(.*?)\1", re.DOTALL)


def _check_peak_reference_in_sync(
    data_js_text: str,
    expected_days: int,
    expected_source: str,
) -> None:
    """Raise if data.js text does not mirror src/constants.json's peak_reference.

    Both `days` and `source` are validated. Pure function over text — kept
    separate so tests can exercise the regex and comparison without filesystem
    fixtures.
    """
    block = _PEAK_REFERENCE_BLOCK_RE.search(data_js_text)
    if not block:
        raise RuntimeError("PEAK_REFERENCE block not found in js/core/data.js")
    body = block.group("body")

    days_match = _PEAK_DAYS_FIELD_RE.search(body)
    if not days_match:
        raise RuntimeError("PEAK_REFERENCE.days not found in js/core/data.js")
    js_days = int(days_match.group(1))
    if js_days != expected_days:
        raise RuntimeError(
            f"PEAK_REFERENCE.days drift: "
            f"src/constants.json={expected_days}, js/core/data.js={js_days}. "
            f"Update both files to keep them in sync."
        )

    source_match = _PEAK_SOURCE_FIELD_RE.search(body)
    if not source_match:
        raise RuntimeError("PEAK_REFERENCE.source not found in js/core/data.js")
    js_source = source_match.group(2)
    if js_source != expected_source:
        raise RuntimeError(
            "PEAK_REFERENCE.source drift: "
            f"src/constants.json={expected_source!r}, "
            f"js/core/data.js={js_source!r}. "
            "Update both files to keep them in sync."
        )


def verify_constants_in_sync() -> None:
    """Fail the build when js/core/data.js drifts from src/constants.json.

    The JS side cannot import the JSON SSOT directly (no build step), so it
    keeps a hand-mirrored copy of PEAK_REFERENCE. This check catches drift
    of both `days` and `source` before it ships.
    """
    _check_peak_reference_in_sync(
        _DATA_JS_PATH.read_text(encoding="utf-8"),
        PEAK_DAYS,
        PEAK_SOURCE,
    )


# 属性なしの <script>…</script>（gtag 初期化ブロック）だけにマッチする。
# gtag ローダ (<script async src=…>) や module script (src 付き) は対象外。
_INLINE_SCRIPT_RE = re.compile(r"<script>(?P<body>.*?)</script>", re.DOTALL)


def compute_inline_script_hashes(template_text: str) -> list[str]:
    """属性なしインライン <script> ごとに CSP の 'sha256-…' ソーストークンを返す。

    ハッシュはタグの「間」のバイト列（UTF-8）に対して取る。これは CSP の
    script-src ハッシュが一致を求める対象そのもの。base.html は LF 固定
    （.gitattributes eol=lf）かつ生成 HTML も LF で書き出すため、テンプレート
    から取ったハッシュが配信バイトと一致する。
    """
    hashes = []
    for match in _INLINE_SCRIPT_RE.finditer(template_text):
        digest = hashlib.sha256(match.group("body").encode("utf-8")).digest()
        hashes.append("sha256-" + base64.b64encode(digest).decode("ascii"))
    return hashes


def build_csp(template_text: str) -> str:
    """全ページ共通の Content-Security-Policy 値を組み立てる。

    インライン gtag ブロックのハッシュをテンプレートから算出して埋めるため、
    その script を変更してもポリシーが自動追従する（SSOT）。unpkg(Leaflet) と
    tile.openstreetmap は /tankers/ でしか使わないが、全ページで許可しても
    過剰許可は軽微で、単一の定義に保てる利点が勝る。

    GitHub Pages は HTTP ヘッダを設定できないため meta で配信する。meta では
    frame-ancestors / report-uri / sandbox は無効（クリックジャッキング対策は
    本層では提供できない）。
    """
    inline = " ".join(f"'{token}'" for token in compute_inline_script_hashes(template_text))
    script_src = "'self'"
    if inline:
        script_src += f" {inline}"
    script_src += " https://www.googletagmanager.com https://unpkg.com"
    directives = [
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        f"script-src {script_src}",
        "style-src 'self' https://fonts.googleapis.com https://unpkg.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https://tile.openstreetmap.org https://www.google-analytics.com",
        # /opinions/ の国会論戦 YouTube 埋め込み用（Cookie を落とさない nocookie ドメイン）。
        "frame-src https://www.youtube-nocookie.com",
        (
            "connect-src 'self' https://www.googletagmanager.com "
            "https://www.google-analytics.com https://*.google-analytics.com"
        ),
        "form-action 'self'",
    ]
    return "; ".join(directives)


# 提言(/opinions/)に埋め込む国会論戦動画。VideoObject(AEO)の出所。
# uploadDate は公開月までしか判明しないものは月精度(ISO8601)で正直に記載する。
OPINIONS_VIDEOS = [
    {
        "id": "SmgENrlR8XA",
        "name": "たまきチャンネル「ガソリン暫定税率 年内廃止へ・最後の攻防」",
        "description": (
            "国民民主党代表・玉木雄一郎が、ガソリン暫定税率の年内廃止に向けた"
            "国会での攻防を解説する動画。"
        ),
        "uploadDate": "2025-11",
    },
    {
        "id": "1xZVIlnYnpU",
        "name": "重徳和彦「ガソリン暫定税率年内廃止・財源 徹底解説」",
        "description": (
            "立憲民主党 税制調査会長・重徳和彦が、ガソリン暫定税率の廃止とその財源を解説する動画。"
        ),
        "uploadDate": "2025-11",
    },
    {
        "id": "hMKL-g4yNqk",
        "name": "伊佐進一 衆院財務金融委員会「インボイスの現場負担」",
        "description": (
            "伊佐進一が衆議院財務金融委員会でインボイス制度の現場負担を追及する国会質疑。"
        ),
        "uploadDate": "2026-03-04",
    },
]

# 提言の税用語辞典。DefinedTermSet(AEO)の出所。本文(opinions.html)と対応。
OPINIONS_GLOSSARY = [
    (
        "トリガー条項",
        "ガソリン小売価格が3ヶ月連続で160円/Lを超えた場合に、揮発油税の特例税率分"
        "（25.1円）を一時的に停止（減税）する仕組み。現在まで凍結が続いている。",
    ),
    (
        "暫定税率・特例税率",
        "道路整備予算の確保等のため「暫定」として上乗せ開始された揮発油税の割増分"
        "（リッター25.1円など）。一般財源化された現在も事実上の特例として課税が続く。",
    ),
    (
        "二重課税（タックスオンプライス）",
        "ガソリン本体価格に揮発油税や石油石炭税を上乗せした総和に、さらに10%の消費税"
        "を課す仕組み。減税派が是正を訴える論点。",
    ),
    (
        "インボイス制度",
        "消費税の適格請求書等保存方式。免税事業者からの仕入れが実質的な追加負担になり、"
        "フリーランスや零細事業者の負担が委員会等で追究されている。",
    ),
]


def build_opinions_nodes(current_url: str, org_id: str) -> list[dict[str, Any]]:
    """提言ページ固有の VideoObject×3 と DefinedTermSet を組み立てる（AEO）。"""
    nodes: list[dict[str, Any]] = []
    for v in OPINIONS_VIDEOS:
        nodes.append(
            {
                "@type": "VideoObject",
                "name": v["name"],
                "description": v["description"],
                "thumbnailUrl": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg",
                "uploadDate": v["uploadDate"],
                "embedUrl": f"https://www.youtube-nocookie.com/embed/{v['id']}",
                "contentUrl": f"https://www.youtube.com/watch?v={v['id']}",
                "inLanguage": "ja",
                "isPartOf": {"@id": f"{current_url}#webpage"},
            }
        )
    glossary_id = f"{current_url}#glossary"
    nodes.append(
        {
            "@type": "DefinedTermSet",
            "@id": glossary_id,
            "name": "税用語辞典",
            "inLanguage": "ja",
            "hasDefinedTerm": [
                {
                    "@type": "DefinedTerm",
                    "name": term,
                    "description": desc,
                    "inDefinedTermSet": {"@id": glossary_id},
                }
                for term, desc in OPINIONS_GLOSSARY
            ],
        }
    )
    return nodes


def build_structured_data(
    page: dict[str, Any],
    site: dict[str, Any],
    latest: Snapshot,
) -> str:
    """AEO 用の JSON-LD を組み立てる。

    トップは WebApplication + Dataset + FAQPage、それ以外のタブは本体グラフに
    接続した WebPage / AboutPage を出す。

    「石油 あと何日」のような事実系クエリで AI/検索に引用されるための施策。
    値は snapshots.json（SSOT）から取るため、日次の自動ビルドで自動的に新しくなる。

    ⚠ 生成物である index.html を直接編集しないこと。
       2026-07-10 に index.html へ直接書いた JSON-LD は、翌日の
       `data: auto-update` ビルドで丸ごと上書きされ、約10日間 AEO が無効化された。
       スキーマはこの関数（テンプレート側）が唯一の出所。
    """
    org_id = "https://nextlabs.jp/#organization"
    app_id = f"{site['url']}/#app"
    asof_jp = format_jst_date(latest.as_of)

    # home 以外のタブ（tankers / scale / about）も、本体エンティティグラフに
    # 接続した WebPage ノードを持たせて「権威の循環」を各ページに広げる（#柱3 AEO）。
    # about は運営会社を主題にする AboutPage として扱う。
    if page["key"] != "home":
        current_url = f"{site['url']}{page['canonical_path']}"
        page_id = f"{current_url}#webpage"
        is_about = page["key"] == "about"
        webpage: dict[str, Any] = {
            "@type": "AboutPage" if is_about else "WebPage",
            "@id": page_id,
            "url": current_url,
            "name": text_value(page["title"]),
            "description": text_value(page["description"]),
            "inLanguage": "ja",
            "isPartOf": {"@id": app_id},
            "publisher": {"@id": org_id},
            "breadcrumb": {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": 1,
                        "name": "あと何日？日本の石油備蓄",
                        "item": site["url"] + "/",
                    },
                    {
                        "@type": "ListItem",
                        "position": 2,
                        "name": text_value(page["title"]),
                        "item": current_url,
                    },
                ],
            },
        }
        if is_about:
            webpage["mainEntity"] = {"@id": org_id}
        nodes: list[dict[str, Any]] = [webpage]
        # 提言は国会動画(VideoObject)と税用語辞典(DefinedTermSet)を追加してAEOを厚くする。
        if page["key"] == "opinions":
            nodes.extend(build_opinions_nodes(current_url, org_id))
        payload = {"@context": "https://schema.org", "@graph": nodes}
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        return f'<script type="application/ld+json">\n{body}\n</script>\n'

    graph = [
        {
            "@type": "WebApplication",
            "@id": app_id,
            "name": "あと何日？日本の石油備蓄",
            "url": site["url"] + "/",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "All",
            "browserRequirements": "JavaScript を有効にしてください",
            "inLanguage": "ja",
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "JPY"},
            "publisher": {"@id": org_id},
        },
        {
            "@type": "Dataset",
            "@id": f"{site['url']}/#dataset",
            "name": "日本の石油備蓄 推計日数",
            "description": (
                "経済産業省「石油備蓄の現況」速報値をもとに、日本の石油備蓄が"
                "あと何日分あるかを推計したデータセット。国家備蓄・民間備蓄・"
                "産油国共同備蓄の内訳を含む。"
            ),
            "url": site["url"] + "/",
            "inLanguage": "ja",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "isAccessibleForFree": True,
            "creator": {"@id": org_id},
            "publisher": {"@id": org_id},
            "spatialCoverage": {"@type": "Place", "name": "日本"},
            "sourceOrganization": {"@type": "GovernmentOrganization", "name": "経済産業省"},
            "citation": "経済産業省「石油備蓄の現況」",
            "measurementTechnique": "備蓄量 ÷ 1日あたり推定消費量",
            "temporalCoverage": latest.as_of,
            "dateModified": latest.published,
            "variableMeasured": [
                {
                    "@type": "PropertyValue",
                    "name": "合計備蓄日数",
                    "value": latest.total,
                    "unitText": "日分",
                },
                {
                    "@type": "PropertyValue",
                    "name": "国家備蓄",
                    "value": latest.national,
                    "unitText": "日分",
                },
                {
                    "@type": "PropertyValue",
                    "name": "民間備蓄",
                    "value": latest.private_,
                    "unitText": "日分",
                },
                {
                    "@type": "PropertyValue",
                    "name": "産油国共同備蓄",
                    "value": latest.joint,
                    "unitText": "日分",
                },
            ],
        },
        {
            "@type": "FAQPage",
            "@id": f"{site['url']}/#faq",
            "inLanguage": "ja",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "日本の石油備蓄はあと何日分ありますか？",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            f"経済産業省の最新公表値（{asof_jp}集計時点）で、"
                            f"合計約{latest.total}日分です。内訳は国家備蓄"
                            f"{latest.national}日分、民間備蓄{latest.private_}日分、"
                            f"産油国共同備蓄{latest.joint}日分です。"
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": "備蓄日数はどのように計算していますか？",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            "備蓄量を1日あたりの推定消費量で割って算出しています。"
                            "経済産業省が公表した最新データの集計日を起点に、"
                            "1日経過するごとに1日分減る計算で表示しており、"
                            "備蓄量を実測しているわけではありません。"
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": "データの出典はどこですか？",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            "経済産業省が日次で公表する「石油備蓄の現況」速報値です。"
                            "本サイトはその速報値を可視化した非公式サイトで、"
                            "正確性・完全性を保証するものではありません。"
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": "日本の石油備蓄の義務量はどれくらいですか？",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            "日本はIEA（国際エネルギー機関）の基準により、"
                            "90日分の石油備蓄義務を負っています。"
                            "日本は石油の約97%を輸入に依存しています。"
                        ),
                    },
                },
                {
                    "@type": "Question",
                    "name": "このサイトは公式サイトですか？",
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": (
                            "いいえ。株式会社ネクストラボが運営する非公式の情報サイトです。"
                            "経済産業省をはじめとする公的機関とは関係ありません。"
                        ),
                    },
                },
            ],
        },
    ]

    payload = {"@context": "https://schema.org", "@graph": graph}
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{body}\n</script>\n'


def render_nav(page: dict[str, Any], nav_labels: dict[str, str], nav_order: list[str]) -> str:
    links = []
    for key in nav_order:
        classes = "tab tab--active" if key == page["active_nav"] else "tab"
        current = ' aria-current="page"' if key == page["active_nav"] else ""
        links.append(
            f'      <a class="{classes}" href="{page["nav"][key]}"{current}>{nav_labels[key]}</a>'
        )
    return "\n".join(links)


# ボトムナビ用 線画アイコン（22px 表示・stroke 1.8）。ラベル併記のため装飾扱いで
# aria-hidden。キーは site.json の nav_order と一致させる。
# 4 つのグリフは光学的に揃うよう、描画範囲の中心を y≈12.5–12.75 に統一し、
# viewBox 24×24 のうち幅 17–19 / 十分な高さを使う（小さすぎると欠けて見える）。
NAV_ICONS = {
    "home": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M5.6 20.4A9 9 0 1 1 18.4 20.4"/>'
        '<line x1="12" y1="14" x2="16.2" y2="9.8"/></svg>'
    ),
    "tankers": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M2.5 13h19l-3 4.5h-13z"/><path d="M14.5 13v-5h4.5v5"/>'
        '<path d="M5.5 13v-3h6v3"/></svg>'
    ),
    "scale": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="2.5" y="9" width="19" height="7" rx="1"/>'
        '<path d="M7.25 9v3.5M12 9v3.5M16.75 9v3.5"/></svg>'
    ),
    "opinions": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 5.5h16v10H12l-4 3.5v-3.5H4z"/>'
        '<path d="M8 9h8M8 12h5"/></svg>'
    ),
    "about": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12.5" r="8.5"/><line x1="12" y1="12.2" x2="12" y2="16.7"/>'
        '<circle cx="12" cy="8.7" r="0.4" fill="currentColor"/></svg>'
    ),
}


def render_bottom_nav(
    page: dict[str, Any],
    nav_labels_short: dict[str, str],
    nav_order: list[str],
) -> str:
    links = []
    for key in nav_order:
        active = key == page["active_nav"]
        classes = "bottom-nav-item bottom-nav-item--active" if active else "bottom-nav-item"
        current = ' aria-current="page"' if active else ""
        links.append(
            f'  <a class="{classes}" href="{page["nav"][key]}"{current}>'
            f"{NAV_ICONS[key]}<span>{nav_labels_short[key]}</span></a>"
        )
    return "\n".join(links)


def render_page(
    template: Template,
    site_config: dict[str, Any],
    page: dict[str, Any],
    content: str,
    og_image_version: str = "",
    csp: str = "",
    latest_vars: dict[str, str] | None = None,
    latest: Snapshot | None = None,
) -> str:
    site = site_config["site"]
    # 最新値の焼き込みは content / description / header_meta の 3 フィールド限定
    # （og/twitter description は X カードキャッシュ churn を避けるため静的維持）。
    # strict substitute: 未定義プレースホルダ・生の $ はビルドを即失敗させる。
    # latest_vars 未指定でも空 dict で置換を走らせ、置き忘れを KeyError で検知する。
    subs = latest_vars or {}
    content = Template(content).substitute(subs)
    description = Template(page["description"]).substitute(subs)
    header_meta_value = Template(text_value(page.get("header_meta"))).substitute(subs)
    canonical = site["url"] + page["canonical_path"]
    # og:url は canonical + ?v=<og画像ハッシュ> (issue #90)。X のカードキャッシュは
    # 共有URL単位のため、クエリ無し og:url があると versioned 共有URLが canonical へ
    # 正規化され古いカードが使い回されうる。<link rel="canonical"> は SEO のため
    # クリーンなまま維持する。
    og_url = f"{canonical}?v={og_image_version}" if og_image_version else canonical
    # ページ固有 OG 画像があれば使う（提言など）。無ければサイト共通のカウンター画像。
    # 固有画像はライブ数値に依存しない静的アセットなので ?v= バージョンは付けない。
    page_og_image = page.get("og_image")
    if page_og_image:
        og_image = page_og_image
        og_image_alt = page.get("og_image_alt", site["og_image_alt"])
    else:
        og_image = site["og_image"]
        og_image_alt = site["og_image_alt"]
        if og_image_version:
            og_image += f"?v={og_image_version}"
    asset_root = "" if page["root_path"] == "./" else page["root_path"]
    favicon = asset_root + "assets/favicon.svg"
    stylesheet = asset_root + "assets/styles.css"
    extra_head_value = text_value(page.get("extra_head"))
    script_tags_value = text_value(page.get("script_tags"))
    extra_head = f"{extra_head_value}\n" if extra_head_value else ""
    script_tags = f"{script_tags_value}\n" if script_tags_value else ""
    default_site_brand = '      <h1 class="site-title">あと何日？日本の石油備蓄</h1>'
    site_brand = text_value(page.get("site_brand")) or default_site_brand
    header_meta = f"{header_meta_value}\n" if header_meta_value else ""
    return template.substitute(
        csp=csp,
        title=page["title"],
        description=description,
        canonical=canonical,
        og_url=og_url,
        og_title=page["og_title"],
        og_description=page["og_description"],
        og_image=og_image,
        og_image_alt=og_image_alt,
        twitter_title=page["twitter_title"],
        twitter_description=page["twitter_description"],
        favicon=favicon,
        font_href=site["font_href"],
        extra_head=extra_head,
        stylesheet=stylesheet,
        body_class=page.get("body_class", ""),
        home_href=page["root_path"],
        site_brand=site_brand,
        header_meta=header_meta,
        nav=render_nav(page, site_config["nav_labels"], site_config["nav_order"]),
        bottom_nav=render_bottom_nav(
            page, site_config["nav_labels_short"], site_config["nav_order"]
        ),
        content=content,
        script_tags=script_tags,
        structured_data=(build_structured_data(page, site, latest) if latest else ""),
    )


def main() -> int:
    verify_constants_in_sync()
    site_config = load_site_config()
    base_text = BASE_TEMPLATE.read_text(encoding="utf-8")
    template = Template(base_text)
    csp = build_csp(base_text)
    og_image_version = compute_og_image_version(OG_IMAGE_PATH)
    snapshot_rows = load_snapshots(SNAPSHOTS_PATH)
    latest_vars = build_latest_vars(snapshot_rows)
    latest = pick_latest_snapshot(snapshot_rows)
    for page in site_config["pages"]:
        output = REPO_ROOT / page["output"]
        content = (PAGES_DIR / page["source"]).read_text(encoding="utf-8").strip()
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered = render_page(
            template, site_config, page, content, og_image_version, csp, latest_vars, latest
        )
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"built {page['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
