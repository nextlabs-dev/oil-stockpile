/**
 * /scale/index.html のエントリーポイント。
 *
 * 経産省最新公表値の備蓄日数から、4 カードを描画する:
 *   - バレル換算 / リットル換算（容量視点）
 *   - VLCC 隻数 / お風呂杯数（スケール視点）
 *
 * 値の精度より「桁感」を優先し、すべて約・概算で表示する。
 * 大きな数値は core/format.js の formatJaNumber で「億・万」区切りに整形する。
 */

import {
  computeCurrentDays,
  DAILY_CONSUMPTION_KL,
  elapsedDaysSince,
  loadHistory,
  loadLpgHistory,
  STALE_THRESHOLD_DAYS,
  VLCC_CAPACITY_KL,
} from '../core/data.js';
import { onReady, setText, showElement } from '../core/dom.js';
import { formatDotDate, formatInt, formatJaNumber } from '../core/format.js';

const CONSTANTS = {
  // 石油
  LITERS_PER_BARREL: 158.987,
  BATH_VOLUME_L: 300,
  POPULATION: 125_000_000,

  // LPG
  LPG_SPHERICAL_TANK_TONS: 1000,
  LPG_CASSETTE_CARTRIDGE_KG: 0.25,
  LPG_PROPANE_CYLINDER_KG: 50,
  LPG_VLGC_TONS: 44000,
  LPG_VOLUME_TONS: 2_912_000,
};

function formatYearMonth(iso) {
  if (!iso) return '—';
  const [y, m] = iso.split('-');
  if (!y || !m) return iso;
  return `${parseInt(y, 10)}年${parseInt(m, 10)}月`;
}

function showLoadError() {
  setText('scale-days', '—');
  for (const id of [
    'unit-barrels',
    'unit-liters',
    'compare-vlcc',
    'compare-bath',
    'compare-bath-years',
  ]) {
    setText(id, '—');
  }
}

function renderCards(days) {
  const totalKl = days * DAILY_CONSUMPTION_KL;
  const totalL = totalKl * 1_000;
  const totalBarrels = totalL / CONSTANTS.LITERS_PER_BARREL;
  const vlccCount = totalKl / VLCC_CAPACITY_KL;
  const bathCount = totalL / CONSTANTS.BATH_VOLUME_L;
  // 全国民が 1 日 1 杯入る場合、備蓄でまかなえる日数
  const bathDays = bathCount / CONSTANTS.POPULATION;

  setText('unit-barrels', formatJaNumber(totalBarrels));
  setText('unit-liters', formatJaNumber(totalL));
  setText('compare-vlcc', formatInt(vlccCount));
  setText('compare-bath', formatJaNumber(bathCount));
  setText('compare-bath-years', formatInt(bathDays));
}

function renderLpgCards(snapshot) {
  const volumeTons = CONSTANTS.LPG_VOLUME_TONS;
  const volumeKg = volumeTons * 1_000;

  // 6 ものさしカード
  const sphericalTanks = volumeTons / CONSTANTS.LPG_SPHERICAL_TANK_TONS;
  const cartridges = volumeKg / CONSTANTS.LPG_CASSETTE_CARTRIDGE_KG;
  const propaneCylinders = volumeKg / CONSTANTS.LPG_PROPANE_CYLINDER_KG;
  const vlgcShips = volumeTons / CONSTANTS.LPG_VLGC_TONS;

  setText('unit-volume', formatJaNumber(volumeTons / 1_000_000)); // 万トン単位（例：291万）
  setText('unit-spherical-tanks', formatInt(sphericalTanks));
  setText('unit-cassettes', formatJaNumber(cartridges));
  setText('unit-propane-cylinders', formatJaNumber(propaneCylinders));
  setText('compare-vlgc', formatInt(vlgcShips));
  setText('compare-disaster-days', Math.round(snapshot.totalDays * 10) / 10);
}

async function main() {
  let oilHistory, lpgHistory;
  try {
    oilHistory = await loadHistory('../data/snapshots.json');
    lpgHistory = await loadLpgHistory('../data/lpg_snapshots.json');
  } catch (e) {
    console.error('history load failed:', e);
    showLoadError();
    return;
  }

  function renderOil() {
    const snapshot = oilHistory[oilHistory.length - 1];
    const days = computeCurrentDays(snapshot);
    if (!Number.isFinite(days)) {
      console.error('invalid snapshot:', snapshot);
      showLoadError();
      return;
    }
    setText('scale-days', String(Math.floor(days)));
    setText('scale-as-of', formatYearMonth(snapshot.asOf));
    setText('header-last-updated', formatDotDate(snapshot.published));
    if (elapsedDaysSince(snapshot.asOf) > STALE_THRESHOLD_DAYS) {
      showElement('scale-stale-warning');
    }
    renderCards(days);
  }

  function renderLpg() {
    const snapshot = lpgHistory[lpgHistory.length - 1];
    setText('scale-days', String(Math.round(snapshot.totalDays * 10) / 10));
    setText('scale-as-of', formatYearMonth(snapshot.asOf));
    setText('header-last-updated', formatDotDate(snapshot.published));
    // LPG は月次なので古さ警告は常に非表示
    const warning = document.getElementById('scale-stale-warning');
    if (warning) warning.style.display = 'none';
    renderLpgCards(snapshot);
  }

  renderOil();

  // [石油][LPG] トグル
  document.querySelectorAll('[data-fuel]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const fuel = btn.dataset.fuel;
      if (fuel === 'oil') {
        renderOil();
      } else if (fuel === 'lpg') {
        renderLpg();
      }
      document.querySelectorAll('[data-fuel]').forEach((b) => {
        b.classList.toggle('active', b.dataset.fuel === fuel);
      });
    });
  });

  const oilBtn = document.querySelector('[data-fuel="oil"]');
  if (oilBtn) oilBtn.classList.add('active');
}

onReady(main);
