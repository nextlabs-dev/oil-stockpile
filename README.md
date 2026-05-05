# 日本の石油備蓄 — あと何日？

経済産業省「石油備蓄の現況」速報PDFを元に、日本の石油備蓄日数を Minimal に可視化する非公式サイト。

- 元データ: https://www.enecho.meti.go.jp/statistics/petroleum_and_lpgas/pl001/
- 公開URL: （デプロイ後に記入）

## 構成

```
oil-stockpile/
├── index.html              -- カウンタータブ
├── tankers/
│   └── index.html          -- タンカータブ
├── scale/
│   └── index.html          -- 石油のものさしタブ
├── about/
│   └── index.html          -- about タブ（サイトの目的・出典・運営）
├── assets/
│   ├── styles.css
│   ├── favicon.svg
│   └── og-image.png        -- 後日作成（1200x630）
├── js/
│   ├── data.js             -- 設定値とデータ読み込みヘルパ（手動メンテ）
│   ├── counter.js          -- F-01 リアルタイムカウンター
│   ├── tank-gauge.js       -- F-02 タンクゲージ
│   ├── chart.js            -- F-03 推移グラフ
│   ├── breakdown.js        -- 3区分内訳
│   ├── share.js            -- F-05 シェア
│   ├── main.js             -- カウンタータブのエントリーポイント
│   ├── tankers-page.js     -- タンカータブのエントリーポイント
│   └── scale-page.js       -- 石油のものさしタブのエントリーポイント
├── data/
│   ├── snapshots.json      -- 備蓄日数（毎日自動更新）
│   └── tankers.json        -- タンカー集計（毎時自動更新）
├── scripts/
│   ├── fetch_pdf.py        -- 備蓄PDF取得・パース・JSON更新
│   ├── fetch_tankers.py    -- AIS WebSocket サンプラ
│   ├── test_fetch_pdf.py
│   ├── test_fetch_tankers.py
│   └── requirements.txt
├── .github/workflows/
│   ├── fetch-daily.yml     -- 備蓄日数の毎朝取得 (07:00 JST)
│   ├── fetch-tankers.yml   -- タンカーの毎時取得
│   └── test.yml            -- ユニットテスト CI
├── robots.txt
└── sitemap.xml
```

## データ更新の自動化

毎朝 07:00 JST（22:00 UTC）に GitHub Actions が走り、`oil_daily.pdf` を取得して `data/snapshots.json` を更新します。

### 仕組み

1. `.github/workflows/fetch-daily.yml` の cron が `scripts/fetch_pdf.py` を起動
2. 経産省の `oil_daily.pdf` をダウンロード（リトライ3回）
3. `pdfplumber` でテキスト抽出 → 全角数字を半角化 → 正規表現で6フィールド抽出
4. バリデーション
   - `total` が 50〜500 日の範囲内
   - 内訳合計と total の差が ±2以内
   - 前日比の絶対差が 30日以内
5. 既存 `data/snapshots.json` と統合（asOf キーで重複排除、PDF優先）
6. 差分があれば commit → push（GitHub Pages が自動デプロイ）
7. 失敗時は何もコミットせず Actions ログにエラーを残す

### 手動実行

GitHub UI: Actions タブ → "Fetch oil_daily.pdf" → "Run workflow" で即時実行。

ローカルでも実行可能:

```bash
cd oil-stockpile
pip install -r scripts/requirements.txt
python scripts/fetch_pdf.py            # 本番（snapshots.json を書き換え）
python scripts/fetch_pdf.py --dry-run  # パースだけ実行、書き換えなし
```

### 失敗したら（自動化が壊れた時の手動フォールバック）

1. Actions のログでエラー内容を確認（PDF レイアウト変更、ネットワーク等）
2. 直近の値を `oil_daily.pdf` から目視で読み取る
3. `data/snapshots.json` の末尾に1行追加:
   ```json
   { "published": "YYYY-MM-DD", "asOf": "YYYY-MM-DD",
     "total": NNN, "national": NN, "private": NN, "joint": N }
   ```
4. commit & push
5. パーサ自体の修正が必要なら `scripts/fetch_pdf.py` を直す

スクリプトは「失敗時は何も書かない」をデフォルトにしているため、放置していても**サイトが壊れたデータを表示することはない**（古いデータのまま停滞する）。古さが14日を超えると画面に警告バナーが出る。

### バリデーションを変える

`scripts/fetch_pdf.py` の `validate()` 内の閾値（total範囲・内訳乖離・前日比）を編集。新規 commit で次の cron 実行から反映。

### テスト

パーサ・バリデータ・マージ・タンカー集計のロジックは `scripts/test_*.py` でユニットテストされています。

```bash
python -m unittest discover -s scripts -p 'test_*.py'
```

`scripts/` 以下を変更した PR / push では `.github/workflows/test.yml` が自動実行され、テストが落ちた場合はマージ前に検知できます。

## タンカータブ（`/tankers/`）

`aisstream.io` の AIS WebSocket ストリームから日本周辺のタンカー隻数を集計し、`/tankers/` ページで表示します。

### 表示しているもの／表示していないもの

| 項目 | 状態 | 理由 |
|---|---|---|
| 海域内のタンカー隻数 | 表示 | サンプル時間中に静的データを送信した数 |
| うち日本港 destination の隻数 | 表示 | destination の文字列マッチで判定 |
| 上位の destination 港 | 表示 | 集計値のみ |
| 推計バレル数・リットル数 | **非表示** | DWT→バレル換算は誤差が大きく誤解を招くため |
| 個別船舶の MMSI / 船名 / 位置 | **非表示** | 規約・プライバシー上の保守的判断 |
| 実際の月次原油輸入量 | リンクのみ | 財務省貿易統計（HS 2709.00）を参照 |

### AISSTREAM_API_KEY のセットアップ

1. https://aisstream.io/ で GitHub 認証してアカウント作成、API key を取得
2. リポジトリの **Settings → Secrets and variables → Actions → New repository secret**
3. Name: `AISSTREAM_API_KEY`、Value: 取得したキー
4. `.github/workflows/fetch-tankers.yml` が毎時 cron で動作開始

### 自動化の仕組み

1. 毎時 0分 UTC に `fetch-tankers.yml` が起動
2. `scripts/fetch_tankers.py` が aisstream.io WebSocket に接続、8分間サンプリング
3. ShipStaticData / PositionReport を集めて MMSI でユニーク化
4. 船種コード 80-89 (Tanker) のみ抽出、destination を日本港名/UN-LOCODE と部分一致
5. 集計（隻数、上位港）を `data/tankers.json` に書き込み
6. 差分があれば commit → push

### ローカル実行

```bash
export AISSTREAM_API_KEY=xxx
python scripts/fetch_tankers.py --duration 480           # 本番モード
python scripts/fetch_tankers.py --duration 60 --dry-run  # 短時間、書き込まない
```

### 失敗したら

- aisstream.io が BETA のため、突然プロトコル変更や障害があり得ます
- 失敗時は `tankers.json` を更新せず Actions ログにエラー
- 6時間以上更新が止まると `/tankers/` ページに警告バナー表示
- 復旧後は手動で workflow_dispatch 実行 or 次の cron を待つ

## 設定値の手動メンテ

`js/data.js` には以下が残っています（自動化対象外）:

- `PEAK_REFERENCE.days` — タンクゲージ最大値の基準。新しい高値が観測されたら更新
- `SITE_CONFIG.url` — 本番URL。デプロイ時に書き換え
- `STALE_THRESHOLD_DAYS` — 古さ警告のしきい値（既定 14日）

## ローカル動作確認

ES Modules を使うため `file://` 直開きでは動作しない。HTTPサーバが必須。

```bash
cd oil-stockpile
python -m http.server 8080
# → http://localhost:8080
```

## 動作確認チェックリスト

- [ ] 1秒ごとに秒値が変わる（`60→00` で分繰り上がり、`23→00` で日が1減る）
- [ ] タンクゲージの fill 高さ・色が現在値と一致
- [ ] 充填率パーセントがタンク横に表示される
- [ ] グラフの点をホバー/フォーカスすると公表日・内訳が下のヒント文に出る
- [ ] 「3区分の内訳も表示する」チェックでY軸が再スケールし国家・民間・産油国共同の線が出る
- [ ] `<details>` を Tab+Enter で開閉できる
- [ ] X シェアボタンで新規タブが開きツイート文が prefill される
- [ ] コピーボタンで `日本の石油備蓄、いまNNN日分。 https://...` がクリップボードに入る
- [ ] フッターに出典・データ時点・公表日が表示
- [ ] スマホ幅（375px）でレイアウト破綻しない
- [ ] 14日以上 asOf を更新しないと古さ警告が出る

## デプロイ（GitHub Pages）

1. リポジトリを作成し push
2. Settings → Pages → Source: `main` ブランチ `/ (root)`
3. Settings → Actions → General → Workflow permissions: **Read and write permissions** をON（Bot が `data/snapshots.json` を push できるように）
4. （任意）カスタムドメインを CNAME で設定
5. `js/data.js` の `SITE_CONFIG.url` を実 URL に書き換える
6. `index.html` 内の `oil-stockpile.example` を実 URL に置換（canonical / og:url / og:image）
7. `robots.txt` と `sitemap.xml` の Sitemap / loc も同様に置換

## 設計メモ

- Vanilla HTML / JS (ES Modules) / CSS のみ。ビルドステップなし
- 外部CDNは Google Fonts (Inter) のみ
- データ取得は GitHub Actions + Python pdfplumber（コスト$0）
- 「リアルタイム」表記は速報PDFが日次更新されているため整合
- タンクゲージ基準値・Y軸スケール・色閾値はすべて根拠を出典で示す方針
- 失敗時は古いデータを保持＋警告 — 黙ってデータを壊さないことを優先

## 関連ドキュメント

設計書・分析レポートは `docs/` 以下にあります。

- [`docs/oil-stockpile-design-v2.0.md`](docs/oil-stockpile-design-v2.0.md) — 元設計書（v2.0）
- [`docs/oil-stockpile-design-v2.0-concerns.md`](docs/oil-stockpile-design-v2.0-concerns.md) — 設計書への懸念点リスト
- [`docs/oil-stockpile-design-v2.0-feasibility.md`](docs/oil-stockpile-design-v2.0-feasibility.md) — 一次データの実在性・実現性レビュー
- [`docs/oil-stockpile-strategic-review.md`](docs/oil-stockpile-strategic-review.md) — 戦略整理（Plan A/B/C）
- [`docs/gontarobee-analysis.md`](docs/gontarobee-analysis.md) — 競合（gontarobee/oil）分析
