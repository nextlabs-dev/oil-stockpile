/**
 * /tankers/index.html のエントリーポイント。
 *
 * data/tankers.json を取得し、隻数・上位港・取得情報を埋める。
 * 6時間以上経過しているデータには警告を出す。
 *
 * 数値は「サンプル時間中に AIS 静的データを送信したタンカー数」。
 * リアルタイムストリームではなく、バックエンドが定期取得した snapshot を読むだけ。
 */

import { initTankerMap } from '../components/tanker-map.js';
import { loadJson } from '../core/data.js';
import { setText, showElement } from '../core/dom.js';
import { formatJaDateTime } from '../core/format.js';

const TANKERS_URL = '../data/tankers.json';
const STALE_HOURS = 6;

async function loadTankers() {
  return loadJson(TANKERS_URL, (data) => {
    if (typeof data.totalTankersInRegion !== 'number') {
      throw new Error('tankers.json is missing required fields');
    }
  });
}

function showLoadError() {
  const el = document.getElementById('total-tankers');
  if (el) el.textContent = '—';
  const sub = document.querySelector('.tanker-sub');
  if (sub) {
    sub.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    sub.style.color = 'var(--tank-fill-warn)';
  }
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
    showElement('stale-warning');
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
  setText('sampling-duration', `約 ${Math.round((data.samplingDurationSec || 0) / 60)} 分`);
  setText('bounding-box', data.boundingBox || '—');

  initTankerMap(data.vessels);

  checkStaleness(data.fetchedAt);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
