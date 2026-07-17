"""Unit tests for scripts/build_site.py.

Run from project root:
    python -m unittest discover -s scripts -p 'test_*.py'

I/O から切り離した純粋関数 (text_value / render_nav /
render_page / _check_peak_reference_in_sync) をカバーする。
"""

import base64
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_site import (  # noqa: E402
    _check_peak_reference_in_sync,
    build_csp,
    build_latest_vars,
    compute_inline_script_hashes,
    compute_og_image_version,
    render_bottom_nav,
    render_nav,
    render_page,
    text_value,
)


def _sha256_token(body: str) -> str:
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    return "sha256-" + base64.b64encode(digest).decode("ascii")


SAMPLE_SOURCE = "経産省「石油備蓄の現況」過去公表値の高水準（2025年3月末ごろ）"
SAMPLE_DATA_JS = f"""\
export const PEAK_REFERENCE = {{
  days: 247,
  source: '{SAMPLE_SOURCE}',
}};
"""


class CheckPeakReferenceInSyncTest(unittest.TestCase):
    def test_matches_returns_none(self):
        # 一致すれば例外を投げない
        self.assertIsNone(_check_peak_reference_in_sync(SAMPLE_DATA_JS, 247, SAMPLE_SOURCE))

    def test_days_mismatch_message_contains_both_values(self):
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_reference_in_sync(SAMPLE_DATA_JS, 250, SAMPLE_SOURCE)
        msg = str(cm.exception)
        self.assertIn("247", msg)
        self.assertIn("250", msg)
        self.assertIn("days", msg)
        self.assertIn("drift", msg)

    def test_source_mismatch_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_reference_in_sync(SAMPLE_DATA_JS, 247, "別の出典")
        msg = str(cm.exception)
        self.assertIn("source", msg)
        self.assertIn("drift", msg)

    def test_block_not_found_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_reference_in_sync("// no peak reference here\n", 247, SAMPLE_SOURCE)
        self.assertIn("not found", str(cm.exception))

    def test_days_field_missing_inside_block_raises(self):
        text = "export const PEAK_REFERENCE = { source: 'x' };"
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_reference_in_sync(text, 247, "x")
        self.assertIn("days", str(cm.exception))

    def test_source_field_missing_inside_block_raises(self):
        text = "export const PEAK_REFERENCE = { days: 247 };"
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE)
        self.assertIn("source", str(cm.exception))

    def test_tolerates_whitespace_variants(self):
        # JS フォーマッタの整形違いに耐えること
        text = (
            "export const PEAK_REFERENCE  =  {\n"
            "  days  :  247  ,\n"
            f"  source  :  '{SAMPLE_SOURCE}'  ,\n"
            "};"
        )
        self.assertIsNone(_check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE))

    def test_picks_fields_inside_peak_reference_block(self):
        # PEAK_REFERENCE 以外のブロックに紛れた days は拾わないこと
        text = f"""
        export const OTHER = {{ days: 999, source: 'other' }};
        export const PEAK_REFERENCE = {{
          days: 247,
          source: '{SAMPLE_SOURCE}',
        }};
        """
        self.assertIsNone(_check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE))

    def test_supports_double_quoted_source(self):
        text = f'export const PEAK_REFERENCE = {{\n  days: 247,\n  source: "{SAMPLE_SOURCE}",\n}};'
        self.assertIsNone(_check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE))


class TextValueTest(unittest.TestCase):
    def test_none_returns_empty_string(self):
        self.assertEqual(text_value(None), "")

    def test_string_returns_as_is(self):
        self.assertEqual(text_value("hello"), "hello")

    def test_list_joined_with_newlines(self):
        self.assertEqual(text_value(["a", "b", "c"]), "a\nb\nc")


class RenderNavTest(unittest.TestCase):
    NAV_LABELS = {"home": "ホーム", "about": "About"}
    NAV_ORDER = ["home", "about"]

    def _page(self, active: str) -> dict:
        return {
            "active_nav": active,
            "nav": {"home": "./", "about": "./about/"},
        }

    def test_active_nav_has_aria_current_and_active_class(self):
        out = render_nav(self._page("home"), self.NAV_LABELS, self.NAV_ORDER)
        self.assertIn('class="tab tab--active"', out)
        self.assertIn('aria-current="page"', out)
        self.assertIn(">ホーム<", out)

    def test_inactive_nav_has_no_aria_current(self):
        out = render_nav(self._page("home"), self.NAV_LABELS, self.NAV_ORDER)
        # About リンクは active ではない: tab だけ、aria-current なし
        about_line = next(line for line in out.splitlines() if "About" in line)
        self.assertIn('class="tab"', about_line)
        self.assertNotIn("aria-current", about_line)

    def test_links_emitted_in_nav_order(self):
        out = render_nav(self._page("home"), self.NAV_LABELS, self.NAV_ORDER)
        self.assertLess(out.index("ホーム"), out.index("About"))


class RenderBottomNavTest(unittest.TestCase):
    NAV_LABELS_SHORT = {"home": "カウンター", "about": "about"}
    NAV_ORDER = ["home", "about"]

    def _page(self, active: str) -> dict:
        return {
            "active_nav": active,
            "nav": {"home": "./", "about": "./about/"},
        }

    def test_active_item_has_active_class_and_aria_current(self):
        out = render_bottom_nav(self._page("home"), self.NAV_LABELS_SHORT, self.NAV_ORDER)
        home_line = next(line for line in out.splitlines() if "カウンター" in line)
        self.assertIn('class="bottom-nav-item bottom-nav-item--active"', home_line)
        self.assertIn('aria-current="page"', home_line)
        self.assertIn('href="./"', home_line)

    def test_inactive_item_has_no_aria_current(self):
        out = render_bottom_nav(self._page("home"), self.NAV_LABELS_SHORT, self.NAV_ORDER)
        about_line = next(line for line in out.splitlines() if "about" in line)
        self.assertIn('class="bottom-nav-item"', about_line)
        self.assertNotIn("aria-current", about_line)
        self.assertIn('href="./about/"', about_line)

    def test_labels_come_from_nav_labels_short(self):
        # ボトムバー専用の短縮ラベル辞書を使うこと（nav_labels ではない）
        short = {"home": "短い", "about": "about"}
        out = render_bottom_nav(self._page("home"), short, self.NAV_ORDER)
        self.assertIn("<span>短い</span>", out)

    def test_links_emitted_in_nav_order(self):
        out = render_bottom_nav(self._page("home"), self.NAV_LABELS_SHORT, self.NAV_ORDER)
        self.assertLess(out.index("カウンター"), out.index("about"))

    def test_each_item_has_aria_hidden_icon_svg(self):
        out = render_bottom_nav(self._page("home"), self.NAV_LABELS_SHORT, self.NAV_ORDER)
        for line in out.splitlines():
            self.assertIn("<svg", line)
            self.assertIn('aria-hidden="true"', line)


class RenderPageTest(unittest.TestCase):
    """最小テンプレで render_page の組み立てを検証する。"""

    TEMPLATE = Template(
        "T=$title|D=$description|C=$canonical|OG_URL=$og_url|"
        "OG_IMG=$og_image|FAVI=$favicon|CSS=$stylesheet|"
        "FONT=$font_href|EXTRA=[$extra_head]|BODY_CLASS=[$body_class]|HOME=$home_href|"
        "NAV=[$nav]|BOTTOM=[$bottom_nav]|HM=[$header_meta]BODY=$content|"
        "SCRIPTS=[$script_tags]|"
        "OG_TITLE=$og_title|OG_DESC=$og_description|"
        "TW_TITLE=$twitter_title|TW_DESC=$twitter_description|"
        "OG_ALT=$og_image_alt"
    )

    SITE_CONFIG = {
        "site": {
            "url": "https://example.com",
            "og_image": "https://example.com/og.png",
            "og_image_alt": "alt",
            "font_href": "https://fonts.example.com/css",
        },
        "nav_order": ["home", "about"],
        "nav_labels": {"home": "ホーム", "about": "About"},
        "nav_labels_short": {"home": "カウンター", "about": "About"},
    }

    def _page(self, **overrides) -> dict:
        page = {
            "title": "T",
            "description": "D",
            "canonical_path": "/scale/",
            "og_title": "OT",
            "og_description": "OD",
            "twitter_title": "TT",
            "twitter_description": "TD",
            "active_nav": "home",
            "root_path": "../",
            "nav": {"home": "../", "about": "../about/"},
        }
        page.update(overrides)
        return page

    def test_canonical_concatenates_url_and_path(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("C=https://example.com/scale/", out)

    def test_root_path_dot_slash_yields_empty_asset_root(self):
        # root_path="./" のページ (home) では favicon/css が "assets/..." (前置なし)
        page = self._page(root_path="./", canonical_path="/")
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, page, "BODY")
        self.assertIn("FAVI=assets/favicon.svg|", out)
        self.assertIn("CSS=assets/styles.css|", out)

    def test_subpage_root_path_prepends_to_assets(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("FAVI=../assets/favicon.svg|", out)
        self.assertIn("CSS=../assets/styles.css|", out)

    def test_extra_head_empty_when_missing(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("EXTRA=[]|", out)

    def test_extra_head_appends_newline_when_present(self):
        page = self._page(extra_head=['<link rel="x" href="y">'])
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, page, "BODY")
        self.assertIn('EXTRA=[<link rel="x" href="y">\n]|', out)

    def test_content_passed_through_unchanged(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "<p>X</p>")
        self.assertIn("BODY=<p>X</p>|", out)

    def test_nav_renders_inside_template(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn('aria-current="page"', out)
        self.assertIn("ホーム", out)
        self.assertIn("About", out)

    def test_bottom_nav_renders_inside_template(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn('class="bottom-nav-item bottom-nav-item--active"', out)
        self.assertIn("<span>カウンター</span>", out)

    def test_body_class_empty_when_missing(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("BODY_CLASS=[]|", out)

    def test_body_class_passes_through_when_set(self):
        page = self._page(body_class="page-home")
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, page, "BODY")
        self.assertIn("BODY_CLASS=[page-home]|", out)

    def test_og_image_version_appended_as_query(self):
        # cache-busting: ハッシュが渡されると og:image / twitter:image (同一変数) に
        # ?v=<hash> が付く。
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            self._page(),
            "BODY",
            og_image_version="abc12345",
        )
        self.assertIn("OG_IMG=https://example.com/og.png?v=abc12345|", out)

    def test_og_image_no_query_when_version_empty(self):
        # 省略時 (デフォルト空) はクエリを付けない。
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("OG_IMG=https://example.com/og.png|", out)

    def test_og_url_appends_version_query(self):
        # X のカードキャッシュは共有URL単位。og:url に og:image と同じ ?v=<hash> を
        # 付け、画像更新のたびに共有URLも変えて再クロールさせる (issue #90)。
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            self._page(),
            "BODY",
            og_image_version="abc12345",
        )
        self.assertIn("OG_URL=https://example.com/scale/?v=abc12345|", out)
        # og:image と同一ハッシュ (ビルド全体で version は 1 つ)
        self.assertIn("OG_IMG=https://example.com/og.png?v=abc12345|", out)

    def test_og_url_no_query_when_version_empty(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("OG_URL=https://example.com/scale/|", out)

    def test_canonical_stays_clean_when_version_present(self):
        # <link rel="canonical"> は SEO のためクエリ無しのまま維持する。
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            self._page(),
            "BODY",
            og_image_version="abc12345",
        )
        self.assertIn("C=https://example.com/scale/|", out)


class ComputeInlineScriptHashesTest(unittest.TestCase):
    """インライン <script> の CSP ハッシュ算出を検証する。"""

    def test_hash_is_sha256_of_body_between_tags(self):
        # ハッシュは <script> と </script> の「間」のバイト列に対して取る
        # （CSP の script-src ハッシュが一致すべき対象）。
        body = "\n  gtag('config', 'G-XYZ');\n"
        html = f"<script>{body}</script>"
        self.assertEqual(compute_inline_script_hashes(html), [_sha256_token(body)])

    def test_skips_scripts_with_src(self):
        # gtag ローダや module script は src を持つので対象外。
        html = (
            '<script async src="https://x/gtag.js"></script>\n'
            "<script>INNER</script>\n"
            '<script type="module" src="../js/app.js"></script>'
        )
        self.assertEqual(compute_inline_script_hashes(html), [_sha256_token("INNER")])

    def test_returns_one_token_per_inline_script(self):
        html = "<script>A</script>\n<script>B</script>"
        self.assertEqual(
            compute_inline_script_hashes(html),
            [_sha256_token("A"), _sha256_token("B")],
        )

    def test_no_inline_scripts_returns_empty(self):
        self.assertEqual(compute_inline_script_hashes("<p>no script</p>"), [])


class BuildCspTest(unittest.TestCase):
    """build_csp が生成する Content-Security-Policy 値を検証する。"""

    GTAG_BODY = "\n  window.dataLayer = window.dataLayer || [];\n"
    TEMPLATE_TEXT = (
        '<script async src="https://www.googletagmanager.com/gtag/js?id=G-X"></script>\n'
        f"<script>{GTAG_BODY}</script>"
    )

    def setUp(self):
        self.csp = build_csp(self.TEMPLATE_TEXT)
        self.directives = {
            d.split(" ", 1)[0]: d.split(" ", 1)[1]
            for d in (part.strip() for part in self.csp.split(";"))
            if d
        }

    def test_script_src_contains_inline_hash(self):
        # インライン gtag ブロックのハッシュが script-src に入る。
        self.assertIn(f"'{_sha256_token(self.GTAG_BODY)}'", self.directives["script-src"])

    def test_script_src_has_no_unsafe_inline(self):
        # Issue の主目的: 任意インライン script を許さない。
        self.assertNotIn("unsafe-inline", self.directives["script-src"])

    def test_script_src_allows_known_origins(self):
        script_src = self.directives["script-src"]
        self.assertIn("'self'", script_src)
        self.assertIn("https://www.googletagmanager.com", script_src)
        self.assertIn("https://unpkg.com", script_src)

    def test_default_src_is_self(self):
        self.assertEqual(self.directives["default-src"], "'self'")

    def test_connect_src_allows_google_analytics_beacons(self):
        connect_src = self.directives["connect-src"]
        self.assertIn("'self'", connect_src)
        self.assertIn("https://www.google-analytics.com", connect_src)
        self.assertIn("https://*.google-analytics.com", connect_src)

    def test_img_src_allows_tiles_and_data(self):
        img_src = self.directives["img-src"]
        self.assertIn("https://tile.openstreetmap.org", img_src)
        self.assertIn("data:", img_src)

    def test_font_and_style_allow_google_fonts(self):
        self.assertIn("https://fonts.gstatic.com", self.directives["font-src"])
        self.assertIn("https://fonts.googleapis.com", self.directives["style-src"])

    def test_hardening_directives_present(self):
        self.assertEqual(self.directives["object-src"], "'none'")
        self.assertEqual(self.directives["base-uri"], "'self'")


class ComputeOgImageVersionTest(unittest.TestCase):
    """compute_og_image_version の SHA-256[:8] 算出と fail-fast を検証する。"""

    def test_returns_sha256_first8_of_contents(self):
        payload = b"fake png bytes"
        expected = hashlib.sha256(payload).hexdigest()[:8]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "og-image.png"
            path.write_bytes(payload)
            self.assertEqual(compute_og_image_version(path), expected)

    def test_version_changes_when_contents_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "og-image.png"
            path.write_bytes(b"version one")
            first = compute_og_image_version(path)
            path.write_bytes(b"version two")
            second = compute_og_image_version(path)
        self.assertNotEqual(first, second)

    def test_raises_when_asset_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "og-image.png"
            with self.assertRaises(FileNotFoundError):
                compute_og_image_version(missing)


class BuildLatestVarsTest(unittest.TestCase):
    # asOf 昇順で末尾が最新になることを確かめるため、意図的に順序を崩してある
    ROWS = [
        {
            "published": "2026-03-18",
            "asOf": "2026-03-15",
            "total": 241,
            "national": 146,
            "private": 89,
            "joint": 6,
        },
        {
            "published": "2026-03-17",
            "asOf": "2026-03-14",
            "total": 242,
            "national": 146,
            "private": 90,
            "joint": 6,
        },
    ]

    def test_picks_latest_by_asof_and_formats(self):
        self.assertEqual(
            build_latest_vars(self.ROWS),
            {
                "latest_total_days": "241",
                "latest_published_dot": "2026.03.18",
                "latest_asof_jp": "2026年3月15日",
            },
        )

    def test_empty_rows_raise_value_error(self):
        with self.assertRaises(ValueError):
            build_latest_vars([])


class RenderPageLatestVarsTest(unittest.TestCase):
    """render_page の latest_vars 置換（Issue #93）。

    置換対象は content / description / header_meta の 3 フィールドのみ。
    strict substitute なので未定義プレースホルダ・生の $ はビルドを落とす。
    """

    TEMPLATE = RenderPageTest.TEMPLATE
    SITE_CONFIG = RenderPageTest.SITE_CONFIG
    LATEST_VARS = {
        "latest_total_days": "242",
        "latest_published_dot": "2026.03.17",
        "latest_asof_jp": "2026年3月14日",
    }

    def _page(self, **overrides) -> dict:
        # RenderPageTest._page と同内容（TestCase インスタンス跨ぎの共有を避けて複製）
        page = {
            "title": "T",
            "description": "D",
            "canonical_path": "/scale/",
            "og_title": "OT",
            "og_description": "OD",
            "twitter_title": "TT",
            "twitter_description": "TD",
            "active_nav": "home",
            "root_path": "../",
            "nav": {"home": "../", "about": "../about/"},
        }
        page.update(overrides)
        return page

    def test_substitutes_in_content(self):
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            self._page(),
            "DAYS=${latest_total_days}",
            latest_vars=self.LATEST_VARS,
        )
        self.assertIn("BODY=DAYS=242|", out)

    def test_substitutes_in_description_and_header_meta(self):
        page = self._page(
            description="約${latest_total_days}日分（${latest_asof_jp}集計時点）",
            header_meta="U=${latest_published_dot}",
        )
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            page,
            "BODY",
            latest_vars=self.LATEST_VARS,
        )
        self.assertIn("D=約242日分（2026年3月14日集計時点）|", out)
        self.assertIn("HM=[U=2026.03.17", out)

    def test_does_not_touch_og_and_twitter_description(self):
        page = self._page(og_description="OD ${latest_total_days}")
        out = render_page(
            self.TEMPLATE,
            self.SITE_CONFIG,
            page,
            "BODY",
            latest_vars=self.LATEST_VARS,
        )
        # og_description は置換対象外 — プレースホルダが素通しで残る
        self.assertIn("OG_DESC=OD ${latest_total_days}|", out)

    def test_unknown_placeholder_raises_key_error(self):
        with self.assertRaises(KeyError):
            render_page(
                self.TEMPLATE,
                self.SITE_CONFIG,
                self._page(),
                "BODY=${no_such_var}",
                latest_vars=self.LATEST_VARS,
            )

    def test_bare_dollar_raises_value_error(self):
        with self.assertRaises(ValueError):
            render_page(
                self.TEMPLATE,
                self.SITE_CONFIG,
                self._page(),
                "PRICE $ 100",
                latest_vars=self.LATEST_VARS,
            )

    def test_placeholder_without_latest_vars_raises_key_error(self):
        # main() が latest_vars を渡し忘れても沈黙劣化しない（Fail Fast）
        with self.assertRaises(KeyError):
            render_page(
                self.TEMPLATE,
                self.SITE_CONFIG,
                self._page(),
                "DAYS=${latest_total_days}",
            )


if __name__ == "__main__":
    unittest.main()
