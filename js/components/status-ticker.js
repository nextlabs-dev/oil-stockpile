/**
 * 現況ヘッドライン（右から左へ流れるティッカー）
 *
 * 備蓄日数そのものはヒーローの大きな数字で見せているため、ここでは
 * 数字を出さず「いまの水準をどう受け止めればよいか」だけを言葉で伝える。
 *
 * 判定は 充填率 = 公表値の日数 / PEAK_REFERENCE.days の 1 つの軸のみ。
 * 秒按分の値を購読すると文言が頻繁に入れ替わって読めなくなるため、
 * 公表値（snapshots.json の最新 total）で 1 回だけ評価して固定する。
 * しきい値は粗いので、秒按分後の値との差で判定が変わることはまずない。
 */

import { PEAK_REFERENCE } from '../core/data.js';

/** 充填率のしきい値と、それに対応する現況コメント（高い順に評価する）。 */
const LEVELS = [
  {
    minRatio: 0.75,
    level: 'safe',
    text: '現在の備蓄水準は安全水域です。国際的な備蓄義務の水準を大きく上回っており、供給が止まった場合でも当面は落ち着いて対応できる余裕があります。',
  },
  {
    minRatio: 0.6,
    level: 'normal',
    text: '現在の備蓄水準は平常の範囲内です。ただちに生活や経済活動に影響が出る状況ではありません。',
  },
  {
    minRatio: 0.4,
    level: 'watch',
    text: '現在の備蓄水準はやや低下しています。直ちに不足する段階ではありませんが、今後の推移を注視したい局面です。',
  },
  {
    minRatio: 0,
    level: 'low',
    text: '現在の備蓄水準は低めです。輸入の停滞が続く場合の影響を見込んでおきたい局面です。',
  },
];

export function pickStatusMessage(days, peakDays = PEAK_REFERENCE.days) {
  if (!Number.isFinite(days) || !Number.isFinite(peakDays) || peakDays <= 0) return null;
  const ratio = days / peakDays;
  return LEVELS.find((entry) => ratio >= entry.minRatio) ?? LEVELS[LEVELS.length - 1];
}

export function initStatusTicker(history) {
  const track = document.getElementById('status-ticker-track');
  const textEl = document.getElementById('status-ticker-text');
  if (!track || !textEl) return;

  const latest = Array.isArray(history) && history.length > 0 ? history[history.length - 1] : null;
  const match = latest ? pickStatusMessage(Number(latest.total)) : null;
  if (!match) return;

  textEl.textContent = match.text;
  track.dataset.level = match.level;

  // 途切れずにループさせるため同じ文言をもう 1 つ並べる。
  // 複製は読み上げ・検索の重複になるので aria-hidden で隠す。
  const clone = textEl.cloneNode(true);
  clone.removeAttribute('id');
  clone.setAttribute('aria-hidden', 'true');
  track.appendChild(clone);
  track.classList.add('is-scrolling');
}
