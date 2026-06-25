"""Unit tests for scripts/build_site.py.

Run from project root:
    python -m unittest discover -s scripts -p 'test_*.py'

I/O から切り離した純粋関数 (text_value / render_nav /
render_page / _check_peak_reference_in_sync) をカバーする。
"""

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
    compute_og_image_version,
    render_nav,
    render_page,
    text_value,
)


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
        self.assertIsNone(
            _check_peak_reference_in_sync(SAMPLE_DATA_JS, 247, SAMPLE_SOURCE)
        )

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
            _check_peak_reference_in_sync(
                "// no peak reference here\n", 247, SAMPLE_SOURCE
            )
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
        self.assertIsNone(
            _check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE)
        )

    def test_picks_fields_inside_peak_reference_block(self):
        # PEAK_REFERENCE 以外のブロックに紛れた days は拾わないこと
        text = f"""
        export const OTHER = {{ days: 999, source: 'other' }};
        export const PEAK_REFERENCE = {{
          days: 247,
          source: '{SAMPLE_SOURCE}',
        }};
        """
        self.assertIsNone(
            _check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE)
        )

    def test_supports_double_quoted_source(self):
        text = (
            "export const PEAK_REFERENCE = {\n"
            "  days: 247,\n"
            f'  source: "{SAMPLE_SOURCE}",\n'
            "};"
        )
        self.assertIsNone(
            _check_peak_reference_in_sync(text, 247, SAMPLE_SOURCE)
        )


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


class RenderPageTest(unittest.TestCase):
    """最小テンプレで render_page の組み立てを検証する。"""

    TEMPLATE = Template(
        "T=$title|D=$description|C=$canonical|"
        "OG_IMG=$og_image|FAVI=$favicon|CSS=$stylesheet|"
        "FONT=$font_href|EXTRA=[$extra_head]|BODY_CLASS=[$body_class]|HOME=$home_href|"
        "NAV=[$nav]|BODY=$content|"
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
            self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY",
            og_image_version="abc12345",
        )
        self.assertIn("OG_IMG=https://example.com/og.png?v=abc12345|", out)

    def test_og_image_no_query_when_version_empty(self):
        # 省略時 (デフォルト空) はクエリを付けない。
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn("OG_IMG=https://example.com/og.png|", out)


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


if __name__ == "__main__":
    unittest.main()
