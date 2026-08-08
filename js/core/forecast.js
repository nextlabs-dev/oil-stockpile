/**
 * 有事終息予想（/forecast/）の設定と純ロジック。
 *
 * ⚠ FORECAST_CONFIG は src/constants.json の forecast ブロックを手で写したもの。
 *    JS 側は JSON を import できない（ビルド工程を持たない）ため data.js の
 *    PEAK_REFERENCE と同じ方式を取り、build_site.py の drift チェックで
 *    ズレを検出する。**片方だけ直さないこと。**
 *
 * api_origin / turnstile_site_key はデプロイ後に実値を入れる。
 * 空のままだと投票 UI は無効化され、「準備中」を表示する（モックは出さない）。
 */
export const FORECAST_CONFIG = {
  apiOrigin: '',
  turnstileSiteKey: '',
  questionId: 'hormuz_end_2026',
  minVotesForPercent: 100,
};

/** 設問の 4 択。id は Workers 側 QUESTIONS の choices と一致させる。 */
export const FORECAST_CHOICES = [
  { id: 'm3', label: '〜3ヶ月' },
  { id: 'm6', label: '〜6ヶ月' },
  { id: 'y1', label: '〜1年' },
  { id: 'long', label: '1年以上（長期化）' },
];

/** API 未設定なら投票も集計取得もできない。UI はこの判定で「準備中」に落とす。 */
export function isForecastEnabled(config = FORECAST_CONFIG) {
  return Boolean(config.apiOrigin);
}

/**
 * 得票率を出してよいか。総投票数が下限未満のときは率を伏せ、実数だけ見せる。
 * 数票で「75% が長期化と予想」のような誤引用が独り歩きするのを防ぐ（仕様 §4）。
 */
export function shouldShowPercent(total, minVotes = FORECAST_CONFIG.minVotesForPercent) {
  return Number.isFinite(total) && total >= minVotes;
}

/**
 * API の結果を描画用に整える。
 * 得票率は API が返さない（実数のみ）ため、ここで算出する。
 * 下限未満のときは percent を null にして「率が無い」ことを型で表す。
 */
export function toDisplayRows(results, minVotes = FORECAST_CONFIG.minVotesForPercent) {
  const total = Number(results?.total) || 0;
  const showPercent = shouldShowPercent(total, minVotes);
  const choices = Array.isArray(results?.choices) ? results.choices : [];
  return choices.map((c) => {
    const votes = Number(c.votes) || 0;
    return {
      id: c.id,
      label: c.label,
      votes,
      percent: showPercent && total > 0 ? (votes * 100) / total : null,
    };
  });
}

/** 表示用の得票率文字列。率を出さない期間は空文字を返す。 */
export function formatPercent(percent) {
  if (percent == null || !Number.isFinite(percent)) return '';
  return `${percent.toFixed(1)}%`;
}

/** バーの幅（%）。率が無い期間は 0 にして、バーそのものを出さない。 */
export function barWidth(percent) {
  if (percent == null || !Number.isFinite(percent)) return 0;
  return Math.max(0, Math.min(100, percent));
}

/** 下限に達するまであと何票か。「あと N 票で割合を表示」の案内に使う。 */
export function votesUntilPercent(total, minVotes = FORECAST_CONFIG.minVotesForPercent) {
  const n = Number(total) || 0;
  return Math.max(0, minVotes - n);
}
