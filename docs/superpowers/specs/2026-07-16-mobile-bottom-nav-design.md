# モバイルボトムナビバー 設計書

日付: 2026-07-16
ブランチ: `tkysi-mi/mobile-nav-redesign`
ステータス: 設計確定（実装前）

## 背景と目的

現在のモバイルナビ（≤640px）はハンバーガーボタン + ドロップダウンパネル。ナビがボタンの中に
隠れているため、カウンター以外のページ（タンカー / 石油のものさし / about）の存在に気づかれ
にくい。**発見性の改善**を目的に、全ページへの導線を常時可視化する画面下固定のボトムナビ
バーへ置き換える。

検討した代替案: ヘッダー常時タブ行（横スクロール）、現行ハンバーガーの改良（ラベル付き）。
ブラウザモックアップ比較の結果、常時表示 + 親指到達性で発見性を根本解決できるボトムナビ
バーを採用。

## スコープ

- 対象: モバイル表示（`max-width: 640px`）のナビゲーションのみ
- 対象外: デスクトップ表示（>640px）は一切変更しない（ヘッダー内ピルタブを維持）

## UI・UX 仕様

### ボトムナビバー

- 画面下に `position: fixed` で常時表示（スクロールによる自動非表示なし）。全 4 ページ共通
- 高さ約 58px + `padding-bottom: env(safe-area-inset-bottom)`（iOS ホームインジケータ対応）
- 背景 `var(--header-bg)`（#0f1535）、上罫線 `rgba(255, 255, 255, 0.1)`。ヘッダーと対の見た目
- 項目は 4 つ均等割り（`flex: 1`）: 線画 SVG アイコン（22px、stroke-width 1.8）+ ラベル 10px
- ラベル: カウンター / タンカー / ものさし / about（`scale` のみ「石油のものさし」から短縮）
- アクティブページ: アイコンをブランド青 `var(--brand)`（#5983f1）、ラベルを白（
  `var(--header-fg-strong)`）・太字に。アンカーに `aria-current="page"` を付与
- 非アクティブ: アイコン・ラベルとも `var(--header-fg-muted)`（#9ea7c0）
- 各項目のタップ領域は 44px 以上を確保
- アイコン SVG は `aria-hidden="true"`（テキストラベルがアクセシブルネーム）
- アイコンの意匠: カウンター=ゲージ（半円+針）、タンカー=船体+ブリッジ、ものさし=定規、
  about=丸囲み i（採用モックアップ準拠）

### ヘッダー（モバイル）

- ブランド + 「最終更新」メタ（右端、縦積み小型表示）のみの 1 行に簡素化
- ハンバーガーボタン・ドロップダウンパネルは完全廃止

### 本文・フッター

- バーで本文・フッターが隠れないよう、ページ下部にバー高さ分（58px + セーフエリア）の
  余白を追加

## 実装構造

### 変更ファイル

| ファイル | 変更内容 |
| --- | --- |
| `src/templates/base.html` | `nav-toggle` ボタンと `.site-nav` ラッパーを削除しヘッダーを brand + tabs + meta のフラット構造に戻す。フッター前に `$bottom_nav` プレースホルダ追加。`$nav_script` の `<script>` 行を削除 |
| `src/site.json` | `nav_labels_short` を追加（`scale: "ものさし"`、他は `nav_labels` と同値） |
| `scripts/build_site.py` | `render_bottom_nav()` を新設: `nav_order` を回して `<a>` + インライン SVG + `aria-current` を生成（`render_nav()` と同パターン）。アイコン SVG はキー別定数として同ファイル内に定義。`nav_script` 変数と参照を削除 |
| `js/components/nav.js` | 削除（ハンバーガー開閉専用のため死コード化） |
| `assets/styles/layout.css` | `.nav-toggle` 系ルール全削除。モバイル媒体クエリ内の `.site-nav` ドロップダウンルールを `.bottom-nav` スタイルへ置換。ヘッダーメタはモバイルでも右端縦積みに統一 |
| `assets/styles/components.css` | モバイルのタブ縦積みルールを削除し、≤640px では `.site-header .tabs { display: none }` |

### データフロー

`src/site.json`（nav_order / nav_labels / nav_labels_short / pages[].nav / active_nav）
→ `scripts/build_site.py`（`render_nav()` = デスクトップタブ、`render_bottom_nav()` =
モバイルバー）→ 生成 HTML 4 ページ。リンク定義の SSOT は従来どおり site.json。

## テスト・検証

- `scripts/test_build_site.py` に `render_bottom_nav` のユニットテストを追加
  （4 項目生成・href・`aria-current` 位置・短縮ラベル適用）
- `nav_script` 削除に伴う既存テストの期待値更新
- `python scripts/build_site.py` でビルドし、生成 4 ページを確認
- ブラウザ実機検証: ローカルサーバー + 375px 幅 iframe でモバイル表示を確認
  （OS ウィンドウが約 718px 未満に縮まないため iframe 手法を使う）。
  デスクトップ幅のリグレッション（タブ表示・バー非表示）も確認
- `npm test` / `npm run check`（Biome）/ Python テストがすべてパスすること

## エッジケース

- iOS セーフエリア: `env(safe-area-inset-bottom)` で対応
- CSP: インライン SVG は `style-src` / `script-src` に影響せず、CSP 変更不要
- 開閉 JS が消えるため、Esc・外側クリック・フォーカス管理の考慮自体が不要になる
- 641px 境界: 既存の `max-width: 640px` メディアクエリをそのまま使用

## 成功基準

1. モバイル幅で 4 ページへのリンクが常時視認できる
2. 「最終更新」メタがモバイルのヘッダー右に常時表示される
3. デスクトップ表示に視覚的差分がない
4. 全テスト（`npm test` / `scripts/test_build_site.py` などの Python テスト / `npm run check`）がパスする
