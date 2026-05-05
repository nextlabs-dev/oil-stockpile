/**
 * /scale/index.html のエントリーポイント。
 *
 * data/snapshots.json から最新の備蓄日数を取得し、以下を描画する:
 *   - 単位換算: 日数 → kL / バレル / リットル
 *   - スケール比較: VLCC 換算 / 年間消費比 / IEA 90日比
 *   - サブタブ切替（ARIA tablist パターン）
 *
 * 換算根拠の概算値は CONSTANTS にまとめ、HTML 側にも出典注記を併記する。
 * 値の精度より「桁感の正しさ」を優先し、すべて約・概算で表示する。
 */

import { computeCurrentDays, loadHistory } from '../core/data.js';
import { setText } from '../core/dom.js';
import { formatFixed1, formatInt, formatJaDate } from '../core/format.js';

const CONSTANTS = {
  /** エネ庁備蓄算出ベース（純消費量、原油換算）約 28 万 kL/日 ≈ 176 万 bbl/日。
   *  備蓄日数 × 本値 = 経産省 PDF の備蓄量と直接突き合わせ可能。
   *  国際統計 (BP/EIA) ベースの 50 万 kL/日 (LPG・ナフサ込み) とは別系列なので注意。 */
  DAILY_CONSUMPTION_KL: 280_000,
  /** 1 バレル = 158.987 L (USA Petroleum barrel)。 */
  LITERS_PER_BARREL: 158.987,
  /** VLCC 1 隻の典型的積載量。30 万 DWT 級・原油密度 0.86 で約 32 万 kL。 */
  VLCC_CAPACITY_KL: 320_000,
  /** IEA 加盟国に課された備蓄義務（純輸入量の 90 日分）。 */
  IEA_OBLIGATION_DAYS: 90,
};

function showLoadError() {
  const num = document.getElementById('scale-days');
  if (num) num.textContent = '—';
  const sub = document.querySelector('.scale-sub');
  if (sub) {
    sub.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    sub.style.color = 'var(--tank-fill-warn)';
  }
}

function renderUnitConversion(days) {
  const totalKl = days * CONSTANTS.DAILY_CONSUMPTION_KL;
  const totalLiters = totalKl * 1_000;
  const totalBarrels = totalLiters / CONSTANTS.LITERS_PER_BARREL;

  setText('unit-kl', formatInt(totalKl));
  setText('unit-barrels', formatInt(totalBarrels));
  setText('unit-liters', formatInt(totalLiters));
}

function renderScaleComparison(days) {
  const totalKl = days * CONSTANTS.DAILY_CONSUMPTION_KL;
  const vlccCount = totalKl / CONSTANTS.VLCC_CAPACITY_KL;
  const yearPct = (days / 365) * 100;
  const yearFrac = days / 365;
  const ieaPct = (days / CONSTANTS.IEA_OBLIGATION_DAYS) * 100;

  setText('compare-vlcc', formatInt(vlccCount));
  setText('compare-year-pct', formatFixed1(yearPct));
  setText('compare-year-frac', `約 ${formatFixed1(yearFrac)}`);
  setText('compare-iea-pct', formatInt(ieaPct));
}

function initSubTabs() {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  const panels = Array.from(document.querySelectorAll('[role="tabpanel"]'));
  if (tabs.length === 0) return;

  function activate(targetTab) {
    for (const t of tabs) {
      const isActive = t === targetTab;
      t.setAttribute('aria-selected', isActive ? 'true' : 'false');
      t.tabIndex = isActive ? 0 : -1;
      t.classList.toggle('subtab--active', isActive);
    }
    const controlsId = targetTab.getAttribute('aria-controls');
    for (const p of panels) {
      p.hidden = p.id !== controlsId;
    }
  }

  for (const tab of tabs) {
    tab.addEventListener('click', () => activate(tab));
    tab.addEventListener('keydown', (e) => {
      const idx = tabs.indexOf(tab);
      let nextIdx = null;
      if (e.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length;
      else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length;
      else if (e.key === 'Home') nextIdx = 0;
      else if (e.key === 'End') nextIdx = tabs.length - 1;
      if (nextIdx !== null) {
        e.preventDefault();
        const next = tabs[nextIdx];
        activate(next);
        next.focus();
      }
    });
  }
}

async function main() {
  initSubTabs();

  let snapshot;
  try {
    const history = await loadHistory('../data/snapshots.json');
    snapshot = history[history.length - 1];
  } catch (e) {
    console.error('snapshots load failed:', e);
    showLoadError();
    return;
  }

  // カウンターページと同じ「いまこの瞬間の推計値」を起点に表示
  const days = computeCurrentDays(snapshot);
  setText('scale-days', String(Math.floor(days)));
  setText('scale-as-of', formatJaDate(snapshot.asOf));

  renderUnitConversion(days);
  renderScaleComparison(days);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
