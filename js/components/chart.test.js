import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildChartModel, getYDomain, pickXLabelIndices } from './chart.js';

test('pickXLabelIndices: n<=0 は空配列', () => {
  assert.deepEqual(pickXLabelIndices(0, 9), []);
  assert.deepEqual(pickXLabelIndices(-5, 9), []);
});

test('pickXLabelIndices: n<=max は全インデックスを返す', () => {
  assert.deepEqual(pickXLabelIndices(5, 9), [0, 1, 2, 3, 4]);
});

test('pickXLabelIndices: n>max は max個以下・両端を含む・昇順ユニーク', () => {
  const idx = pickXLabelIndices(100, 9);
  assert.ok(idx.length <= 9);
  assert.equal(idx[0], 0);
  assert.equal(idx[idx.length - 1], 99);
  assert.deepEqual(
    idx,
    [...new Set(idx)].sort((a, b) => a - b),
  );
});

test('getYDomain: showSegments=true は 0 起点・max+10', () => {
  assert.deepEqual(getYDomain([100, 200, 150], true), { yMin: 0, yMax: 210 });
});

test('getYDomain: showSegments=false は min-5..max+5（下限は0でクランプ）', () => {
  assert.deepEqual(getYDomain([220, 230, 225], false), { yMin: 215, yMax: 235 });
  assert.deepEqual(getYDomain([3, 4], false), { yMin: 0, yMax: 9 });
});

const SAMPLE = [
  { asOf: '2026-01-01', published: '2026-01-03', total: 200, national: 130, private: 65, joint: 5 },
  { asOf: '2026-01-02', published: '2026-01-04', total: 210, national: 135, private: 68, joint: 7 },
  { asOf: '2026-01-03', published: '2026-01-05', total: 190, national: 125, private: 60, joint: 5 },
];

test('buildChartModel: 点数・index・元行を保持する', () => {
  const m = buildChartModel(SAMPLE, false);
  assert.equal(m.points.length, SAMPLE.length);
  m.points.forEach((p, i) => {
    assert.equal(p.i, i);
    assert.equal(p.row, SAMPLE[i]);
  });
});

test('buildChartModel: x は左から右へ単調増加する', () => {
  const m = buildChartModel(SAMPLE, false);
  for (let i = 1; i < m.points.length; i++) {
    assert.ok(m.points[i].x > m.points[i - 1].x);
  }
});

test('buildChartModel: 値が大きいほど y は小さい（上にプロットされる）', () => {
  const m = buildChartModel(SAMPLE, false);
  // total: 200, 210, 190 → 210 の y が最小、190 の y が最大
  assert.ok(m.points[1].yTotal < m.points[0].yTotal);
  assert.ok(m.points[2].yTotal > m.points[0].yTotal);
});

test('buildChartModel: 1点でも例外を投げず有限値を返す（中央寄せ）', () => {
  const m = buildChartModel([SAMPLE[0]], false);
  assert.equal(m.points.length, 1);
  assert.ok(Number.isFinite(m.points[0].x));
  assert.ok(Number.isFinite(m.points[0].yTotal));
});
