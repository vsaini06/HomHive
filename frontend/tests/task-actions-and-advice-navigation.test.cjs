const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '../app/page.tsx'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../app/refined.css'), 'utf8');

test('task action loading is scoped to the individual task', () => {
  assert.match(page, /pendingTaskActionRef\.current\.has\(taskId\)/);
  assert.match(page, /pendingTaskActionRef\.current\.add\(taskId\)/);
  assert.match(page, /pendingTaskActionRef\.current\.delete\(taskId\)/);
  assert.match(page, /disabled=\{Boolean\(pendingTaskActions\[task\.id\]\)\}/);
  assert.match(page, /pendingTaskActions\[task\.id\] === "accept"/);
  assert.match(page, /pendingTaskActions\[task\.id\] === "done"/);
  assert.doesNotMatch(page, /disabled=\{pendingTaskAction !== null\}/);
});

test('Nemotron advice links to the exact currently active household task', () => {
  assert.match(page, /function openRecommendedTask\(taskId: string\)/);
  assert.match(page, /autonomousTasks\.find\(item => item\.id === taskId && !\["dismissed", "completed"\]/);
  assert.match(page, /setTaskRoomFilter\("all"\)/);
  assert.match(page, /setFocusedTaskId\(task\.id\)/);
  assert.match(page, /setView\("tasks"\)/);
  assert.match(page, /openRecommendedTask\(currentAdviceTask\.task_id\)/);
  assert.match(page, /openRecommendedTask\(waitingAdvisorTask\.task_id\)/);
  assert.match(page, /openRecommendedTask\(latestScanTask\.task_id\)/);
  assert.match(page, /id=\{`hh-task-\$\{task\.id\}`\}/);
  assert.match(page, /scrollIntoView\(\{behavior: "smooth", block: "center"\}\)/);
  assert.match(page, /Review household readiness/);
  assert.match(css, /\.hh-intelligent-task\.hh-recommended-task/);
});

test('task navigation never changes interface mode or mutates task approval', () => {
  const handler = page.split('function openRecommendedTask(taskId: string) {')[1]?.split('\n  }')[0];
  assert.ok(handler);
  assert.doesNotMatch(handler, /setSimpleInterface|decideAutonomousTask/);
});
