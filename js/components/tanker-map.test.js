import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildVesselTableHtml } from './tanker-map.js';

const SAMPLE = [
  {
    mmsi: 440204360,
    name: 'NO.7 MINSUNG',
    destination: 'CHIBA',
    isJapanBound: true,
    lat: 35.0621,
    lon: 129.1029,
  },
  {
    mmsi: 123456789,
    name: 'OCEAN STAR',
    destination: 'BUSAN',
    isJapanBound: false,
    lat: 34.5,
    lon: 130.25,
  },
];

test('buildVesselTableHtml: 視覚的に隠した table と caption を返す（chart の隠し表と同パターン）', () => {
  const html = buildVesselTableHtml(SAMPLE);
  assert.match(html, /<table class="visually-hidden">/);
  assert.match(html, /<caption>/);
  // 列見出しは scope="col"
  assert.match(html, /<th scope="col">/);
});

test('buildVesselTableHtml: 船ごとに行を1つ描画する（船名は th scope="row"）', () => {
  const html = buildVesselTableHtml(SAMPLE);
  const rowHeaders = (html.match(/<th scope="row">/g) || []).length;
  assert.equal(rowHeaders, SAMPLE.length);
});

test('buildVesselTableHtml: 各行に 船名・destination・MMSI・座標 が含まれる', () => {
  const html = buildVesselTableHtml(SAMPLE);
  assert.match(html, /NO\.7 MINSUNG/);
  assert.match(html, /CHIBA/);
  assert.match(html, /440204360/);
  // 座標は popup と同じ小数3桁表記
  assert.match(html, /35\.062°N, 129\.103°E/);
});

test('buildVesselTableHtml: 日本港向け/それ以外 の区分を表示する', () => {
  const html = buildVesselTableHtml(SAMPLE);
  assert.match(html, /日本港向け/);
  assert.match(html, /それ以外/);
});

test('buildVesselTableHtml: 船名・destination を HTML エスケープする（XSS 防止）', () => {
  const html = buildVesselTableHtml([
    {
      mmsi: 1,
      name: '<script>alert(1)</script>',
      destination: '<img src=x onerror=alert(2)>',
      isJapanBound: false,
      lat: 30,
      lon: 130,
    },
  ]);
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /<img /);
  assert.match(html, /&lt;script&gt;/);
});

test('buildVesselTableHtml: 船名/destination 欠落時はフォールバック文言を出す', () => {
  const html = buildVesselTableHtml([
    { mmsi: 1, name: '', destination: '   ', isJapanBound: false, lat: 30, lon: 130 },
  ]);
  assert.match(html, /船名未取得/);
  assert.match(html, /destination 未入力/);
});

test('buildVesselTableHtml: 空配列なら空文字を返す（表を描かない）', () => {
  assert.equal(buildVesselTableHtml([]), '');
});

test('buildVesselTableHtml: 幽霊タブストップを作らない（tabindex/role を付与しない）', () => {
  const html = buildVesselTableHtml(SAMPLE);
  assert.doesNotMatch(html, /tabindex/);
  assert.doesNotMatch(html, /role=/);
});
