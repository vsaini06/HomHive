const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');

test('no-ready advisor displays only a verified waiting task and its reasons', () => {
  assert.match(page, /waitingAdvisorTask\.reasons\.map\(simpleReason\)/);
  assert.match(page, /<h4>\{waitingAdvisorTask.title\}<\/h4>/);
  assert.match(page, /Review household readiness/);
  assert.match(page, /This is an existing task, but it is not ready to schedule automatically/);
});

test('consumer Today has one header scan entry and no completed checkmarks on pending work', () => {
  assert.doesNotMatch(page, /className="hh-consumer-scan"/);
  assert.match(page, /hh-consumer-task-icon[^>]*>→<\/span>/);
  assert.match(page, /simpleReason\(task.reasons\[0\]/);
});
