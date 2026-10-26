const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const typescript = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'account-session.ts'), 'utf8');
const compiled = typescript.transpileModule(source, {compilerOptions: {
  target: typescript.ScriptTarget.ES2022,
  module: typescript.ModuleKind.CommonJS,
}}).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, {exports: moduleExports});
const {ACCOUNT_SESSION_KEY, saveAccountSession, readAccountSession, clearAccountSession} = moduleExports;

function fakeStorage() {
  const items = new Map();
  return {
    getItem: (key) => items.get(key) ?? null,
    setItem: (key, value) => items.set(key, value),
    removeItem: (key) => items.delete(key),
  };
}
const example = {
  apiUrl: 'http://127.0.0.1:8000',
  householdId: 'home_14ebadab112747a299ccc41d6f4cceeb',
  accessToken: 'test_only_token_that_is_not_a_real_secret_1234567',
  expiresAt: '2026-10-30T10:00:00+00:00',
};
const now = Date.parse('2026-10-26T10:00:00+00:00');

test('saved session survives a page reload in the same tab', () => {
  const storage = fakeStorage();
  saveAccountSession(storage, example);
  assert.deepEqual(JSON.parse(JSON.stringify(readAccountSession(storage, example.apiUrl, now))), example);
});

test('expired session is cleared rather than restored', () => {
  const storage = fakeStorage();
  saveAccountSession(storage, example);
  assert.equal(readAccountSession(storage, example.apiUrl, Date.parse('2026-10-31')), null);
  assert.equal(storage.getItem(ACCOUNT_SESSION_KEY), null);
});

test('wrong backend session is rejected without sending credentials to another API', () => {
  const storage = fakeStorage();
  saveAccountSession(storage, example);
  assert.equal(readAccountSession(storage, 'http://localhost:8001', now), null);
  assert.equal(storage.getItem(ACCOUNT_SESSION_KEY), null);
});

test('corrupted storage entry is cleared safely', () => {
  const storage = fakeStorage();
  storage.setItem(ACCOUNT_SESSION_KEY, '{');
  assert.equal(readAccountSession(storage, example.apiUrl, now), null);
  assert.equal(storage.getItem(ACCOUNT_SESSION_KEY), null);
});

test('malformed membership and token are rejected', () => {
  const storage = fakeStorage();
  saveAccountSession(storage, {...example, householdId: 'other', accessToken: 'short'});
  assert.equal(readAccountSession(storage, example.apiUrl, now), null);
});

test('explicit sign-out removes the stored bearer token', () => {
  const storage = fakeStorage();
  saveAccountSession(storage, example);
  clearAccountSession(storage);
  assert.equal(storage.getItem(ACCOUNT_SESSION_KEY), null);
  assert.equal(readAccountSession(storage, example.apiUrl, now), null);
});
