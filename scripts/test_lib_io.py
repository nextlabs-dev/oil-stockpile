"""Unit tests for scripts/lib/io.py.

Run from project root:
    python -m unittest discover -s scripts -p 'test_*.py'

write_json はリポジトリ全体の JSON 出力フォーマット契約
(UTF-8 / ensure_ascii=False / indent=2 / 末尾改行) を担保する。
ここでフォーマットを破ると毎日の自動コミットで diff ノイズが出る。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib.io import read_json, write_json  # noqa: E402


class WriteJsonRoundTripTest(unittest.TestCase):
    def test_round_trip_preserves_data(self):
        data = {"asOf": "2026-04-28", "total": 211, "list": [1, 2, 3]}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            write_json(path, data)
            self.assertEqual(read_json(path), data)

    def test_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "dir" / "out.json"
            write_json(path, [1, 2, 3])
            self.assertEqual(read_json(path), [1, 2, 3])


class WriteJsonFormatContractTest(unittest.TestCase):
    """フォーマット契約は他スクリプトの diff 安定性を保証する。"""

    def _read(self, data) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            write_json(path, data)
            return path.read_text(encoding="utf-8")

    def test_japanese_kept_as_utf8_not_escaped(self):
        text = self._read({"key": "石油備蓄"})
        self.assertIn("石油備蓄", text)
        self.assertNotIn("\\u", text)

    def test_indent_is_two_spaces(self):
        text = self._read({"a": 1, "b": [1, 2]})
        self.assertIn('\n  "a"', text)
        self.assertIn('\n    1', text)

    def test_trailing_newline(self):
        text = self._read({"a": 1})
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
