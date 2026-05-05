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

const W = 720;
const H = 280;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 16;
const PAD_B = 56;
const MAX_X_LABELS = 9;

function formatMd(iso) {
  const [, m, d] = iso.split('-').map(Number);
  return `${m}/${d}`;
}

function formatJaDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${y}年${m}月${d}日`;
}

function pickXLabelIndices(n, max) {
  if (n <= 0) return [];
  if (n <= max) return Array.from({ length: n }, (_, i) => i);
  const out = [];
  for (let k = 0; k < max; k++) {
    out.push(Math.round((k / (max - 1)) * (n - 1)));
  }
  return [...new Set(out)].sort((a, b) => a - b);
}

function escapeAttr(s) {
  return String(s).replace(/[<>&"']/g, (c) => ({
    '<': '&lt;', '>': '&gt;', '&': '&amp;', '"': '&quot;', "'": '&#39;',
  })[c]);
}

function buildHiddenTable(data) {
  const rows = data
    .map(
      (r) =>
        `<tr><th scope="row">${escapeAttr(formatJaDate(r.asOf))}</th>` +
        `<td>${r.total}</td><td>${r.national}</td><td>${r.private}</td><td>${r.joint}</td></tr>`
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

  const totals = data.map((r) => r.total);
  const defaultHint = hint ? hint.textContent : '';

  function render(showSegments) {
    let yMin, yMax;
    if (showSegments) {
      yMin = 0;
      yMax = Math.max(...totals) + 10;
    } else {
      yMin = Math.max(0, Math.min(...totals) - 5);
      yMax = Math.max(...totals) + 5;
    }

    const plotW = W - PAD_L - PAD_R;
    const plotH = H - PAD_T - PAD_B;
    const n = data.length;

    const xAt = (i) => PAD_L + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW);
    const yAt = (v) => PAD_T + (1 - (v - yMin) / (yMax - yMin)) * plotH;

    const points = data.map((row, i) => ({
      x: xAt(i),
      yTotal: yAt(row.total),
      yNational: yAt(row.national),
      yPrivate: yAt(row.private),
      yJoint: yAt(row.joint),
      row,
      i,
    }));

    const linePath = (key) =>
      points
        .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p[key].toFixed(1)}`)
        .join(' ');

    // Y grid + ticks
    const yTickCount = 4;
    let gridSvg = '';
    for (let t = 0; t <= yTickCount; t++) {
      const v = yMin + (t / yTickCount) * (yMax - yMin);
      const y = yAt(v);
      gridSvg += `<line class="chart-grid" x1="${PAD_L}" y1="${y.toFixed(1)}" x2="${W - PAD_R}" y2="${y.toFixed(1)}" />`;
      gridSvg += `<text class="chart-ytick" x="${PAD_L - 8}" y="${(y + 4).toFixed(1)}" text-anchor="end">${Math.round(v)}</text>`;
    }

    // X tick labels
    const xIdx = pickXLabelIndices(n, MAX_X_LABELS);
    let xTickSvg = '';
    for (const i of xIdx) {
      const p = points[i];
      xTickSvg += `<text class="chart-xtick" x="${p.x.toFixed(1)}" y="${(H - PAD_B + 16).toFixed(1)}" text-anchor="middle">${formatMd(p.row.asOf)}</text>`;
    }

    // Points
    let circles = '';
    points.forEach((p) => {
      const r = p.row;
      const label = `${formatJaDate(r.asOf)} 合計${r.total}日（国家${r.national}・民間${r.private}・産油国共同${r.joint}）`;
      circles +=
        `<circle class="chart-point" cx="${p.x.toFixed(1)}" cy="${p.yTotal.toFixed(1)}" r="3" data-i="${p.i}" role="button" tabindex="0" aria-label="${escapeAttr(label)}"><title>${escapeAttr(label)}</title></circle>`;
    });

    // Segment lines (only rendered when shown)
    const segmentLines = showSegments
      ? `<path class="chart-line-segment chart-line-joint" d="${linePath('yJoint')}" />
         <path class="chart-line-segment chart-line-private" d="${linePath('yPrivate')}" />
         <path class="chart-line-segment chart-line-national" d="${linePath('yNational')}" />`
      : '';

    wrap.innerHTML = `
      ${buildHiddenTable(data)}
      <svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
        ${gridSvg}
        <text class="chart-axis-label" x="${((PAD_L + (W - PAD_R)) / 2).toFixed(1)}" y="${(H - 4).toFixed(1)}" text-anchor="middle">データ時点（月/日）</text>
        ${segmentLines}
        <path class="chart-line-total" d="${linePath('yTotal')}" />
        ${circles}
        ${xTickSvg}
      </svg>
    `;

    if (showSegments) wrap.classList.add('chart-segments-on');
    else wrap.classList.remove('chart-segments-on');

    // Attach hover/focus listeners for hint update
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

  // Initial render (segments hidden)
  render(false);

  if (toggle) {
    toggle.addEventListener('change', () => {
      render(toggle.checked);
    });
  }
}
