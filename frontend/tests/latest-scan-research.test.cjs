const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app', 'page.tsx'), 'utf8');
const api = fs.readFileSync(path.join(__dirname, '..', 'lib', 'api.ts'), 'utf8');

test('latest scan Tavily references are visible even if no task is created', () => {
  assert.match(page, /latest_automatic_coordination\?\.scene_research\?\.some\(topic => topic\.sources\.length > 0\)/);
  assert.match(page, /RESEARCH FROM YOUR LATEST PHOTO/);
  assert.match(page, /Plant identification and care/);
  assert.match(page, /source\.url.*target="_blank"/);
  assert.match(api, /latest_automatic_coordination\?:\s*\{[\s\S]*?scene_research\?: Array/);
});

test('reference results are never represented as confirmed visual plant identification', () => {
  assert.match(page, /Web references cannot confirm a plant's identity from a photograph/);
});
