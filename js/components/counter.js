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

import { computeCurrentDays as computeFromSnapshot, STALE_THRESHOLD_DAYS } from '../core/data.js';
import { setText, showElement } from '../core/dom.js';

const MS_PER_DAY = 86_400_000;

let latestSnapshot = null;
let asOfTimestamp = null;

function setLatest(history) {
  if (!Array.isArray(history) || history.length === 0) {
    throw new Error('history is empty');
  }
  latestSnapshot = history[history.length - 1];
  // JST明示。UTC計算ズレを防ぐため必ず +09:00 を付ける
  asOfTimestamp = new Date(`${latestSnapshot.asOf}T00:00:00+09:00`).getTime();
}

export function computeCurrentDays(now = Date.now()) {
  return computeFromSnapshot(latestSnapshot, now);
}

function getElapsedDays(now = Date.now()) {
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

const subscribers = new Set();

/**
 * 1秒ごとに最新の現在備蓄日数（小数）を受け取るリスナーを登録する。
 * 戻り値は購読解除関数。
 *
 * latestSnapshot が未設定の段階で subscribe された場合は初回 callback を
 * 呼ばない。次の tick() で正しい値が配信される（DOM に "NaN" が一瞬書き込まれるのを防ぐ）。
 */
export function subscribe(fn) {
  subscribers.add(fn);
  if (latestSnapshot) {
    try {
      fn(computeCurrentDays());
    } catch (e) {
      console.error(e);
    }
  }
  return () => subscribers.delete(fn);
}

let timer = null;

function tick() {
  const days = computeCurrentDays();
  const { d, h, m, s } = splitBreakdown(days);

  setText('counter-days', String(d));
  setText('counter-hours', pad2(h));
  setText('counter-minutes', pad2(m));
  setText('counter-seconds', pad2(s));

  subscribers.forEach((fn) => {
    try {
      fn(days);
    } catch (e) {
      console.error(e);
    }
  });
}

/**
 * @param {Array<{published:string,asOf:string,total:number,national:number,private:number,joint:number}>} history
 */
export function initCounter(history) {
  setLatest(history);

  // 古さ警告（asOf から閾値日数以上経過しているとき）
  const elapsedDays = getElapsedDays();
  if (elapsedDays > STALE_THRESHOLD_DAYS) {
    showElement('stale-warning');
  }

  tick();
  if (timer) clearInterval(timer);
  timer = setInterval(tick, 1000);

  // タブ非アクティブで setInterval が間引かれた後の即時補正
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') tick();
  });
}
