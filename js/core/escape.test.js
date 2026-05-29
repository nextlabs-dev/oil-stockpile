import assert from 'node:assert/strict';
import { test } from 'node:test';
import { escapeHtml } from './escape.js';

test('escapeHtml: 特殊文字5種を実体参照に変換する', () => {
  assert.equal(escapeHtml('&<>"\''), '&amp;&lt;&gt;&quot;&#39;');
});

test('escapeHtml: & を最初に変換し二重エスケープしない', () => {
  // '<' → '&lt;' に変換された後の '&' が再変換されないこと
  assert.equal(escapeHtml('<script>'), '&lt;script&gt;');
  assert.equal(escapeHtml('a & b'), 'a &amp; b');
});

test('escapeHtml: XSS ペイロード（外部AIS文字列を想定）を無害化する', () => {
  assert.equal(
    escapeHtml('"><img src=x onerror=alert(1)>'),
    '&quot;&gt;&lt;img src=x onerror=alert(1)&gt;',
  );
});

test('escapeHtml: 特殊文字を含まない文字列はそのまま返す', () => {
  assert.equal(escapeHtml('YOKOHAMA 123'), 'YOKOHAMA 123');
});

test('escapeHtml: null / undefined は空文字を返す', () => {
  assert.equal(escapeHtml(null), '');
  assert.equal(escapeHtml(undefined), '');
});

test('escapeHtml: 非文字列は String 化して処理する（falsy な 0 も空にしない）', () => {
  assert.equal(escapeHtml(123456789), '123456789');
  assert.equal(escapeHtml(0), '0');
});
