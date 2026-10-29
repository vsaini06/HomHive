import test from 'node:test';
import assert from 'node:assert/strict';
import {splitClock, joinClock} from '../lib/clock-time.ts';

test('minutes can be set individually, not just half-hour increments', () => {
  assert.equal(joinClock('7', '23', 'PM'), '19:23');
  assert.equal(joinClock('12', '01', 'AM'), '00:01');
  assert.equal(joinClock('12', '59', 'PM'), '12:59');
});

test('midnight, noon and full 24-hour clock round-trip correctly', () => {
  for (let h=0;h<24;h++) for(let m=0;m<60;m++) {
    const v = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
    const p = splitClock(v);
    assert.equal(joinClock(p.hour,p.minute,p.period), v);
  }
});

test('clock does not accept impossible selections', () => {
  assert.throws(() => joinClock('0','00','AM'));
  assert.throws(() => joinClock('12','60','PM'));
  assert.throws(() => joinClock('8','23','NOON'));
});
