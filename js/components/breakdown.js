/**
 * 3区分内訳（国家・民間・産油国共同）の最新値を <details> 内に埋め込む。
 *
 * 値は asOf 時点の静的スナップショット（瞬間値で問題ない）。
 *
 * initBreakdown(history) で初期化。history の末尾要素を最新として扱う。
 */

import { setText } from '../core/dom.js';

/**
 * @param {Array<{national:number,private:number,joint:number}>} history
 */
export function initBreakdown(history) {
  if (!Array.isArray(history) || history.length === 0) return;
  const latest = history[history.length - 1];

  setText('breakdown-national', String(latest.national));
  setText('breakdown-private', String(latest.private));
  setText('breakdown-joint', String(latest.joint));
}
