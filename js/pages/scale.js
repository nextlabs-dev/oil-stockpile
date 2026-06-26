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
  STALE_THRESHOLD_DAYS,
  VLCC_CAPACITY_KL,
} from '../core/data.js';
import { onReady, setText, showElement } from '../core/dom.js';
import { formatDotDate, formatInt, formatJaNumber } from '../core/format.js';

const CONSTANTS = {
  /** 1 バレル = 158.987 L (USA Petroleum barrel)。 */
  LITERS_PER_BARREL: 158.987,
  /** 家庭用お風呂 1 杯。一般的に 200–300 L とされ、本実装では 300 L を採用。 */
  BATH_VOLUME_L: 300,
  /** 日本の総人口（概算）。 */
  POPULATION: 125_000_000,
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

async function main() {
  let history;
  try {
    history = await loadHistory('../data/snapshots.json');
  } catch (e) {
    console.error('snapshots load failed:', e);
    showLoadError();
    return;
  }
  const snapshot = history[history.length - 1];

  const days = computeCurrentDays(snapshot);
  // 構造的に有効だが内容無効（total 非数値 / asOf 欠落・不正）なスナップショットを
  // fetch 失敗と同じエラー状態に倒す。"NaN日分" を描かないためのガード。
  if (!Number.isFinite(days)) {
    console.error('invalid snapshot (computeCurrentDays returned NaN):', snapshot);
    showLoadError();
    return;
  }

  setText('scale-days', String(Math.floor(days)));
  setText('scale-as-of', formatYearMonth(snapshot.asOf));
  setText('header-last-updated', formatDotDate(snapshot.published));

  // データ取得が止まっている可能性の警告（counter と同じ 14 日しきい値）。
  if (elapsedDaysSince(snapshot.asOf) > STALE_THRESHOLD_DAYS) {
    showElement('scale-stale-warning');
  }

  renderCards(days);
}

onReady(main);
