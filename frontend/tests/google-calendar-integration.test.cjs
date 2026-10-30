const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const api = fs.readFileSync(path.join(__dirname, '../lib/api.ts'), 'utf8');
const google = fs.readFileSync(path.join(__dirname, '../lib/google-calendar.ts'), 'utf8');

test('Google OAuth only requests read-only Free/Busy scope', () => {
  assert.match(google, /auth\/calendar\.freebusy/);
  assert.doesNotMatch(google, /calendar\.events|calendar\.readonly|gmail/);
  assert.match(google, /oauth\.initTokenClient/);
});

test('Google Calendar credentials stay in memory and are not persisted', () => {
  assert.match(page, /useState<GoogleCalendarSession \| null>/);
  assert.match(page, /setCalendarSession\(null\)/);
  assert.doesNotMatch(google, /localStorage|sessionStorage|cookie/i);
});

test('Calendar-aware advice is called with the verified calendar permission', () => {
  assert.match(page, /googleCalendarNemotronAdvice\(calendarSession\.accessToken\)/);
  assert.match(api, /\/coordination\/google-calendar\/nemotron-advice/);
  assert.match(api, /\/coordination\/google-calendar\/plan/);
});

test('The interface distinguishes preference from confirmed availability', () => {
  assert.match(page, /This does not prove you are personally available/);
  assert.match(page, /No scheduled conflicts found/);
  assert.match(page, /Add dummy meetings to your own calendar/);
});
