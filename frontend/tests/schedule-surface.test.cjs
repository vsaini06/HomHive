const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');

test('schedule is primary navigation and visible on the Home screen', () => {
  assert.match(page, /id: "schedule", label: "Schedule"/);
  assert.match(page, /hh-home-schedule/);
  assert.match(page, /setView\("schedule"\)/);
});

test('schedule editor shows distinct day buttons and a custom minute-level picker', () => {
  assert.match(page, /aria-pressed=\{windowWeekdays\.includes\(index\)\}/);
  assert.match(page, /TimeWheelField/);
  assert.match(page, /hh-window-from/);
  assert.match(page, /hh-window-until/);
  assert.doesNotMatch(page, /type="time"/);
});

test('schedule persists through existing household API and never claims calendar access', () => {
  assert.match(page, /await api\.setWorkWindow\(/);
  assert.match(page, /Your routine doesn't automatically reserve time on your calendar/);
  assert.match(page, /Save my schedule/);
});
