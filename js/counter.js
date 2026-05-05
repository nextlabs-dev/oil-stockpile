/**
 * F-01 リアルタイムカウンター
 *
 * 経産省 速報PDF の最新値（asOf 時点）を起点に、現在時刻までの経過分を
 * 日・時・分・秒に按分して表示する。
 *
 * モデル: 「1日経過 = 1日分減る」（消費量推計を別途持たなくても単位整合する）
 * counter.js は subscribe() で他モジュール（tank-gauge等）と値を共有する。
 *
 * initCounter(history) で初期化。history は [{published, asOf, total, ...}, ...]
 * を asOf 昇順で並べた配列。
 */

import {
  STALE_THRESHOLD_DAYS,
  computeCurrentDays as computeFromSnapshot,
} from './data.js';

const MS_PER_DAY = 86_400_000;

let latestSnapshot = null;
let asOfTimestamp = null;

function setLatest(history) {
  if (!Array.isArray(history) || history.length === 0) {
    throw new Error('history is empty');
  }
  latestSnapshot = history[history.length - 1];
  // JST明示。UTC計算ズレを防ぐため必ず +09:00 を付ける
  asOfTimestamp = new Date(latestSnapshot.asOf + 'T00:00:00+09:00').getTime();
}

export function getLatestSnapshot() {
  return latestSnapshot;
}

export function computeCurrentDays(now = Date.now()) {
  return computeFromSnapshot(latestSnapshot, now);
}

export function getElapsedDays(now = Date.now()) {
  if (!latestSnapshot) return NaN;
  return (now - asOfTimestamp) / MS_PER_DAY;
}

function splitBreakdown(days) {
  const total = Math.max(0, days);
  const d = Math.floor(total);
  const fracDay = total - d;
  const hoursTotal = fracDay * 24;
  const h = Math.floor(hoursTotal);
  const minutesTotal = (hoursTotal - h) * 60;
  const m = Math.floor(minutesTotal);
  const s = Math.floor((minutesTotal - m) * 60);
  return { d, h, m, s };
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

function formatJaDate(iso) {
  const [y, m, d] = iso.split('-').map(Number);
  return `${y}年${m}月${d}日`;
}

const subscribers = new Set();

/**
 * 1秒ごとに最新の現在備蓄日数（小数）を受け取るリスナーを登録する。
 * 戻り値は購読解除関数。
 */
export function subscribe(fn) {
  subscribers.add(fn);
  // 登録直後に1回呼んで初期値を渡す（latestSnapshot が無いと NaN になるが許容）
  try { fn(computeCurrentDays()); } catch (e) { console.error(e); }
  return () => subscribers.delete(fn);
}

let timer = null;

function tick() {
  const days = computeCurrentDays();
  const { d, h, m, s } = splitBreakdown(days);

  const elDays = document.getElementById('counter-days');
  const elHours = document.getElementById('counter-hours');
  const elMinutes = document.getElementById('counter-minutes');
  const elSeconds = document.getElementById('counter-seconds');
  if (elDays) elDays.textContent = String(d);
  if (elHours) elHours.textContent = pad2(h);
  if (elMinutes) elMinutes.textContent = pad2(m);
  if (elSeconds) elSeconds.textContent = pad2(s);

  subscribers.forEach((fn) => {
    try { fn(days); } catch (e) { console.error(e); }
  });
}

/**
 * @param {Array<{published:string,asOf:string,total:number,national:number,private:number,joint:number}>} history
 */
export function initCounter(history) {
  setLatest(history);

  // フッターの「データ時点」「公表」を埋める
  const elAsOf = document.getElementById('footer-as-of');
  const elPublished = document.getElementById('footer-published');
  if (elAsOf) elAsOf.textContent = formatJaDate(latestSnapshot.asOf);
  if (elPublished) elPublished.textContent = formatJaDate(latestSnapshot.published);

  // 古さ警告（asOf から閾値日数以上経過しているとき）
  const elapsedDays = getElapsedDays();
  if (elapsedDays > STALE_THRESHOLD_DAYS) {
    const warn = document.getElementById('stale-warning');
    if (warn) warn.hidden = false;
  }

  tick();
  if (timer) clearInterval(timer);
  timer = setInterval(tick, 1000);

  // タブ非アクティブで setInterval が間引かれた後の即時補正
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tick();
  });
}
