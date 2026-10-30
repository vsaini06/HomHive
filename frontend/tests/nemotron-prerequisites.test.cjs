const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');

test('no-ready advisor displays real model explanation and a review action', () => {
  assert.match(page, /<p>\{nemotronAdvice.summary\}<\/p>/);
  assert.match(page, /Review household readiness/);
  assert.match(page, /never treats a pending task as approved or ready/);
});

test('consumer Today has one header scan entry and no completed checkmarks on pending work', () => {
  assert.doesNotMatch(page, /className="hh-consumer-scan"/);
  assert.match(page, /hh-consumer-task-icon[^>]*>→<\/span>/);
  assert.match(page, /simpleReason\(task.reasons\[0\]/);
});
