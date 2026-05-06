/**
 * F-05 シェア
 *  - X (Twitter) intent URL を新規タブで開く
 *  - Clipboard API でリンクとテキストをコピー
 *
 * シェアテキストは「いま{N}日分」を含む。N は computeCurrentDays() の整数部。
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

export function initShare() {
  const btnX = document.getElementById('share-x');
  const btnCopy = document.getElementById('share-copy');

  if (btnX) {
    btnX.addEventListener('click', () => {
      const text = buildShareText();
      if (text == null) {
        showToast('データを取得できていません');
        return;
      }
      const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(SITE_CONFIG.url)}`;
      window.open(url, '_blank', 'noopener,noreferrer');
    });
  }

  if (btnCopy) {
    btnCopy.addEventListener('click', async () => {
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
          // 古いブラウザや非HTTPS時のフォールバック
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
    });
  }
}
