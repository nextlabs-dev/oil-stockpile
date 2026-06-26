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

/** 整数を「○億○,○○○万」表記に整形する（億・万のいずれか / 両方）。 */
export function formatJaNumber(n) {
  if (n == null || !Number.isFinite(n)) return '—';
  const x = Math.round(n);
  const oku = 100_000_000;
  const man = 10_000;
  if (x >= oku) {
    const okuPart = Math.floor(x / oku);
    const manPart = Math.floor((x % oku) / man);
    const head = okuPart.toLocaleString('ja-JP');
    if (manPart === 0) return `${head}億`;
    return `${head}億${manPart.toLocaleString('ja-JP')}万`;
  }
  if (x >= man) {
    const manPart = Math.floor(x / man);
    const remainder = x % man;
    const head = manPart.toLocaleString('ja-JP');
    if (remainder === 0) return `${head}万`;
    return `${head}万${remainder.toLocaleString('ja-JP')}`;
  }
  return x.toLocaleString('ja-JP');
}

/** ISO 日付 (YYYY-MM-DD) をドット区切り (YYYY.MM.DD) に。空なら '—'。 */
export function formatDotDate(iso) {
  if (!iso) return '—';
  return iso.replaceAll('-', '.');
}
