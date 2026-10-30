const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '..', 'app', 'globals.css'), 'utf8');

test('More menu is anchored to its button and closes on outside click or Escape', () => {
  assert.match(page, /moreButtonRef = useRef<HTMLButtonElement>/);
  assert.match(page, /getBoundingClientRect\(\)/);
  assert.match(page, /style=\{\{ top: moreMenuPosition\.top, left: moreMenuPosition\.left, right: "auto" \}\}/);
  assert.match(page, /document\.addEventListener\("pointerdown", closeOutside\)/);
  assert.match(page, /event\.key === "Escape"/);
  assert.match(css, /\.hh-app \.hh-more-links\{position:fixed;right:auto/);
});

test('historical work-window alerts cannot masquerade as current calendar availability', () => {
  assert.match(page, /isEarlierTimingAdvice/);
  assert.match(page, /"Suggested: "/);
  assert.match(page, /This is not confirmation that the time is free now/);
  assert.match(page, /<summary>Original scheduling note<\/summary>/);
  assert.match(page, /not a verified current calendar opening/);
});

test('task cards are compact only in simple mode and still expose evidence', () => {
  assert.match(page, /simpleInterface \? " hh-simple-task-card" : ""/);
  assert.match(page, /Why was this suggested\?/);
  assert.match(page, /Earlier suggested time/);
  assert.match(css, /\.hh-simple-task-card \.hh-task-description\{display:-webkit-box/);
});
