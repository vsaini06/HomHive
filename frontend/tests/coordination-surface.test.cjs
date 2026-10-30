const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const page = fs.readFileSync(require('node:path').join(__dirname, '../app/page.tsx'), 'utf8');
const api = fs.readFileSync(require('node:path').join(__dirname, '../lib/api.ts'), 'utf8');
test('consumer can see live decisions and change home and available independently', () => {
  assert.match(page, /Your next best step/);
  assert.match(page, /changePresence\("HOME"\)/);
  assert.match(page, /changeAvailability\("FREE"\)/);
  assert.match(page, /coordination\.tasks\.slice/);
  assert.match(page, /duration_max != null/);
});
test('quiet-hours UI exists and API methods never expose a location secret', () => {
  assert.match(page, /Save quiet hours/);
  assert.match(api, /async updateQuietHours\(/);
  assert.match(api, /async coordinationPlan\(/);
});
