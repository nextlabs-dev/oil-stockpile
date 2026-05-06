/**
 * F-03 推移グラフ（SVG手書き）
 *
 * メイン折れ線: 合計（黒、太め）
 * トグルON時: 国家/民間/産油国共同の3線を追加表示
 *   ※ 3区分は値域が異なる（合計~230 / 国家~140 / 民間~85 / 産油国~5）ため、
 *      トグルONでY軸を0〜maxの広域に再スケールする。
 *
 * 各点に role="button" tabindex="0" を付与し、ホバー/フォーカスでヒント文を更新。
 *
 * initChart(history) で初期化。
 */

import { escapeHtml } from '../core/escape.js';
import { formatJaDate, formatMd } from '../core/format.js';

const W = 720;
const H = 280;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 56;
const MAX_X_LABELS = 9;

function pickXLabelIndices(n, max) {
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

function getYDomain(totals, showSegments) {
  if (showSegments) {
    return {
      yMin: 0,
      yMax: Math.max(...totals) + 10,
    };
  }
  return {
    yMin: Math.max(0, Math.min(...totals) - 5),
    yMax: Math.max(...totals) + 5,
  };
}

function buildChartModel(data, showSegments) {
  const totals = data.map((r) => r.total);
  const { yMin, yMax } = getYDomain(totals, showSegments);
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
      yNational: yAt(row.national),
      yPrivate: yAt(row.private),
      yJoint: yAt(row.joint),
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

function renderGridSvg(model) {
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

function renderXTicksSvg(points) {
  const xIdx = pickXLabelIndices(points.length, MAX_X_LABELS);
  return xIdx
    .map((i) => {
      const p = points[i];
      return `<text class="chart-xtick" x="${p.x.toFixed(1)}" y="${(H - PAD_B + 16).toFixed(1)}" text-anchor="middle">${formatMd(p.row.asOf)}</text>`;
    })
    .join('');
}

function renderPointsSvg(points) {
  return points
    .map((p) => {
      const r = p.row;
      const label = `${formatJaDate(r.asOf)} 合計${r.total}日（国家${r.national}・民間${r.private}・産油国共同${r.joint}）`;
      return `<circle class="chart-point" cx="${p.x.toFixed(1)}" cy="${p.yTotal.toFixed(1)}" r="3" data-i="${p.i}" role="button" tabindex="0" aria-label="${escapeHtml(label)}"><title>${escapeHtml(label)}</title></circle>`;
    })
    .join('');
}

function renderSegmentLinesSvg(points, showSegments) {
  if (!showSegments) return '';
  return `<path class="chart-line-segment chart-line-joint" d="${linePath(points, 'yJoint')}" />
         <path class="chart-line-segment chart-line-private" d="${linePath(points, 'yPrivate')}" />
         <path class="chart-line-segment chart-line-national" d="${linePath(points, 'yNational')}" />`;
}

function renderChartSvg(data, showSegments) {
  const model = buildChartModel(data, showSegments);
  return `
      ${buildHiddenTable(data)}
      <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        ${renderGridSvg(model)}
        <text class="chart-axis-label" x="${((PAD_L + (W - PAD_R)) / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" text-anchor="middle">データ時点（月/日）</text>
        ${renderSegmentLinesSvg(model.points, showSegments)}
        <path class="chart-line-total" d="${linePath(model.points, 'yTotal')}" />
        ${renderPointsSvg(model.points)}
        ${renderXTicksSvg(model.points)}
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
    el.addEventListener('mouseenter', setText);
    el.addEventListener('mouseleave', resetText);
    el.addEventListener('focus', setText);
    el.addEventListener('blur', resetText);
  });
}

/**
 * @param {Array<{published:string,asOf:string,total:number,national:number,private:number,joint:number}>} history
 */
export function initChart(history) {
  const wrap = document.getElementById('chart-wrap');
  const hint = document.getElementById('chart-hint');
  const toggle = document.getElementById('chart-toggle-segments');
  if (!wrap) return;

  const data = history;
  if (!Array.isArray(data) || data.length === 0) {
    wrap.innerHTML = '<p class="chart-error">データがありません</p>';
    return;
  }

  const defaultHint = hint ? hint.textContent : '';

  function render(showSegments) {
    wrap.innerHTML = renderChartSvg(data, showSegments);

    if (showSegments) wrap.classList.add('chart-segments-on');
    else wrap.classList.remove('chart-segments-on');

    bindChartInteractions(wrap, data, hint, defaultHint);
  }

  // Initial render (segments hidden)
  render(false);

  if (toggle) {
    toggle.addEventListener('change', () => {
      render(toggle.checked);
    });
  }
}
