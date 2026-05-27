/**
 * About page entry.
 *  - Share buttons (X / LINE / Copy) reuse the home share module.
 *  - Sidebar nav highlights the section currently in view via IntersectionObserver.
 *  - Newsletter form is local-only (no backend yet): shows a confirmation toast.
 */

import { initCounter } from '../components/counter.js';
import { initShare } from '../components/share.js';
import { loadHistory } from '../core/data.js';
import { setText } from '../core/dom.js';

function formatBannerDate(iso) {
  if (!iso) return '—';
  return iso.replaceAll('-', '.');
}

function initSidebarScrollSpy() {
  const links = Array.from(document.querySelectorAll('.about-nav-link'));
  if (links.length === 0) return;

  const linkBySection = new Map(links.map((a) => [a.dataset.section, a]));

  const targets = links.map((a) => document.getElementById(a.dataset.section)).filter(Boolean);
  if (targets.length === 0) return;

  let currentId = links.find((a) => a.classList.contains('is-active'))?.dataset.section ?? null;

  const setActive = (id) => {
    if (!id || id === currentId) return;
    currentId = id;
    for (const a of links) {
      a.classList.toggle('is-active', a.dataset.section === id);
    }
  };

  const observer = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio);
      if (visible[0]) setActive(visible[0].target.id);
    },
    {
      rootMargin: '-30% 0px -55% 0px',
      threshold: [0, 0.25, 0.5, 0.75, 1],
    },
  );

  for (const t of targets) observer.observe(t);

  for (const a of links) {
    a.addEventListener('click', () => {
      const id = a.dataset.section;
      if (linkBySection.has(id)) setActive(id);
    });
  }
}

function initNewsletterForm() {
  const form = document.getElementById('newsletter-form');
  const status = document.getElementById('newsletter-status');
  if (!form || !status) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const input = form.querySelector('input[type="email"]');
    const value = (input?.value ?? '').trim();
    if (!value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      status.textContent = 'メールアドレスをご確認ください。';
      status.classList.add('is-error');
      return;
    }
    status.classList.remove('is-error');
    status.textContent = 'ご登録ありがとうございます。確認メールをお送りしました。';
    form.reset();
  });
}

async function main() {
  try {
    const history = await loadHistory('../data/snapshots.json');
    initCounter(history);
    const latest = history[history.length - 1];
    if (latest) setText('header-last-updated', formatBannerDate(latest.published));
  } catch (e) {
    console.error('history:', e);
  }
  try {
    initShare();
  } catch (e) {
    console.error('share:', e);
  }
  try {
    initSidebarScrollSpy();
  } catch (e) {
    console.error('scrollspy:', e);
  }
  try {
    initNewsletterForm();
  } catch (e) {
    console.error('newsletter:', e);
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main);
} else {
  main();
}
