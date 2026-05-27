/**
 * /scale/index.html のエントリーポイント。
 *
 * 経産省最新公表値の備蓄日数から、4 カードを描画する:
 *   - バレル換算 / リットル換算（容量視点）
 *   - VLCC 隻数 / お風呂杯数（スケール視点）
 *
 * 値の精度より「桁感」を優先し、すべて約・概算で表示する。
 * Japan 番組向けの「億・万」区切り表記に整形する formatJaNumber を用意。
 */

import { initCounter } from '../components/counter.js';
import { initShare } from '../components/share.js';
import { computeCurrentDays, loadHistory } from '../core/data.js';
import { setText } from '../core/dom.js';
import { formatInt } from '../core/format.js';

const CONSTANTS = {
  /** エネ庁備蓄算出ベース（純消費量、原油換算）約 28 万 kL/日。 */
  DAILY_CONSUMPTION_KL: 280_000,
  /** 1 バレル = 158.987 L (USA Petroleum barrel)。 */
  LITERS_PER_BARREL: 158.987,
  /** VLCC 1 隻の典型的積載量。30 万 kL（リファレンスの説明文に合わせる）。 */
  VLCC_CAPACITY_KL: 300_000,
  /** 家庭用お風呂 1 杯。一般的に 200–300 L とされ、本実装では 300 L を採用。 */
  BATH_VOLUME_L: 300,
  /** 日本の総人口（概算）。 */
  POPULATION: 125_000_000,
};

/** 整数を「○億○,○○○万」表記に整形する（億・万のいずれか / 両方）。 */
function formatJaNumber(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const x = Math.round(n);
  const oku = 100_000_000;
  const man = 10_000;
  if (x >= oku) {
    const okuPart = Math.floor(x / oku);
    const manPart = Math.floor((x % oku) / man);
    const head = okuPart.toLocaleString('ja-JP');
    if (manPart === 0) return `${head}億`;
    return `${head}億${manPart.toLocaleString('ja-JP')}万`;
  }
  if (x >= man) {
    const manPart = Math.floor(x / man);
    const remainder = x % man;
    const head = manPart.toLocaleString('ja-JP');
    if (remainder === 0) return `${head}万`;
    return `${head}万${remainder.toLocaleString('ja-JP')}`;
  }
  return x.toLocaleString('ja-JP');
}

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
  const totalKl = days * CONSTANTS.DAILY_CONSUMPTION_KL;
  const totalL = totalKl * 1_000;
  const totalBarrels = totalL / CONSTANTS.LITERS_PER_BARREL;
  const vlccCount = totalKl / CONSTANTS.VLCC_CAPACITY_KL;
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

  // initCounter populates latestSnapshot for the share module to read
  initCounter(history);

  const days = computeCurrentDays(snapshot);
  setText('scale-days', String(Math.floor(days)));
  setText('scale-as-of', formatYearMonth(snapshot.asOf));
  setText('header-last-updated', snapshot.published?.replaceAll('-', '.') ?? '—');

  renderCards(days);
  initShare();
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
