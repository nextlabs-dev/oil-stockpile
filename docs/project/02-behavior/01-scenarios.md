# Gherkin シナリオ一覧

「日本の石油備蓄」サイトの振る舞いを Gherkin 形式で定義する。経産省の備蓄速報 PDF と AIS タンカーデータを統合した公開サイトとして、訪問者が「いま日本の備蓄が何日分か」を数秒で把握し、出典付きで SNS 拡散できる体験を保証することが目的。

ユーザーストーリー（`docs/project/01-requirements/05-user-stories.md`）と実装済み機能（`docs/project/01-requirements/02-features-implemented.md`）に対応するシナリオを集約している。

---

## シナリオ一覧

| シナリオID | 機能 | シナリオ名 | 優先度 |
|-----------|------|-----------|--------|
| SC-001 | 備蓄日数カウンター | ファーストビューで現在の備蓄日数が読み取れる | High |
| SC-002 | 備蓄日数カウンター | 表示中にカウンターが秒単位で減算する | High |
| SC-003 | タンクゲージ | 過去最高値に対する充填率がゲージで可視化される | High |
| SC-004 | タンクゲージ | 充填率がパーセンテージで並記される | High |
| SC-005 | 12 ヶ月推移グラフ | 過去 12 ヶ月の総備蓄日数推移が表示される | High |
| SC-006 | 12 ヶ月推移グラフ | 個別月の値と公表日を確認できる | Medium |
| SC-007 | 12 ヶ月推移グラフ | 3 区分内訳をトグルで切替表示できる | Medium |
| SC-008 | タンカー流入 | 日本周辺海域のタンカー隻数が表示される | Medium |
| SC-009 | タンカー流入 | 日本港向け隻数と上位港が確認できる | Medium |
| SC-010 | SNS シェア | X シェアボタンで prefill 済みツイートが開く | High |
| SC-011 | SNS シェア | リンクコピーで同等のテキストと URL がコピーされる | High |
| SC-012 | 出典・データ時点 | フッターに経産省 PDF へのリンクが常時表示される | High |
| SC-013 | 出典・データ時点 | 公表日と asOf がフッターに表示される | High |
| SC-014 | データ古さ警告 | 備蓄データが 14 日以上更新されない場合に警告される | High |
| SC-015 | データ古さ警告 | タンカーデータが 6 時間以上更新されない場合に警告される | High |
| SC-016 | 石油のものさし | 備蓄日数が kL・バレル・リットルに換算表示される | Medium |
| SC-017 | 石油のものさし | 備蓄量が VLCC 隻数・年間消費比・IEA 90 日比に換算表示される | Medium |
| SC-018 | 石油のものさし | サブタブで 3 視点（単位換算・スケール比較・豆知識）を切替できる | Medium |
| SC-019 | about | サイトの目的・出典・計算方法・運営者情報を 1 ページで確認できる | Medium |
| SC-020 | 問い合わせ CTA | about タブ末尾の CTA から運営会社の問い合わせ動線に遷移できる | Low |
| SC-021 | OGP 自動生成 | 備蓄データ更新時に OGP 画像が再生成される | Medium |

---

## シナリオ詳細

### Feature: 備蓄日数カウンター

```gherkin
@counter @core
Feature: 備蓄日数カウンター

  As a ニュースで石油備蓄の話題を見たユーザー
  I want サイト訪問後数秒で「いま日本の備蓄が何日分か」を把握したい
  So that 報道された数字が多いか少ないか自分の感覚で判断できる

  Background:
    Given 経産省の最新スナップショットが `data/snapshots.json` に存在する
    And 訪問者がトップページ `/` を開いている

  @SC-001 @smoke @happy-path @high
  Scenario: ファーストビューで現在の備蓄日数が読み取れる
    Given スナップショットの総備蓄日数が "215.3 日" である
    When ページの初期描画が完了する
    Then ファーストビュー中央に "N 日 HH 時間 MM 分 SS 秒" 形式のカウンターが大きく表示される
    And カウンターはスクロールせずに視認できる

  @SC-002 @smoke @happy-path @high
  Scenario: 表示中にカウンターが秒単位で減算する
    Given カウンターが "215 日 12 時間 00 分 00 秒" を表示している
    When 1 秒経過する
    Then カウンターは "215 日 11 時間 59 分 59 秒" に更新される
```

---

### Feature: タンクゲージ

```gherkin
@gauge @core
Feature: タンクゲージによる充填率可視化

  As a 「N 日分」という数字に肌感覚を持てない訪問者
  I want 過去最高値に対する相対的な残量を視覚的に確認したい
  So that 絶対値より直感的に「いつもより多いか少ないか」を判断できる

  Background:
    Given 過去最高値 `PEAK_REFERENCE` が定義されている
    And 訪問者がカウンタータブを表示している

  @SC-003 @smoke @happy-path @high
  Scenario Outline: 過去最高値に対する充填率がゲージで可視化される
    Given 現在の総備蓄日数が "<current>" 日である
    And 過去最高値が "<peak>" 日である
    When タンクゲージが描画される
    Then ゲージの fill 高さは充填率 "<ratio>" に一致する
    And ゲージ色は "<color>" 区分で表示される

    Examples: 充填率の区分
      | current | peak | ratio | color |
      | 240     | 240  | 100%  | 高水準 |
      | 200     | 240  | 約 83% | 中水準 |
      | 130     | 240  | 約 54% | 低水準 |

  @SC-004 @happy-path @high
  Scenario: 充填率がパーセンテージで並記される
    Given 現在の総備蓄日数が "200" 日、過去最高値が "240" 日である
    When タンクゲージが描画される
    Then ゲージの近傍に "約 83%" のような充填率が数値で表示される
```

---

### Feature: 12 ヶ月推移グラフ

```gherkin
@trend @counter
Feature: 12 ヶ月推移グラフによる傾向把握

  As a 備蓄量の傾向に関心を持つユーザー
  I want 過去 12 ヶ月のトレンドを一目で確認したい
  So that 現在値だけでなく増減傾向まで把握できる

  Background:
    Given 直近 12 ヶ月分の月次スナップショットが `data/snapshots.json` に存在する
    And 訪問者がカウンタータブを表示している

  @SC-005 @smoke @happy-path @high
  Scenario: 過去 12 ヶ月の総備蓄日数推移が表示される
    When 推移グラフが描画される
    Then 12 ヶ月分の総備蓄日数がライン表示される
    And X 軸は月、Y 軸は備蓄日数で表現される

  @SC-006 @happy-path @medium
  Scenario: 個別月の値と公表日を確認できる
    Given 推移グラフが描画されている
    When 訪問者が任意のデータポイントにホバーまたはフォーカスする
    Then その月の備蓄日数と公表日がツールチップで表示される

  @SC-007 @happy-path @medium
  Scenario: 3 区分内訳をトグルで切替表示できる
    Given 推移グラフが「総量」表示である
    When 訪問者が内訳トグルを「3 区分」に切り替える
    Then 国家備蓄・民間備蓄・産油国共同備蓄の 3 ラインが表示される
    When 訪問者が内訳トグルを「総量」に戻す
    Then 総量の単一ラインのみ表示される
```

---

### Feature: タンカー流入状況

```gherkin
@tankers
Feature: 日本周辺タンカー流入の表示

  As a エネルギー安全保障に関心がある訪問者
  I want 日本周辺のタンカー流入状況を確認したい
  So that 備蓄量に加えて流入動向で現況を補完できる

  Background:
    Given `data/tankers.json` に最新のタンカー集計が存在する
    And 訪問者がタンカータブを表示している

  @SC-008 @happy-path @medium
  Scenario: 日本周辺海域のタンカー隻数が表示される
    Given 集計対象海域内に "42" 隻のタンカーがサンプリングされている
    When タンカータブが描画される
    Then 海域内タンカー隻数として "42 隻" が表示される

  @SC-009 @happy-path @medium
  Scenario: 日本港向け隻数と上位港が確認できる
    Given `destination` が日本港のタンカーが "12" 隻ある
    And 上位の到着港が "千葉, 横浜, 川崎" である
    When タンカータブが描画される
    Then 日本港向け隻数として "12 隻" が表示される
    And 上位港として "千葉" "横浜" "川崎" が確認できる
```

---

### Feature: SNS シェア

```gherkin
@share @core
Feature: SNS による出典付き拡散

  As a SNS で関連話題を共有したいユーザー
  I want 現在の備蓄日数を 1 タップで X にシェアしたい
  So that 自分で文章を起こさず、出典付きで拡散できる

  Background:
    Given カウンターが "215 日分" を表示している
    And ページ URL が "https://example.com/" である

  @SC-010 @smoke @happy-path @high
  Scenario: X シェアボタンで prefill 済みツイートが開く
    When 訪問者が X シェアボタンを押下する
    Then 新規タブが開く
    And ツイート本文に "日本の石油備蓄、いま 215 日分。" が prefill されている
    And ツイートに本サイトの URL が含まれている

  @SC-011 @happy-path @high
  Scenario: リンクコピーで同等のテキストと URL がコピーされる
    When 訪問者がリンクコピーボタンを押下する
    Then クリップボードに "日本の石油備蓄、いま 215 日分。" に相当するテキストが格納される
    And クリップボードに本サイトの URL が含まれる
    And 訪問者にコピー完了のフィードバックが表示される
```

---

### Feature: 出典・データ時点の表示

```gherkin
@footer @trust
Feature: 出典とデータ時点の常時表示

  As a データの信頼性を重視する訪問者
  I want 表示値の出典とデータ取得日時を常時確認したい
  So that 出典不明の数字を引用するリスクを回避できる

  Background:
    Given スナップショットの公表日が "2026-04-30" である
    And `asOf` が "2026-05-01T07:00:00+09:00" である

  @SC-012 @smoke @happy-path @high
  Scenario: フッターに経産省 PDF へのリンクが常時表示される
    When 訪問者がページのどのタブを表示していても
    Then フッターに経産省 PDF へのリンクが表示される
    And リンクは新規タブで開く

  @SC-013 @smoke @happy-path @high
  Scenario: 公表日と asOf がフッターに表示される
    When 訪問者がフッターを確認する
    Then 公表日として "2026-04-30" が表示される
    And `asOf` として "2026-05-01" が表示される
```

---

### Feature: データ古さ警告

```gherkin
@stale-warning @trust
Feature: データが古い場合の警告表示

  As a 訪問者
  I want データが長期間更新されていない場合に即座に気づきたい
  So that 知らずに古い情報を共有してしまうことを防げる

  @SC-014 @error-handling @high
  Scenario Outline: 備蓄データが asOf から一定期間以上経過すると警告される
    Given 現在時刻が "2026-05-05T10:00:00+09:00" である
    And `asOf` が "<asOf>" である
    When 訪問者がカウンタータブを開く
    Then 警告バナーは "<warning>"

    Examples: 14 日が境界
      | asOf                        | warning   |
      | 2026-05-04T07:00:00+09:00   | 表示されない |
      | 2026-04-22T07:00:00+09:00   | 表示されない |
      | 2026-04-21T07:00:00+09:00   | 表示される  |
      | 2026-04-01T07:00:00+09:00   | 表示される  |

  @SC-015 @error-handling @high
  Scenario Outline: タンカーデータが一定期間以上更新されないと警告される
    Given 現在時刻が "2026-05-05T10:00:00+09:00" である
    And `tankers.json` の最終更新時刻が "<updatedAt>" である
    When 訪問者がタンカータブを開く
    Then 警告バナーは "<warning>"

    Examples: 6 時間が境界
      | updatedAt                   | warning   |
      | 2026-05-05T05:00:00+09:00   | 表示されない |
      | 2026-05-05T04:01:00+09:00   | 表示されない |
      | 2026-05-05T03:59:00+09:00   | 表示される  |
      | 2026-05-04T20:00:00+09:00   | 表示される  |
```

---

### Feature: 石油のものさし

```gherkin
@scale @education
Feature: 備蓄量の換算とスケール比較

  As a 「N 日分」という数字に肌感覚を持てない訪問者
  I want 備蓄量を kL・バレル・VLCC 隻数・年間消費比など別の単位で見たい
  So that 桁感や規模を直感的に把握できる

  Background:
    Given 経産省の最新スナップショットが `data/snapshots.json` に存在する
    And 訪問者が「石油のものさし」タブ `/scale/` を開いている

  @SC-016 @happy-path @medium
  Scenario: 備蓄日数が kL・バレル・リットルに換算表示される
    Given 最新スナップショットの総備蓄日数が "215" 日である
    When 単位換算サブタブが描画される
    Then キロリットル換算値が表示される
    And バレル換算値が表示される
    And リットル換算値が表示される
    And 換算根拠（1 日あたり消費量・1 バレル換算）が注記として併記される

  @SC-017 @happy-path @medium
  Scenario Outline: 備蓄量が VLCC 隻数・年間消費比・IEA 90 日比に換算表示される
    Given 最新スナップショットの総備蓄日数が "<days>" 日である
    When スケール比較サブタブが描画される
    Then VLCC 換算隻数が表示される
    And 年間消費比 "<yearPct>" 程度が表示される
    And IEA 90 日比 "<ieaPct>" 程度が表示される

    Examples: 比率の桁感
      | days | yearPct | ieaPct |
      | 90   | 約 25%  | 約 100% |
      | 215  | 約 59%  | 約 239% |
      | 240  | 約 66%  | 約 267% |

  @SC-018 @happy-path @medium
  Scenario: サブタブで 3 視点を切替できる
    Given 単位換算サブタブが選択されている
    When 訪問者が「スケール比較」サブタブを押下する
    Then スケール比較パネルが表示される
    And 単位換算パネルは非表示になる
    When 訪問者が「豆知識」サブタブを押下する
    Then 豆知識パネルが表示される
    And 他のパネルは非表示になる
```

---

### Feature: about（サイト紹介）

```gherkin
@about
Feature: サイトの目的・出典・運営者の集約表示

  As a データの信頼性と運営主体を確認したい訪問者
  I want サイトの目的・データ出典・計算方法・運営者情報を 1 ページで確認したい
  So that 出典不明のサイトを引用するリスクを避け、安心して情報を扱える

  Background:
    Given 訪問者が about タブ `/about/` を開いている

  @SC-019 @smoke @happy-path @medium
  Scenario: サイトの主要情報が 1 ページで確認できる
    When ページが描画される
    Then サイトの目的セクションが表示される
    And データ出典セクションに経産省 PDF と aisstream.io の参照先が表示される
    And 計算方法と限界セクションが表示される
    And 運営セクションに会社名「株式会社ネクストラボ」と所在地・代表者・設立年・事業内容が表示される
    And 免責事項セクションが表示される

  @SC-020 @cta @happy-path @low
  Scenario: 問い合わせ CTA から運営会社の問い合わせ動線に遷移できる
    Given 訪問者が about タブをスクロールしている
    When 訪問者がページ末尾の CTA「ネクストラボに問い合わせる」を押下する
    Then 新規タブで `https://nextlabs.jp/#contact` が開く
    And CTA は親要素の幅いっぱい（横幅フル）に表示されている
```

---

### Feature: OGP 画像の自動再生成

```gherkin
@ogp @automation
Feature: OGP 画像が備蓄データに追従して再生成される

  As a SNS 経由でサイトを発見する訪問者
  I want シェア時に表示される OGP 画像が最新の備蓄日数を反映していてほしい
  So that 古い数字を出典付きで拡散してしまう事故を避けられる

  Background:
    Given GitHub Actions の `fetch-daily.yml` が毎朝 07:00 JST に走行する
    And `scripts/generate_ogp.py` が `data/snapshots.json` の最新値を読む

  @SC-021 @smoke @automation @medium
  Scenario: 備蓄データ更新時に OGP 画像が再生成される
    Given `data/snapshots.json` の最新 asOf が "2026-04-28" / total 211 である
    When `python scripts/generate_ogp.py` が実行される
    Then `assets/og-image.png` が 1200×630 の PNG として書き出される
    And 画像内に「211 日分」「データ時点 2026年4月28日」が描画されている
    And 画像内のタンクゲージが充填率（基準 247 日比 約85%）を反映している

  @SC-021 @error-handling @medium
  Scenario: 入力データ異常時は OGP を更新しない
    Given `data/snapshots.json` が空または不正である
    When `python scripts/generate_ogp.py` が実行される
    Then スクリプトは exit code 1 で終了する
    And 既存の `assets/og-image.png` は変更されない
```

---

## タグの活用

本プロジェクトで採用するタグ体系。

| タグ | 用途 |
|------|------|
| `@SC-XXX` | シナリオ ID（必須、トレーサビリティ） |
| `@smoke` | リリース前の最小確認対象。ファーストビュー・シェア・出典・警告など中核体験 |
| `@happy-path` | 正常系シナリオ |
| `@error-handling` | データ古さ警告など、異常時の振る舞い |
| `@high` / `@medium` / `@low` | 優先度（一覧テーブルと同期） |
| `@counter` / `@gauge` / `@trend` / `@tankers` / `@share` / `@footer` / `@stale-warning` / `@scale` / `@about` / `@cta` / `@ogp` | 機能カテゴリ。タブやコンポーネント単位の選択実行に利用 |
| `@education` | 備蓄量への肌感覚を補強する教育系コンテンツ |
| `@automation` | GitHub Actions 等のバックグラウンド自動化（人手操作なしで走るもの） |
| `@core` | サイトの存在意義に直結する機能（カウンター・ゲージ・シェア） |
| `@trust` | データ信頼性に関わる機能（出典表示・古さ警告） |

選択実行例:
- `@smoke` のみ: リリース前の最終チェック
- `@core and @happy-path`: 中核ハッピーパスのリグレッション
- `@trust`: 出典・警告周りの確認

---

## メモ

### 振る舞いの原則
- カウンターの秒次減算は「年間消費量 ÷ 365 ÷ 86400」相当のレートで進む。リアルタイム性は演出であり、ページ遷移時にスナップショット値へリセットされる。
- 充填率の色区分（高水準 / 中水準 / 低水準）の閾値は実装側の定数で管理し、シナリオでは具体値を例示するに留める。
- 警告バナー（SC-014 / SC-015）は「14 日 / 6 時間」が現状の閾値。閾値変更時は本シナリオと一覧テーブルを同時に更新する。

### Living Documentation としての運用
- ユーザーストーリー（`docs/project/01-requirements/05-user-stories.md`）または実装機能（`docs/project/01-requirements/02-features-implemented.md`）が更新されたら、対応する `@SC-XXX` を見直す。
- シナリオ追加時は一覧テーブルと詳細セクションの両方に記載する。

### 自動化の方針（将来）
- 現状は人手レビュー用の Living Documentation。将来的に Cucumber / Playwright + cucumber-js 等で `@smoke` 系から段階的に自動化することを想定。
- 自動化前段階でも、Gherkin の Given-When-Then 構造はテスト設計のチェックリストとして利用可能。

### ドメイン用語
シナリオ内で使われる主要用語は以下の文書に揃える:
- 総備蓄日数 / 国家備蓄 / 民間備蓄 / 産油国共同備蓄: 経産省「石油備蓄の現況」用語に準拠
- `asOf` / `PEAK_REFERENCE`: 実装側の定義に準拠（`data/snapshots.json` および設定定数）
- 海域 / 日本港: `data/tankers.json` の集計範囲定義に準拠
