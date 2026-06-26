/**
 * F-03 推移グラフ（SVG手書き）
 *
 * 折れ線: 合計（黒、太め）の1本。Y軸は min-5..max+5 にスケールする。
 *
 * SVG 全体は aria-hidden の装飾。各データ点は純装飾の <circle>（focusable にしない）で、
 * マウスホバーで内訳ヒントを更新する。AT 向けの数値は buildHiddenTable の隠し表で提供する。
 *
 * initChart(history) で初期化。
 */

import { escapeHtml } from '../core/escape.js';
import { formatJaDate, formatMd } from '../core/format.js';

const DESKTOP_DIMS = {
  W: 720,
  H: 280,
  PAD_L: 44,
  PAD_R: 16,
  PAD_T: 16,
  PAD_B: 56,
  MAX_X_LABELS: 9,
};

// モバイル(≤640px)は viewBox を小さく・縦長にして SVG の縮小率を抑える。
// 文字サイズはユーザー単位固定で SVG と一緒に拡縮されるため、縮小率が下がると
// ラベルが相対的に大きく描画され、グラフ自体も縦に伸びて読み取りやすくなる。
const MOBILE_DIMS = {
  W: 400,
  H: 300,
  PAD_L: 40,
  PAD_R: 14,
  PAD_T: 18,
  PAD_B: 52,
  MAX_X_LABELS: 5,
};

function getChartDims() {
  const isMobile =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(max-width: 640px)').matches;
  return isMobile ? MOBILE_DIMS : DESKTOP_DIMS;
}

export function pickXLabelIndices(n, max) {
  if (n <= 0) return [];
  if (n <= max) return Array.from({ length: n }, (_, i) => i);
  const out = [];
  for (let k = 0; k < max; k++) {
    out.push(Math.round((k / (max - 1)) * (n - 1)));
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function buildHiddenTable(data) {
  const rows = data
    .map(
      (r) =>
        `<tr><th scope="row">${escapeHtml(formatJaDate(r.asOf))}</th>` +
        `<td>${r.total}</td><td>${r.national}</td><td>${r.private}</td><td>${r.joint}</td></tr>`,
    )
    .join('');
  return (
    `<table class="visually-hidden">` +
    `<caption>備蓄日数の推移（直近${data.length}データ点・単位は日）</caption>` +
    `<thead><tr>` +
    `<th scope="col">データ時点</th>` +
    `<th scope="col">合計</th>` +
    `<th scope="col">国家</th>` +
    `<th scope="col">民間</th>` +
    `<th scope="col">産油国共同</th>` +
    `</tr></thead>` +
    `<tbody>${rows}</tbody>` +
    `</table>`
  );
}

export function getYDomain(totals) {
  return {
    yMin: Math.max(0, Math.min(...totals) - 5),
    yMax: Math.max(...totals) + 5,
  };
}

export function buildChartModel(data, dims = DESKTOP_DIMS) {
  const { W, H, PAD_L, PAD_R, PAD_T, PAD_B } = dims;
  const totals = data.map((r) => r.total);
  const { yMin, yMax } = getYDomain(totals);
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;
  const n = data.length;

  const xAt = (i) => PAD_L + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const yAt = (v) => PAD_T + (1 - (v - yMin) / (yMax - yMin)) * plotH;

  return {
    yMin,
    yMax,
    points: data.map((row, i) => ({
      x: xAt(i),
      yTotal: yAt(row.total),
      row,
      i,
    })),
  };
}

function linePath(points, key) {
  return points
    .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p[key].toFixed(1)}`)
    .join(' ');
}

function renderGridSvg(model, dims) {
  const { W, H, PAD_L, PAD_R, PAD_T, PAD_B } = dims;
  const yTickCount = 4;
  let out = '';
  for (let t = 0; t <= yTickCount; t++) {
    const v = model.yMin + (t / yTickCount) * (model.yMax - model.yMin);
    const y = PAD_T + (1 - (v - model.yMin) / (model.yMax - model.yMin)) * (H - PAD_T - PAD_B);
    out += `<line class="chart-grid" x1="${PAD_L}" y1="${y.toFixed(1)}" x2="${W - PAD_R}" y2="${y.toFixed(1)}" />`;
    out += `<text class="chart-ytick" x="${PAD_L - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end">${Math.round(v)}</text>`;
  }
  return out;
}

function renderXTicksSvg(points, dims) {
  const { H, PAD_B, MAX_X_LABELS } = dims;
  const xIdx = pickXLabelIndices(points.length, MAX_X_LABELS);
  return xIdx
    .map((i) => {
      const p = points[i];
      return `<text class="chart-xtick" x="${p.x.toFixed(1)}" y="${(H - PAD_B + 16).toFixed(1)}" text-anchor="middle">${formatMd(p.row.asOf)}</text>`;
    })
    .join('');
}

export function renderPointsSvg(points) {
  return points
    .map((p) => {
      const r = p.row;
      const label = `${formatJaDate(r.asOf)} 合計${r.total}日（国家${r.national}・民間${r.private}・産油国共同${r.joint}）`;
      // 点は装飾（祖先 <svg> が aria-hidden）。tabindex/role/aria-label は付けない:
      // aria-hidden 下の focusable 要素は axe-core aria-hidden-focus 違反になり、
      // 無言の「幽霊タブストップ」を生むため。AT 向けデータは buildHiddenTable が担う。
      // <title> はマウスホバー時のネイティブツールチップ（視覚的補助）として残す。
      return `<circle class="chart-point" cx="${p.x.toFixed(1)}" cy="${p.yTotal.toFixed(1)}" r="3" data-i="${p.i}"><title>${escapeHtml(label)}</title></circle>`;
    })
    .join('');
}

function renderChartSvg(data, dims) {
  const { W, H, PAD_L, PAD_R, PAD_T } = dims;
  const model = buildChartModel(data, dims);
  return `
      ${buildHiddenTable(data)}
      <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        ${renderGridSvg(model, dims)}
        <text class="chart-axis-label" x="${((PAD_L + (W - PAD_R)) / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" text-anchor="middle">日付（月／日）</text>
        <text class="chart-axis-label" x="${PAD_L}" y="${(PAD_T - 4).toFixed(1)}" text-anchor="start">備蓄日数（日）</text>
        <path class="chart-line-total" d="${linePath(model.points, 'yTotal')}" />
        ${renderPointsSvg(model.points)}
        ${renderXTicksSvg(model.points, dims)}
      </svg>
    `;
}

function bindChartInteractions(wrap, data, hint, defaultHint) {
  wrap.querySelectorAll('.chart-point').forEach((el) => {
    const i = Number(el.getAttribute('data-i'));
    const row = data[i];
    const text = `${formatJaDate(row.asOf)}（公表 ${formatJaDate(row.published)}） 合計 ${row.total}日 ／ 国家 ${row.national} ・ 民間 ${row.private} ・ 産油国共同 ${row.joint}`;
    const setText = () => {
      if (hint) hint.textContent = text;
    };
    const resetText = () => {
      if (hint) hint.textContent = defaultHint;
    };
    // 点は focusable ではない（装飾）ため focus/blur は発火しない。ホバーのみ連動。
    el.addEventListener('mouseenter', setText);
    el.addEventListener('mouseleave', resetText);
  });
}

/**
 * @param {Array<{published:string,asOf:string,total:number,national:number,private:number,joint:number}>} history
 */
export function initChart(history) {
  const wrap = document.getElementById('chart-wrap');
  const hint = document.getElementById('chart-hint');
  if (!wrap) return;

  const data = history;
  if (!Array.isArray(data) || data.length === 0) {
    wrap.innerHTML = '<p class="chart-error">データがありません</p>';
    return;
  }

  const defaultHint = hint ? hint.textContent : '';

  function render() {
    wrap.innerHTML = renderChartSvg(data, getChartDims());
    bindChartInteractions(wrap, data, hint, defaultHint);
  }

  render();

  // モバイル境界を跨いだら、その幅向けの viewBox で描き直す
  if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
    const mq = window.matchMedia('(max-width: 640px)');
    if (typeof mq.addEventListener === 'function') {
      mq.addEventListener('change', () => render());
    }
  }
}
