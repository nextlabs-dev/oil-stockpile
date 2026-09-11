/**
 * KPI カード（稼働中タンカー / 今日の消費ベース）
 *
 * - 日本に向かうタンカー（AIS）: data/tankers.json の japanBoundTankers を表示
 * - 今日の消費ベース: 1 / current_days × 100 で「1日経過すると備蓄が何 % 減るか」
 * - 前日比: 直近 2 snapshot の total 差分（日）
 *
 * 充填率カード（#tank-percent）は tank-gauge.js が更新する。
 */

import { loadJson } from '../core/data.js';
import { setText } from '../core/dom.js';
import { subscribe } from './counter.js';

const TANKERS_URL = './data/tankers.json';

function formatSigned(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  if (n === 0) return '±0';
  const fixed = Math.abs(n) < 10 ? n.toFixed(2) : n.toFixed(1);
  return n > 0 ? `+${fixed}` : fixed;
}

function formatPercent2(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  return n.toFixed(2);
}

function renderTankerCount(tankers) {
  // タンカータブと同じ「日本に向かうタンカー」（japanBoundTankers）を表示する。
  const count = Number(tankers?.japanBoundTankers);
  setText('kpi-tankers', Number.isFinite(count) ? String(count) : '—');
}

export function deltaBetweenSnapshots(history) {
  if (!Array.isArray(history) || history.length < 2) return Number.NaN;
  const latest = history[history.length - 1];
  const prev = history[history.length - 2];
  if (!Number.isFinite(latest?.total) || !Number.isFinite(prev?.total)) {
    return Number.NaN;
  }
  return latest.total - prev.total;
}

function renderDelta(history) {
  setText('kpi-delta', formatSigned(deltaBetweenSnapshots(history)));
}

export function initKpi(history) {
  // 1) burn rate は秒按分で更新
  const burnEl = document.getElementById('kpi-burn');
  if (burnEl) {
    subscribe((days) => {
      const pct = days > 0 ? (1 / days) * 100 : NaN;
      setText('kpi-burn', formatPercent2(pct));
    });
  }

  // 2) 前日比は snapshot 同士の差で固定値
  renderDelta(history);

  // 3) タンカー数は別 JSON を fetch
  loadJson(TANKERS_URL)
    .then(renderTankerCount)
    .catch((e) => {
      console.error('tankers.json load failed:', e);
      setText('kpi-tankers', '—');
    });
}
