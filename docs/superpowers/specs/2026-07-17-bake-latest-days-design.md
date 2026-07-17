# 最新備蓄日数の静的 HTML 焼き込み — 設計

- Issue: [#93](https://github.com/CountieeReturns/oil-stockpile/issues/93)
- 日付: 2026-07-17
- 重要度: High（SEO 施策の中で実装コストと効果のバランスが最良）

## 背景と問題

ホームのカウンター・更新日バナー・ヘッダー最終更新はすべて初期値「—」のプレースホルダで、
JS が `data/snapshots.json` を fetch して埋めている。JS を実行しないクローラの一次クロールや
レンダリングキュー遅延時、生 HTML には備蓄日数が存在せず、SERP スニペットにも具体的な数値が
出ない。

`build_site.py` は `fetch-daily.yml` で毎日データ取得直後に実行されるため、ビルド時点の最新
公表値を静的 HTML に焼き込んでも鮮度は保てる。

## 決定事項（ブレストで確定）

**焼き込む値は「公表値そのまま」**（snapshots.json の最新エントリの `total` と日付）とする。

- ビルド出力は**リポジトリ状態だけから決定論的**でなければならない。`test.yml` が
  `build_site.py` を再実行して生成 HTML の drift を検査しており、実行時刻依存の値
  （`compute_current_days(now)` 方式）を焼くと日付跨ぎで CI が誤検知する
  （og-image.png の日次 churn = Issue #81 と同じ病気を HTML に広げる）。
- 焼き込み値（例: 242 日）は JS 起動後にリアルタイム推計値（例: 239 日）へ上書きされる。
  数日ぶんの差が一瞬見える可能性はユーザー確認済みで許容する。ラベル（集計時点の日付）を
  併記して値の意味を正直に示す。
- **JS は一切変更しない**。`counter.js` の `tick()` は無条件に `#counter-days` を上書きするため
  焼き込み初期値と共存できる。fetch 失敗時に `showLoadError` が「—」へ戻す既存挙動も維持する。

## 焼き込み対象（home ページのみ）

| 箇所 | 現状 | 焼き込み後（例） | ソース |
|---|---|---|---|
| `#counter-days`（src/pages/home.html） | `—` | `242` | 最新 `total` |
| `#update-banner-date`（src/pages/home.html） | `—` | `2026.03.17` | 最新 `published`（JS `formatDotDate` と同形式） |
| `#header-last-updated`（src/site.json home の header_meta） | `—` | `2026.03.17` | 同上 |
| meta description（src/site.json home の description） | 固定文 | 下記 | `total` + `asOf` |

新 description（プレースホルダは Python `string.Template` の `${...}` 記法）:

> 日本の石油備蓄はいま約${latest_total_days}日分（${latest_asof_jp}集計時点）。経済産業省「石油備蓄の現況」速報値を毎日更新で可視化する非公式カウンター。

- **noscript ブロックは追加しない**。実要素に値を焼くため JS 無効でもそのまま表示される
  （Issue 本文の「noscript フォールバック」はこの方式で不要になる。Issue にコメントで明記する）。
- **og_description / twitter_description / title は静的維持**。X のカードキャッシュ churn を
  避ける。数値は og-image（日次生成）が既に担っている。
- **tankers / scale / about のヘッダー最終更新は対象外**。tankers は tankers.json 由来で
  `fetch-tankers.yml` はビルドを回さないため、焼くと逆に古い値が固定される。

## 詳細設計

### 1. `scripts/lib/snapshots.py` 新設（generate_ogp.py からの移動、DRY）

`generate_ogp.py` から以下を**移動**する（コピーではない。後方互換 shim も置かない）:

- `Snapshot` dataclass
- `load_snapshots(path) -> list[dict]`
- `pick_latest_snapshot(rows) -> Snapshot`
- `format_jst_date(iso) -> str`（'2026-03-14' → '2026年3月14日'）

`generate_ogp.py` と `test_generate_ogp.py` は import 先を `lib.snapshots` に変更する。
`compute_current_days` は build_site では使わないため generate_ogp.py に残す（移動はスコープ外）。

### 2. `build_site.py` の変更

- `main()` で `pick_latest_snapshot(load_snapshots(SNAPSHOTS_PATH))` を呼び、テンプレート変数
  を組み立てる:

| 変数 | 値 | 例 |
|---|---|---|
| `latest_total_days` | `str(latest.total)` | `242` |
| `latest_published_dot` | `latest.published.replace("-", ".")` | `2026.03.17` |
| `latest_asof_jp` | `format_jst_date(latest.as_of)` | `2026年3月14日` |

- `render_page()` に `latest_vars: dict[str, str]` を渡し、**`content`・`description`・
  `header_meta` の 3 フィールドのみ**に `Template(...).substitute(latest_vars)` を適用する。
  - **strict な `substitute()`**（`safe_substitute` ではない）を使う。未定義プレースホルダや
    生の `$` はビルドを即失敗させる（Fail Fast、沈黙の劣化を避ける）。リテラル `$` が必要に
    なったら `$$` でエスケープする。現状 `src/pages/*.html` と `src/site.json` に `$` は
    存在しないことを確認済み。
  - 適用フィールドを 3 つに限定することで、og_description 等に誤ってプレースホルダを書いた
    場合は置換されず生の `${...}` が出力に現れ、目視・テストで気づける。

### 3. `src/site.json` / `src/pages/home.html` の変更

- home の `description` を上記の新文言に差し替え。
- home の `header_meta` 内 `>—<` を `>${latest_published_dot}<` に差し替え。
- `src/pages/home.html` の `#counter-days` と `#update-banner-date` の `—` をそれぞれ
  `${latest_total_days}` / `${latest_published_dot}` に差し替え。

### 4. エラー処理

`snapshots.json` が欠損・空・必須キー不足の場合、`load_snapshots` / `pick_latest_snapshot` の
`ValueError` でビルドが落ちる（OGP アセット欠損時の `FileNotFoundError` と同じ fail fast
ポリシー）。`fetch-daily.yml` は既にビルド失敗時「スナップショットのみコミット + エラー注記」の
ハンドリングを持つため変更不要。

## 変更ファイル一覧

| ファイル | 変更 |
|---|---|
| `scripts/lib/snapshots.py` | 新規（generate_ogp.py から Snapshot / load_snapshots / pick_latest_snapshot / format_jst_date を移動） |
| `scripts/generate_ogp.py` | 移動した関数を削除し `lib.snapshots` から import |
| `scripts/build_site.py` | 最新スナップショット読込・latest_vars 組み立て・3 フィールドへの substitute 適用 |
| `src/site.json` | home の description / header_meta にプレースホルダ |
| `src/pages/home.html` | `#counter-days` / `#update-banner-date` にプレースホルダ |
| `scripts/test_build_site.py` | 焼き込みテスト・strict substitute 失敗テストを追加 |
| `scripts/test_generate_ogp.py` | import 先の更新 |
| `index.html` ほか生成 HTML | `build_site.py` 再実行で再生成しコミット（drift チェック対策） |

## 検証方法

- `python -m unittest discover -s scripts -p 'test_*.py' -v` が通る。
- `python scripts/build_site.py` 後の `index.html` に最新の日数・日付・新 description が
  含まれることを grep で確認する。
- 再度 `python scripts/build_site.py` を実行して差分ゼロ（決定論性）を確認する。
- ブラウザ実機確認: 初期表示に焼き込み値が出て、JS 起動後にリアルタイム値へ上書きされること。
  DevTools で JS 無効化した場合も焼き込み値が表示されたままであること。
- 完了後、Issue #93 に「noscript は実要素焼き込みで不要になった」旨をコメントする。

## 非対象（YAGNI）

- ビルド実行時刻の推計値焼き込み（決定論性を壊すため不採用、上記のとおり）。
- KPI カード（`#tank-percent` 等）・donut・チャートの焼き込み。ファーストビュー下で
  SEO 上の価値が薄く、tank-gauge の描画ロジックと絡んで複雑化する。
- tankers / scale / about ページへの焼き込み。
- og_description / twitter_description の動的化。
