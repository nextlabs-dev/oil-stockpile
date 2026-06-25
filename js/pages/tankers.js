/**
 * /tankers/index.html のエントリーポイント。
 *
 * data/tankers.json を取得し、隻数・上位港・取得情報を埋める。
 * 6時間以上経過しているデータには警告を出す。
 *
 * 数値は「サンプル時間中に AIS 静的データを送信したタンカー数」。
 * リアルタイムストリームではなく、バックエンドが定期取得した snapshot を読むだけ。
 */

import { setLatest } from '../components/counter.js';
import { initShare } from '../components/share.js';
import { initTankerMap } from '../components/tanker-map.js';
import { consumptionDaysFromKl, loadHistory, loadJson, VLCC_CAPACITY_KL } from '../core/data.js';
import { onReady, setText, showElement } from '../core/dom.js';
import { formatDotDate, formatInt, formatJaDateTime } from '../core/format.js';

const TANKERS_URL = '../data/tankers.json';
const STALE_HOURS = 6;
// VLCC 1 隻あたりの概算容量 [万 kL]。SSOT は js/core/data.js の VLCC_CAPACITY_KL [kL]。
const VLCC_MAN_KL_PER_SHIP = VLCC_CAPACITY_KL / 10_000;
const SHIP_ICON_JP_SRC = '../assets/tanker_japan.png';
const SHIP_ICON_OTHER_SRC = '../assets/tanker_other.png';

async function loadTankers() {
  return loadJson(TANKERS_URL, (data) => {
    if (typeof data.totalTankersInRegion !== 'number') {
      throw new Error('tankers.json is missing required fields');
    }
  });
}

function showLoadError() {
  setText('total-tankers', '—');
  setText('japan-bound', '—');
  setText('tankers-other', '—');
  const note = document.querySelector('.ais-live-note');
  if (note) {
    note.textContent = 'データの読み込みに失敗しました。時間をおいて再読み込みしてください。';
    note.classList.add('is-error');
  }
}

function renderShipViz(japanBound, other) {
  const wrap = document.getElementById('ship-viz');
  if (!wrap) return;
  const jp = Math.max(0, Number(japanBound) || 0);
  const ot = Math.max(0, Number(other) || 0);
  const parts = [];
  for (let i = 0; i < jp; i++) {
    parts.push(
      `<img class="ship-icon ship-icon--jp" src="${SHIP_ICON_JP_SRC}" alt="" aria-hidden="true" loading="lazy" decoding="async">`,
    );
  }
  for (let i = 0; i < ot; i++) {
    parts.push(
      `<img class="ship-icon ship-icon--other" src="${SHIP_ICON_OTHER_SRC}" alt="" aria-hidden="true" loading="lazy" decoding="async">`,
    );
  }
  wrap.innerHTML = parts.join('');
}

function renderPorts(ports, unknownCount) {
  const list = document.getElementById('ports-list');
  const empty = document.getElementById('ports-empty');
  const unknown = document.getElementById('ports-unknown');
  const unknownCountEl = document.getElementById('ports-unknown-count');
  const none = document.getElementById('ports-none');
  const noneCountEl = document.getElementById('ports-none-count');
  if (!list) return;

  list.innerHTML = '';
  const hasPorts = Array.isArray(ports) && ports.length > 0;
  const hasUnknown = typeof unknownCount === 'number' && unknownCount > 0;

  if (hasPorts) {
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
    // 一部の港を特定できた場合のみ「上記のほか N 隻…」を補足する
    if (hasUnknown && unknown) {
      if (unknownCountEl) unknownCountEl.textContent = String(unknownCount);
      unknown.hidden = false;
    }
    return;
  }

  // 港を 1 つも特定できなかった: 未特定の有無で文言を出し分ける
  if (hasUnknown && none) {
    if (noneCountEl) noneCountEl.textContent = String(unknownCount);
    none.hidden = false;
  } else if (empty) {
    empty.hidden = false;
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

  const total = Number(data.totalTankersInRegion) || 0;
  const jp = Number(data.japanBoundTankers) || 0;
  const other = Math.max(0, total - jp);
  const jpKl = jp * VLCC_MAN_KL_PER_SHIP;
  // 「N 日分の原油消費量」欄: 隻数ではなく jpKl を日消費量で割った日数を入れる。
  const jpDays = consumptionDaysFromKl(jp * VLCC_CAPACITY_KL);
  setText('total-tankers', String(total));
  setText('japan-bound', String(jp));
  setText('japan-bound-2', String(jp));
  setText('tankers-other', String(other));
  setText('jp-volume-kl', String(jpKl));
  setText('ais-note-jp', String(jp));
  setText('ais-note-kl', String(jpKl));
  setText('ais-note-days', formatInt(jpDays));
  setText('jp-volume-days', formatInt(jpDays));

  renderShipViz(jp, other);
  renderPorts(data.topDestinationPorts, data.japanBoundUnknownPort);

  setText('fetched-at', formatJaDateTime(data.fetchedAt));
  setText('header-last-updated', formatDotDate((data.fetchedAt ?? '').slice(0, 10)));
  setText('sampling-duration', `約 ${Math.round((data.samplingDurationSec || 0) / 60)} 分`);
  setText('bounding-box', data.boundingBox || '—');

  initTankerMap(data.vessels);

  checkStaleness(data.fetchedAt);

  // Load snapshot history just to enable the share button to show "いま N 日分".
  // setLatest() だけ呼ぶ: tankers にはカウンター DOM が無いので、initCounter の
  // 1Hz タイマー・visibilitychange listener・stale 副作用（油データの古さ警告）は不要。
  try {
    const history = await loadHistory('../data/snapshots.json');
    setLatest(history);
  } catch (e) {
    console.error('snapshots load (for share):', e);
  }
  initShare();
}

onReady(main);
