const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const typescript = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '..', 'lib', 'photo-check.ts'), 'utf8');
const compiled = typescript.transpileModule(source, { compilerOptions: {
  target: typescript.ScriptTarget.ES2022,
  module: typescript.ModuleKind.CommonJS,
}}).outputText;
const moduleExports = {};
vm.runInNewContext(compiled, {exports: moduleExports});
const {validatePhotoFile, photoQualityWarnings} = moduleExports;

test('rejects empty, oversized, and unsupported files before upload', () => {
  assert.throws(() => validatePhotoFile({size: 0, type: 'image/jpeg'}), /empty/);
  assert.throws(() => validatePhotoFile({size: 11 * 1024 * 1024, type: 'image/png'}), /10 MB/);
  assert.throws(() => validatePhotoFile({size: 1200, type: 'application/pdf'}), /JPG/);
  assert.doesNotThrow(() => validatePhotoFile({size: 1024, type: 'image/webp'}));
});

test('reports measurable image concerns with qualified wording', () => {
  assert.match(photoQualityWarnings(320, 200, 100).join(' '), /low-resolution/);
  assert.match(photoQualityWarnings(900, 700, 22).join(' '), /very dark/);
  assert.match(photoQualityWarnings(900, 700, 249).join(' '), /washed out/);
  assert.match(photoQualityWarnings(900, 700, 122, 1).join(' '), /may be out of focus/);
  assert.equal(photoQualityWarnings(900, 700, 122, 25).length, 0);
});
