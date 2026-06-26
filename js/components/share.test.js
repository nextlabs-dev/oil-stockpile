import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildShareUrl } from './share.js';

const SITE_URL = 'https://oilstock.nextlabs.jp/';
const OG = 'https://oilstock.nextlabs.jp/assets/og-image.png';

test('buildShareUrl: og:image の ?v=<hash> をページ(共有)URLに反映する', () => {
  // X のカード(ページ)キャッシュは共有URL単位。画像ハッシュを共有URLに載せることで
  // 画像が変わるたびに共有URLが別物になり、再クロールされる。
  assert.equal(
    buildShareUrl(SITE_URL, `${OG}?v=8b7353b1`),
    'https://oilstock.nextlabs.jp/?v=8b7353b1',
  );
});

test('buildShareUrl: 画像が変われば共有URLも変わる（cache-bust の要件）', () => {
  const a = buildShareUrl(SITE_URL, `${OG}?v=aaaa1111`);
  const b = buildShareUrl(SITE_URL, `${OG}?v=bbbb2222`);
  assert.notEqual(a, b);
});

test('buildShareUrl: og:image に ?v= が無ければクリーンな siteUrl を返す', () => {
  assert.equal(buildShareUrl(SITE_URL, OG), SITE_URL);
});

test('buildShareUrl: og:image が空/未取得ならクリーンな siteUrl を返す', () => {
  assert.equal(buildShareUrl(SITE_URL, null), SITE_URL);
  assert.equal(buildShareUrl(SITE_URL, undefined), SITE_URL);
  assert.equal(buildShareUrl(SITE_URL, ''), SITE_URL);
});

test('buildShareUrl: 不正な og:image でも例外を投げず siteUrl を返す（fail safe）', () => {
  assert.equal(buildShareUrl(SITE_URL, 'not a url'), SITE_URL);
});
