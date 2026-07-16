# モバイルボトムナビバー Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** モバイル（≤640px）のハンバーガードロップダウンを、画面下固定のボトムナビバー（線画 SVG アイコン + ラベル）に置き換えて発見性を改善する。

**Architecture:** 静的サイト。`src/site.json`（SSOT）+ `src/templates/base.html` から `scripts/build_site.py` が 4 ページ（`index.html` / `tankers/index.html` / `scale/index.html` / `about/index.html`）を生成する。既存の `render_nav()`（デスクトップ用ヘッダータブ）と同じパターンで `render_bottom_nav()` を追加し、テンプレートの `$bottom_nav` に流し込む。ハンバーガー開閉 JS（`js/components/nav.js`）は死コード化するので削除。CSS は `assets/styles.css` が `@import` する `layout.css` / `components.css` を変更する。

**Tech Stack:** Python 3（stdlib のみ、`string.Template`）/ `python -m unittest` / vanilla CSS / Node は `npm test`（node --test）と `npm run check`（Biome）のみ。

**Spec:** `docs/superpowers/specs/2026-07-16-mobile-bottom-nav-design.md`

## Global Constraints

- デスクトップ（>640px）の見た目は一切変えない。ブレークポイントは既存の `max-width: 640px` を使う
- 色は既存 CSS 変数のみ: バー背景 `var(--header-bg)`、非アクティブ `var(--header-fg-muted)`、アクティブ文字 `var(--header-fg-strong)`、アクティブアイコン `var(--brand)`、上罫線 `rgba(255, 255, 255, 0.1)`
- ボトムバーのラベルは `nav_labels_short`: カウンター / タンカー / ものさし / about（`scale` のみ短縮）
- CSP（meta）は変更しない（インライン SVG は影響なし）
- コミットは husky + lint-staged（Biome が js/css/md を自動整形）を通す。`--no-verify` 禁止
- Python テスト実行コマンド（プロジェクトルートから）: `python -m unittest discover -s scripts -p "test_*.py"`
- コミットメッセージ末尾に `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: `render_bottom_nav()` を build_site.py に追加（TDD）

**Files:**
- Modify: `scripts/build_site.py`（`render_nav()` の直後、182 行目付近に追加）
- Test: `scripts/test_build_site.py`

**Interfaces:**
- Consumes: なし（純粋関数の新設のみ。既存 `render_nav()` のパターンを踏襲）
- Produces: `render_bottom_nav(page: dict[str, Any], nav_labels_short: dict[str, str], nav_order: list[str]) -> str` — `<a class="bottom-nav-item">` 行を改行連結した文字列。モジュール定数 `NAV_ICONS: dict[str, str]`（キー: home / tankers / scale / about）。Task 2 の `render_page()` がこの関数を呼ぶ

- [ ] **Step 1: 失敗するテストを書く**

`scripts/test_build_site.py` の `RenderNavTest` クラスの直後に追加:

```python
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
            self.assertIn('<svg', line)
            self.assertIn('aria-hidden="true"', line)
```

同ファイル冒頭の import ブロックに `render_bottom_nav` を追加:

```python
from build_site import (  # noqa: E402
    _check_peak_reference_in_sync,
    build_csp,
    compute_inline_script_hashes,
    compute_og_image_version,
    render_bottom_nav,
    render_nav,
    render_page,
    text_value,
)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m unittest discover -s scripts -p "test_*.py" 2>&1 | tail -5`
Expected: `ImportError: cannot import name 'render_bottom_nav'`

- [ ] **Step 3: 最小実装を書く**

`scripts/build_site.py` の `render_nav()`（180 行目 `return "\n".join(links)`）の直後に追加:

```python
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
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest discover -s scripts -p "test_*.py" 2>&1 | tail -3`
Expected: `OK`（失敗 0。既存テストもすべてパス）

- [ ] **Step 5: Commit**

```bash
git add scripts/build_site.py scripts/test_build_site.py
git commit -m "feat(build): add render_bottom_nav for mobile bottom nav links

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: ボトムナビの CSS を追加（マークアップより先・見た目の変化なし）

**Files:**
- Modify: `assets/styles/layout.css:92-177`（`.site-nav` / `.nav-toggle` 全ルールと `@media (max-width: 640px)` ブロックを置換）
- Modify: `assets/styles/components.css:56-70`（モバイルのタブ縦積みブロックを置換）

**Interfaces:**
- Consumes: クラス名 `bottom-nav` / `bottom-nav-item` / `bottom-nav-item--active`（Task 1 の `render_bottom_nav()` が生成。ラッパー `<nav class="bottom-nav">` は Task 3 でテンプレートに入る）
- Produces: 上記クラスのスタイル定義。`.bottom-nav` は基本 `display: none`（デスクトップ非表示）で、この時点ではマークアップ未導入のため既存ページの見た目は変わらない

- [ ] **Step 1: layout.css のヘッダー/ナビ CSS を置き換える**

`assets/styles/layout.css` の 92〜177 行目（`/* Nav wrapper: ... */` コメントから `@media (max-width: 640px) { ... }` ブロックの閉じ括弧まで。`.site-nav`、`.nav-toggle`、`.nav-toggle-bar`、`aria-expanded` 変形ルールを含む全部）を削除し、同じ場所に以下を挿入:

```css
/* =============================================================
   Bottom nav — mobile only (≤640px), fixed to the viewport bottom.
   Desktop keeps the header pill tabs; this bar replaces the old
   hamburger dropdown.
   ============================================================= */
.bottom-nav {
  display: none;
}

@media (max-width: 640px) {
  .site-header-inner {
    flex-wrap: nowrap;
    padding: var(--space-3);
    gap: var(--space-3);
  }

  body {
    /* Keep page bottom clear of the fixed bottom nav */
    padding-bottom: calc(64px + env(safe-area-inset-bottom));
  }

  .bottom-nav {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
    z-index: 60;
    display: flex;
    padding: 6px 4px calc(6px + env(safe-area-inset-bottom));
    background: var(--header-bg);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
  }

  .bottom-nav-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    min-height: 44px;
    padding: 4px 0;
    color: var(--header-fg-muted);
    font-size: 10px;
    letter-spacing: 0.02em;
    text-decoration: none;
  }

  .bottom-nav-item:hover {
    text-decoration: none;
  }

  .bottom-nav-item svg {
    width: 22px;
    height: 22px;
  }

  .bottom-nav-item--active {
    color: var(--header-fg-strong);
    font-weight: 600;
  }

  .bottom-nav-item--active svg {
    color: var(--brand);
  }
}
```

注意: 旧 `@media` ブロック内にあった `.site-header-meta` のモバイル上書き（横並び・border-top）は**復元しない**。メタはモバイルでもデスクトップと同じ「右端・縦積み」表示にする（スペック通り）。

- [ ] **Step 2: components.css のモバイルタブ縦積みを「非表示」に置き換える**

`assets/styles/components.css` の 56〜70 行目:

```css
@media (max-width: 640px) {
  /* Inside the hamburger dropdown: stack tabs vertically, full-width */
  .site-header .tabs {
    flex: none;
    flex-direction: column;
    align-items: stretch;
    gap: 2px;
  }
  .site-header .tab {
    width: 100%;
    justify-content: flex-start;
    padding: 12px 14px;
    font-size: 14px;
  }
}
```

を以下に置き換える:

```css
@media (max-width: 640px) {
  /* Bottom nav (layout.css) takes over — hide the header pill tabs */
  .site-header .tabs {
    display: none;
  }
}
```

- [ ] **Step 3: Biome チェック**

Run: `npm run check 2>&1 | tail -3`
Expected: エラー 0（`Checked N files ... No fixes applied` 等）。整形差分が出たら `npm run format` で直してから次へ

- [ ] **Step 4: Commit**

```bash
git add assets/styles/layout.css assets/styles/components.css
git commit -m "feat(nav): add fixed bottom nav styles, drop hamburger css

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

注意: この時点でモバイル幅はタブ非表示・ハンバーガーは残るが動く（nav.js はまだ存在）。中間状態はブランチ内のみで許容

---

### Task 3: テンプレート・site.json・render_page 配線 + nav.js 削除 + 再ビルド

**Files:**
- Modify: `src/templates/base.html`
- Modify: `src/site.json`（`nav_labels` の直後に `nav_labels_short` 追加）
- Modify: `scripts/build_site.py`（`render_page()` の配線変更）
- Modify: `scripts/test_build_site.py`（`RenderPageTest` 更新）
- Delete: `js/components/nav.js`
- Regenerate: `index.html` / `tankers/index.html` / `scale/index.html` / `about/index.html`

**Interfaces:**
- Consumes: `render_bottom_nav(page, nav_labels_short, nav_order)`（Task 1）、`site_config["nav_labels_short"]`
- Produces: 生成 HTML に `<nav class="bottom-nav" aria-label="主要ページ">` ラッパー + 項目リンク。テンプレート変数 `$bottom_nav`。`$nav_script` は廃止

- [ ] **Step 1: 失敗するテストを書く（RenderPageTest 更新）**

`scripts/test_build_site.py` の `RenderPageTest` を更新。`TEMPLATE` に `$bottom_nav` を追加（`NAV=[$nav]|` の直後）:

```python
    TEMPLATE = Template(
        "T=$title|D=$description|C=$canonical|"
        "OG_IMG=$og_image|FAVI=$favicon|CSS=$stylesheet|"
        "FONT=$font_href|EXTRA=[$extra_head]|BODY_CLASS=[$body_class]|HOME=$home_href|"
        "NAV=[$nav]|BOTTOM=[$bottom_nav]|BODY=$content|"
        "SCRIPTS=[$script_tags]|"
        "OG_TITLE=$og_title|OG_DESC=$og_description|"
        "TW_TITLE=$twitter_title|TW_DESC=$twitter_description|"
        "OG_ALT=$og_image_alt"
    )
```

`SITE_CONFIG` に `nav_labels_short` を追加:

```python
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
```

`test_nav_renders_inside_template` の直後にテストを追加:

```python
    def test_bottom_nav_renders_inside_template(self):
        out = render_page(self.TEMPLATE, self.SITE_CONFIG, self._page(), "BODY")
        self.assertIn('class="bottom-nav-item bottom-nav-item--active"', out)
        self.assertIn("<span>カウンター</span>", out)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `python -m unittest discover -s scripts -p "test_*.py" 2>&1 | tail -5`
Expected: `RenderPageTest` が `KeyError: 'bottom_nav'`（Template.substitute が `$bottom_nav` の値を要求）で複数 FAIL / ERROR

- [ ] **Step 3: render_page を配線する**

`scripts/build_site.py` の `render_page()` 内、2 箇所を変更。

199 行目の `nav_script = asset_root + "js/components/nav.js"` を**削除**。

`template.substitute(...)` の呼び出しから `nav_script=nav_script,` の行を**削除**し、`nav=...` の直後に `bottom_nav=` を追加:

```python
        nav=render_nav(page, site_config["nav_labels"], site_config["nav_order"]),
        bottom_nav=render_bottom_nav(
            page, site_config["nav_labels_short"], site_config["nav_order"]
        ),
```

- [ ] **Step 4: テストが通ることを確認**

Run: `python -m unittest discover -s scripts -p "test_*.py" 2>&1 | tail -3`
Expected: `OK`

- [ ] **Step 5: site.json に nav_labels_short を追加**

`src/site.json` の `nav_labels` ブロック（9〜14 行目）の直後に追加:

```json
  "nav_labels_short": {
    "home": "カウンター",
    "tankers": "タンカー",
    "scale": "ものさし",
    "about": "about"
  },
```

- [ ] **Step 6: base.html を書き換える**

`src/templates/base.html` のヘッダー部（46〜62 行目）:

```html
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-brand" href="$home_href" aria-label="あと何日？日本の石油備蓄 ホーム">
$site_brand
    </a>
    <button type="button" class="nav-toggle" id="nav-toggle" aria-controls="site-nav" aria-expanded="false" aria-label="メニューを開く">
      <span class="nav-toggle-bar" aria-hidden="true"></span>
      <span class="nav-toggle-bar" aria-hidden="true"></span>
      <span class="nav-toggle-bar" aria-hidden="true"></span>
    </button>
    <div class="site-nav" id="site-nav">
      <nav class="tabs" aria-label="セクション">
$nav
      </nav>
$header_meta    </div>
  </div>
</header>
```

を以下に置き換える（ハンバーガーと `.site-nav` ラッパー除去、タブとメタを `site-header-inner` 直下に戻す）:

```html
<header class="site-header">
  <div class="site-header-inner">
    <a class="site-brand" href="$home_href" aria-label="あと何日？日本の石油備蓄 ホーム">
$site_brand
    </a>
    <nav class="tabs" aria-label="セクション">
$nav
    </nav>
$header_meta  </div>
</header>
```

`$content` の直後（`<section class="footer-share-section"` の前）にボトムナビを追加:

```html
$content

<nav class="bottom-nav" aria-label="主要ページ">
$bottom_nav
</nav>
```

末尾付近の `<script type="module" src="$nav_script"></script>` の行を**削除**（`$script_tags` は残す）。

- [ ] **Step 7: nav.js を削除**

```bash
git rm js/components/nav.js
```

ハンバーガー開閉専用のため死コード化。参照箇所（`base.html` の `$nav_script`、`build_site.py` の `nav_script`）は Step 3 / 6 で除去済み。

- [ ] **Step 8: 再ビルドして生成 HTML を確認**

Run: `python scripts/build_site.py`
Expected: `built index.html` など 4 行

Run: `grep -c "bottom-nav-item" index.html tankers/index.html scale/index.html about/index.html`
Expected: 各ページ 4（4 リンク分。1 行に 1 項目）

Run: `grep -c "nav-toggle\|nav\.js" index.html tankers/index.html scale/index.html about/index.html || true`
Expected: 各ページ 0（grep は 0 件時に exit 1 を返すので `|| true` を付けている）

Run: `grep -n 'aria-current="page"' index.html | head -3`
Expected: ヘッダータブ 1 箇所 + ボトムナビ 1 箇所（home がアクティブ）

- [ ] **Step 9: 全テスト実行**

Run: `python -m unittest discover -s scripts -p "test_*.py" 2>&1 | tail -3` → Expected: `OK`
Run: `npm test 2>&1 | tail -5` → Expected: `fail 0`
Run: `npm run check 2>&1 | tail -3` → Expected: エラー 0

- [ ] **Step 10: Commit**

```bash
git add src/templates/base.html src/site.json scripts/build_site.py scripts/test_build_site.py index.html tankers/index.html scale/index.html about/index.html
git commit -m "feat(nav): replace mobile hamburger with fixed bottom nav bar

Nav links are always visible on mobile now (discoverability). The
last-updated meta moves back into the header row, and the hamburger
toggle script js/components/nav.js is removed as dead code.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: ブラウザ実機検証（モバイル + デスクトップ回帰）

**Files:**
- Create: `<scratchpad>/mobile-frame.html`（検証用 iframe ラッパー。プロジェクト外の scratchpad に置く）

**Interfaces:**
- Consumes: Task 3 までの生成 HTML 一式（ローカルサーバーで配信）
- Produces: 検証結果の報告のみ（コード変更なし。問題があれば該当タスクに戻って修正）

- [ ] **Step 1: ローカルサーバーを起動**

Run（プロジェクトルートで、バックグラウンド実行）: `python -m http.server 8123`

- [ ] **Step 2: モバイル幅検証用の iframe ラッパーを作る**

OS ウィンドウは約 718px 未満に縮まらないため、幅固定 iframe で ≤640px の媒体クエリを発火させる（既知の検証手法）。scratchpad に `mobile-frame.html` を作成:

```html
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>mobile 375px frame</title></head>
<body style="margin:0;display:flex;gap:16px;background:#333;padding:16px">
  <iframe src="http://localhost:8123/" style="width:375px;height:700px;border:0"></iframe>
  <iframe src="http://localhost:8123/tankers/" style="width:375px;height:700px;border:0"></iframe>
</body>
</html>
```

- [ ] **Step 3: claude-in-chrome でモバイル表示を確認**

`mobile-frame.html` をブラウザで開き、スクリーンショットで以下を確認:

- ボトムバーが画面下に固定表示され、4 項目（カウンター / タンカー / ものさし / about）がアイコン + ラベルで見える
- 表示中ページの項目だけアイコンが青（#5983f1）・ラベルが白太字
- ヘッダーは「ブランド + 最終更新」の 1 行のみ（ハンバーガーなし）
- ページ最下部までスクロールしてもフッター（運営クレジット）がバーに隠れない
- バー項目をクリックすると該当ページへ遷移し、アクティブ表示が切り替わる
- `scale/` と `about/` も iframe の src を替えて同様に確認

- [ ] **Step 4: デスクトップ回帰確認**

`http://localhost:8123/` をフルウィンドウ（>640px）で開き、スクリーンショットで以下を確認:

- ヘッダーが従来通り「ブランド + ピルタブ + 最終更新」の 1 行
- ボトムバーが表示されて**いない**
- 4 ページとも同様

- [ ] **Step 5: サーバー停止・後片付け**

http.server のバックグラウンドプロセスを停止する。問題が見つかった場合は該当タスクへ戻って修正 → 再ビルド → 再検証。コード変更が出たら Task 3 のコミットに倣って追加コミットする

---

## 完了条件（スペックの成功基準）

1. モバイル幅で 4 ページへのリンクが常時視認できる
2. 「最終更新」メタがモバイルのヘッダー右に常時表示される
3. デスクトップ表示に視覚的差分がない
4. `npm test` / `python -m unittest discover -s scripts -p "test_*.py"` / `npm run check` がすべてパスする
