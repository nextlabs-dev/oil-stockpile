import assert from 'node:assert/strict';
import { test } from 'node:test';
import { deltaBetweenSnapshots } from './kpi.js';

test('deltaBetweenSnapshots: 正常な2行の差分を返す', () => {
  assert.equal(deltaBetweenSnapshots([{ total: 205 }, { total: 203 }]), -2);
});

test('deltaBetweenSnapshots: 欠損値はNaNにして表示側のダッシュへ倒す', () => {
  assert.ok(Number.isNaN(deltaBetweenSnapshots([{ total: 205 }, {}])));
  assert.ok(Number.isNaN(deltaBetweenSnapshots([{}, { total: 203 }])));
  assert.ok(Number.isNaN(deltaBetweenSnapshots([{ total: '203' }, { total: 205 }])));
  assert.ok(Number.isNaN(deltaBetweenSnapshots([{ total: 205 }])));
});
