/**
 * エントリーポイント。
 *
 * data/snapshots.json を fetch してから各モジュールを初期化する。
 * fetch失敗時はカウンター部にエラーを表示し、可能な範囲で停止する。
 */

import { initChart } from '../components/chart.js';
import { initCounter } from '../components/counter.js';
import { initKpi } from '../components/kpi.js';
import { initShare } from '../components/share.js';
import { initStatusTicker } from '../components/status-ticker.js';
import { initTankGauge } from '../components/tank-gauge.js';
import { loadHistory } from '../core/data.js';
import { onReady, safeInit, setText } from '../core/dom.js';
import { formatDotDate } from '../core/format.js';

function populateHeaderAndBanner(history) {
  const latest = history[history.length - 1];
  if (!latest) return;
  setText('update-banner-date', formatDotDate(latest.published));
  setText('header-last-updated', formatDotDate(latest.published));
}

function showLoadError(err) {
  console.error('Failed to load history:', err);
  const days = document.getElementById('counter-days');
  if (days) days.textContent = '—';
  const note = document.querySelector('.counter-note');
  if (note) {
    note.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    note.classList.add('is-error');
  }
}

async function main() {
  let history;
  try {
    history = await loadHistory();
  } catch (e) {
    showLoadError(e);
    return;
  }

  // counter を先に初期化することで、続く tank-gauge の subscribe() が
  // 即座に正しい値で同期される（latestSnapshot 未設定で NaN が DOM に
  // 書き込まれる隙間を作らない）。順序を保つため逐次に呼ぶ。
  safeInit('counter', () => initCounter(history));
  safeInit('kpi', () => initKpi(history));
  safeInit('chart', () => initChart(history));
  safeInit('tank-gauge', () => initTankGauge(history));
  safeInit('share', () => initShare());
  safeInit('status-ticker', () => initStatusTicker(history));

  populateHeaderAndBanner(history);
}

onReady(main);
