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
import re
from pathlib import Path
from string import Template
from typing import Any

from lib.constants import PEAK_DAYS, PEAK_SOURCE
from lib.io import read_json
from lib.paths import OG_IMAGE_PATH, REPO_ROOT, SITE_CONFIG_PATH, SRC_DIR

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
        (
            "connect-src 'self' https://www.googletagmanager.com "
            "https://www.google-analytics.com https://*.google-analytics.com"
        ),
        "form-action 'self'",
    ]
    return "; ".join(directives)


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
NAV_ICONS = {
    "home": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M4 17a8 8 0 1 1 16 0"/><line x1="12" y1="17" x2="16" y2="11"/></svg>'
    ),
    "tankers": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<path d="M2 15h20l-3 4H5z"/><path d="M15 15v-4h4v4"/><path d="M6 15v-2h6v2"/></svg>'
    ),
    "scale": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<rect x="3" y="9" width="18" height="6" rx="1"/>'
        '<path d="M7.5 9v3M12 9v3M16.5 9v3"/></svg>'
    ),
    "about": (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        '<circle cx="12" cy="12" r="9"/><line x1="12" y1="11" x2="12" y2="16.5"/>'
        '<circle cx="12" cy="7.8" r="0.4" fill="currentColor"/></svg>'
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
) -> str:
    site = site_config["site"]
    canonical = site["url"] + page["canonical_path"]
    og_image = site["og_image"]
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
    header_meta_value = text_value(page.get("header_meta"))
    header_meta = f"{header_meta_value}\n" if header_meta_value else ""
    return template.substitute(
        csp=csp,
        title=page["title"],
        description=page["description"],
        canonical=canonical,
        og_title=page["og_title"],
        og_description=page["og_description"],
        og_image=og_image,
        og_image_alt=site["og_image_alt"],
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
    )


def main() -> int:
    verify_constants_in_sync()
    site_config = load_site_config()
    base_text = BASE_TEMPLATE.read_text(encoding="utf-8")
    template = Template(base_text)
    csp = build_csp(base_text)
    og_image_version = compute_og_image_version(OG_IMAGE_PATH)
    for page in site_config["pages"]:
        output = REPO_ROOT / page["output"]
        content = (PAGES_DIR / page["source"]).read_text(encoding="utf-8").strip()
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered = render_page(template, site_config, page, content, og_image_version, csp)
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"built {page['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
