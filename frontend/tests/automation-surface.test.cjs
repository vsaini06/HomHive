const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');
const api = fs.readFileSync(path.join(__dirname, '..', 'lib', 'api.ts'), 'utf8');

test('visible household pulse is grounded in backend household-scoped observations', () => {
  assert.match(api, /async householdPulse\(/);
  assert.match(page, /HOUSEHOLD PULSE/);
  assert.match(page, /householdPulse\.suggestions/);
  assert.match(page, /not invented urgency or calendar availability/);
});

test('task evidence history remains explorable', () => {
  assert.match(api, /async taskTimeline\(/);
  assert.match(page, /<summary>Why was this suggested\?<\/summary>/);
  assert.match(page, /showTaskTimeline\(task\.id\)/);
  assert.match(page, /taskTimelines\[task\.id\]/);
  assert.match(page, /progress_percent/);
});

test('calendar is an explicit export rather than silent account access', () => {
  assert.match(page, /text\/calendar/);
  assert.match(page, /function exportCalendarTask\(task: AutonomousTask\)/);
  assert.match(page, /onClick=\{\(\) => exportCalendarTask\(task\)\}/);
  assert.match(page, /Download suggested calendar slot/);
  assert.match(page, /not checked whether you're free/);
});
