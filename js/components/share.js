/**
 * F-05 シェア
 *  - X (Twitter) intent URL を新規タブで開く（テキスト＋URL）
 *  - LINE 公式シェア URL を新規タブで開く（URL のみ。lineit/share は text 非対応のため）
 *  - Clipboard API でリンクとテキストをコピー
 *
 * X とコピーのシェアテキストは「いま{N}日分」を含む。N は computeCurrentDays() の整数部。
 *
 * バインドは `data-share="x|line|copy"` 属性で行い、ページ上の
 * 複数インスタンス（例: ヒーロー内 + フッター内）に同時に作用する。
 *
 * 共有URL（X/LINE がクロールする URL）には og:url に焼かれた ?v=<hash>
 * （og:image と同一のビルドハッシュ）を反映する。X 等のカードキャッシュは
 * 「共有URL単位」（X は約7日TTL）で、画像URL側を ?v= でバストしても共有URLが
 * 不変だと再クロールされない。画像が変わるたびに共有URLも変えることで毎回
 * 再クロールさせ、最新カードを出させる。共有URLと og:url が一致するため、
 * クローラーが og:url でカードを正規化しても古いカードに統合されない (issue #90)。
 */

import { SITE_CONFIG } from '../core/data.js';
import { computeCurrentDays } from './counter.js';

const TOAST_MS = 2400;

/**
 * og:url の content（例 'https://oilstock.nextlabs.jp/?v=8b7353b1'）から ?v= の値を
 * 取り出し、ページURL（siteUrl）に同じ ?v= を付けて返す純粋関数。
 * ハッシュが取れない／不正な値なら siteUrl をそのまま返す（fail safe・共有は止めない）。
 */
export function buildShareUrl(siteUrl, ogUrl) {
  let version = null;
  if (ogUrl) {
    try {
      version = new URL(ogUrl).searchParams.get('v');
    } catch {
      // og:url が不正 URL なら cache-bust 無しで継続（version は null のまま）
    }
  }
  if (!version) return siteUrl;
  const url = new URL(siteUrl);
  url.searchParams.set('v', version);
  return url.toString();
}

function currentShareUrl() {
  const ogUrl = document.querySelector('meta[property="og:url"]')?.content;
  return buildShareUrl(SITE_CONFIG.url, ogUrl);
}

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
  const url = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(currentShareUrl())}`;
  window.open(url, '_blank', 'noopener,noreferrer');
}

function openShareLine() {
  const url = `https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(currentShareUrl())}`;
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
  copy: copyShareLink,
};

export function initShare() {
  for (const el of document.querySelectorAll('[data-share]')) {
    const handler = HANDLERS[el.dataset.share];
    if (handler) el.addEventListener('click', handler);
  }
}
