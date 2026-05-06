const ESCAPE_MAP = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/**
 * HTML 本文・属性値の双方に使える escape。
 * `&` → `&amp;` を最初に変換する順序を維持するため正規表現を1パスで適用する。
 */
export function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/[&<>"']/g, (c) => ESCAPE_MAP[c]);
}
