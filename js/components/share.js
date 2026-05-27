/**
 * F-05 シェア
 *  - X (Twitter) intent URL を新規タブで開く（テキスト＋URL）
 *  - LINE / Facebook 公式シェア URL を新規タブで開く（URL のみ。
 *    Facebook は quote 廃止済み、LINE の lineit/share も text 非対応のため）
 *  - Clipboard API でリンクとテキストをコピー
 *
 * X とコピーのシェアテキストは「いま{N}日分」を含む。N は computeCurrentDays() の整数部。
 *
 * バインドは `data-share="x|line|facebook|copy"` 属性で行い、ページ上の
 * 複数インスタンス（例: ヒーロー内 + フッター内）に同時に作用する。
 */

import { SITE_CONFIG } from '../core/data.js';
import { computeCurrentDays } from './counter.js';

const TOAST_MS = 2400;

function buildShareText() {
  const days = computeCurrentDays();
  if (!Number.isFinite(days)) return null;
  return `日本の石油備蓄、いま${Math.floor(days)}日分。`;
}

let toastTimer = null;
function showToast(msg) {
  const toast = document.getElementById('share-toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.classList.add('is-visible');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove('is-visible');
  }, TOAST_MS);
}

function openShareX() {
  const text = buildShareText();
  if (text == null) {
    showToast('データを取得できていません');
    return;
  }
  const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(SITE_CONFIG.url)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

function openShareLine() {
  const url = `https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(SITE_CONFIG.url)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

function openShareFacebook() {
  const url = `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(SITE_CONFIG.url)}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

async function copyShareLink() {
  const shareText = buildShareText();
  if (shareText == null) {
    showToast('データを取得できていません');
    return;
  }
  const text = `${shareText} ${SITE_CONFIG.url}`;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      showToast('コピーしました');
    } else {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showToast('コピーしました');
    }
  } catch (e) {
    console.error('Copy failed:', e);
    showToast('コピーに失敗しました');
  }
}

const HANDLERS = {
  x: openShareX,
  line: openShareLine,
  facebook: openShareFacebook,
  copy: copyShareLink,
};

export function initShare() {
  for (const el of document.querySelectorAll('[data-share]')) {
    const handler = HANDLERS[el.dataset.share];
    if (handler) el.addEventListener('click', handler);
  }
}
