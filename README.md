# 日本の石油備蓄 — あと何日？

経済産業省「石油備蓄の現況」速報 PDF と AIS データを元に、日本の石油備蓄日数とタンカー隻数を Minimal に可視化する非公式サイト。

- 元データ（備蓄日数）: https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/
- 元データ（タンカー）: https://aisstream.io/
- 公開 URL: https://oilstock.nextlabs.jp/

## ページ構成

| パス | 役割 |
|---|---|
| `/`        | カウンター（備蓄日数の秒按分表示・タンクゲージ・履歴グラフ・内訳） |
| `/tankers/`| 日本周辺タンカーの隻数集計と地図 |
| `/scale/`  | 備蓄日数を kL / バレル / VLCC隻数 / 年間消費比に換算 |
| `/about/`  | サイトの目的・データ出典・運営会社情報 |

## ディレクトリ構成

```
oil-stockpile/
├── index.html              -- カウンタータブ（生成物）
├── tankers/index.html      -- タンカータブ（生成物）
├── scale/index.html        -- 石油のものさしタブ（生成物）
├── about/index.html        -- about タブ（生成物）
├── src/
│   ├── site.json           -- ページ定義（タイトル / nav / footer 等）
│   ├── constants.json      -- 言語横断 SSOT（PEAK_REFERENCE 等）
│   ├── pages/              -- ページ固有の <main> 本文（home / tankers / scale / about）
│   └── templates/base.html -- 共通 head/header/footer テンプレート
├── assets/
│   ├── styles.css          -- CSS エントリーポイント
│   ├── styles/
│   │   ├── base.css
│   │   ├── layout.css
│   │   ├── components.css
│   │   └── pages/          -- home.css / tankers.css / scale.css / about.css
│   ├── favicon.svg
│   └── og-image.png        -- OGP 画像（毎日 generate_ogp.py が再生成）
├── js/
│   ├── core/               -- data / dom / format / escape ヘルパ
│   ├── components/         -- counter / chart / kpi / nav / share / tank-gauge（内訳ドーナツ） / tanker-map
│   └── pages/              -- home.js / tankers.js / scale.js / about.js
├── data/
│   ├── snapshots.json      -- 備蓄日数（毎日自動更新）
│   └── tankers.json        -- タンカー集計（毎時自動更新）
├── scripts/
│   ├── lib/
│   │   ├── paths.py        -- リポジトリ内パスの一元定義
│   │   ├── io.py           -- JSON read/write（プロジェクト共通整形）
│   │   └── constants.py    -- src/constants.json ローダ
│   ├── build_site.py       -- src から公開 HTML を生成 + SSOT 整合検証
│   ├── fetch_pdf.py        -- 備蓄 PDF 取得・パース・JSON 更新
│   ├── fetch_tankers.py    -- AIS WebSocket サンプラ
│   ├── generate_ogp.py     -- OGP 画像生成（snapshots → assets/og-image.png）
│   ├── test_*.py           -- ユニットテスト
│   └── requirements.txt
├── .github/workflows/
│   ├── fetch-daily.yml     -- 備蓄日数の毎朝取得 (07:00 JST) + OGP 再生成
│   ├── fetch-tankers.yml   -- タンカーの毎時取得
│   └── test.yml            -- ユニットテスト + 生成 HTML の drift 検知
├── docs/                   -- プロジェクト設計・参考資料（後述）
├── biome.json
├── package.json            -- Biome / Husky / lint-staged
├── robots.txt
└── sitemap.xml
```

## 設定の単一情報源 (SSOT)

言語横断で参照する定数は `src/constants.json` に集約しています。

| キー | 用途 | 参照側 |
|---|---|---|
| `peak_reference.days` / `.source` | タンクゲージ最大値の基準 | Python: `scripts/lib/constants.py`、JS: `js/core/data.js` の `PEAK_REFERENCE` |

JS は `import` できないためミラーを保持していますが、`scripts/build_site.py` の `verify_constants_in_sync()` が両者の drift を検出し、不一致なら build を失敗させます（CI でも実行）。

## データ更新の自動化

### 備蓄日数（毎朝 07:00 JST）

1. `.github/workflows/fetch-daily.yml` の cron が `scripts/fetch_pdf.py` を起動
2. 経産省の `oil_daily.pdf` をダウンロード（curl-cffi で実ブラウザ TLS フィンガープリントを模倣、リトライ 3 回）
3. `pdfplumber` でテキスト抽出 → 全角数字を半角化 → 正規表現で 6 フィールド抽出
4. バリデーション
   - `total` が 50〜500 日の範囲内
   - 内訳合計と total の差が ±2 以内
   - 前日比の絶対差が 30 日以内
5. 既存 `data/snapshots.json` と統合（`asOf` キーで重複排除、PDF 優先）
6. 続けて `scripts/generate_ogp.py` が `assets/og-image.png` を再生成
7. 差分があれば `data/snapshots.json` と `assets/og-image.png` を rebase 後に commit & push
8. 失敗時は何もコミットせず Actions ログにエラーを残す

#### 手動実行

GitHub UI: Actions タブ → "Fetch oil_daily.pdf" → "Run workflow"。

ローカル:

```bash
cd oil-stockpile
pip install -r scripts/requirements.txt
python scripts/fetch_pdf.py            # 本番（snapshots.json を書き換え）
python scripts/fetch_pdf.py --dry-run  # パースのみ、書き換えなし
```

#### 失敗したら（自動化が壊れた時の手動フォールバック）

1. Actions のログでエラー内容を確認（PDF レイアウト変更、ネットワーク等）
2. 直近の値を `oil_daily.pdf` から目視で読み取る
3. `data/snapshots.json` の末尾に 1 行追加:
   ```json
   { "published": "YYYY-MM-DD", "asOf": "YYYY-MM-DD",
     "total": NNN, "national": NN, "private": NN, "joint": N }
   ```
4. commit & push
5. パーサ自体の修正が必要なら `scripts/fetch_pdf.py` を直す

スクリプトは「失敗時は何も書かない」をデフォルトにしているため、放置していても **サイトが壊れたデータを表示することはない**（古いデータのまま停滞する）。古さが 14 日を超えると画面に警告バナーが出ます。

#### バリデーションを変える

`scripts/fetch_pdf.py` の `validate()` 内の閾値を編集。新規 commit で次の cron 実行から反映。

### タンカー集計（毎時）

`/tankers/` ページの数字は `aisstream.io` の AIS WebSocket ストリームから集計します。

1. 毎時 17 分 UTC に `fetch-tankers.yml` が起動
2. `scripts/fetch_tankers.py` が aisstream.io WebSocket に接続、8 分間サンプリング（日本周辺バウンディングボックス: 24-46N / 122-146E）
3. ShipStaticData / PositionReport を集めて MMSI でユニーク化
4. 船種コード 80-89（Tanker）のみ抽出、destination を日本港名 / UN-LOCODE と部分一致
5. 集計（隻数・上位港・船舶位置）を `data/tankers.json` に書き込み
6. 差分があれば commit。push が他の commit と競合した場合は最新 main で 3 回まで rebase&retry

#### 表示しているもの／表示していないもの

| 項目 | 状態 | 理由 |
|---|---|---|
| 海域内のタンカー隻数 | 表示 | サンプル時間中に静的データを送信した数 |
| うち日本港 destination の隻数 | 表示 | destination の文字列マッチで判定 |
| 上位の destination 港 | 表示 | 集計値のみ |
| 推計バレル数・リットル数 | **非表示** | DWT→バレル換算は誤差が大きく誤解を招くため |
| 個別船舶の MMSI / 船名 / 位置 | 表示 | AIS は IMO 規定により公開放送される情報。`aisstream.io` の業界慣行に従い地図ポップアップで表示 |
| 実際の月次原油輸入量 | リンクのみ | 財務省貿易統計（HS 2709.00）を参照 |

#### AISSTREAM_API_KEY のセットアップ

1. https://aisstream.io/ で GitHub 認証してアカウント作成、API key を取得
2. リポジトリの **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `AISSTREAM_API_KEY`、Value: 取得したキー
4. `.github/workflows/fetch-tankers.yml` が毎時 cron で動作開始

#### ローカル実行

```bash
export AISSTREAM_API_KEY=xxx
python scripts/fetch_tankers.py --duration 720           # 本番モード
python scripts/fetch_tankers.py --duration 60 --dry-run  # 短時間、書き込まない
```

#### 失敗したら

- aisstream.io が BETA のため、突然プロトコル変更や障害があり得ます
- 失敗時は `tankers.json` を更新せず Actions ログにエラー
- 6 時間以上更新が止まると `/tankers/` ページに警告バナー表示
- 復旧後は手動で `workflow_dispatch` 実行 or 次の cron を待つ

### OGP 画像（毎日）

SNS シェア時に表示される OGP 画像（`assets/og-image.png`、1200×630）は、毎日の備蓄データ取得後に `scripts/generate_ogp.py` が再生成します。

1. `fetch-daily.yml` 内で `python scripts/fetch_pdf.py` の後に `python scripts/generate_ogp.py` を実行
2. `data/snapshots.json` の最新値を読み、Pillow で 1200×630 の PNG を描画
3. 内容: 「あと何日？日本の石油備蓄」 / 「N 日分」 / 充填率タンクゲージ / 出典・データ時点
4. 差分があれば `assets/og-image.png` も `data/snapshots.json` と一緒に commit & push

「動的生成」ではなく、データ更新粒度（日次）に合わせた事前生成方式です。

#### ローカル実行

```bash
python scripts/generate_ogp.py            # 本番（assets/og-image.png を上書き）
python scripts/generate_ogp.py --dry-run  # 描画ロジックのスモーク確認、書き出さず終了
```

ローカルでは Windows なら游ゴシック / メイリオ、macOS なら Arial Unicode、Linux なら Noto Sans CJK を自動探索します。GitHub Actions では `fonts-noto-cjk` を apt で入れています。

#### 失敗したら

- 失敗時は `assets/og-image.png` を更新せず Actions ログにエラー
- 旧 OGP 画像が残るので「壊れた画像をシェア」状態にはならない
- `scripts/test_generate_ogp.py` でロジック単位のテストをカバー（`test.yml` で自動実行）

## HTML の編集とビルド

公開 HTML（`index.html` / `tankers/index.html` / `scale/index.html` / `about/index.html`）はすべて `scripts/build_site.py` が `src/` から生成する **生成物** です。直接編集しないでください。

| 編集対象 | 役割 |
|---|---|
| `src/pages/*.html`         | ページ本文（`<main>` 内） |
| `src/templates/base.html`  | 共通 head / header / footer |
| `src/site.json`            | title / description / nav / footer / canonical / OGP |
| `src/constants.json`       | 言語横断定数（PEAK_REFERENCE 等） |

ビルド:

```bash
python scripts/build_site.py
```

build 時に `verify_constants_in_sync()` が `src/constants.json` ↔ `js/core/data.js` の整合をチェックします。`PEAK_REFERENCE.days` または `.source` を更新する場合は両方を同じ値に揃えてください（CI でも検出）。

CI（`test.yml`）では `python scripts/build_site.py` を実行し、生成 HTML が staged のものと一致しない場合は失敗します（コミット忘れ防止）。

## テスト

パーサ・バリデータ・マージ・タンカー集計・OGP 描画・ビルドロジック・JSON I/O は `scripts/test_*.py` でユニットテストされています。

```bash
python -m unittest discover -s scripts -p 'test_*.py' -v
```

`scripts/` / `src/` / `assets/` / `js/` 配下を変更した PR / push では `.github/workflows/test.yml` が自動実行されます。

## コード整形と pre-commit

JS / CSS / JSON / Markdown の整形と lint には Biome を使います。HTML 生成物と `src/**/*.html`、自動更新データの `data/**/*.json` は Biome 対象外です。

```bash
npm install
npm run check   # Biome のチェック
npm run format  # Biome の自動整形
```

`npm install` 後は Husky が pre-commit hook を設定し、コミット時に `lint-staged` 経由で staged files だけ `biome check --write` を実行します。hook 本体は `.husky/pre-commit` です。

## ローカル動作確認

ES Modules を使うため `file://` 直開きでは動作しません。HTTP サーバが必須。

```bash
cd oil-stockpile
python scripts/build_site.py    # src/ を編集している場合
python -m http.server 8080
# → http://localhost:8080
```

### 動作確認チェックリスト

- [ ] 1 秒ごとに秒値が変わる（`60→00` で分繰り上がり、`23→00` で日が 1 減る）
- [ ] タンクゲージの fill 高さ・色が現在値と一致
- [ ] 充填率パーセントがタンク横に表示される
- [ ] グラフの点をホバー / フォーカスすると公表日・内訳が下のヒント文に出る
- [ ] 「3 区分の内訳も表示する」チェックで Y 軸が再スケールし国家・民間・産油国共同の線が出る
- [ ] `<details>` を Tab+Enter で開閉できる
- [ ] X シェアボタンで新規タブが開きツイート文が prefill される
- [ ] コピーボタンで `日本の石油備蓄、いま NNN 日分。 https://...` がクリップボードに入る
- [ ] フッターに出典・データ時点・公表日が表示される
- [ ] スマホ幅（375px）でレイアウト破綻しない
- [ ] 14 日以上 asOf を更新しないと古さ警告が出る
- [ ] `/tankers/` で隻数・上位港・地図ピンが表示される

## デプロイ（GitHub Pages）

公開 URL は `https://oilstock.nextlabs.jp/`。コード内の絶対 URL は `src/site.json` の `site.url` / `site.og_image` と `js/core/data.js` の `SITE_CONFIG.url` に集約されています。

### 初回セットアップ

1. リポジトリ `nextlabs-dev/oil-stockpile` の **Settings → Pages**
   - Source: **Deploy from a branch**
   - Branch: **main** / **/ (root)**
2. **Settings → Actions → General → Workflow permissions** を **Read and write permissions** に変更（Bot が `data/*.json` と `assets/og-image.png` を自動 push できるように）
3. **Settings → Secrets and variables → Actions** に `AISSTREAM_API_KEY` を登録（タンカータブが必要な場合）
4. main へ push → 初回ビルドが走り、〜1 分で公開

### デプロイ後の確認

- カウンターが秒単位で動くこと
- `/assets/og-image.png` が 1200×630 で配信されていること
- `https://www.opengraph.xyz/url/...` などで OGP メタが取れていること
- 実際に X からツイートを送り、リンクプレビュー画像が表示されること

### カスタムドメインに切り替える場合

1. **Settings → Pages → Custom domain** で独自ドメインを設定 + DNS で CNAME を `nextlabs-dev.github.io` に向ける
2. 絶対 URL を新ドメインに置換:
   - `src/site.json` の `site.url` / `site.og_image`
   - `js/core/data.js` の `SITE_CONFIG.url`
   - `robots.txt` の `Sitemap`
   - `sitemap.xml` の各 `<loc>`
   - 本 README 冒頭の「公開 URL」
3. `python scripts/build_site.py` を実行して生成 HTML を再ビルド & commit

## 設計メモ

- Vanilla HTML / JS（ES Modules）/ CSS。HTML は軽量な Python スクリプトで共通テンプレートから生成
- 外部 CDN は Google Fonts (Inter / Noto Sans JP) と `/tankers/` 用 Leaflet のみ
- データ取得は GitHub Actions + Python（`pdfplumber` / `curl-cffi` / `websockets` / `Pillow`）。コスト $0
- 「リアルタイム」表記は速報 PDF が日次更新されているため整合
- タンクゲージ基準値・Y 軸スケール・色閾値はすべて根拠を出典で示す方針
- 失敗時は古いデータを保持＋警告 — 黙ってデータを壊さないことを優先
- 言語横断する定数は `src/constants.json` に SSOT を置き、build で drift を検出

## 関連ドキュメント

`docs/` 以下に設計書・参考資料を配置しています（[`docs/README.md`](docs/README.md) も参照）。

- `docs/project/01-requirements/` — 要件定義（システム概要 / 実装済み機能 / 計画機能 / 非機能要件 / ユーザーストーリー）
- `docs/project/02-behavior/` — 振る舞い定義（シナリオ）
- `docs/project/03-domain/` — ドメインモデル
- `docs/project/04-design/` — 設計（アーキテクチャ等）
- `docs/references/` — 元設計書・戦略整理・競合分析
  - [`oil-stockpile-design-v2.0.md`](docs/references/oil-stockpile-design-v2.0.md)
  - [`oil-stockpile-design-v2.0-concerns.md`](docs/references/oil-stockpile-design-v2.0-concerns.md)
  - [`oil-stockpile-design-v2.0-feasibility.md`](docs/references/oil-stockpile-design-v2.0-feasibility.md)
  - [`oil-stockpile-strategic-review.md`](docs/references/oil-stockpile-strategic-review.md)
  - [`gontarobee-analysis.md`](docs/references/gontarobee-analysis.md)
- `docs/tasks/` — 個別タスクの作業ノート
