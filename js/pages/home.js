/**
 * エントリーポイント。
 *
 * data/snapshots.json を fetch してから各モジュールを初期化する。
 * fetch失敗時はカウンター部にエラーを表示し、可能な範囲で停止する。
 */

import { initBreakdown } from '../components/breakdown.js';
import { initChart } from '../components/chart.js';
import { initCounter } from '../components/counter.js';
import { initShare } from '../components/share.js';
import { initTankGauge } from '../components/tank-gauge.js';
import { loadHistory } from '../core/data.js';

function showLoadError(err) {
  console.error('Failed to load history:', err);
  const days = document.getElementById('counter-days');
  if (days) days.textContent = '—';
  const note = document.querySelector('.counter-note');
  if (note) {
    note.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    note.style.color = 'var(--tank-fill-warn)';
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

  try {
    initBreakdown(history);
  } catch (e) {
    console.error('breakdown:', e);
  }
  try {
    initChart(history);
  } catch (e) {
    console.error('chart:', e);
  }
  try {
    initTankGauge();
  } catch (e) {
    console.error('tank-gauge:', e);
  }
  try {
    initShare();
  } catch (e) {
    console.error('share:', e);
  }
  try {
    initCounter(history);
  } catch (e) {
    console.error('counter:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
