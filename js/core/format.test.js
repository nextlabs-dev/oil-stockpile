import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  formatDotDate,
  formatInt,
  formatJaDate,
  formatJaDateTime,
  formatJaNumber,
  formatMd,
} from './format.js';

test('formatJaDate: ISO 日付を和暦表記に変換する（ゼロ埋めしない）', () => {
  assert.equal(formatJaDate('2026-06-26'), '2026年6月26日');
  assert.equal(formatJaDate('2026-01-05'), '2026年1月5日');
});

test('formatJaDate: 空文字・null は em dash を返す', () => {
  assert.equal(formatJaDate(''), '—');
  assert.equal(formatJaDate(null), '—');
  assert.equal(formatJaDate(undefined), '—');
});

test('formatJaDate: 構成要素が欠ける不正値は入力をそのまま返す', () => {
  assert.equal(formatJaDate('2026-13'), '2026-13'); // 日が欠落
  assert.equal(formatJaDate('garbage'), 'garbage');
});

test('formatMd: ISO 日付を M/D に変換する', () => {
  assert.equal(formatMd('2026-06-26'), '6/26');
  assert.equal(formatMd('2026-01-05'), '1/5');
});

test('formatMd: 月日を取り出せない不正値は入力をそのまま返す', () => {
  assert.equal(formatMd('xxxx'), 'xxxx');
});

test('formatJaDateTime: ローカル時刻として時分まで整形する（時分はゼロ埋め）', () => {
  // TZ オフセット無しの ISO はローカル時刻として解釈されるため CI(UTC)/ローカル(JST) で不変
  assert.equal(formatJaDateTime('2026-06-26T09:05:00'), '2026年6月26日 09:05');
  assert.equal(formatJaDateTime('2026-12-01T23:59:00'), '2026年12月1日 23:59');
});

test('formatJaDateTime: パースできない値は入力をそのまま返す', () => {
  assert.equal(formatJaDateTime('not-a-date'), 'not-a-date');
});

test('formatInt: 四捨五入して ja-JP の桁区切りを付ける', () => {
  assert.equal(formatInt(1234567), '1,234,567');
  assert.equal(formatInt(1234.6), '1,235');
  assert.equal(formatInt(0), '0'); // falsy だが有限なので em dash にしない
});

test('formatInt: null / 非有限値は em dash を返す', () => {
  assert.equal(formatInt(null), '—');
  assert.equal(formatInt(undefined), '—');
  assert.equal(formatInt(Number.NaN), '—');
  assert.equal(formatInt(Number.POSITIVE_INFINITY), '—');
});

test('formatDotDate: ISO 日付をドット区切りにする（ゼロ埋めは保持）', () => {
  assert.equal(formatDotDate('2026-06-26'), '2026.06.26');
});

test('formatDotDate: 空文字・null は em dash を返す', () => {
  assert.equal(formatDotDate(''), '—');
  assert.equal(formatDotDate(null), '—');
});

test('formatJaNumber: null / 非有限値は em dash を返す', () => {
  assert.equal(formatJaNumber(null), '—');
  assert.equal(formatJaNumber(undefined), '—');
  assert.equal(formatJaNumber(Number.NaN), '—');
  assert.equal(formatJaNumber(Number.POSITIVE_INFINITY), '—');
});

test('formatJaNumber: 1億以上は端数の万を付け、万が 0 なら「○億」だけにする', () => {
  assert.equal(formatJaNumber(100_000_000), '1億'); // 万部分 0
  assert.equal(formatJaNumber(100_010_000), '1億1万'); // 億 + 万
  assert.equal(formatJaNumber(1_234_567_890), '12億3,456万'); // 億・万とも桁区切り
});

test('formatJaNumber: 1万以上 1億未満は端数を付け、端数 0 なら「○万」だけにする', () => {
  assert.equal(formatJaNumber(50_000), '5万'); // 端数 0
  assert.equal(formatJaNumber(12_345), '1万2,345'); // 万 + 端数
});

test('formatJaNumber: 1万未満はそのまま桁区切りする（0 も em dash にしない）', () => {
  assert.equal(formatJaNumber(9_999), '9,999');
  assert.equal(formatJaNumber(0), '0');
});

test('formatJaNumber: 四捨五入してから整形する（万境界をまたぐ繰り上げを含む）', () => {
  assert.equal(formatJaNumber(12_345.6), '1万2,346'); // 端数を四捨五入
  assert.equal(formatJaNumber(9_999.5), '1万'); // 繰り上げで 1万に乗る
});
