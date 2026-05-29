export function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

export function showElement(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = false;
}

/** DOM 構築完了後に fn を実行する。各ページのエントリーポイント起動に使う。 */
export function onReady(fn) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fn);
  } else {
    fn();
  }
}

/**
 * 同期初期化を個別に実行し、失敗しても他を巻き込まずログだけ残す。
 * 1 モジュールの例外でページ全体が止まるのを防ぐ。
 */
export function safeInit(label, fn) {
  try {
    fn();
  } catch (e) {
    console.error(`${label}:`, e);
  }
}
