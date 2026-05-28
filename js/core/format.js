export function formatJaDate(iso) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${y}年${m}月${d}日`;
}

export function formatMd(iso) {
  const [, m, d] = iso.split('-').map(Number);
  if (!m || !d) return iso;
  return `${m}/${d}`;
}

export function formatJaDateTime(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const y = d.getFullYear();
  const m = d.getMonth() + 1;
  const day = d.getDate();
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${y}年${m}月${day}日 ${hh}:${mm}`;
}

export function formatInt(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  return Math.round(n).toLocaleString('ja-JP');
}

/** ISO 日付 (YYYY-MM-DD) をドット区切り (YYYY.MM.DD) に。空なら '—'。 */
export function formatDotDate(iso) {
  if (!iso) return '—';
  return iso.replaceAll('-', '.');
}
