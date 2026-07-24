import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  barWidth,
  FORECAST_CHOICES,
  FORECAST_CONFIG,
  formatPercent,
  isForecastEnabled,
  shouldShowPercent,
  toDisplayRows,
  votesUntilPercent,
} from './forecast.js';

describe('FORECAST_CHOICES', () => {
  it('Workers 側と同じ 4 択を同じ順で持つ', () => {
    assert.deepEqual(
      FORECAST_CHOICES.map((c) => c.id),
      ['m3', 'm6', 'y1', 'long'],
    );
  });
});

describe('isForecastEnabled', () => {
  it('api_origin 未設定なら無効（モックを出さないため）', () => {
    assert.equal(isForecastEnabled({ apiOrigin: '' }), false);
    assert.equal(isForecastEnabled({}), false);
  });

  it('api_origin があれば有効', () => {
    assert.equal(isForecastEnabled({ apiOrigin: 'https://api.example' }), true);
  });
});

describe('shouldShowPercent', () => {
  it('下限は 100 票（既定）', () => {
    assert.equal(FORECAST_CONFIG.minVotesForPercent, 100);
    assert.equal(shouldShowPercent(99), false);
    assert.equal(shouldShowPercent(100), true);
    assert.equal(shouldShowPercent(101), true);
  });

  it('0 票・不正値では出さない', () => {
    assert.equal(shouldShowPercent(0), false);
    assert.equal(shouldShowPercent(Number.NaN), false);
  });
});

describe('toDisplayRows', () => {
  const results = {
    total: 200,
    choices: [
      { id: 'm3', label: '〜3ヶ月', votes: 50 },
      { id: 'm6', label: '〜6ヶ月', votes: 50 },
      { id: 'y1', label: '〜1年', votes: 50 },
      { id: 'long', label: '1年以上（長期化）', votes: 50 },
    ],
  };

  it('下限以上なら得票率を算出する', () => {
    const rows = toDisplayRows(results);
    assert.deepEqual(
      rows.map((r) => r.percent),
      [25, 25, 25, 25],
    );
  });

  it('下限未満なら percent は null（率を伏せる）', () => {
    const rows = toDisplayRows({ ...results, total: 4, choices: results.choices });
    assert.ok(rows.every((r) => r.percent === null));
    // 実数は伏せない
    assert.deepEqual(
      rows.map((r) => r.votes),
      [50, 50, 50, 50],
    );
  });

  it('総数 0 でもゼロ除算せず null を返す', () => {
    const rows = toDisplayRows({
      total: 0,
      choices: [{ id: 'm3', label: '〜3ヶ月', votes: 0 }],
    });
    assert.equal(rows[0].percent, null);
    assert.equal(rows[0].votes, 0);
  });

  it('choices が欠けていても落ちない', () => {
    assert.deepEqual(toDisplayRows(undefined), []);
    assert.deepEqual(toDisplayRows({ total: 5 }), []);
  });
});

describe('formatPercent', () => {
  it('小数第1位まで', () => {
    assert.equal(formatPercent(25), '25.0%');
    assert.equal(formatPercent(33.333), '33.3%');
  });

  it('null（率を出さない期間）は空文字', () => {
    assert.equal(formatPercent(null), '');
    assert.equal(formatPercent(Number.NaN), '');
  });
});

describe('barWidth', () => {
  it('0〜100 に丸める', () => {
    assert.equal(barWidth(50), 50);
    assert.equal(barWidth(-5), 0);
    assert.equal(barWidth(150), 100);
  });

  it('率が無い期間はバーを出さない', () => {
    assert.equal(barWidth(null), 0);
  });
});

describe('votesUntilPercent', () => {
  it('下限までの残り票数を返す', () => {
    assert.equal(votesUntilPercent(0), 100);
    assert.equal(votesUntilPercent(60), 40);
  });

  it('下限到達後は 0', () => {
    assert.equal(votesUntilPercent(100), 0);
    assert.equal(votesUntilPercent(500), 0);
  });
});
