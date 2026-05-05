/**
 * F-02 タンクゲージ
 *
 * 縦長 SVG。fill rect の高さを (current / PEAK_REFERENCE.days) で計算する。
 * counter.js の subscribe() を使って秒ごとに同期する。
 *
 * 色分岐:
 *   ratio >= 0.8        : 黒（--tank-fill-ok）
 *   0.4 <= ratio < 0.8  : グレー（--tank-fill-mid）
 *   ratio < 0.4         : 控えめな赤（--tank-fill-warn）
 */

import { PEAK_REFERENCE } from '../core/data.js';
import { subscribe } from './counter.js';

const SVG_W = 200;
const SVG_H = 420;
const TANK_X = 36;
const TANK_Y = 40;
const TANK_W = 130;
const TANK_H = 340;
const STROKE = 1.5;

const insetTopY = TANK_Y + STROKE;
const insetBottomY = TANK_Y + TANK_H - STROKE;
const insetX = TANK_X + STROKE;
const insetW = TANK_W - STROKE * 2;
const insetH = insetBottomY - insetTopY;

function colorForRatio(r) {
  if (r >= 0.8) return 'var(--tank-fill-ok)';
  if (r >= 0.4) return 'var(--tank-fill-mid)';
  return 'var(--tank-fill-warn)';
}

function markY(frac) {
  return insetBottomY - insetH * frac;
}

export function initTankGauge() {
  const wrap = document.getElementById('tank-svg-wrap');
  if (!wrap) return;

  const peakDays = PEAK_REFERENCE.days;
  const halfDays = Math.round(peakDays / 2);

  wrap.innerHTML = `
    <svg viewBox="0 0 ${SVG_W} ${SVG_H}" xmlns="http://www.w3.org/2000/svg" role="img">
      <title>タンクゲージ: 現在の備蓄残量</title>
      <defs>
        <clipPath id="tank-clip">
          <rect x="${insetX}" y="${insetTopY}"
                width="${insetW}" height="${insetH}"
                rx="3" ry="3" />
        </clipPath>
      </defs>

      <!-- right-side ticks (25 / 50 / 75%) -->
      ${[0.25, 0.5, 0.75]
        .map(
          (f) =>
            `<line x1="${TANK_X + TANK_W}" y1="${markY(f)}" x2="${TANK_X + TANK_W + 6}" y2="${markY(f)}" stroke="#bbb" stroke-width="1" />`,
        )
        .join('')}

      <!-- top pipe stub -->
      <rect x="${TANK_X + TANK_W / 2 - 14}" y="${TANK_Y - 14}"
            width="28" height="14" fill="#1a1a1a" />

      <!-- fill (height set dynamically) -->
      <rect id="tank-fill" class="tank-fill-rect"
            x="${insetX}" y="${insetBottomY}"
            width="${insetW}" height="0"
            clip-path="url(#tank-clip)"
            fill="${colorForRatio(0.85)}" />

      <!-- outer frame on top of fill -->
      <rect x="${TANK_X}" y="${TANK_Y}"
            width="${TANK_W}" height="${TANK_H}"
            rx="4" ry="4"
            fill="none" stroke="#1a1a1a" stroke-width="${STROKE}" />

      <!-- right-side scale labels -->
      <text x="${TANK_X + TANK_W + 12}" y="${insetTopY + 4}"
            font-size="11" fill="#666" font-family="Inter, sans-serif">${peakDays}</text>
      <text x="${TANK_X + TANK_W + 12}" y="${markY(0.5) + 4}"
            font-size="11" fill="#999" font-family="Inter, sans-serif">${halfDays}</text>
      <text x="${TANK_X + TANK_W + 12}" y="${insetBottomY + 4}"
            font-size="11" fill="#999" font-family="Inter, sans-serif">0</text>
    </svg>
  `;

  const fillEl = wrap.querySelector('#tank-fill');
  const svgEl = wrap.querySelector('svg');
  const percentEl = document.getElementById('tank-percent');
  const peakEl = document.getElementById('tank-peak-days');
  const peakSourceEl = document.getElementById('tank-peak-source');
  if (peakEl) peakEl.textContent = String(peakDays);
  if (peakSourceEl) peakSourceEl.textContent = PEAK_REFERENCE.source;

  subscribe((days) => {
    const ratio = Math.max(0, Math.min(1, days / peakDays));
    const h = insetH * ratio;
    const y = insetBottomY - h;
    fillEl.setAttribute('height', h.toFixed(2));
    fillEl.setAttribute('y', y.toFixed(2));
    fillEl.setAttribute('fill', colorForRatio(ratio));

    if (percentEl) percentEl.textContent = (ratio * 100).toFixed(1);
    if (svgEl) {
      svgEl.setAttribute(
        'aria-label',
        `現在の備蓄: 約${Math.floor(days)}日（基準${peakDays}日の${(ratio * 100).toFixed(0)}%）`,
      );
    }
  });
}
