"""Unit tests for scripts/build_site.py.

Run from project root:
    python -m unittest discover -s scripts -p 'test_*.py'

verify_constants_in_sync の本体は _check_peak_days_in_sync(text, expected)
に分離してあり、純粋なテキスト関数として正規表現と比較ロジックを検証する。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from build_site import _check_peak_days_in_sync  # noqa: E402


SAMPLE_DATA_JS = """\
export const PEAK_REFERENCE = {
  days: 247,
  source: '経産省「石油備蓄の現況」過去公表値の高水準（2025年3月末ごろ）',
};
"""


class CheckPeakDaysInSyncTest(unittest.TestCase):
    def test_matches_returns_none(self):
        # 一致すれば例外を投げない
        self.assertIsNone(_check_peak_days_in_sync(SAMPLE_DATA_JS, 247))

    def test_mismatch_message_contains_both_values(self):
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_days_in_sync(SAMPLE_DATA_JS, 250)
        msg = str(cm.exception)
        self.assertIn("247", msg)
        self.assertIn("250", msg)
        self.assertIn("drift", msg)

    def test_pattern_not_found_raises(self):
        with self.assertRaises(RuntimeError) as cm:
            _check_peak_days_in_sync("// no peak reference here\n", 247)
        self.assertIn("not found", str(cm.exception))

    def test_tolerates_whitespace_variants(self):
        # JS フォーマッタの整形違いに耐えること
        text = "export const PEAK_REFERENCE  =  {\n  days  :  247  ,\n};"
        self.assertIsNone(_check_peak_days_in_sync(text, 247))

    def test_picks_first_days_inside_peak_reference_block(self):
        # PEAK_REFERENCE 以外のブロックに紛れた days は拾わないこと
        text = """
        export const OTHER = { days: 999 };
        export const PEAK_REFERENCE = {
          days: 247,
        };
        """
        self.assertIsNone(_check_peak_days_in_sync(text, 247))


if __name__ == "__main__":
    unittest.main()
