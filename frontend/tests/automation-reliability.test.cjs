const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../app/refined.css'), 'utf8');
const picker = fs.readFileSync(path.join(__dirname, '../lib/time-zone-picker.tsx'), 'utf8');

test('time-zone choice includes common zones, all browser-supported zones, and search', () => {
  assert.match(picker, /Intl\.supportedValuesOf\("timeZone"\)/);
  assert.match(picker, /placeholder="Search city, country, or time zone"/);
  assert.match(picker, /America\/Phoenix/);
  assert.match(picker, /Asia\/Kolkata/);
  assert.match(page, /HouseholdTimeZonePicker/);
});

test('transient calendar errors and notifications expire', () => {
  assert.match(page, /window\.setTimeout\(\(\) => setCalendarError\(""\), 7000\)/);
  assert.match(page, /Dismiss calendar notice/);
  assert.match(page, /kind === "error" \? 7000 : 4500/);
});

test('task completion shows feedback and awaits real photo verification', () => {
  assert.match(page, /setPendingTaskAction\(taskId\)/);
  assert.match(page, /notify\("success", feedback\[decision\]\[0\], feedback\[decision\]\[1\]\)/);
  assert.match(page, /Completion reported\. Add a newer photo to verify the result\./);
  assert.match(page, /Add follow-up photo/);
  assert.doesNotMatch(page, /I did this · verify later/);
});

test('unmatched and stale model advice cannot become an executable task', () => {
  assert.match(page, /latestScanAdvice\?\.selected_task_id/);
  assert.match(page, /currentAdviceTask/);
  assert.match(page, /task\.status === "NOW"/);
  assert.match(page, /nemotronAdviceContext === currentAdvisorContext/);
});

test('automatic research is primary and manual questions are optional', () => {
  assert.match(page, /Automatic household research/);
  assert.match(page, /automatic_guidance\?\.sources\?\.length/);
  assert.match(page, /<details className="hh-research-optional">/);
  assert.match(page, /setAutoPlanEnabled\] = useState\(true\)/);
});

test('calendar spacing and research feedback styling are consistent', () => {
  assert.match(css, /\.hh-app \.hh-calendar-connection\s*\{\s*margin: 0 0 1rem !important/);
  assert.match(css, /\.hh-dismissible-error/);
  assert.match(css, /\.hh-research-optional/);
});
