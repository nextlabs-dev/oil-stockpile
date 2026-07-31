/**
 * エントリーポイント。
 *
 * data/snapshots.json を fetch してから各モジュールを初期化する。
 * fetch失敗時はカウンター部にエラーを表示し、可能な範囲で停止する。
 */

import { initChart } from '../components/chart.js';
import { initCounter, setFuelMode } from '../components/counter.js';
import { initKpi } from '../components/kpi.js';
import { initShare } from '../components/share.js';
import { initTankGauge } from '../components/tank-gauge.js';
import { loadHistory, loadLpgHistory } from '../core/data.js';
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
  let oilHistory, lpgHistory;
  try {
    oilHistory = await loadHistory();
    lpgHistory = await loadLpgHistory();
  } catch (e) {
    showLoadError(e);
    return;
  }

  setFuelMode('oil');
  safeInit('counter', () => initCounter(oilHistory));
  safeInit('kpi', () => initKpi(oilHistory));
  safeInit('chart', () => initChart(oilHistory));
  safeInit('tank-gauge', () => initTankGauge(oilHistory));
  safeInit('share', () => initShare());

  populateHeaderAndBanner(oilHistory);

  // [石油][LPG] トグル
  document.querySelectorAll('[data-fuel]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      const fuel = btn.dataset.fuel;
      const history = fuel === 'oil' ? oilHistory : lpgHistory;

      setFuelMode(fuel);
      initCounter(history);
      initKpi(history);
      initChart(history);
      initTankGauge(history);

      populateHeaderAndBanner(history);

      // トグル状態を更新（active クラス）
      document.querySelectorAll('[data-fuel]').forEach((b) => {
        b.classList.toggle('active', b.dataset.fuel === fuel);
      });
    });
  });

  // 初期時点で石油ボタンをアクティブ化
  const oilBtn = document.querySelector('[data-fuel="oil"]');
  if (oilBtn) oilBtn.classList.add('active');
}

onReady(main);
