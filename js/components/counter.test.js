import assert from 'node:assert/strict';
import { test } from 'node:test';
import { splitBreakdown } from './counter.js';

const SEC_PER_DAY = 86_400;

/** breakdown を通算秒に畳んで隣接 tick の差分を検査するためのヘルパ。 */
function totalSeconds({ d, h, m, s }) {
  return ((d * 24 + h) * 60 + m) * 60 + s;
}

test('splitBreakdown: 整数日はちょうど d日 0:00:00', () => {
  assert.deepEqual(splitBreakdown(230), { d: 230, h: 0, m: 0, s: 0 });
});

test('splitBreakdown: 日境界の1秒経過は 59 をスキップせず 23:59:59 を表示する', () => {
  // 230日ちょうどから1秒経過 → 229d 23:59:59 でなければならない。
  // 旧実装は段階的 floor の累積誤差で :58 にスキップしていた（issue #11）。
  assert.deepEqual(splitBreakdown(230 - 1 / SEC_PER_DAY), {
    d: 229,
    h: 23,
    m: 59,
    s: 59,
  });
});

test('splitBreakdown: 1秒刻みで秒が重複/スキップせず必ず1ずつ減る（日・時・分境界を含むスイープ）', () => {
  // issue の実データ（total=201, asOf+5日 → 196日）付近を 2 時間ぶんスイープ。
  // 197 から下げて開始直後に日境界(197.0)を跨ぎ、以降 時・分 境界を多数通過する。
  const startDays = 197;
  let prev = totalSeconds(splitBreakdown(startDays));
  for (let k = 1; k <= 7200; k++) {
    const cur = totalSeconds(splitBreakdown(startDays - k / SEC_PER_DAY));
    assert.equal(prev - cur, 1, `tick ${k}: 通算秒 ${prev} -> ${cur}（差が1でない=重複/スキップ）`);
    prev = cur;
  }
});

test('splitBreakdown: 負の入力は 0d 0:00:00 にクランプ', () => {
  assert.deepEqual(splitBreakdown(-3), { d: 0, h: 0, m: 0, s: 0 });
});
