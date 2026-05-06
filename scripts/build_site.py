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

import re
from string import Template
from typing import Any

from lib.constants import PEAK_DAYS
from lib.io import read_json
from lib.paths import REPO_ROOT, SITE_CONFIG_PATH, SRC_DIR

PAGES_DIR = SRC_DIR / "pages"
TEMPLATES_DIR = SRC_DIR / "templates"
BASE_TEMPLATE = TEMPLATES_DIR / "base.html"


EXTERNAL_NOTE = '<span class="visually-hidden">（外部サイト・別タブで開きます）</span>'


def expand_tokens(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace("{{ external_note }}", EXTERNAL_NOTE)
    if isinstance(value, list):
        return [expand_tokens(item) for item in value]
    if isinstance(value, dict):
        return {key: expand_tokens(item) for key, item in value.items()}
    return value


def text_value(value: str | list[str] | None) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(value)
    return value


def load_site_config() -> dict[str, Any]:
    return expand_tokens(read_json(SITE_CONFIG_PATH))


_DATA_JS_PATH = REPO_ROOT / "js" / "core" / "data.js"
_PEAK_DAYS_RE = re.compile(
    r"PEAK_REFERENCE\s*=\s*\{[^}]*?\bdays\s*:\s*(\d+)",
    re.DOTALL,
)


def _check_peak_days_in_sync(data_js_text: str, expected: int) -> None:
    """Raise if data.js text does not mirror the expected PEAK_REFERENCE.days.

    Pure function over text — kept separate so tests can exercise the regex
    and comparison without filesystem fixtures.
    """
    match = _PEAK_DAYS_RE.search(data_js_text)
    if not match:
        raise RuntimeError(
            "PEAK_REFERENCE.days not found in js/core/data.js"
        )
    js_days = int(match.group(1))
    if js_days != expected:
        raise RuntimeError(
            f"PEAK_REFERENCE.days drift: "
            f"src/constants.json={expected}, js/core/data.js={js_days}. "
            f"Update both files to keep them in sync."
        )


def verify_constants_in_sync() -> None:
    """Fail the build when js/core/data.js drifts from src/constants.json.

    The JS side cannot import the JSON SSOT directly (no build step), so it
    keeps a hand-mirrored copy of PEAK_REFERENCE.days. This check catches
    drift before it ships.
    """
    _check_peak_days_in_sync(
        _DATA_JS_PATH.read_text(encoding="utf-8"),
        PEAK_DAYS,
    )


def render_nav(page: dict[str, Any], nav_labels: dict[str, str], nav_order: list[str]) -> str:
    links = []
    for key in nav_order:
        classes = "tab tab--active" if key == page["active_nav"] else "tab"
        current = ' aria-current="page"' if key == page["active_nav"] else ""
        links.append(f'      <a class="{classes}" href="{page["nav"][key]}"{current}>{nav_labels[key]}</a>')
    return "\n".join(links)


def render_page(template: Template, site_config: dict[str, Any], page: dict[str, Any]) -> str:
    site = site_config["site"]
    content = (PAGES_DIR / page["source"]).read_text(encoding="utf-8").strip()
    canonical = site["url"] + page["canonical_path"]
    asset_root = "" if page["root_path"] == "./" else page["root_path"]
    favicon = asset_root + "assets/favicon.svg"
    stylesheet = asset_root + "assets/styles.css"
    extra_head_value = text_value(page.get("extra_head"))
    script_tags_value = text_value(page.get("script_tags"))
    extra_head = f"{extra_head_value}\n" if extra_head_value else ""
    script_tags = f"{script_tags_value}\n" if script_tags_value else ""
    return template.substitute(
        title=page["title"],
        description=page["description"],
        canonical=canonical,
        og_title=page["og_title"],
        og_description=page["og_description"],
        og_image=site["og_image"],
        og_image_alt=site["og_image_alt"],
        twitter_title=page["twitter_title"],
        twitter_description=page["twitter_description"],
        favicon=favicon,
        font_href=site["font_href"],
        extra_head=extra_head,
        stylesheet=stylesheet,
        home_href=page["root_path"],
        nav=render_nav(page, site_config["nav_labels"], site_config["nav_order"]),
        content=content,
        footer_source=text_value(page.get("footer_source")),
        footer_disclaimer=text_value(page.get("footer_disclaimer")),
        script_tags=script_tags,
    )


def main() -> int:
    verify_constants_in_sync()
    site_config = load_site_config()
    template = Template(BASE_TEMPLATE.read_text(encoding="utf-8"))
    for page in site_config["pages"]:
        output = REPO_ROOT / page["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_page(template, site_config, page), encoding="utf-8", newline="\n")
        print(f"built {page['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
