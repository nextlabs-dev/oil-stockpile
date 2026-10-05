# UTM ルール（公式 SNS 立ち上げ）

X（公式アカウント）の投稿と、サイトから SNS へ出る導線の流入を HubSpot / GA で比較できるよう、UTM を次のとおり統一する。
HubSpot キャンペーン「ネクストラボ公式SNS立ち上げ」（2026-10-01〜2026-12-31）と対応する。

## パラメータ

| パラメータ | 値 | 備考 |
|---|---|---|
| `utm_source` | `x` | 固定 |
| `utm_medium` | `social` | 固定 |
| `utm_campaign` | `official_sns` | 固定（HubSpot キャンペーンに対応） |
| `utm_content` | 投稿・導線の種類 | 下表。小文字 snake_case |

### `utm_content` の値

| 値 | 用途 |
|---|---|
| `daily_oil` | 毎朝 7 時の石油ネタ投稿 |
| `share_button` | サイトの「Xで共有する」ボタン経由の共有 |

新しい種類を足すときはこの表に追記する（表にない値を黙って使わない）。

## 使い方

- **X の投稿リンク（人が HubSpot で作る）**: `https://oilstock.nextlabs.jp/?d=YYYYMMDD&utm_source=x&utm_medium=social&utm_campaign=official_sns&utm_content=daily_oil`
  - `d` は OGP 画像・カードのキャッシュ対策（日付ごとに別 URL にする）。UTM とは別物。
- **サイトの共有ボタン**: `js/components/share.js` の `addUtm()` が自動で付ける（`utm_content=share_button`）。LINE 共有は対象外（規約は X 用）。
- **設定値の置き場所**: `src/constants.json` の `social` ブロックが正。JS 側は `js/core/data.js` の `SOCIAL_CONFIG` にミラーがあり、`scripts/build_site.py` が不一致を検出する。

## 公式アカウント確定時の差し替え（TODO）

アカウントのハンドルが決まったら、次の 3 か所を同時に更新する（`@` 付き）。

| ファイル | キー | 反映先 |
|---|---|---|
| `src/constants.json` | `social.twitter_site` | 全ページの `twitter:site` |
| `src/constants.json` | `social.official_handle` | 共有文のメンション |
| `js/core/data.js` | `SOCIAL_CONFIG.officialHandle` | 共有文のメンション（ミラー） |

更新後は `python scripts/build_site.py` で全ページを再生成する。

## 日付パラメータ `?d=` と OGP 画像

- `?d=YYYYMMDD` は X のカードキャッシュ対策（X はカードを共有URL単位でキャッシュする）。日付ごとに別URLにすると、その日に新しくクロールされる。サイト側は `d` を無視する（GitHub Pages の静的配信）。
- カードに出る画像は、クロール時点の `assets/og-image.png`（ページの `og:image` は `?v=<画像ハッシュ>` 付き）。**備蓄日数は画像の生成時刻で決まる**。
- **投稿は JST 11:00 以降にする**。画像は `fetch-daily.yml`（cron は 07:00 JST 指定）が更新するが、GitHub の cron 遅延で実際は JST 09:10〜10:40 頃（2026-09〜10 の実績。最大 10:39）。11:00 ならその日の画像・当日の日数でカードが出る。7 時投稿だと前日の画像になるため避ける。
- 遅延が 11:00 を超えた日は前日の画像になる。気づいたら Actions の実行時刻を確認し、必要なら手動実行（workflow_dispatch）してから投稿する。
- 画像右下の「提供：ネクストラボ」は `scripts/generate_ogp.py` の `SPONSORS`。週 1 回「提供：バクアゲ配送」にするには、`src/constants.json` の `ogp.bakuage_haiso_weekday` に曜日（JST、0=月 … 6=日）を入れる。`null` の間は毎日ネクストラボ。手動確認は `python scripts/generate_ogp.py --sponsor bakuage_haiso --output /tmp/og.png`。

## バクアゲ関連の投稿（リンク先は bakuage.co、問い合わせに流す）

石油ネタの投稿（`daily_oil`）は oilstock.nextlabs.jp へ、**バクアゲ関連の投稿は bakuage.co へ**リンクし、バクアゲへの問い合わせに流す。石油サイトの読者は EC 事業者から遠いので、バクアゲのフォームへの導線は石油サイトには置かない。

| 投稿の種類 | `utm_content` | リンク先 |
|---|---|---|
| サービス紹介（一般） | `bakuage_service` | `https://bakuage.co/service/` |
| バクアゲ配送（旧返品くん） | `bakuage_haiso` | `https://bakuage.co/service/return/`（URL は旧名のまま） |
| 住所チェック | `bakuage_address_check` | `https://bakuage.co/service/address-check/` |
| バクアゲ送金 | `bakuage_pay` | `https://bakuage.co/service/pay/` |
| 問い合わせ誘導（CTA） | `bakuage_contact` | `https://bakuage.co/contact/?inq_service_contact=inq_introducing` |

- 例: `https://bakuage.co/service/return/?utm_source=x&utm_medium=social&utm_campaign=official_sns&utm_content=bakuage_haiso`
- source / medium / campaign は石油ネタと同じ固定値。**キャンペーンは 1 つで、`utm_content` の接頭辞（`daily_oil` / `bakuage_*`）で石油とバクアゲを分けて見る**。
- バクアゲ配送の提供表示の日（OGP の `ogp.bakuage_haiso_weekday`）の投稿は、原則 `bakuage_haiso`（`/service/return/`）にする。
- **計測の前提（要対応）**: 2026-10-06 時点で bakuage.co（トップ・問い合わせページ）に HubSpot のトラッキングコードは入っておらず、問い合わせフォームが HubSpot に繋がっているかも未確認。ここが繋がっていないと、X → bakuage.co の訪問と問い合わせがキャンペーンに帰属しない。
