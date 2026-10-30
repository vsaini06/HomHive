const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');

test('periodic coordination evaluation does not discard the visible Nemotron recommendation', () => {
  assert.doesNotMatch(source, /\}, \[coordination\?\.evaluated_at\]\)/);
  assert.match(source, /setNemotronAdviceContext\(contextAtRequest\)/);
  assert.match(source, /setNemotronAdvice\(advice\)/);
});

test('account changes clear advice but routine coordination polling does not', () => {
  assert.match(source, /nemotronRequestId\.current \+= 1;[\s\S]*\}, \[token, householdId\]\)/);
  assert.match(source, /setInterval\(\(\) => \{ void loadAutonomousState\(\); \}, 60000\)/);
});

test('outdated requests cannot reappear after the account changes', () => {
  assert.match(source, /if \(nemotronRequestId\.current !== requestId\) return;/);
});

test('outdated recommendations do not appear as current advice', () => {
  assert.match(source, /nemotronAdviceContext === currentAdvisorContext/);
  assert.match(source, /currentAdviceTask/);
  assert.match(source, /activeAdvisorTasks\.find/);
  assert.match(source, /task\.task_id, task\.title, task\.status, task\.priority, task\.duration_min, task\.duration_max/);
});

test('automatic planning does not repeatedly spend credits due only to minute-by-minute time changes', () => {
  assert.match(source, /const planSignature = currentAdvisorContext;/);
  assert.doesNotMatch(source, /window:coordination\.preferred_minutes_remaining/);
});
