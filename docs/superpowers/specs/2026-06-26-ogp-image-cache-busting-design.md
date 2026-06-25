# OGP 画像の cache-busting 設計

- 日付: 2026-06-26
- 対象ブランチ: `tkysi-mi/ogp-image-cache-fix`
- ステータス: 設計承認済み（実装計画待ち）

## 背景 / 問題

本番サイトを X（旧 Twitter）で共有すると、OGP プレビュー画像が
`assets/og-image.png` の最新版ではなく、以前の画像のまま表示される。

原因は X 側の OGP キャッシュである。X のカードクローラーは画像を **URL 単位**で
キャッシュする（公式トラブルシュートに「画像はカードデータと別に URL キーで
キャッシュされ、URL が同じだと更新されない」と明記）。本サイトは:

- og:image / twitter:image が固定 URL `https://oilstock.nextlabs.jp/assets/og-image.png`
  （`src/site.json` → `build_site.py` が `base.html` に焼き込み）
- その URL の **中身だけ**が毎日 cron（`fetch-daily.yml` → `generate_ogp.py`）で
  上書きされる

という「URL 不変・中身可変」構造のため、X は初回クロール時の古い画像を出し続ける。
Card Validator は X リブランド後に廃止・不安定化しており、手動パージは当てにできない。

さらに、現状の cron は `og-image.png` と `snapshots.json` のみ再生成・コミットし、
**HTML は再ビルドしていない**。そのため og:image の URL を更新する運用上の口が存在しない。

## 目標 / 非目標

**目標**
- 画像を更新したら、X 共有プレビューにも新しい画像が反映されるようにする
- OGP 画像は現状どおり「毎日 cron 時点の数字」で最新化する（粒度は毎日）

**非目標**
- 既に投稿済みのツイートのカードを更新すること（X の仕様上不可能）
- OGP 画像のレイアウト・内容そのものの変更
- `generate_ogp.py` の数字算出ロジックの変更

## 採用案: コンテンツハッシュによる cache-busting（案A）

`build_site.py` が `assets/og-image.png` の SHA-256 先頭8桁 `h` を計算し、
og:image / twitter:image を `https://oilstock.nextlabs.jp/assets/og-image.png?v=h`
として HTML に焼き込む。X はクエリ込みの URL を別物として扱い、画像が変わるたびに
再クロールする。

### 却下した代替案

- **案B（日付クエリ `?v=20260626`）**: 実装は簡単だが、画像が同一でも日付で URL が
  変わり無駄な再クロール差分が出る。JST 境界の定義も必要。画像内容と連動しない。
- **案C（ファイル名に日付 `og-image-20260626.png`）**: URL は確実に別物になるが、
  古いファイルの掃除・参照整合・容量増を伴い複雑。YAGNI。

案A は「画像が変わった時だけ URL が変わり、変わらなければ変わらない」という
cache-busting の理想形を、追加の状態ファイルなしで実現できるため採用する。

## データフロー（`fetch-daily.yml` cron 毎日）

```
fetch_pdf.py    → data/snapshots.json 更新
generate_ogp.py → assets/og-image.png 更新（その日の数字）
build_site.py   → og-image.png のハッシュ h を計算
                  og:image / twitter:image を .../assets/og-image.png?v=h に焼いて
                  index.html, tankers/index.html, scale/index.html, about/index.html を再生成
Commit if changed → snapshots.json, og-image.png, *.html をコミット & push
```

順序保証（`generate_ogp` → `build_site`）により、HTML に焼かれるハッシュは
常にその時点の `og-image.png` と一致する。

## 変更点

### 0. `scripts/lib/paths.py`

- `OG_IMAGE_PATH = ASSETS_DIR / "og-image.png"` 定数を追加し、`build_site.py` と
  `generate_ogp.py`（現状は `DEFAULT_OUTPUT = ASSETS_DIR / "og-image.png"` をローカル定義）
  で共有する。パスの二重定義を避ける（SSOT）。

### 1. `scripts/build_site.py`

- `compute_og_image_version(path) -> str` ヘルパーを追加。`path.read_bytes()` の
  SHA-256 先頭8桁（hex）を返す。`og-image.png` が存在しない場合は例外を送出して
  **fail fast**（必須アセットの欠損をクエリ無しで静かに継続して隠さない）。
- **`render_page` の純粋性を保つ**：`render_page` は「I/O から切り離した純粋関数」
  として設計・テストされている（`test_build_site.py` 冒頭コメント）。ハッシュ計算を
  関数内に入れず、`render_page(..., og_image_version: str)` 引数を追加して内部で
  `og_image = site["og_image"]; if og_image_version: og_image += f"?v={og_image_version}"`
  とする。`base.html` は og:image・twitter:image の両方が `$og_image` を参照するため、
  1 箇所の変更で両方に反映される。
- `main()`（I/O 境界）で `compute_og_image_version(OG_IMAGE_PATH)` を 1 回計算し、
  各ページの `render_page` に渡す。

### 2. `.github/workflows/fetch-daily.yml`

- 「Generate OGP image」ステップの後に「Build site」ステップ
  （`python scripts/build_site.py`）を追加。
- 「Commit if changed」の `changed_paths` 判定に HTML 4ファイル
  （`index.html`, `tankers/index.html`, `scale/index.html`, `about/index.html`）を追加。

### 3. `src/site.json`

- `og_image` は base URL のまま（クエリは `build_site.py` が動的付与）。**変更なし**。
  バージョン情報を site.json に持たせると二重管理になるため持たせない。

## エラーハンドリング

- `generate_ogp.py` 失敗時は既存 `og-image.png` を維持して exit 1 →
  フロー停止（既存方針どおり、人間に通知）。`build_site` には進まない。
- `build_site.py` は `og-image.png` 欠損時に exit 1。CI が赤くなり人間に通知。

## テスト / 検証

**ユニットテスト（`scripts/test_build_site.py`）**
- 生成 HTML の og:image / twitter:image に `?v=<8桁hex>` が付与されることを検証。
- `?v=` の値が、その時点の `og-image.png` の SHA-256 先頭8桁と一致することを検証。
- 既存の render 系テストが新しい og_image 値で壊れないよう fixture を調整。

**実装前の重要検証（手戻り防止）**
- 現リポジトリで `build_site.py` を実行し、コミット済み HTML との diff が
  **og:image / twitter:image 行のみ**であることを確認する。
  src とコミット済み HTML がズレていると、毎日フローで予期せぬ差分が出るため、
  着手時に最初に潰す。

**手動検証（outer loop）**
- ローカルで `build_site.py` を実行し、4ページすべての og:image / twitter:image に
  `?v=` が付き、ハッシュが画像内容と一致することを確認。
- 本番反映後、X 共有プレビューで新しい画像が出ることを事後確認（X 仕様上、
  反映は新規共有のみ・既存ツイートは不変）。

## 運用上の注意

- **生成 HTML はコミット済み `og-image.png` と常に同期させる**。`test.yml` の
  「Verify generated HTML is in sync with src/」が、push 毎に `build_site.py` を
  実行してコミット済み HTML との差分が無いことを検証するため、`scripts/` `src/`
  `assets/` `js/` を変更したら `build_site.py` を実行して 4 HTML をコミットする。
  - 当初は「ローカルの `?v=` 差分はコミットしない（CI 任せ）」運用を想定したが、
    上記同期ガードと両立しないため撤回した。`?v=` はコミット済み画像から決定的に
    算出されるので、コミット済み画像と HTML が揃っていればローカル/CI で同一。
- 毎日 cron（`fetch-daily.yml`）は `og-image.png` を再生成した後に `build_site.py` を
  走らせ、画像・HTML をセットでコミットするため、同期は自動的に保たれる。
- 注意点: `og-image.png` を再生成したら必ず `build_site.py` も走らせてセットで
  コミットする（画像だけ／HTML だけのコミットは同期を壊す）。
