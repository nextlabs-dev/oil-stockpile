# 最新備蓄日数の静的 HTML 焼き込み — 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `data/snapshots.json` の最新公表値（total・published・asOf）をビルド時に home の静的 HTML と meta description へ焼き込み、JS なしでも備蓄日数が生 HTML に載る状態にする（Issue #93）。

**Architecture:** `generate_ogp.py` からスナップショット読込ヘルパーを `scripts/lib/snapshots.py` へ移動（DRY）。`build_site.py` が最新値からテンプレート変数 3 つを組み立て、strict な `string.Template.substitute()` で `content` / `description` / `header_meta` の 3 フィールドにのみ適用する。JS は一切変更しない。

**Tech Stack:** Python 3.11+ 標準ライブラリ（`string.Template`, `dataclasses`, `unittest`）。追加依存なし。

**Spec:** `docs/superpowers/specs/2026-07-17-bake-latest-days-design.md`

## Global Constraints

- **ビルド決定論**: `build_site.py` の出力はリポジトリ状態のみから決まる。`datetime.now()` / 実行時刻依存の値を焼き込まない（`test.yml` の生成 HTML drift チェックが前提）。
- **strict substitution**: `Template.substitute()` を使う。`safe_substitute()` は禁止（未定義プレースホルダの沈黙通過を許さない）。
- **置換対象は 3 フィールドのみ**: ページ `content`・`description`・`header_meta`。`title` / `og_description` / `twitter_description` には適用しない。
- **JS ファイル（`js/**`）は一切変更しない。**
- src/ を変更したら必ず `python scripts/build_site.py` を実行し、再生成された `index.html` / `tankers/index.html` / `scale/index.html` / `about/index.html` を同じコミットに含める（drift チェック対策）。
- 各コミット前に `python -m unittest discover -s scripts -p 'test_*.py'` と `ruff check scripts` が全緑であること。
- 作業ブランチ: `feat/93-bake-latest-days`（作成済み）。コミットメッセージ末尾に `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` を付ける。
- 実行環境: Windows / Git Bash。パスはフォワードスラッシュ。作業ディレクトリはリポジトリルート。

---

### Task 1: スナップショットヘルパーを `scripts/lib/snapshots.py` へ移動

純粋な移動リファクタリング。挙動変更なし。既存テストがそのまま安全網になる。

**Files:**
- Create: `scripts/lib/snapshots.py`
- Modify: `scripts/generate_ogp.py`（定義削除・import 追加、28行/34行の不要 import 削除）
- Modify: `scripts/test_generate_ogp.py`（import 元の変更のみ）

**Interfaces:**
- Consumes: `lib.io.read_json`, `lib.paths`（既存）
- Produces（Task 2 が利用）:
  - `lib.snapshots.Snapshot` — frozen dataclass（`published: str, as_of: str, total: int, national: int, private_: int, joint: int`）
  - `lib.snapshots.load_snapshots(path: Path) -> list[dict]`
  - `lib.snapshots.pick_latest_snapshot(rows: list[dict]) -> Snapshot`
  - `lib.snapshots.format_jst_date(iso: str) -> str`

- [ ] **Step 1: `scripts/lib/snapshots.py` を新規作成**

`generate_ogp.py` から移動する 4 定義をそのまま置く（本文は一字一句変更しない。lib 内は相対 import 慣習に従う）:

```python
"""data/snapshots.json の読込・最新値選択・日付整形の共有ヘルパー。

generate_ogp.py（OGP 画像）と build_site.py（HTML 焼き込み, Issue #93）の
両方が同じ「最新スナップショット」の解釈を使うため、ここに一元化する。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .io import read_json


@dataclass(frozen=True)
class Snapshot:
    published: str
    as_of: str
    total: int
    national: int
    private_: int
    joint: int


def load_snapshots(path: Path) -> list[dict]:
    data = read_json(path)
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} is empty or invalid")
    return data


def pick_latest_snapshot(rows: list[dict]) -> Snapshot:
    """asOf 昇順で末尾を最新とする。"""
    if not rows:
        raise ValueError("snapshots is empty")
    # ソートキー (asOf) を含む必須キーをソート前に全行で検証する。
    # ソートを先に行うと asOf 欠落行が不透明な KeyError を投げ、
    # 下のドキュメント化された ValueError 経路に到達しない。
    required = ("published", "asOf", "total", "national", "private", "joint")
    for row in rows:
        for k in required:
            if k not in row:
                raise ValueError(f"snapshot is missing key: {k}")
    r = sorted(rows, key=lambda row: row["asOf"])[-1]
    return Snapshot(
        published=r["published"],
        as_of=r["asOf"],
        total=int(r["total"]),
        national=int(r["national"]),
        private_=int(r["private"]),
        joint=int(r["joint"]),
    )


def format_jst_date(iso: str) -> str:
    """'2026-04-28' → '2026年4月28日'。"""
    parts = iso.split("-")
    if len(parts) != 3:
        return iso
    y, m, d = parts
    try:
        return f"{int(y)}年{int(m)}月{int(d)}日"
    except ValueError:
        return iso
```

- [ ] **Step 2: `scripts/generate_ogp.py` から移動元を削除し import に置換**

1. `@dataclass(frozen=True)` 付き `class Snapshot`（108–116 行付近）、`load_snapshots`（123–127 行付近）、`pick_latest_snapshot`（130–150 行付近）、`format_jst_date`（183–192 行付近）の 4 定義を削除する。**`compute_current_days` と `compute_fill_ratio` は削除しない**（間に挟まっているので注意）。
2. import ブロックを変更する:
   - 削除: `from dataclasses import dataclass`（28 行目 — Snapshot 移動後は未使用）
   - 削除: `from lib.io import read_json`（34 行目 — load_snapshots 移動後は未使用）
   - 追加: `from lib.snapshots import Snapshot, format_jst_date, load_snapshots, pick_latest_snapshot`
3. 「データ読込・計算」セクションコメントは `compute_current_days` の上に残す。

- [ ] **Step 3: `scripts/test_generate_ogp.py` の import を更新**

```python
from generate_ogp import (  # noqa: E402
    ILLUSTRATION_PATH,
    PEAK_DAYS,
    compute_current_days,
    compute_fill_ratio,
    render_image,
    resolve_inter,
)
from lib.io import read_json  # noqa: E402
from lib.paths import CURRENT_DAYS_FIXTURE_PATH  # noqa: E402
from lib.snapshots import Snapshot, format_jst_date, pick_latest_snapshot  # noqa: E402
```

（`mock.patch.object(generate_ogp, "load_snapshots", ...)` を使う既存テストは、generate_ogp が import した名前を patch するので変更不要。）

- [ ] **Step 4: テストと lint が全緑であることを確認**

```bash
python -m unittest discover -s scripts -p 'test_*.py'
ruff check scripts
```

Expected: `OK`（全テストパス、既存の `PickLatestSnapshotTest` / `FormatJstDateTest` が移動後の実装を検証）、ruff エラーなし。

- [ ] **Step 5: 挙動不変のスモーク確認（ビルドと OGP dry-run）**

```bash
python scripts/build_site.py
python scripts/generate_ogp.py --dry-run
git status --short
```

Expected: ビルド成功・dry-run 成功・**作業ツリーに差分なし**（`git status` は変更ファイルなし。純粋移動の証明）。

- [ ] **Step 6: コミット**

```bash
git add scripts/lib/snapshots.py scripts/generate_ogp.py scripts/test_generate_ogp.py
git commit -m "refactor(scripts): extract snapshot helpers into lib/snapshots (#93)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `build_site.py` に latest_vars 組み立てと strict 置換を実装（TDD）

**Files:**
- Modify: `scripts/build_site.py`
- Test: `scripts/test_build_site.py`

**Interfaces:**
- Consumes: `lib.snapshots.load_snapshots / pick_latest_snapshot / format_jst_date`（Task 1）、`lib.paths.SNAPSHOTS_PATH`（既存）
- Produces（Task 3 が利用）:
  - `build_latest_vars(rows: list[dict]) -> dict[str, str]` — キーは `latest_total_days` / `latest_published_dot` / `latest_asof_jp`
  - `render_page(..., latest_vars: dict[str, str] | None = None)` — content / description / header_meta にプレースホルダを書けるようになる

- [ ] **Step 1: 失敗するテストを書く**

`scripts/test_build_site.py` の import に `build_latest_vars` を追加:

```python
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
```

`RenderPageTest.TEMPLATE` に `header_meta` の出力口を追加する（既存アサーションは
`assertIn` ベースなので影響しない）。`BODY=$content|` の直前に挿入:

```python
    TEMPLATE = Template(
        "T=$title|D=$description|C=$canonical|"
        "OG_IMG=$og_image|FAVI=$favicon|CSS=$stylesheet|"
        "FONT=$font_href|EXTRA=[$extra_head]|BODY_CLASS=[$body_class]|HOME=$home_href|"
        "NAV=[$nav]|BOTTOM=[$bottom_nav]|HM=[$header_meta]BODY=$content|"
        "SCRIPTS=[$script_tags]|"
        "OG_TITLE=$og_title|OG_DESC=$og_description|"
        "TW_TITLE=$twitter_title|TW_DESC=$twitter_description|"
        "OG_ALT=$og_image_alt"
    )
```

ファイル末尾（`if __name__ == "__main__":` より前）に新テストクラスを追加:

```python
class BuildLatestVarsTest(unittest.TestCase):
    # asOf 昇順で末尾が最新になることを確かめるため、意図的に順序を崩してある
    ROWS = [
        {"published": "2026-03-18", "asOf": "2026-03-15", "total": 241,
         "national": 146, "private": 89, "joint": 6},
        {"published": "2026-03-17", "asOf": "2026-03-14", "total": 242,
         "national": 146, "private": 90, "joint": 6},
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
            self.TEMPLATE, self.SITE_CONFIG, self._page(),
            "DAYS=${latest_total_days}", latest_vars=self.LATEST_VARS,
        )
        self.assertIn("BODY=DAYS=242|", out)

    def test_substitutes_in_description_and_header_meta(self):
        page = self._page(
            description="約${latest_total_days}日分（${latest_asof_jp}集計時点）",
            header_meta="U=${latest_published_dot}",
        )
        out = render_page(
            self.TEMPLATE, self.SITE_CONFIG, page, "BODY", latest_vars=self.LATEST_VARS,
        )
        self.assertIn("D=約242日分（2026年3月14日集計時点）|", out)
        self.assertIn("HM=[U=2026.03.17", out)

    def test_does_not_touch_og_and_twitter_description(self):
        page = self._page(og_description="OD ${latest_total_days}")
        out = render_page(
            self.TEMPLATE, self.SITE_CONFIG, page, "BODY", latest_vars=self.LATEST_VARS,
        )
        # og_description は置換対象外 — プレースホルダが素通しで残る
        self.assertIn("OG_DESC=OD ${latest_total_days}|", out)

    def test_unknown_placeholder_raises_key_error(self):
        with self.assertRaises(KeyError):
            render_page(
                self.TEMPLATE, self.SITE_CONFIG, self._page(),
                "BODY=${no_such_var}", latest_vars=self.LATEST_VARS,
            )

    def test_bare_dollar_raises_value_error(self):
        with self.assertRaises(ValueError):
            render_page(
                self.TEMPLATE, self.SITE_CONFIG, self._page(),
                "PRICE $ 100", latest_vars=self.LATEST_VARS,
            )

    def test_placeholder_without_latest_vars_raises_key_error(self):
        # main() が latest_vars を渡し忘れても沈黙劣化しない（Fail Fast）
        with self.assertRaises(KeyError):
            render_page(
                self.TEMPLATE, self.SITE_CONFIG, self._page(),
                "DAYS=${latest_total_days}",
            )
```

- [ ] **Step 2: テストが失敗することを確認**

```bash
python -m unittest discover -s scripts -p 'test_build_site.py' -v 2>&1 | tail -20
```

Expected: FAIL — `ImportError: cannot import name 'build_latest_vars'`。

- [ ] **Step 3: `build_site.py` に最小実装**

import 変更（ファイル冒頭）:

```python
from lib.constants import PEAK_DAYS, PEAK_SOURCE
from lib.io import read_json
from lib.paths import OG_IMAGE_PATH, REPO_ROOT, SITE_CONFIG_PATH, SNAPSHOTS_PATH, SRC_DIR
from lib.snapshots import format_jst_date, load_snapshots, pick_latest_snapshot
```

`load_site_config()` の直後に追加:

```python
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
```

`render_page` のシグネチャ末尾に `latest_vars: dict[str, str] | None = None` を追加し、
本文の先頭（`site = site_config["site"]` の直後）に置換を入れる:

```python
def render_page(
    template: Template,
    site_config: dict[str, Any],
    page: dict[str, Any],
    content: str,
    og_image_version: str = "",
    csp: str = "",
    latest_vars: dict[str, str] | None = None,
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
```

既存の `header_meta_value = text_value(page.get("header_meta"))` 行は上記に置き換え、
`template.substitute(...)` 呼び出しの `description=page["description"]` を
`description=description` に変更する。

`main()` のループ前に latest_vars を組み立て、`render_page` へ渡す:

```python
def main() -> int:
    verify_constants_in_sync()
    site_config = load_site_config()
    base_text = BASE_TEMPLATE.read_text(encoding="utf-8")
    template = Template(base_text)
    csp = build_csp(base_text)
    og_image_version = compute_og_image_version(OG_IMAGE_PATH)
    latest_vars = build_latest_vars(load_snapshots(SNAPSHOTS_PATH))
    for page in site_config["pages"]:
        output = REPO_ROOT / page["output"]
        content = (PAGES_DIR / page["source"]).read_text(encoding="utf-8").strip()
        output.parent.mkdir(parents=True, exist_ok=True)
        rendered = render_page(
            template, site_config, page, content, og_image_version, csp, latest_vars
        )
        output.write_text(rendered, encoding="utf-8", newline="\n")
        print(f"built {page['output']}")
    return 0
```

- [ ] **Step 4: テストが通ることを確認**

```bash
python -m unittest discover -s scripts -p 'test_*.py'
ruff check scripts
```

Expected: 全テスト `OK`（新クラス 2 つ含む）、ruff エラーなし。

- [ ] **Step 5: ビルドがまだ差分ゼロであることを確認**

```bash
python scripts/build_site.py && git status --short
```

Expected: 差分なし（プレースホルダ未使用なので出力不変。機構だけ先に入る）。

- [ ] **Step 6: コミット**

```bash
git add scripts/build_site.py scripts/test_build_site.py
git commit -m "feat(build): add latest snapshot vars with strict template substitution (#93)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: home にプレースホルダを入れ、HTML を再生成

**Files:**
- Modify: `src/pages/home.html`（2 箇所）
- Modify: `src/site.json`（home の description と header_meta）
- Modify（再生成）: `index.html`, `tankers/index.html`, `scale/index.html`, `about/index.html`

**Interfaces:**
- Consumes: Task 2 の `${latest_total_days}` / `${latest_published_dot}` / `${latest_asof_jp}`

- [ ] **Step 1: `src/pages/home.html` の 2 箇所を置換**

6 行目（更新バナー）:

```html
    <span class="update-banner-date" id="update-banner-date">${latest_published_dot}</span>
```

20 行目（カウンター）:

```html
            <span id="counter-days" class="counter-num">${latest_total_days}</span>
```

（どちらも変更は `—` → プレースホルダのみ。他の属性・クラスは触らない。）

- [ ] **Step 2: `src/site.json` の home エントリを 2 箇所変更**

`description`（41 行目）を差し替え:

```json
      "description": "日本の石油備蓄はいま約${latest_total_days}日分（${latest_asof_jp}集計時点）。経済産業省「石油備蓄の現況」速報値を毎日更新で可視化する非公式カウンター。",
```

home の `header_meta`（37 行目）の `—` を差し替え:

```json
        "      <span class=\"site-header-meta-value\" id=\"header-last-updated\">${latest_published_dot}</span>",
```

**注意**: `header_meta` は tankers / scale / about のエントリにも同じ形で存在するが、
**home のみ**変更する（tankers は tankers.json 由来の値を JS が入れるため、焼くと逆に
古い値が固定される — spec「焼き込み対象」参照）。

- [ ] **Step 3: ビルドして焼き込みを確認**

```bash
python scripts/build_site.py
grep -o 'id="counter-days" class="counter-num">[0-9]*' index.html
grep -o 'id="update-banner-date">[0-9.]*' index.html
grep -o '<meta name="description" content="[^"]*"' index.html
grep -c '—</span>' tankers/index.html
```

Expected:
- `counter-days` に最新 total（数値）が入っている
- `update-banner-date` に `YYYY.MM.DD` が入っている
- description が「日本の石油備蓄はいま約N日分（YYYY年M月D日集計時点）。…」になっている
- tankers はヘッダー値が `—` のまま（対象外の証明）

- [ ] **Step 4: 決定論性の確認（2 回ビルドで差分ゼロ）**

```bash
python scripts/build_site.py && git diff --stat
```

Expected: 1 回目のビルド結果から追加差分なし（`git diff --stat` の対象は
src/ 2 ファイル + 生成 HTML のみで、2 回目のビルドで増えない）。

- [ ] **Step 5: テスト・lint 全緑を確認**

```bash
python -m unittest discover -s scripts -p 'test_*.py'
ruff check scripts
npm test
```

Expected: Python・JS とも全テストパス（JS は無変更の回帰確認）。

- [ ] **Step 6: コミット**

```bash
git add src/pages/home.html src/site.json index.html tankers/index.html scale/index.html about/index.html
git commit -m "feat(seo): bake latest stockpile days into home HTML and meta description (#93)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

（tankers/scale/about の生成 HTML は今回の変更では内容不変のはずだが、`git add` に
含めて無害。`git status` で実際に変わったファイルだけ add してもよい。）

---

### Task 4: ブラウザ実機検証・Issue コメント・PR 作成

**Files:** なし（検証と手続きのみ）

- [ ] **Step 1: ローカルサーバで生 HTML を検証**

```bash
python -m http.server 8000 &
curl -s http://localhost:8000/ | grep -o 'class="counter-num">[0-9]*'
curl -s http://localhost:8000/ | grep -o 'name="description" content="[^"]*"'
```

Expected: JS なしの生 HTML に最新日数と新 description が含まれる（= noscript 相当の保証）。

- [ ] **Step 2: ブラウザで JS 上書きを確認（claude-in-chrome）**

1. 新規タブで `http://localhost:8000/` を開く（キャッシュ回避のためハードリロード相当を行う。Chrome は localhost の CSS/JS をセッション跨ぎでキャッシュする点に注意）
2. カウンターに数値が表示されること（焼き込み値 → JS のリアルタイム推計値に上書き。integer が数日ぶん小さくなるのは想定内）
3. 更新バナー・ヘッダー最終更新に日付が出ていること
4. コンソールにエラーがないこと

- [ ] **Step 3: サーバを停止し、Issue #93 にコメント**

```bash
gh issue comment 93 --body "実装方針の補足: 実要素（#counter-days 等）に値を焼き込む方式にしたため、Issue 本文にあった noscript フォールバックは不要になりました（JS 無効時は焼き込み値がそのまま表示されます）。焼き込み値は snapshots.json の公表値そのまま（決定論的ビルド維持のため。設計: docs/superpowers/specs/2026-07-17-bake-latest-days-design.md）。"
```

- [ ] **Step 4: push して PR 作成**

```bash
git push -u origin feat/93-bake-latest-days
gh pr create --title "feat(seo): bake latest stockpile days into static HTML (#93)" --body "## 概要
Issue #93。data/snapshots.json の最新公表値をビルド時に home の静的 HTML へ焼き込む。

- counter / 更新バナー / ヘッダー最終更新の初期値と meta description に最新値（total, published, asOf）を埋め込み
- generate_ogp.py のスナップショットヘルパーを scripts/lib/snapshots.py へ移動して共用（DRY）
- strict な Template.substitute で content / description / header_meta のみ置換（未定義プレースホルダはビルド失敗 = Fail Fast）
- 公表値そのまま（実行時刻非依存）なのでビルドは決定論的のまま — test.yml の drift チェックと共存
- JS 変更なし（counter.js がロード後にリアルタイム推計値で上書き）

設計: docs/superpowers/specs/2026-07-17-bake-latest-days-design.md

## 検証
- python -m unittest discover -s scripts -p 'test_*.py' 全緑
- ruff check scripts / npm test 全緑
- 2 回ビルドで差分ゼロ（決定論性）
- curl で生 HTML に最新日数・新 description を確認
- ブラウザで JS 上書き・コンソールエラーなしを確認

Closes #93

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Expected: PR が作成され、CI（test.yml の drift チェック含む）が緑になる。

---

## Self-Review 済み確認事項

- spec の全要件にタスクが対応: lib 移動（Task 1）、変数組み立て + strict 置換（Task 2）、home 焼き込み + 再生成（Task 3）、検証 + Issue コメント（Task 4 = spec「検証方法」）
- `latest_vars` 未指定時も空 dict で strict 置換が走る設計により、main の渡し忘れ = 沈黙劣化を KeyError で防止（spec の Fail Fast 要件を強化する形で満たす）
- 型・名前の整合: `build_latest_vars` のキー 3 つは Task 2 のテスト・Task 3 のプレースホルダと一字一句一致
