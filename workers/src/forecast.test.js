import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  computeVoterHash,
  corsHeaders,
  getQuestion,
  isValidChoice,
  parseAllowedOrigins,
  QUESTIONS,
  tallyToResults,
} from './forecast.js';

const QID = 'hormuz_end_2026';

describe('getQuestion', () => {
  it('未知の設問は null を返す', () => {
    assert.equal(getQuestion('nope'), null);
  });

  it('プロトタイプ汚染のキーを設問として扱わない', () => {
    assert.equal(getQuestion('constructor'), null);
    assert.equal(getQuestion('__proto__'), null);
  });

  it('「終息」の定義が設問に必ず付いている', () => {
    for (const q of Object.values(QUESTIONS)) {
      assert.ok(q.definition && q.definition.length > 0, `${q.id} に definition がない`);
    }
  });
});

describe('isValidChoice', () => {
  it('仕様どおりの 4 択のみ受け付ける', () => {
    for (const id of ['m3', 'm6', 'y1', 'long']) {
      assert.equal(isValidChoice(QID, id), true, id);
    }
    assert.equal(isValidChoice(QID, 'y2'), false);
    assert.equal(isValidChoice(QID, ''), false);
    assert.equal(isValidChoice('nope', 'm3'), false);
  });
});

describe('computeVoterHash', () => {
  it('同じ入力なら安定し、SHA-256 hex を返す', async () => {
    const args = {
      secret: 's',
      questionId: QID,
      saltEpoch: '2026-07',
      ip: '1.2.3.4',
      userAgent: 'UA',
    };
    const a = await computeVoterHash(args);
    const b = await computeVoterHash(args);
    assert.equal(a, b);
    assert.match(a, /^[0-9a-f]{64}$/);
  });

  it('IP・UA・設問・世代のいずれかが違えば別のハッシュになる', async () => {
    const base = {
      secret: 's',
      questionId: QID,
      saltEpoch: '2026-07',
      ip: '1.2.3.4',
      userAgent: 'UA',
    };
    const hash = await computeVoterHash(base);
    for (const diff of [
      { ip: '1.2.3.5' },
      { userAgent: 'UA2' },
      { questionId: 'other' },
      { saltEpoch: '2026-08' },
      { secret: 's2' },
    ]) {
      assert.notEqual(await computeVoterHash({ ...base, ...diff }), hash, JSON.stringify(diff));
    }
  });

  it('生 IP をハッシュに素通しさせない', async () => {
    const hash = await computeVoterHash({
      secret: 's',
      questionId: QID,
      saltEpoch: '2026-07',
      ip: '1.2.3.4',
      userAgent: 'UA',
    });
    assert.ok(!hash.includes('1.2.3.4'));
  });

  it('secret 未設定なら例外を投げる（黙って弱いハッシュを作らない）', async () => {
    await assert.rejects(
      () => computeVoterHash({ questionId: QID, saltEpoch: '2026-07', ip: '', userAgent: '' }),
      /VOTER_SALT_SECRET/,
    );
  });
});

describe('tallyToResults', () => {
  it('0 票の選択肢も 0 として含め、合計を出す', () => {
    const out = tallyToResults(QID, [
      { choice: 'm3', votes: 2 },
      { choice: 'long', votes: 5 },
    ]);
    assert.equal(out.question_id, QID);
    assert.equal(out.total, 7);
    assert.deepEqual(
      out.choices.map((c) => [c.id, c.votes]),
      [
        ['m3', 2],
        ['m6', 0],
        ['y1', 0],
        ['long', 5],
      ],
    );
  });

  it('投票ゼロでも 4 択すべてを 0 で返す', () => {
    const out = tallyToResults(QID, []);
    assert.equal(out.total, 0);
    assert.equal(out.choices.length, 4);
  });

  it('得票率は返さない（表示の下限ルールが未決のため）', () => {
    const out = tallyToResults(QID, [{ choice: 'm3', votes: 1 }]);
    assert.ok(!('percent' in out.choices[0]));
  });

  it('未知の設問は例外', () => {
    assert.throws(() => tallyToResults('nope', []), /unknown question_id/);
  });
});

describe('corsHeaders', () => {
  const allowed = ['https://oilstock.nextlabs.jp'];

  it('許可オリジンにのみ CORS を返す', () => {
    assert.equal(
      corsHeaders('https://oilstock.nextlabs.jp', allowed)['Access-Control-Allow-Origin'],
      'https://oilstock.nextlabs.jp',
    );
  });

  it('未許可・欠落オリジンには CORS を一切返さない', () => {
    assert.deepEqual(corsHeaders('https://evil.example', allowed), {});
    assert.deepEqual(corsHeaders(null, allowed), {});
    // 前方一致で騙せないこと
    assert.deepEqual(corsHeaders('https://oilstock.nextlabs.jp.evil.example', allowed), {});
  });
});

describe('parseAllowedOrigins', () => {
  it('カンマ区切りを空白除去して配列にする', () => {
    assert.deepEqual(parseAllowedOrigins('https://a.example, https://b.example'), [
      'https://a.example',
      'https://b.example',
    ]);
  });

  it('未設定なら空配列（既定で全拒否）', () => {
    assert.deepEqual(parseAllowedOrigins(undefined), []);
    assert.deepEqual(parseAllowedOrigins(''), []);
  });
});
