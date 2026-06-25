import assert from 'node:assert/strict';
import { test } from 'node:test';
import { asOfToMs, computeCurrentDays, elapsedDaysSince, STALE_THRESHOLD_DAYS } from './data.js';

const DAY_MS = 86_400_000;

test('asOfToMs: JST 0時の epoch を返す（UTCでは前日15時）', () => {
  // 2026-01-01 00:00 JST === 2025-12-31 15:00 UTC
  assert.equal(asOfToMs('2026-01-01'), Date.UTC(2025, 11, 31, 15, 0, 0));
});

test('computeCurrentDays: asOf 当日0時(JST)では total をそのまま返す', () => {
  const snap = { asOf: '2026-01-01', total: 200 };
  assert.equal(computeCurrentDays(snap, asOfToMs('2026-01-01')), 200);
});

test('computeCurrentDays: 経過日数ぶん線形に減る', () => {
  const snap = { asOf: '2026-01-01', total: 200 };
  const now = asOfToMs('2026-01-01') + 2.5 * DAY_MS;
  assert.equal(computeCurrentDays(snap, now), 200 - 2.5);
});

test('computeCurrentDays: now が asOf より過去でも total を超えない（上限cap）', () => {
  const snap = { asOf: '2026-01-01', total: 200 };
  const now = asOfToMs('2026-01-01') - 10 * DAY_MS;
  assert.equal(computeCurrentDays(snap, now), 200);
});

test('computeCurrentDays: 大きく経過しても 0 未満にならない（下限cap）', () => {
  const snap = { asOf: '2026-01-01', total: 200 };
  const now = asOfToMs('2026-01-01') + 1000 * DAY_MS;
  assert.equal(computeCurrentDays(snap, now), 0);
});

test('computeCurrentDays: 不正な入力は NaN を返す', () => {
  assert.ok(Number.isNaN(computeCurrentDays(null)));
  assert.ok(Number.isNaN(computeCurrentDays({ total: 200 }))); // asOf 欠落
  assert.ok(Number.isNaN(computeCurrentDays({ asOf: '2026-01-01' }))); // total 欠落
  assert.ok(Number.isNaN(computeCurrentDays({ asOf: '2026-01-01', total: 'x' }))); // total 非数値
});

test('elapsedDaysSince: asOf 当日0時(JST)では 0', () => {
  assert.equal(elapsedDaysSince('2026-01-01', asOfToMs('2026-01-01')), 0);
});

test('elapsedDaysSince: 経過日数を小数で返す', () => {
  const now = asOfToMs('2026-01-01') + 2.5 * DAY_MS;
  assert.equal(elapsedDaysSince('2026-01-01', now), 2.5);
});

test('elapsedDaysSince: しきい値ちょうど(14日)は古さ判定の境界（> で false）', () => {
  const now = asOfToMs('2026-01-01') + STALE_THRESHOLD_DAYS * DAY_MS;
  const elapsed = elapsedDaysSince('2026-01-01', now);
  assert.equal(elapsed, STALE_THRESHOLD_DAYS);
  assert.equal(elapsed > STALE_THRESHOLD_DAYS, false);
});

test('elapsedDaysSince: しきい値超過(15日)は古さ判定が true', () => {
  const now = asOfToMs('2026-01-01') + 15 * DAY_MS;
  assert.equal(elapsedDaysSince('2026-01-01', now) > STALE_THRESHOLD_DAYS, true);
});

test('elapsedDaysSince: now が asOf より過去なら負値', () => {
  const now = asOfToMs('2026-01-01') - 3 * DAY_MS;
  assert.equal(elapsedDaysSince('2026-01-01', now), -3);
});
