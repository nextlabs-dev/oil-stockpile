/**
 * 内訳ドーナツ（4 区分の pie / donut）
 *
 * 国家備蓄・民間備蓄・産油国共同備蓄・その他 の 4 セグメントを比率で描く。
 * 中央には latest.total 日分を表示。凡例は #donut-legend に流し込む。
 *
 * 充填率（current / PEAK_REFERENCE.days）は KPI カード #tank-percent に
 * 別途反映する。counter.js の subscribe() を購読する。
 */

import { PEAK_REFERENCE } from '../core/data.js';
import { escapeHtml } from '../core/escape.js';
import { subscribe } from './counter.js';

const SVG_SIZE = 200;
const CENTER = SVG_SIZE / 2;
const RADIUS = 72;
const STROKE = 22;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const SEGMENTS = [
  { key: 'national', label: '国家備蓄', color: 'var(--donut-national)' },
  { key: 'private', label: '民間備蓄', color: 'var(--donut-private)' },
  { key: 'joint', label: '産油国共同備蓄', color: 'var(--donut-joint)' },
  { key: 'other', label: 'その他', color: 'var(--donut-other)' },
];

function computeSegments(snapshot) {
  const national = Number(snapshot.national) || 0;
  const privateVal = Number(snapshot.private) || 0;
  const joint = Number(snapshot.joint) || 0;
  const total = Number(snapshot.total) || 0;
  const sum3 = national + privateVal + joint;
  const other = Math.max(0, total - sum3);
  return {
    national,
    private: privateVal,
    joint,
    other,
    total,
  };
}

function renderDonutSvg(segs) {
  const denom = segs.national + segs.private + segs.joint + segs.other;
  let offset = 0;
  const arcs = SEGMENTS.map((seg) => {
    const value = segs[seg.key];
    const portion = denom > 0 ? value / denom : 0;
    const arcLen = portion * CIRCUMFERENCE;
    const path = `<circle cx="${CENTER}" cy="${CENTER}" r="${RADIUS}"
      fill="none"
      stroke="${seg.color}"
      stroke-width="${STROKE}"
      stroke-linecap="butt"
      stroke-dasharray="${arcLen.toFixed(2)} ${(CIRCUMFERENCE - arcLen).toFixed(2)}"
      stroke-dashoffset="${(-offset).toFixed(2)}" />`;
    offset += arcLen;
    return path;
  }).join('');

  return `
    <svg viewBox="0 0 ${SVG_SIZE} ${SVG_SIZE}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="備蓄日数の内訳ドーナツ">
      <title>備蓄日数の内訳</title>
      <g transform="rotate(-90 ${CENTER} ${CENTER})">
        ${arcs}
      </g>
      <text
        x="${CENTER}" y="${CENTER - 18}"
        text-anchor="middle"
        class="donut-center-label">合計</text>
      <text id="donut-center-value"
        x="${CENTER}" y="${CENTER + 8}"
        text-anchor="middle"
        class="donut-center-value">${segs.total}</text>
      <text
        x="${CENTER}" y="${CENTER + 26}"
        text-anchor="middle"
        class="donut-center-unit">日分</text>
    </svg>
  `;
}

function renderLegend(segs) {
  return SEGMENTS.map(
    (seg) => `
      <div class="donut-legend-row">
        <span class="donut-legend-dot" style="background: ${seg.color}" aria-hidden="true"></span>
        <dt class="donut-legend-label">${escapeHtml(seg.label)}</dt>
        <dd class="donut-legend-value">${segs[seg.key]}<span class="donut-legend-unit">日分</span></dd>
      </div>
    `,
  ).join('');
}

export function initTankGauge(history) {
  const wrap = document.getElementById('tank-svg-wrap');
  const legend = document.getElementById('donut-legend');
  if (!wrap) return;

  const latest = Array.isArray(history) && history.length > 0 ? history[history.length - 1] : null;
  if (!latest) return;

  const segs = computeSegments(latest);
  wrap.innerHTML = renderDonutSvg(segs);
  if (legend) legend.innerHTML = renderLegend(segs);

  for (const id of ['tank-peak-days', 'hero-peak-days', 'hero-meter-peak']) {
    const el = document.getElementById(id);
    if (el) el.textContent = String(PEAK_REFERENCE.days);
  }

  // 充填率を秒按分で更新する（KPI カード + ヒーローのリード文 / メーター）
  const peakDays = PEAK_REFERENCE.days;
  const percentEl = document.getElementById('tank-percent');
  const heroPercentEl = document.getElementById('hero-fill-percent');
  const heroFillEl = document.getElementById('hero-meter-fill');
  subscribe((days) => {
    const ratio = Math.max(0, Math.min(1, days / peakDays));
    const percent = (ratio * 100).toFixed(1);
    if (percentEl) percentEl.textContent = percent;
    if (heroPercentEl) heroPercentEl.textContent = percent;
    if (heroFillEl) heroFillEl.style.width = `${percent}%`;
  });
}
