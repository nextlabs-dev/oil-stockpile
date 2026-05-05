/**
 * 3区分内訳（国家・民間・産油国共同）の最新値を <details> 内に埋め込む。
 *
 * 値は asOf 時点の静的スナップショット（瞬間値で問題ない）。
 *
 * initBreakdown(history) で初期化。history の末尾要素を最新として扱う。
 */

/**
 * @param {Array<{national:number,private:number,joint:number}>} history
 */
export function initBreakdown(history) {
  if (!Array.isArray(history) || history.length === 0) return;
  const latest = history[history.length - 1];

  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(v);
  };

  set('breakdown-national', latest.national);
  set('breakdown-private', latest.private);
  set('breakdown-joint', latest.joint);
}
