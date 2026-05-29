/**
 * 設定値とデータ読み込みヘルパ。
 *
 * 履歴データ自体は data/snapshots.json にあり、自動取得スクリプト
 * (scripts/fetch_pdf.py) が更新する。本ファイルは手動メンテ対象（基準値・
 * サイト情報など）のみ。
 *
 * フィールド（snapshots.json の各行）:
 *   published — PDF が公表された日（YYYY-MM-DD, JST）
 *   asOf      — データ時点（公表日の2-3日前であることが多い）
 *   total     — 総備蓄日数（合計）
 *   national  — 国家備蓄日数
 *   private   — 民間備蓄日数
 *   joint     — 産油国共同備蓄日数
 */

const DEFAULT_SNAPSHOTS_URL = './data/snapshots.json';

export async function loadJson(url, validate = null) {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`Failed to load ${url}: ${r.status}`);
  const data = await r.json();
  if (validate) validate(data);
  return data;
}

/**
 * snapshots.json を取得する。
 * fetch失敗時は例外を投げる（呼び出し側で握り潰さないこと）。
 */
export async function loadHistory(url = DEFAULT_SNAPSHOTS_URL) {
  const data = await loadJson(url);
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error('snapshots.json is empty or invalid');
  }
  // asOf 昇順に並べる（json側で並んでいる前提だが、念のため）
  return data.slice().sort((a, b) => a.asOf.localeCompare(b.asOf));
}

/**
 * タンクゲージの基準（最大値）。
 *
 * SSOT: src/constants.json (peak_reference)
 * 値の更新時は src/constants.json と本ファイルの両方を更新すること。
 * scripts/build_site.py が build 時に整合性を verify する（不一致なら build 失敗）。
 */
export const PEAK_REFERENCE = {
  days: 247,
  source: '経産省「石油備蓄の現況」過去公表値の高水準（2025年3月末ごろ）',
};

/**
 * シェアテキストや OGP に使うサイト情報。
 * 本番デプロイ時に url を実 URL に書き換える。
 */
export const SITE_CONFIG = {
  url: 'https://tkysi-mi.github.io/oil-stockpile/',
  title: '日本の石油備蓄',
};

/**
 * 古さ警告のしきい値（asOf からの経過日数）。
 */
export const STALE_THRESHOLD_DAYS = 14;

/**
 * VLCC（大型原油タンカー）1 隻の典型的積載量 [kL]。
 * scale ページの換算・tankers ページの概算容量で共通参照する SSOT。
 * 30 万 kL は一般に流通する代表値。
 */
export const VLCC_CAPACITY_KL = 300_000;

/**
 * asOf 日付文字列 (YYYY-MM-DD) を JST 0時の epoch ms に変換する。
 * UTC 計算ズレを防ぐため必ず +09:00 を明示する。
 */
export function asOfToMs(asOf) {
  return new Date(`${asOf}T00:00:00+09:00`).getTime();
}

/**
 * snapshot の asOf 時点からの経過分を引いた「いまこの瞬間の推計備蓄日数」を返す。
 * モデル: 「1 日経過 = 1 日分減る」（年間消費量推計を別途持たなくても整合）。
 *
 * カウンターページ (秒按分) と石油のものさしページ (整数日) が
 * 同じ値起点で動くよう、両モジュールから本関数を呼ぶ。
 */
export function computeCurrentDays(snapshot, now = Date.now()) {
  if (!snapshot || typeof snapshot.total !== 'number' || !snapshot.asOf) {
    return NaN;
  }
  const asOfMs = asOfToMs(snapshot.asOf);
  const elapsedDays = (now - asOfMs) / 86_400_000;
  // 端末時計が asOf より過去寄りでも total を超えた値を返さないよう上限で cap
  return Math.min(snapshot.total, Math.max(0, snapshot.total - elapsedDays));
}
