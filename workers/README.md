# 有事終息予想 API (フェーズ1)

`/forecast/` タブのバックエンド。Cloudflare Workers + D1。
仕様は [`docs/project/01-requirements/06-crisis-forecast-tab.md`](../docs/project/01-requirements/06-crisis-forecast-tab.md)。

フェーズ1の範囲は **API 単体の構築と疎通確認まで**。GitHub Pages 本体の静的サイトは変更しない。

## エンドポイント

| メソッド | パス | 内容 |
| --- | --- | --- |
| `GET` | `/v1/forecast/results?q=hormuz_end_2026` | 選択肢ごとの得票数と総数 |
| `POST` | `/v1/forecast/vote` | `{question_id, choice, turnstile_token}` を記録し最新結果を返す |

エラーは `{"error": "..."}` と HTTP ステータスで返す。
`unknown_question` / `invalid_choice` / `turnstile_required` / `turnstile_failed` /
`rate_limited` / `internal_error`。

**フロントはエラー時にモックや推測値へフォールバックしないこと**（仕様 §6）。

## 仕様書からの差分（実装時の決裁）

| 項目 | 仕様書 | 本実装 | 理由 |
| --- | --- | --- | --- |
| 再投票 | 不可 | **可（上書き）** | 決裁: 亀井 2026-07-24。情勢変化を反映できるようにするため |
| ソルト | 日次ローテーション | **設問ごとに固定**（`saltEpoch`） | 上書き方式では日次だと日をまたいだ同一来訪者が別ハッシュになり二重計上する。設問をまたいだ名寄せは `question_id` をソルトに含めて防ぐ |
| 「終息」の定義 | 未決 | **政治・軍事イベント基準** | 決裁: 亀井 2026-07-24。文言は `forecast.js` の `QUESTIONS[].definition` が SSOT |
| 得票率 | — | **API は実数のみ返す** | 「票数が少ない期間に率を出すか」が未決（仕様 §10）のため、表示ルールをフェーズ2のフロントに委ねる |

## セットアップ

```bash
npx wrangler login
```

```bash
cd workers && npx wrangler d1 create oilstock-forecast
```

出力された `database_id` を `wrangler.toml` に転記してから、スキーマを適用する。

```bash
cd workers && npx wrangler d1 execute oilstock-forecast --remote --file=./schema.sql
```

シークレットを登録する（値は Keychain / パスワードマネージャで管理し、リポジトリに書かない）。

```bash
cd workers && npx wrangler secret put VOTER_SALT_SECRET
```

```bash
cd workers && npx wrangler secret put TURNSTILE_SECRET_KEY
```

## ローカル実行

ローカル D1 にスキーマを適用してから起動する。

```bash
cd workers && npx wrangler d1 execute oilstock-forecast --local --file=./schema.sql && npx wrangler dev
```

## デプロイと疎通確認

```bash
cd workers && npx wrangler deploy
```

```bash
curl -s "https://oilstock-forecast-api.<subdomain>.workers.dev/v1/forecast/results?q=hormuz_end_2026" | python3 -m json.tool
```

投票は Turnstile トークンが必須のため、`curl` 単体では `turnstile_required` が返るのが正常。
実投票の確認はフェーズ2のフロント実装後に行う。

## テスト

純ロジック（設問検証・投票者ハッシュ・集計・CORS）は `node --test` で検証する。

```bash
npm test
```

## フェーズ2以降で必要になる作業

- `build_site.py` 経路で `/forecast/` ページを追加（生成 HTML は直接編集しない）
- `build_csp()` に `connect-src` の API オリジンと Turnstile
  (`https://challenges.cloudflare.com`) を追加
- `src/site.json` の `nav_order` / `nav_labels` / `nav_labels_short` と全ページの `nav` 辞書、
  `build_site.py` の `NAV_ICONS` を更新
- `sitemap.xml` に `/forecast/` を追加
