/**
 * モバイル用ヘッダーナビの開閉（ハンバーガーメニュー）。
 *
 * ボタンは CSS により ≤640px でのみ表示される。デスクトップ幅では
 * .site-nav が display:contents で展開されるため、このスクリプトの
 * クラス操作は見た目に影響しない。
 *
 * - クリックでトグル（aria-expanded を同期）
 * - メニュー内のリンクをタップしたら閉じる
 * - メニュー外クリック / Esc キーで閉じる
 */

const toggle = document.getElementById('nav-toggle');
const panel = document.getElementById('site-nav');

if (toggle && panel) {
  const setOpen = (open) => {
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
    panel.classList.toggle('is-open', open);
  };

  const isOpen = () => toggle.getAttribute('aria-expanded') === 'true';

  toggle.addEventListener('click', (e) => {
    e.stopPropagation();
    setOpen(!isOpen());
  });

  // メニュー内リンクのタップで閉じる
  panel.addEventListener('click', (e) => {
    if (e.target.closest('a')) setOpen(false);
  });

  // メニュー外クリックで閉じる
  document.addEventListener('click', (e) => {
    if (isOpen() && !panel.contains(e.target) && !toggle.contains(e.target)) {
      setOpen(false);
    }
  });

  // Esc で閉じてボタンにフォーカスを戻す
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) {
      setOpen(false);
      toggle.focus();
    }
  });
}
