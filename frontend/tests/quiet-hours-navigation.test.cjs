const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
const sourcePath = path.join(__dirname, '../lib/quiet-hours.ts');
const source = fs.readFileSync(sourcePath, 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}, reportDiagnostics: true});
assert.deepEqual(compiled.diagnostics || [], []);
const compiledModule = new Module(sourcePath, module);
compiledModule.filename = sourcePath;
compiledModule._compile(compiled.outputText, sourcePath);
const quiet = compiledModule.exports;
const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../app/refined.css'), 'utf8');

const settings = (timezone, start_time = '22:00', end_time = '07:00') => ({ enabled: true, timezone, start_time, end_time });

test('quiet hours follow the saved IANA zone, not the device time zone', () => {
  const at = new Date('2026-10-30T04:30:00Z');
  assert.equal(quiet.quietHoursActiveAt(at, settings('America/Phoenix')), false);
  assert.equal(quiet.quietHoursActiveAt(at, settings('America/New_York')), true);
  assert.equal(quiet.quietHoursActiveAt(at, settings('Asia/Kolkata')), false);
});

test('overnight quiet hours respect end-exclusive boundaries', () => {
  const zone = settings('UTC');
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T21:59:00Z'), zone), false);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T22:00:00Z'), zone), true);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-31T06:59:00Z'), zone), true);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-31T07:00:00Z'), zone), false);
});

test('daytime hours and disabled state work', () => {
  const s = settings('UTC', '08:30', '16:15');
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T09:00:00Z'), s), true);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T17:00:00Z'), s), false);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T09:00:00Z'), {...s, enabled: false}), false);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-10-30T09:00:00Z'), {...s, timezone: 'Invalid/Nowhere'}), false);
});

test('daylight saving is interpreted using time zone rules', () => {
  const s = settings('America/New_York');
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-07-04T05:00:00Z'), s), true);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-12-04T05:00:00Z'), s), true);
  assert.equal(quiet.quietHoursActiveAt(new Date('2026-07-04T12:00:00Z'), s), false);
});

test('quiet hours editing never changes the active page or display mode', () => {
  assert.match(page, /onClick=\{reviewHouseholdReadiness\}>Review household readiness/);
  assert.match(page, /document\.getElementById\("hh-household-readiness"\)/);
  assert.match(page, /onClick=\{openQuietHoursEditor\}>Manage quiet hours/);
  assert.match(page, /quietEditorOpen && <div className="hh-modal-backdrop"/);
  assert.doesNotMatch(page, /onClick=\{\(\) => changeInterfaceMode\(false\)\}>Review household readiness/);
  assert.match(page, /api\.updateQuietHours\(quietEnabled, quietStart, quietEnd, quietTimezone\)/);
  assert.match(page, /setQuietTimezone\(results\[6\]\.value\.quiet_hours\.timezone\)/);
  assert.match(page, /timezone: workWindow\?\.timezone \|\| coordination\?\.quiet_hours\.timezone \|\| deviceTimezone/);
  assert.match(css, /\.hh-app \.hh-header\s*\{\s*position: relative;/);
});
