import assert from 'node:assert/strict';
import { test } from 'node:test';
import { addUtm, buildShareUrl, officialMention } from './share.js';

const SITE_URL = 'https://oilstock.nextlabs.jp/';

test('buildShareUrl: og:url の ?v=<hash> をページ(共有)URLに反映する', () => {
  // X のカード(ページ)キャッシュは共有URL単位。画像ハッシュを共有URLに載せることで
  // 画像が変わるたびに共有URLが別物になり、再クロールされる。
  assert.equal(
    buildShareUrl(SITE_URL, `${SITE_URL}?v=8b7353b1`),
    'https://oilstock.nextlabs.jp/?v=8b7353b1',
  );
});

test('buildShareUrl: サブページの og:url でも共有URLはトップ + ?v=<hash>', () => {
  // 共有先は全ページからトップページURL固定。og:url の path は共有URLに載せない。
  assert.equal(
    buildShareUrl(SITE_URL, 'https://oilstock.nextlabs.jp/tankers/?v=8b7353b1'),
    'https://oilstock.nextlabs.jp/?v=8b7353b1',
  );
});

test('buildShareUrl: 画像が変われば共有URLも変わる（cache-bust の要件）', () => {
  const a = buildShareUrl(SITE_URL, `${SITE_URL}?v=aaaa1111`);
  const b = buildShareUrl(SITE_URL, `${SITE_URL}?v=bbbb2222`);
  assert.notEqual(a, b);
});

test('buildShareUrl: og:url に ?v= が無ければクリーンな siteUrl を返す', () => {
  assert.equal(buildShareUrl(SITE_URL, SITE_URL), SITE_URL);
});

test('buildShareUrl: og:url が空/未取得ならクリーンな siteUrl を返す', () => {
  assert.equal(buildShareUrl(SITE_URL, null), SITE_URL);
  assert.equal(buildShareUrl(SITE_URL, undefined), SITE_URL);
  assert.equal(buildShareUrl(SITE_URL, ''), SITE_URL);
});

test('buildShareUrl: 不正な og:url でも例外を投げず siteUrl を返す（fail safe）', () => {
  assert.equal(buildShareUrl(SITE_URL, 'not a url'), SITE_URL);
});

const UTM = { utmSource: 'x', utmMedium: 'social', utmCampaign: 'official_sns' };

test('addUtm: 規約どおり4つの utm_* を付け、既存の ?v= は保つ', () => {
  const u = new URL(addUtm(`${SITE_URL}?v=8b7353b1`, 'share_button', UTM));
  assert.equal(u.searchParams.get('v'), '8b7353b1');
  assert.equal(u.searchParams.get('utm_source'), 'x');
  assert.equal(u.searchParams.get('utm_medium'), 'social');
  assert.equal(u.searchParams.get('utm_campaign'), 'official_sns');
  assert.equal(u.searchParams.get('utm_content'), 'share_button');
});

test('addUtm: 既存の utm_* は上書きし重複させない', () => {
  const u = new URL(addUtm(`${SITE_URL}?utm_source=foo&utm_content=bar`, 'daily_oil', UTM));
  assert.deepEqual(u.searchParams.getAll('utm_source'), ['x']);
  assert.deepEqual(u.searchParams.getAll('utm_content'), ['daily_oil']);
});

test('addUtm: URL として不正なら例外を投げずそのまま返す', () => {
  assert.equal(addUtm('not a url', 'share_button', UTM), 'not a url');
});

test('officialMention: ハンドル未確定（空・空白）ならメンションなし', () => {
  assert.equal(officialMention({ officialHandle: '' }), '');
  assert.equal(officialMention({ officialHandle: '  ' }), '');
});

test('officialMention: ハンドルがあれば先頭に空白を付けて返す', () => {
  assert.equal(officialMention({ officialHandle: '@example' }), ' @example');
});
