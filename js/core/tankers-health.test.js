import assert from 'node:assert/strict';
import { test } from 'node:test';
import { evaluateAisHealth } from './tankers-health.js';

const NOW = Date.parse('2026-08-19T00:00:00Z');

function data(overrides = {}) {
  return {
    fetchedAt: '2026-08-18T23:00:00Z',
    samplingDurationSec: 480,
    totalTankersInRegion: 10,
    japanBoundTankers: 4,
    ...overrides,
  };
}

test('evaluateAisHealth: fresh snapshot', () => {
  assert.equal(evaluateAisHealth(data(), NOW).state, 'fresh');
});

test('evaluateAisHealth: stale snapshot is distinct from a fresh sample', () => {
  const result = evaluateAisHealth(data({ fetchedAt: '2026-08-18T16:00:00Z' }), NOW);
  assert.equal(result.state, 'stale');
  assert.match(result.message, /最後に取得できたスナップショット/);
});

test('evaluateAisHealth: zero or very short sample is degraded', () => {
  assert.equal(
    evaluateAisHealth(data({ totalTankersInRegion: 0, japanBoundTankers: 0 }), NOW).state,
    'degraded',
  );
  assert.equal(evaluateAisHealth(data({ samplingDurationSec: 30 }), NOW).state, 'degraded');
});

test('evaluateAisHealth: malformed or impossible data is error', () => {
  assert.equal(evaluateAisHealth(data({ fetchedAt: 'not-a-date' }), NOW).state, 'error');
  assert.equal(evaluateAisHealth(data({ japanBoundTankers: 11 }), NOW).state, 'error');
  assert.equal(evaluateAisHealth(null, NOW).state, 'error');
});
