const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../app/globals.css'), 'utf8');
const simpleStart = page.indexOf('{view === "home" && simpleInterface &&');
const fullStart = page.indexOf('{view === "home" && !simpleInterface &&', simpleStart);
const simplePage = page.slice(simpleStart, fullStart);

test('minimal Today shows one prioritized task with evidence-based state', () => {
  assert.match(simplePage, /simpleHomeTasks\[0\]\.title/);
  assert.match(simplePage, /simpleHomeTasks\[0\]\.detail/);
  assert.match(simplePage, /simpleHomeTasks\[0\]\.status/);
  assert.match(page, /\.sort\(\(a, b\) => \(\{ NOW: 0/);
  assert.match(simplePage, /Completion still needs confirmation/);
});

test('additional work is revealed on demand and all tasks remain accessible', () => {
  assert.match(simplePage, /<details className="hh-minimal-extra">/);
  assert.match(simplePage, /simpleHomeTasks\.slice\(1\)/);
  assert.match(simplePage, /setView\("tasks"\)/);
  assert.match(simplePage, /setTaskRoomFilter\("all"\)/);
});

test('simplified Today gives one contextual scan action and room/object links', () => {
  assert.match(simplePage, /setScanOpen\(true\)/);
  assert.match(simplePage, /setView\("spaces"\)/);
  assert.match(simplePage, /setView\("objects"\)/);
  assert.doesNotMatch(simplePage, /hh-consumer-bottom-grid|hh-consumer-hero/);
});

test('the header has separate rows and the More menu is an overlay', () => {
  assert.match(css, /\.hh-app \.hh-header\{display:grid/);
  assert.match(css, /\.hh-app \.hh-header \.hh-nav\{grid-column:1\/-1;grid-row:2/);
  assert.match(css, /\.hh-app \.hh-more-links\{position:fixed/);
  assert.match(page, /aria-label="More household pages"/);
});
