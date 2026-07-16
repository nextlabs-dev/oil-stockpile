// Issue #61 回帰テスト: fetchedAt（UTC タイムスタンプ）の暦日は閲覧者ローカルで組み立てる。
// このファイルは TZ を JST に固定して UTC→JST の日付繰り上がりを検証する。
// node --test はファイルごとに別プロセスで実行するため、TZ 設定は他のテストへ漏れない。
process.env.TZ = 'Asia/Tokyo';

import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatDotDateTime } from './format.js';

test('前提: 実行時の TZ=Asia/Tokyo 設定が有効（効かない環境ではここで失敗する）', () => {
  assert.equal(new Date('2026-07-16T15:00:00+00:00').getHours(), 0);
});

test('formatDotDateTime: UTC タイムスタンプでも JST の暦日を返す（実データ再現）', () => {
  // UTC 7/16 17:38 = JST 7/17 02:38。UTC 文字列の先頭10文字切り出しでは 2026.07.16 になる
  assert.equal(formatDotDateTime('2026-07-16T17:38:47+00:00'), '2026.07.17');
});

test('formatDotDateTime: JST 0時〜9時帯の境界で前日にならない', () => {
  assert.equal(formatDotDateTime('2026-07-16T15:00:00+00:00'), '2026.07.17'); // JST 0:00
  assert.equal(formatDotDateTime('2026-07-16T14:59:59+00:00'), '2026.07.16'); // JST 23:59:59
});
