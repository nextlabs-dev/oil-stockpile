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

const SNAPSHOTS_URL = './data/snapshots.json';

/**
 * snapshots.json を取得する。
 * fetch失敗時は例外を投げる（呼び出し側で握り潰さないこと）。
 */
export async function loadHistory() {
  const r = await fetch(SNAPSHOTS_URL, { cache: 'no-cache' });
  if (!r.ok) throw new Error(`Failed to load snapshots: ${r.status}`);
  const data = await r.json();
  if (!Array.isArray(data) || data.length === 0) {
    throw new Error('snapshots.json is empty or invalid');
  }
  // asOf 昇順に並べる（json側で並んでいる前提だが、念のため）
  return data.slice().sort((a, b) => a.asOf.localeCompare(b.asOf));
}

/**
 * タンクゲージの基準（最大値）。
 * source を併記すること。
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
  url: 'https://oil-stockpile.example/',
  title: '日本の石油備蓄',
};

/**
 * 古さ警告のしきい値（asOf からの経過日数）。
 */
export const STALE_THRESHOLD_DAYS = 14;
