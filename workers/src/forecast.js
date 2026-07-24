// 有事終息予想 API の純ロジック。
// I/O (D1・fetch・Request/Response) を持たないため node:test で単体検証できる。
// 仕様: docs/project/01-requirements/06-crisis-forecast-tab.md

/**
 * 設問定義。表示ラベルもここを SSOT とし、フロント側で二重管理しない。
 *
 * saltEpoch は voter_hash のソルト世代。仕様書は「日次ローテーション」だったが、
 * 再投票=上書き方式では日をまたぐと同一来訪者のハッシュが変わり、
 * 上書きされず二重計上になる。そのため設問ごとに固定し、
 * 集計をリセットして問い直すとき (仕様 §10) にだけ更新する。
 * 設問をまたいだ名寄せは question_id をソルトに含めることで防いでいる。
 */
export const QUESTIONS = {
  hormuz_end_2026: {
    id: 'hormuz_end_2026',
    saltEpoch: '2026-07',
    text: 'ホルムズ海峡の通航支障による有事は、いつ終息すると思いますか？',
    // 「終息」の定義。政治・軍事イベント基準 (決裁: 亀井 2026-07-24)。
    definition:
      '米国・イランの当事国間で停戦または核合意等の公式な合意が発表され、' +
      'ホルムズ海峡の通航支障の原因が解消した状態を「終息」とします。',
    choices: [
      { id: 'm3', label: '〜3ヶ月' },
      { id: 'm6', label: '〜6ヶ月' },
      { id: 'y1', label: '〜1年' },
      { id: 'long', label: '1年以上（長期化）' },
    ],
  },
};

/** 同一来訪者の連投を弾く最小間隔 (ミリ秒)。再投票自体は許可する。 */
export const REVOTE_COOLDOWN_MS = 10_000;

export function getQuestion(questionId) {
  return Object.hasOwn(QUESTIONS, questionId) ? QUESTIONS[questionId] : null;
}

export function isValidChoice(questionId, choice) {
  const question = getQuestion(questionId);
  if (!question) return false;
  return question.choices.some((c) => c.id === choice);
}

async function sha256Hex(input) {
  const bytes = new TextEncoder().encode(input);
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * 投票者の匿名識別子を作る。生 IP / UA は戻り値にも DB にも残さない。
 * ソルトを二段 (secret+epoch -> hash) にして、DB が漏れても
 * secret なしには IP を総当たりできないようにする。
 */
export async function computeVoterHash({ secret, questionId, saltEpoch, ip, userAgent }) {
  if (!secret) throw new Error('VOTER_SALT_SECRET is not configured');
  const salt = await sha256Hex(`${secret}|${questionId}|${saltEpoch}`);
  return sha256Hex(`${salt}|${ip ?? ''}|${userAgent ?? ''}`);
}

/**
 * D1 の集計行を API レスポンス形に整える。
 * 投票が 0 件の選択肢も 0 として必ず含める (フロントで欠落を意識させない)。
 *
 * 得票率は返さない。「票数が少ない期間に率を出すか」は未決 (仕様 §10) のため、
 * API は実数のみを返し、表示ルールはフロント側の判断に委ねる。
 */
export function tallyToResults(questionId, rows) {
  const question = getQuestion(questionId);
  if (!question) throw new Error(`unknown question_id: ${questionId}`);
  const counts = new Map(rows.map((r) => [r.choice, Number(r.votes) || 0]));
  const choices = question.choices.map((c) => ({
    id: c.id,
    label: c.label,
    votes: counts.get(c.id) ?? 0,
  }));
  return {
    question_id: question.id,
    total: choices.reduce((sum, c) => sum + c.votes, 0),
    choices,
  };
}

/** CORS は許可オリジンの完全一致のみ。未許可なら CORS ヘッダを一切返さない。 */
export function corsHeaders(origin, allowedOrigins) {
  if (!origin || !allowedOrigins.includes(origin)) return {};
  return {
    'Access-Control-Allow-Origin': origin,
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
}

export function parseAllowedOrigins(raw) {
  return (raw ?? '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}
