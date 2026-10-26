import test from 'node:test';
import assert from 'node:assert/strict';
import { WORK_TIME_OPTIONS, readableWorkDays, readableWorkTime, workWindowError } from '../lib/work-schedule.ts';

test('half-hour time choices have readable endpoints', () => {
  assert.equal(WORK_TIME_OPTIONS.length, 48);
  assert.equal(WORK_TIME_OPTIONS[0], '00:00');
  assert.equal(WORK_TIME_OPTIONS.at(-1), '23:30');
  assert.equal(readableWorkTime('00:00'), '12:00 AM');
  assert.equal(readableWorkTime('12:30'), '12:30 PM');
  assert.equal(readableWorkTime('18:00'), '6:00 PM');
});

test('day summaries are honest and ordered', () => {
  assert.equal(readableWorkDays([0, 1, 2, 3, 4, 5, 6]), 'Every day');
  assert.equal(readableWorkDays([4, 3, 2, 1, 0]), 'Weekdays');
  assert.equal(readableWorkDays([6, 5]), 'Weekends');
  assert.equal(readableWorkDays([3, 1, 1]), 'Tue, Thu');
  assert.equal(readableWorkDays([]), 'No days selected');
});

test('work window validation rejects no days and backwards windows', () => {
  assert.match(workWindowError('18:00','21:00',[]), /at least one day/);
  assert.match(workWindowError('21:00','18:00',[1]), /later/);
  assert.match(workWindowError('18:00','18:00',[1]), /later/);
  assert.match(workWindowError('18:99','21:00',[1]), /Choose a start/);
  assert.equal(workWindowError('18:00','21:00',[1, 3]), null);
  assert.equal(workWindowError('18:15','21:45',[1, 3]), null);
});
