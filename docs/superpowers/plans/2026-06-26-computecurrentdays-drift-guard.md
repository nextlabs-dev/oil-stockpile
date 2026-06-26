# computeCurrentDays クロス言語ドリフトガード Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python(`generate_ogp.py`) と JS(`data.js`) に重複実装された `computeCurrentDays` の振る舞いを、両言語のテストが共有するゴールデン表でロックしてドリフトを CI で検知する。

**Architecture:** `src/fixtures/current_days_cases.json` を「振る舞いの SSOT」とし、`(asOf, total, now) → expected` のケース表を Python(`test_generate_ogp.py`) と JS(`data.test.js`) の両スイートが読んでアサートする。既存 CI の `unit`/`js-unit` 両ジョブがそのまま走るため新規 CI 設定は不要。実装ロジック自体は変更しない（ガードの追加のみ）。

**Tech Stack:** Python (unittest), Node.js (`node:test` / `node:assert`), JSON フィクスチャ, Biome (lint/format)。

## Global Constraints

- Python: CI は 3.12、ローカルは 3.11+。`datetime.fromisoformat` は両バージョンで `Z` サフィックスとオフセットをパース可能。
- Node.js: CI は 22。`node --test` を使用。
- 新規ランタイム依存を追加しない（フィクスチャは標準ライブラリで読む: Python `lib.io.read_json` / JS `node:fs` `readFileSync`）。
- パス定義は `scripts/lib/paths.py` に集約する既存慣習に従う。
- テストはコード隣接（`scripts/test_*.py`, `js/**/*.test.js`）の既存配置に従う。
- コードスタイルは Biome（シングルクォート・セミコロン・2スペース）。既存 `js/core/data.test.js` のスタイルに合わせる。
- `compute_current_days` / `computeCurrentDays` のロジックは変更しない。
- フィクスチャの `now` は ISO 8601 + 明示オフセット、`expected` は厳密表現可能な値、比較は許容誤差付き（Python `places=6` / JS `< 1e-9`）。

---

## File Structure

| ファイル | 責務 | 変更種別 |
|---|---|---|
| `src/fixtures/current_days_cases.json` | 振る舞いの SSOT（ゴールデン表） | Create |
| `scripts/lib/paths.py` | フィクスチャのパス定数を追加 | Modify |
| `scripts/test_generate_ogp.py` | Python 側がゴールデン表をアサート | Modify |
| `js/core/data.test.js` | JS 側がゴールデン表をアサート | Modify |
| `js/core/data.js` | `computeCurrentDays` に双方向ポインタ注記 | Modify |
| `scripts/generate_ogp.py` | `compute_current_days` にフィクスチャ注記 | Modify |

---

## Task 1: ゴールデン表 + Python 整合テスト

**Files:**
- Create: `src/fixtures/current_days_cases.json`
- Modify: `scripts/lib/paths.py`（`SITE_CONFIG_PATH` の直後に 1 行追加）
- Test: `scripts/test_generate_ogp.py`（新クラス `SharedFixtureConsistencyTest` を末尾の `if __name__` ブロック直前に追加）

**Interfaces:**
- Consumes: 既存 `generate_ogp.compute_current_days(snapshot: Snapshot, now: datetime) -> float`、`generate_ogp.Snapshot`。
- Produces: `paths.CURRENT_DAYS_FIXTURE_PATH: Path`（Task 2 は JS から相対パスで同じファイルを読むため、このパス定数自体には依存しないが、ファイルの場所 `src/fixtures/current_days_cases.json` を確定する）。フィクスチャの JSON スキーマ `{label: str, asOf: str, total: number, now: str(ISO8601), expected: number}` を確定する（Task 2 が同じスキーマを読む）。

- [ ] **Step 1: `paths.py` にフィクスチャのパス定数を追加**

`scripts/lib/paths.py` の `SITE_CONFIG_PATH = SRC_DIR / "site.json"` の行の直後に追加する:

```python
CURRENT_DAYS_FIXTURE_PATH = SRC_DIR / "fixtures" / "current_days_cases.json"
```

- [ ] **Step 2: Python 整合テストを書く（フィクスチャ未作成なので失敗するはず）**

`scripts/test_generate_ogp.py` の import 群（`from generate_ogp import (...)` ブロックの直後、おおよそ 44 行目付近）に次の 2 行を追加する:

```python
from lib.io import read_json  # noqa: E402
from lib.paths import CURRENT_DAYS_FIXTURE_PATH  # noqa: E402
```

そして `if __name__ == "__main__":` の直前に次のテストクラスを追加する:

```python
class SharedFixtureConsistencyTest(unittest.TestCase):
    """js/core/data.js computeCurrentDays と同じゴールデン表
    (src/fixtures/current_days_cases.json) をアサートし、JS 実装との
    ドリフトを検知する。JS 側は js/core/data.test.js が同じ表を読む。"""

    def test_matches_golden_table(self):
        cases = read_json(CURRENT_DAYS_FIXTURE_PATH)
        self.assertGreater(len(cases), 0, "fixture must not be empty")
        for case in cases:
            with self.subTest(label=case["label"]):
                snap = Snapshot(
                    published="2026-05-01",
                    as_of=case["asOf"],
                    total=case["total"],
                    national=0,
                    private_=0,
                    joint=0,
                )
                now = datetime.fromisoformat(case["now"])
                result = compute_current_days(snap, now)
                self.assertAlmostEqual(result, case["expected"], places=6)
```

- [ ] **Step 3: テストを実行して失敗することを確認**

Run: `python scripts/test_generate_ogp.py SharedFixtureConsistencyTest -v`
Expected: FAIL（`src/fixtures/current_days_cases.json` が存在せず `read_json` が `FileNotFoundError` を投げる）

- [ ] **Step 4: ゴールデン表フィクスチャを作成**

`src/fixtures/current_days_cases.json` を新規作成する（`src/fixtures/` ディレクトリも作る）:

```json
[
  {
    "label": "at asOf midnight JST returns total",
    "asOf": "2026-01-01",
    "total": 200,
    "now": "2026-01-01T00:00:00+09:00",
    "expected": 200
  },
  {
    "label": "same instant expressed in UTC locks the +09:00 conversion",
    "asOf": "2026-01-01",
    "total": 200,
    "now": "2025-12-31T15:00:00Z",
    "expected": 200
  },
  {
    "label": "2.5 days elapsed decrements linearly",
    "asOf": "2026-01-01",
    "total": 200,
    "now": "2026-01-03T12:00:00+09:00",
    "expected": 197.5
  },
  {
    "label": "whole day elapsed minus one",
    "asOf": "2026-01-01",
    "total": 200,
    "now": "2026-01-02T00:00:00+09:00",
    "expected": 199
  },
  {
    "label": "now before asOf caps at total (upper clamp)",
    "asOf": "2026-01-01",
    "total": 200,
    "now": "2025-12-22T00:00:00+09:00",
    "expected": 200
  },
  {
    "label": "large elapse floors at zero (lower clamp)",
    "asOf": "2026-01-01",
    "total": 3,
    "now": "2026-03-01T00:00:00+09:00",
    "expected": 0
  }
]
```

- [ ] **Step 5: テストを実行して通ることを確認**

Run: `python scripts/test_generate_ogp.py SharedFixtureConsistencyTest -v`
Expected: PASS（`test_matches_golden_table` が ok。subTest により 6 ケースを内部で検証）

- [ ] **Step 6: Python スイート全体が壊れていないことを確認**

Run: `python -m unittest discover -s scripts -p 'test_generate_ogp.py' -v`
Expected: 既存テスト + 新テストがすべて PASS（OK）

- [ ] **Step 7: コミット**

```bash
git add src/fixtures/current_days_cases.json scripts/lib/paths.py scripts/test_generate_ogp.py
git commit -m "test: lock computeCurrentDays behavior with shared golden fixture (Python side) (#23)"
```

---

## Task 2: JS 整合テスト + ドリフトガード検証

**Files:**
- Modify: `js/core/data.test.js`（`node:fs` の import 追加 + 末尾にフィクスチャ駆動テスト追加）

**Interfaces:**
- Consumes: 既存 `data.js` の `computeCurrentDays(snapshot, now)`、Task 1 が確定したフィクスチャ `src/fixtures/current_days_cases.json`（スキーマ `{label, asOf, total, now, expected}`）。
- Produces: なし（最終テストファイル）。

- [ ] **Step 1: JS フィクスチャ駆動テストを書く**

`js/core/data.test.js` の先頭、`import { test } from 'node:test';` の直後に追加:

```javascript
import { readFileSync } from 'node:fs';
```

ファイル末尾に次を追加する:

```javascript
// 振る舞いの SSOT を Python (scripts/test_generate_ogp.py) と共有してドリフトを検知する。
const currentDaysCases = JSON.parse(
  readFileSync(new URL('../../src/fixtures/current_days_cases.json', import.meta.url), 'utf8'),
);

test('shared fixture: ケースが空でない（vacuous pass を防ぐ）', () => {
  assert.ok(currentDaysCases.length > 0);
});

for (const c of currentDaysCases) {
  test(`shared fixture (computeCurrentDays): ${c.label}`, () => {
    const now = new Date(c.now).getTime();
    const got = computeCurrentDays({ asOf: c.asOf, total: c.total }, now);
    assert.ok(
      Math.abs(got - c.expected) < 1e-9,
      `${c.label}: expected ${c.expected}, got ${got}`,
    );
  });
}
```

- [ ] **Step 2: JS テストを実行して通ることを確認**

Run: `node --test js/core/data.test.js`
Expected: PASS（既存テスト + `shared fixture: ...` 7 件すべて pass。`# pass` 件数が増える）

- [ ] **Step 3: ドリフトガードが機能することを検証（破壊→両方失敗→復元）**

`src/fixtures/current_days_cases.json` の最初のケースの `"expected": 200` を一時的に `"expected": 999` に書き換える。

両スイートを実行する:

Run: `python scripts/test_generate_ogp.py SharedFixtureConsistencyTest -v`
Expected: FAIL（`at asOf midnight JST returns total` の subTest が 200 != 999 で落ちる）

Run: `node --test js/core/data.test.js`
Expected: FAIL（`shared fixture (computeCurrentDays): at asOf...` が落ちる）

両言語が同じ 1 つのフィクスチャ改変で落ちることを確認したら、`"expected": 200` に戻す。

Run: `git diff --stat src/fixtures/current_days_cases.json`
Expected: 差分なし（復元済み）

- [ ] **Step 4: コミット**

```bash
git add js/core/data.test.js
git commit -m "test: assert computeCurrentDays golden fixture from JS side (#23)"
```

---

## Task 3: 双方向コメントポインタ

**Files:**
- Modify: `js/core/data.js`（`computeCurrentDays` の JSDoc、おおよそ 106-112 行）
- Modify: `scripts/generate_ogp.py`（`compute_current_days` の docstring、おおよそ 154-158 行）

**Interfaces:**
- Consumes: なし（コメントのみ。ロジック不変）。
- Produces: なし。

- [ ] **Step 1: `data.js` にポインタを追記**

`js/core/data.js` の `computeCurrentDays` の JSDoc を次のように差し替える（既存ブロック全体を置換）:

```javascript
/**
 * snapshot の asOf 時点からの経過分を引いた「いまこの瞬間の推計備蓄日数」を返す。
 * モデル: 「1 日経過 = 1 日分減る」（年間消費量推計を別途持たなくても整合）。
 *
 * カウンターページ (秒按分) と石油のものさしページ (整数日) が
 * 同じ値起点で動くよう、両モジュールから本関数を呼ぶ。
 *
 * Python ミラー: scripts/generate_ogp.py compute_current_days（OGP 事前生成用）。
 * 両実装の振る舞いは src/fixtures/current_days_cases.json（ゴールデン表）を
 * 両言語のテストがアサートしてドリフトを検知する
 * （js/core/data.test.js と scripts/test_generate_ogp.py）。
 * 式を変えるときは表と両実装を同時に更新すること。
 */
```

- [ ] **Step 2: `generate_ogp.py` にポインタを追記**

`scripts/generate_ogp.py` の `compute_current_days` の docstring を次のように差し替える（既存ブロック全体を置換）:

```python
    """
    サイト本体 (js/core/data.js:computeCurrentDays) と同じ式で「いま時点」の備蓄日数を返す。
    モデル: 「1 日経過 = 1 日分減る」（asOf を JST 0:00 として now との差分日数を減算）。
    OG 画像は事前生成のため、cron 実行時刻の値で固定される（次の実行までは更新されない）。

    両実装の振る舞いは src/fixtures/current_days_cases.json（ゴールデン表）を
    両言語のテストがアサートしてドリフトを検知する
    （scripts/test_generate_ogp.py と js/core/data.test.js）。
    """
```

- [ ] **Step 3: 両スイートが依然 PASS することを確認（コメントのみなので不変）**

Run: `python -m unittest discover -s scripts -p 'test_*.py' -v`
Expected: 全 PASS（OK）

Run: `npm test`
Expected: 全 PASS（`# fail 0`）

- [ ] **Step 4: コミット**

```bash
git add js/core/data.js scripts/generate_ogp.py
git commit -m "docs: cross-reference computeCurrentDays mirror and golden fixture (#23)"
```

---

## 最終検証（全タスク完了後）

- [ ] Python 全スイート: `python -m unittest discover -s scripts -p 'test_*.py' -v` → OK
- [ ] JS 全スイート: `npm test` → `# fail 0`
- [ ] Lint/format: `npm run check`（Biome）→ エラーなし
- [ ] フィクスチャがビルドに影響しないことの確認: `python scripts/build_site.py` → 既存生成物に差分が出ない（`git diff --exit-code -- index.html tankers/index.html scale/index.html about/index.html` が 0）

## Self-Review メモ（spec 対応）

- spec「ゴールデン表」→ Task 1 Step 4
- spec「Python 側アサート」→ Task 1 Step 2/5
- spec「JS 側アサート」→ Task 2 Step 1/2
- spec「UTC ケースで +09:00 をロック」→ フィクスチャ 2 番目のケース
- spec「上限/下限クランプ」→ フィクスチャ 5・6 番目
- spec「既存の各言語テストは残す」→ 既存テストは触らず追加のみ
- spec「双方向コメントポインタ」→ Task 3
- spec「パス SSOT 集約」→ Task 1 Step 1（`paths.py`）
- spec「ドリフト検知の確認手順」→ Task 2 Step 3
- spec「非対象（案 B / ロジック変更）」→ 本計画に含めない
