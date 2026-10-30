const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const page = fs.readFileSync(path.join(__dirname, '..', 'app/page.tsx'), 'utf8');
const api = fs.readFileSync(path.join(__dirname, '..', 'lib/api.ts'), 'utf8');

test('uncertain physical room identity offers both safe user decisions', () => {
  assert.match(page, /Add this photo as a new space/);
  assert.match(page, /Confirm this is the same room/);
  assert.match(page, /confirmExistingRoom\(job\)/);
  assert.match(page, /same physical space/);
  assert.match(page, /heldRoomChoices\[job.media_id\]/);
});

test('existing room assignment uses authenticated API with original media ID', () => {
  assert.match(api, /async assignAutonomousRoom\(/);
  assert.match(api, /assign-existing-room/);
  assert.match(page, /await api.assignAutonomousRoom\(job.media_id, roomId\)/);
});

test('new scans release previous photo preview on successful upload', () => {
  assert.match(page, /setMedia\(stored\);\s*setFile\(null\);\s*setPhotoInspection\(null\);\s*setPhotoPreviewUrl\(null\);/);
});
