/**
 * 有事終息予想（/forecast/）のページエントリ。
 *
 * 方針（仕様 §6）:
 *  - 表示する数値は自サイトの実投票結果だけ。**取得失敗時にモックや推測値へ
 *    フォールバックしない**。落ちたことをそのまま伝える。
 *  - 投票前は全体結果を伏せる（バンドワゴン効果を避ける）。総投票数のみ出す。
 *  - localStorage は「投票済み表示」の UX 補助のみ。信頼の根拠にはしない。
 */

import { loadHistory } from '../core/data.js';
import { onReady, setText } from '../core/dom.js';
import { escapeHtml } from '../core/escape.js';
import {
  barWidth,
  FORECAST_CHOICES,
  FORECAST_CONFIG,
  formatPercent,
  isForecastEnabled,
  toDisplayRows,
  votesUntilPercent,
} from '../core/forecast.js';
import { formatDotDate } from '../core/format.js';

const STORAGE_KEY = `forecast:${FORECAST_CONFIG.questionId}`;

const els = {};
let turnstileWidgetId = null;
let submitting = false;

function cacheElements() {
  for (const id of [
    'forecast-choices',
    'forecast-status',
    'forecast-results',
    'forecast-results-list',
    'forecast-total',
    'forecast-threshold-note',
    'forecast-your-choice',
    'forecast-revote',
    'forecast-turnstile',
  ]) {
    els[id] = document.getElementById(id);
  }
}

/** 前回の選択（UX 補助）。壊れた値や storage 無効環境では黙って null を返す。 */
function readStoredChoice() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return FORECAST_CHOICES.some((c) => c.id === v) ? v : null;
  } catch {
    return null;
  }
}

function storeChoice(choice) {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    /* storage 無効でも投票自体は成立しているので無視する */
  }
}

function setStatus(message, tone = 'info') {
  const el = els['forecast-status'];
  if (!el) return;
  el.textContent = message;
  el.dataset.tone = tone;
  el.hidden = !message;
}

function apiUrl(path) {
  return `${FORECAST_CONFIG.apiOrigin.replace(/\/+$/, '')}${path}`;
}

async function fetchResults() {
  const url = apiUrl(`/v1/forecast/results?q=${encodeURIComponent(FORECAST_CONFIG.questionId)}`);
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) throw new Error(`results ${res.status}`);
  return res.json();
}

async function postVote(choice, turnstileToken) {
  const res = await fetch(apiUrl('/v1/forecast/vote'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question_id: FORECAST_CONFIG.questionId,
      choice,
      turnstile_token: turnstileToken,
    }),
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const err = new Error(data?.error ?? `vote ${res.status}`);
    err.code = data?.error;
    err.status = res.status;
    throw err;
  }
  return data;
}

const VOTE_ERROR_MESSAGES = {
  rate_limited: '投票の間隔が短すぎます。少し待ってからもう一度お試しください。',
  turnstile_required: '認証が完了していません。チェックを終えてから投票してください。',
  turnstile_failed: '認証に失敗しました。ページを再読み込みしてお試しください。',
  invalid_choice: '選択肢が不正です。ページを再読み込みしてください。',
  unknown_question: '設問が見つかりません。ページを再読み込みしてください。',
};

function renderResults(results, yourChoice) {
  const list = els['forecast-results-list'];
  if (!list) return;
  const total = Number(results?.total) || 0;
  const rows = toDisplayRows(results);

  list.innerHTML = rows
    .map((row) => {
      const isYours = row.id === yourChoice;
      const percentText = formatPercent(row.percent);
      // 率を出さない期間はバー自体を描かず、実数だけを見せる。
      // 幅は style 属性ではなく、描画後に CSSOM で入れる（下の for ループ）。
      // CSP の style-src に 'unsafe-inline' が無いため、マークアップ由来の
      // style="…" は無視されて幅 0 になる。CSSOM 代入は CSP の対象外。
      const bar =
        row.percent == null
          ? ''
          : '<span class="fc-bar" aria-hidden="true"><span class="fc-bar-fill"></span></span>';
      return `
        <li class="fc-result${isYours ? ' fc-result--yours' : ''}">
          <span class="fc-result-head">
            <span class="fc-result-label">${escapeHtml(row.label)}${
              isYours ? '<span class="fc-yours-tag">あなたの予測</span>' : ''
            }</span>
            <span class="fc-result-figure">
              <span class="fc-result-votes">${row.votes.toLocaleString('ja-JP')}票</span>
              ${percentText ? `<span class="fc-result-percent">${percentText}</span>` : ''}
            </span>
          </span>
          ${bar}
        </li>`;
    })
    .join('');

  // バー幅を CSSOM で設定する。行の並びは rows と一致する。
  const items = list.querySelectorAll('.fc-result');
  rows.forEach((row, i) => {
    const fill = items[i]?.querySelector('.fc-bar-fill');
    if (fill) fill.style.width = `${barWidth(row.percent)}%`;
  });

  setText('forecast-total', `総投票数 ${total.toLocaleString('ja-JP')}票`);

  const note = els['forecast-threshold-note'];
  if (note) {
    const remaining = votesUntilPercent(total);
    if (remaining > 0) {
      note.textContent = `集計中です。割合の表示は総投票数が${FORECAST_CONFIG.minVotesForPercent}票に達してから（あと${remaining}票）。それまでは実数のみを表示します。`;
      note.hidden = false;
    } else {
      note.hidden = true;
    }
  }

  if (els['forecast-results']) els['forecast-results'].hidden = false;
}

function markSelected(choice) {
  const buttons = els['forecast-choices']?.querySelectorAll('.fc-choice');
  if (!buttons) return;
  for (const b of buttons) {
    const isSelected = b.dataset.choice === choice;
    b.classList.toggle('fc-choice--selected', isSelected);
    b.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
  }
}

/** Turnstile のトークンを取る。未設定・未読込なら null（呼び出し側で弾く）。 */
function getTurnstileToken() {
  if (!FORECAST_CONFIG.turnstileSiteKey) return null;
  if (typeof window.turnstile === 'undefined' || turnstileWidgetId === null) return null;
  return window.turnstile.getResponse(turnstileWidgetId) || null;
}

function resetTurnstile() {
  if (typeof window.turnstile !== 'undefined' && turnstileWidgetId !== null) {
    window.turnstile.reset(turnstileWidgetId);
  }
}

/**
 * Turnstile の api.js は実装を内部で非同期に読み込むため、スクリプトタグの
 * 実行直後（DOMContentLoaded 時点）にはまだ window.turnstile が生えていない。
 * インライン script は CSP で使えず onload コールバックを登録できないので、
 * 準備できるまで短い間隔で待つ。上限を超えたら fail closed（投票させない）。
 */
const TURNSTILE_POLL_MS = 100;
const TURNSTILE_TIMEOUT_MS = 10_000;

function whenTurnstileReady() {
  return new Promise((resolve) => {
    if (window.turnstile?.render) {
      resolve(true);
      return;
    }
    const startedAt = Date.now();
    const timer = setInterval(() => {
      if (window.turnstile?.render) {
        clearInterval(timer);
        resolve(true);
      } else if (Date.now() - startedAt > TURNSTILE_TIMEOUT_MS) {
        clearInterval(timer);
        resolve(false);
      }
    }, TURNSTILE_POLL_MS);
  });
}

async function initTurnstile() {
  const host = els['forecast-turnstile'];
  if (!host || !FORECAST_CONFIG.turnstileSiteKey) return;
  if (!(await whenTurnstileReady())) {
    // 認証を読み込めない以上、投票は受け付けない（bot 対策を素通りさせない）。
    disableVoting('認証の読み込みに失敗しました。ページを再読み込みしてお試しください。');
    return;
  }
  turnstileWidgetId = window.turnstile.render(host, {
    sitekey: FORECAST_CONFIG.turnstileSiteKey,
    action: 'forecast-vote',
  });
  host.hidden = false;
}

async function submitVote(choice) {
  if (submitting) return;
  const token = getTurnstileToken();
  if (!token) {
    setStatus('認証を完了してから投票してください。', 'warn');
    return;
  }

  submitting = true;
  setStatus('投票を送信しています…');
  try {
    const results = await postVote(choice, token);
    storeChoice(choice);
    markSelected(choice);
    renderResults(results, results.your_choice ?? choice);
    setStatus('投票を受け付けました。予測はいつでも変更できます。', 'ok');
    if (els['forecast-revote']) els['forecast-revote'].hidden = false;
  } catch (e) {
    console.error('vote:', e);
    setStatus(
      VOTE_ERROR_MESSAGES[e.code] ?? '投票を送信できませんでした。時間をおいてお試しください。',
      'error',
    );
  } finally {
    resetTurnstile();
    submitting = false;
  }
}

function initChoices() {
  const host = els['forecast-choices'];
  if (!host) return;
  host.addEventListener('click', (event) => {
    const button = event.target.closest('.fc-choice');
    if (!button || !host.contains(button)) return;
    submitVote(button.dataset.choice);
  });
}

/**
 * 投票済みの来訪者には結果を先に見せる（投票前は伏せる仕様のため、
 * localStorage に記録がある場合だけ先読みする）。
 */
async function showResultsIfVoted() {
  const stored = readStoredChoice();
  if (!stored) return;
  markSelected(stored);
  if (els['forecast-revote']) els['forecast-revote'].hidden = false;
  try {
    renderResults(await fetchResults(), stored);
  } catch (e) {
    console.error('results:', e);
    setStatus('現在集計を取得できません。時間をおいて再度お試しください。', 'error');
  }
}

function disableVoting(message) {
  const host = els['forecast-choices'];
  if (host) {
    for (const b of host.querySelectorAll('.fc-choice')) {
      b.disabled = true;
    }
  }
  setStatus(message, 'warn');
}

async function main() {
  cacheElements();

  try {
    const history = await loadHistory('../data/snapshots.json');
    const latest = history[history.length - 1];
    if (latest) setText('header-last-updated', formatDotDate(latest.published));
  } catch (e) {
    console.error('history:', e);
  }

  if (!isForecastEnabled()) {
    // API 未デプロイ。設問は読めるが投票はできない状態を正直に出す。
    disableVoting('投票機能は準備中です。集計基盤の公開までお待ちください。');
    return;
  }

  initChoices();
  // 投票済みなら結果は先に出す。Turnstile の準備完了は待たない（描画を待たせない）。
  await Promise.all([initTurnstile(), showResultsIfVoted()]);
}

onReady(main);
