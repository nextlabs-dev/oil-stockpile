// 有事終息予想 API (Cloudflare Workers + D1)。
// フェーズ1: API 単体で疎通確認する。GitHub Pages 本体 (静的) は変更しない。
// 仕様: docs/project/01-requirements/06-crisis-forecast-tab.md §6・§7

import {
  computeVoterHash,
  corsHeaders,
  getQuestion,
  isValidChoice,
  parseAllowedOrigins,
  REVOTE_COOLDOWN_MS,
  tallyToResults,
} from './forecast.js';

const TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify';

function json(body, { status = 200, headers = {} } = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      // 集計は変動するのでキャッシュさせない。誤った古い数値の表示を防ぐ。
      'Cache-Control': 'no-store',
      ...headers,
    },
  });
}

async function verifyTurnstile(token, secret, ip) {
  if (!secret) throw new Error('TURNSTILE_SECRET_KEY is not configured');
  const form = new FormData();
  form.append('secret', secret);
  form.append('response', token);
  if (ip) form.append('remoteip', ip);
  const res = await fetch(TURNSTILE_VERIFY_URL, { method: 'POST', body: form });
  if (!res.ok) return false;
  const data = await res.json();
  return data.success === true;
}

async function fetchResults(db, questionId) {
  const { results } = await db
    .prepare('SELECT choice, COUNT(*) AS votes FROM votes WHERE question_id = ?1 GROUP BY choice')
    .bind(questionId)
    .all();
  return tallyToResults(questionId, results ?? []);
}

async function handleResults(url, env, cors) {
  const questionId = url.searchParams.get('q');
  if (!getQuestion(questionId)) {
    return json({ error: 'unknown_question' }, { status: 400, headers: cors });
  }
  return json(await fetchResults(env.DB, questionId), { headers: cors });
}

async function handleVote(request, env, cors) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'invalid_json' }, { status: 400, headers: cors });
  }

  const { question_id: questionId, choice, turnstile_token: turnstileToken } = body ?? {};
  const question = getQuestion(questionId);
  if (!question) {
    return json({ error: 'unknown_question' }, { status: 400, headers: cors });
  }
  if (!isValidChoice(questionId, choice)) {
    return json({ error: 'invalid_choice' }, { status: 400, headers: cors });
  }

  const ip = request.headers.get('CF-Connecting-IP') ?? '';
  if (typeof turnstileToken !== 'string' || !turnstileToken) {
    return json({ error: 'turnstile_required' }, { status: 400, headers: cors });
  }
  if (!(await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY, ip))) {
    return json({ error: 'turnstile_failed' }, { status: 403, headers: cors });
  }

  const voterHash = await computeVoterHash({
    secret: env.VOTER_SALT_SECRET,
    questionId,
    saltEpoch: question.saltEpoch,
    ip,
    userAgent: request.headers.get('User-Agent') ?? '',
  });

  // 連投レート制限。再投票は許可するが、短時間の連打は弾く。
  const previous = await env.DB.prepare(
    'SELECT updated_at FROM votes WHERE question_id = ?1 AND voter_hash = ?2',
  )
    .bind(questionId, voterHash)
    .first();
  const now = new Date();
  if (previous) {
    const elapsed = now.getTime() - Date.parse(previous.updated_at);
    if (Number.isFinite(elapsed) && elapsed < REVOTE_COOLDOWN_MS) {
      return json({ error: 'rate_limited' }, { status: 429, headers: cors });
    }
  }

  const nowIso = now.toISOString();
  await env.DB.prepare(
    `INSERT INTO votes (question_id, choice, voter_hash, created_at, updated_at)
     VALUES (?1, ?2, ?3, ?4, ?4)
     ON CONFLICT (question_id, voter_hash)
     DO UPDATE SET choice = excluded.choice, updated_at = excluded.updated_at`,
  )
    .bind(questionId, choice, voterHash, nowIso)
    .run();

  return json(
    { ...(await fetchResults(env.DB, questionId)), your_choice: choice },
    { headers: cors },
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(
      request.headers.get('Origin'),
      parseAllowedOrigins(env.ALLOWED_ORIGINS),
    );

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      if (request.method === 'GET' && url.pathname === '/v1/forecast/results') {
        return await handleResults(url, env, cors);
      }
      if (request.method === 'POST' && url.pathname === '/v1/forecast/vote') {
        return await handleVote(request, env, cors);
      }
    } catch (err) {
      // 詳細はログにのみ残し、クライアントには内部情報を返さない。
      console.error('forecast api error', err);
      return json({ error: 'internal_error' }, { status: 500, headers: cors });
    }

    return json({ error: 'not_found' }, { status: 404, headers: cors });
  },
};
