import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update_sitemap


class UpdateSitemapTest(unittest.TestCase):
    def test_updates_home_and_tanker_lastmod(self):
        source = (
            "<urlset>\n"
            "  <url>\n"
            "    <loc>https://oilstock.nextlabs.jp/</loc>\n"
            "    <changefreq>daily</changefreq>\n"
            "  </url>\n"
            "  <url>\n"
            "    <loc>https://oilstock.nextlabs.jp/tankers/</loc>\n"
            "    <changefreq>hourly</changefreq>\n"
            "  </url>\n"
            "</urlset>\n"
        )
        result = update_sitemap.update_lastmod(
            source,
            {
                "https://oilstock.nextlabs.jp/": "2026-08-18",
                "https://oilstock.nextlabs.jp/tankers/": "2026-08-19",
            },
        )
        self.assertIn("<lastmod>2026-08-18</lastmod>", result)
        self.assertIn("<lastmod>2026-08-19</lastmod>", result)
        self.assertNotIn("\n\n      <lastmod>", result)
        self.assertEqual(
            result,
            update_sitemap.update_lastmod(
                result,
                {
                    "https://oilstock.nextlabs.jp/": "2026-08-18",
                    "https://oilstock.nextlabs.jp/tankers/": "2026-08-19",
                },
            ),
        )

    def test_replaces_existing_lastmod_without_duplicates(self):
        source = (
            "<url>\n"
            "  <loc>https://oilstock.nextlabs.jp/</loc>\n"
            "  <lastmod>2026-01-01</lastmod>\n"
            "  <priority>1.0</priority>\n"
            "</url>\n"
        )
        result = update_sitemap.update_lastmod(
            source, {"https://oilstock.nextlabs.jp/": "2026-08-18"}
        )
        self.assertEqual(result.count("<lastmod>"), 1)
        self.assertIn("<lastmod>2026-08-18</lastmod>", result)
        self.assertNotIn("2026-01-01", result)


if __name__ == "__main__":
    unittest.main()
