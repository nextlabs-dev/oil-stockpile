/**
 * /tankers/index.html のエントリーポイント。
 *
 * data/tankers.json を取得し、隻数・上位港・取得情報を埋める。
 * 6時間以上経過しているデータには警告を出す。
 *
 * 数値は「サンプル時間中に AIS 静的データを送信したタンカー数」。
 * リアルタイムストリームではなく、バックエンドが定期取得した snapshot を読むだけ。
 */

import { initTankerMap } from './tanker-map.js';

const TANKERS_URL = '../data/tankers.json';
const STALE_HOURS = 6;

async function loadTankers() {
  const r = await fetch(TANKERS_URL, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`Failed to load tankers data: ${r.status}`);
  const data = await r.json();
  if (typeof data.totalTankersInRegion !== 'number') {
    throw new Error('tankers.json is missing required fields');
  }
  return data;
}

function formatJaDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${y}年${m}月${day}日 ${hh}:${mm}`;
}

function showLoadError() {
  const el = document.getElementById('total-tankers');
  if (el) el.textContent = '—';
  const lead = document.querySelector('.tanker-lead');
  if (lead) {
    lead.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    lead.style.color = 'var(--tank-fill-warn)';
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderPorts(ports) {
  const list = document.getElementById('ports-list');
  const empty = document.getElementById('ports-empty');
  if (!list) return;

  list.innerHTML = '';
  if (!Array.isArray(ports) || ports.length === 0) {
    if (empty) empty.hidden = false;
    return;
  }

  for (const { port, count } of ports) {
    const li = document.createElement('li');
    li.className = 'port-row';
    const nameEl = document.createElement('span');
    nameEl.className = 'port-name';
    nameEl.textContent = port;
    const countEl = document.createElement('span');
    countEl.className = 'port-count';
    countEl.textContent = String(count);
    const small = document.createElement('small');
    small.textContent = '隻';
    countEl.appendChild(small);
    li.appendChild(nameEl);
    li.appendChild(countEl);
    list.appendChild(li);
  }
}

function checkStaleness(fetchedAtIso) {
  const fetched = new Date(fetchedAtIso).getTime();
  if (Number.isNaN(fetched)) return;
  const ageHours = (Date.now() - fetched) / 3_600_000;
  if (ageHours > STALE_HOURS) {
    const warn = document.getElementById('stale-warning');
    if (warn) warn.hidden = false;
  }
}

async function main() {
  let data;
  try {
    data = await loadTankers();
  } catch (e) {
    console.error('tankers load failed:', e);
    showLoadError();
    return;
  }

  setText('total-tankers', String(data.totalTankersInRegion));
  setText('japan-bound', String(data.japanBoundTankers));

  renderPorts(data.topDestinationPorts);

  setText('fetched-at', formatJaDateTime(data.fetchedAt));
  setText(
    'sampling-duration',
    `約 ${Math.round((data.samplingDurationSec || 0) / 60)} 分`,
  );
  setText('bounding-box', data.boundingBox || '—');

  initTankerMap(data.vessels);

  checkStaleness(data.fetchedAt);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
