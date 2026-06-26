# computeCurrentDays クロス言語ドリフトガード — 設計

- Issue: [#23](https://github.com/CountieeReturns/oil-stockpile/issues/23)
- 日付: 2026-06-26
- 重要度: low（現状はバグではなく将来のドリフトリスク）

## 背景と問題

備蓄日数の「いま時点」計算ロジックが 2 言語に重複実装されている。

- JS: `js/core/data.js` `computeCurrentDays`（113–121）
- Python: `scripts/generate_ogp.py` `compute_current_days`（153–164）

両者は同一モデル（asOf を JST 0:00 として now との差分日数を `total` から減算、`[0, total]` にクランプ）で**現在は完全一致**するが、同期を保証する自動チェックが無い。

対照的に定数 `PEAK_REFERENCE` は `src/constants.json` を SSOT とし、`build_site.py` の `verify_constants_in_sync` / `_check_peak_reference_in_sync` がビルド時に JS をテキスト照合してドリフトを検知し、CI で走る。

`computeCurrentDays` は両言語が**独立に**テストする（`test_generate_ogp.py` の `ComputeCurrentDaysTest` と `data.test.js`）ため、どちらのスイートも相手言語の乖離を検知できない。

### PEAK_REFERENCE との本質的な違い

`PEAK_REFERENCE` は**定数値**なので正規表現でテキスト照合できる。`computeCurrentDays` は**アルゴリズム**であり、関数本体どうしのテキスト照合は意味をなさない。よって「値の照合」ではなく「**振る舞いの照合**」でガードする。

## 中心となる考え方

`src/fixtures/current_days_cases.json` を「**振る舞いの SSOT（ゴールデン表）**」とし、Python と JS の両テストスイートが同じ表を読んでアサートする。

CI は既に両スイートを走らせている（`test.yml` の `unit` ジョブ = Python unittest、`js-unit` ジョブ = `node --test`）。`test.yml` は `src/**` 変更でもトリガするため、**新しい CI 設定は不要**。

### ドリフトを捕捉する仕組み（対称ガード）

1. 片方の実装の振る舞いを、表でカバーされた入力について変える。
2. その言語のスイートがゴールデン表と食い違って落ちる。
3. 通すにはゴールデン表を新しい振る舞いに合わせて更新する必要がある。
4. すると今度はもう片方の言語のスイートが落ちる。
5. 両言語を直すまで CI は通らない。

これにより、片方だけを変えて相手に反映し忘れる「無言のドリフト」が出荷できなくなる。

### 正直な限界

ゴールデン表方式なので、**表でカバーされた振る舞いの変化のみ**捕捉する。表に無いエッジ（新しいクランプ領域など）の変更は捕捉できない。これはゴールデンテスト一般の性質。したがってケースはモデルの全挙動（タイムゾーン変換・線形減衰・上限クランプ・下限クランプ）を張るよう設計する。

## フィクスチャ形式

ファイル: `src/fixtures/current_days_cases.json`

- `now` は **ISO 8601 + 明示オフセット**で表現する。可読性が高く（次の読み手が `2026-01-03T12:00 JST` を読める）、Python `datetime.fromisoformat` と JS `new Date()` の双方がネイティブにパースする。
- `expected` は厳密に表現可能な値（整数日・半日）に設計し、比較は許容誤差付き（Python `assertAlmostEqual(places=6)`、JS `Math.abs(got - expected) < 1e-9`）で行う。
- `label` は失敗時のメッセージと意図の記録に使う。

```json
[
  { "label": "at asOf midnight JST returns total",
    "asOf": "2026-01-01", "total": 200, "now": "2026-01-01T00:00:00+09:00", "expected": 200 },
  { "label": "same instant in UTC locks the +09:00 conversion",
    "asOf": "2026-01-01", "total": 200, "now": "2025-12-31T15:00:00Z",    "expected": 200 },
  { "label": "2.5 days elapsed decrements linearly",
    "asOf": "2026-01-01", "total": 200, "now": "2026-01-03T12:00:00+09:00", "expected": 197.5 },
  { "label": "whole day elapsed minus one",
    "asOf": "2026-01-01", "total": 200, "now": "2026-01-02T00:00:00+09:00", "expected": 199 },
  { "label": "now before asOf caps at total (upper clamp)",
    "asOf": "2026-01-01", "total": 200, "now": "2025-12-22T00:00:00+09:00", "expected": 200 },
  { "label": "large elapse floors at zero (lower clamp)",
    "asOf": "2026-01-01", "total": 3,   "now": "2026-03-01T00:00:00+09:00", "expected": 0 }
]
```

### カバレッジ対応

| ケース | 張る振る舞い |
|---|---|
| at asOf | 起点（経過 0 → total） |
| same instant in UTC | `+09:00` タイムゾーン変換（落とすと壊れる） |
| 2.5 days elapsed | 小数日の線形減衰 |
| whole day elapsed | 整数日の線形減衰 |
| now before asOf | 上限クランプ（total で頭打ち） |
| large elapse | 下限クランプ（0 で底打ち） |

## テスト統合

### Python（`scripts/test_generate_ogp.py`）

- 新テストクラスを追加し、`src/fixtures/current_days_cases.json` を読む。
- 各ケースを `subTest(label=case["label"])` で回し、`asOf`/`total` から `Snapshot` を組み（他フィールドはダミー）、`now` を `datetime.fromisoformat(case["now"])` で `datetime` 化、`compute_current_days` を呼んで `assertAlmostEqual(result, case["expected"], places=6)`。
- パスは `scripts/lib/paths.py` に `CURRENT_DAYS_FIXTURE_PATH = SRC_DIR / "fixtures" / "current_days_cases.json"` を追加して参照（パス SSOT 集約の既存慣習に合わせる）。読込は既存 `lib.io.read_json`。

### JS（`js/core/data.test.js`）

- `JSON.parse(readFileSync(new URL('../../src/fixtures/current_days_cases.json', import.meta.url), 'utf8'))` で読む（`data.test.js` は `js/core/` にあるため相対 `../../src/...`）。
- ケースごとに `test()` を 1 個生成し、明確な失敗メッセージを出す。`now` は `new Date(case.now).getTime()`、`computeCurrentDays({ asOf, total }, now)` を呼び `Math.abs(got - expected) < 1e-9` を assert。

### 既存テストの扱い

既存の各言語テスト（`ComputeCurrentDaysTest` と JS 側 `computeCurrentDays` テスト群）は**残す**。不正入力時の挙動は意図的に言語差がある（Python は不正 `asOf` で `ValueError` を送出して `main` が `return 1`、JS は `NaN` を返す）ため、共有フィクスチャには valid 入力の数値ケースのみを置き、不正入力テストは各言語に残す。

## 双方向コメントポインタ

- `js/core/data.js` `computeCurrentDays`: Python ミラー（`scripts/generate_ogp.py compute_current_days`）と、振る舞いを `src/fixtures/current_days_cases.json` で両言語がアサートする旨を追記。
- `scripts/generate_ogp.py` `compute_current_days`: 既存の JS 参照コメントにフィクスチャ言及を追記。

## 変更ファイル一覧

| ファイル | 変更 |
|---|---|
| `src/fixtures/current_days_cases.json` | 新規（ゴールデン表） |
| `scripts/lib/paths.py` | `CURRENT_DAYS_FIXTURE_PATH` を 1 行追加 |
| `scripts/test_generate_ogp.py` | フィクスチャ駆動テストクラス追加 |
| `js/core/data.test.js` | フィクスチャ駆動テスト追加 |
| `js/core/data.js` | `computeCurrentDays` にコメント追記 |
| `scripts/generate_ogp.py` | `compute_current_days` にコメント追記 |

## 検証方法

- `python -m unittest discover -s scripts -p 'test_*.py' -v` が通る（新フィクスチャクラス含む）。
- `npm test`（`node --test`）が通る（新フィクスチャテスト含む）。
- ドリフト検知の確認: ローカルでフィクスチャの 1 つの `expected` を一時的に改変すると**両スイートが落ちる**ことを確認し、元に戻す。

## 非対象（YAGNI）

- ビルド時に node をサブプロセス実行して JS 出力を Python と照合する方式（案 B）は採らない。Python 専用のビルド/CI ジョブに node 依存を持ち込み、重く脆いため。
- `computeCurrentDays` ロジック自体の変更・リファクタは行わない。今回はガードの追加のみ。
