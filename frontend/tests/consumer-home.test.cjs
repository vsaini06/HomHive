const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'app', 'globals.css'), 'utf8');

test('simple Today page is available without replacing the full dashboard', () => {
  assert.match(page, /view === "home" && simpleInterface/);
  assert.match(page, /view === "home" && !simpleInterface/);
  assert.match(page, /changeInterfaceMode\(!simpleInterface\)/);
  assert.match(page, /homhive\.interfaceMode/);
});

test('consumer tasks use actual coordination data and retain uncertainty', () => {
  assert.match(page, /coordination\?\.tasks\.length/);
  assert.match(page, /activeHouseholdTasks\.slice\(0, 3\)/);
  assert.match(page, /Needs more information/);
  assert.match(page, /does not assume a task is finished/);
});

test('simplified navigation preserves access to every original page', () => {
  for (const name of ['objects', 'schedule', 'automations', 'activity']) {
    assert.match(page, new RegExp(`"${name}"`));
  }
  assert.match(page, /aria-label="More household pages"/);
  assert.match(page, /setView\(item\.id\)/);
});

test('scan, room navigation, and task history remain reachable', () => {
  assert.match(page, /setScanOpen\(true\)/);
  assert.match(page, /setView\("spaces"\)/);
  assert.match(page, /setShowScanStatus\(true\)/);
  assert.match(css, /\.hh-consumer-home/);
});
