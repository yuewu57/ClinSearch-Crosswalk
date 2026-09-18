import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {loadPyodide} from 'pyodide';
const root = fileURLToPath(new URL('../', import.meta.url));
execFileSync(process.env.PYTHON || 'python', ['../scripts/export_browser_parity.py', '--check'], {cwd: root});
execFileSync(process.execPath, ['node_modules/typescript/bin/tsc', '-p', 'tsconfig.core.json'], {cwd: root});
const {createRuntime, sha256} = await import('../.test-build/core/runtime.js');
const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const sourceText = read('../public/runtime/python-sources.json');
const manifest = JSON.parse(read('../public/runtime/manifest.json'));
const defaultCache = read('../public/runtime/mesh-cache.json');
let referenceInterpreter;
const captureLoader = async (options) => {referenceInterpreter = await loadPyodide(options); return referenceInterpreter;};
const runtime = await createRuntime(captureLoader, fileURLToPath(new URL('../node_modules/pyodide/', import.meta.url)), manifest, sourceText, defaultCache);
const cases = JSON.parse(read('../parity/generated.json'));
const runtimes = new Map([[defaultCache, runtime]]);
for (const item of cases) {
  test(`native/WASM full-result parity: ${item.id}`, async () => {
    const cacheText = JSON.stringify(item.cache);
    let instance = runtimes.get(cacheText);
    if (!instance) {
      instance = await createRuntime(loadPyodide, fileURLToPath(new URL('../node_modules/pyodide/', import.meta.url)),
        {...manifest, cacheSha256: await sha256(cacheText)}, sourceText, cacheText);
      runtimes.set(cacheText, instance);
    }
    assert.deepEqual(instance.convert(item.request), item.expected);
    assert.deepEqual(instance.convert(item.request), item.expected, 'repeat must be deterministic');
  });
}
test('reject a corrupted source bundle before starting Python', async () => {
  await assert.rejects(createRuntime(loadPyodide, '', manifest, sourceText + ' ', defaultCache), /integrity/);
});
test('reject a corrupted terminology cache', async () => {
  await assert.rejects(createRuntime(loadPyodide, '', manifest, sourceText, defaultCache + ' '), /integrity/);
});
for (const [name, input] of [
  ['empty', {mode: 'paste', source: ''}],
  ['oversize', {mode: 'paste', source: 'a'.repeat(2097153)}],
  ['deep nesting', {mode: 'paste', source: '1 ' + '('.repeat(101) + 'asthma.tw.' + ')'.repeat(101)}],
  ['bad RTF', {mode: 'rtf', dataBase64: btoa('not RTF')}],
  ['bad base64', {mode: 'rtf', dataBase64: '!!!!'}],
  ['row limit', {mode: 'paste', source: Array.from({length:1001}, (_,i) => `${i+1}. asthma.tw.`).join('\n')}],
]) test(`adapter fails safely: ${name}`, () => {
  const result = runtime.convert(input);
  assert.equal(result.result.validation_status, 'manual_review_required');
  assert.equal(result.oneLineQuery, '');
  assert.ok(result.adapterError);
});
test('prevent exponential one-line expansion before allocation', () => {
  const source = ['1 asthma.tw.', ...Array.from({length:23}, (_,i) => `${i+2} ${i+1} or ${i+1}`)].join('\n');
  const result = runtime.convert({mode:'paste',source});
  assert.equal(result.adapterError, 'browser_expanded_query_limit_exceeded');
  assert.equal(result.oneLineQuery, '');
});
test('source text is data, never executed as Python', () => {
  const result = runtime.convert({mode:'paste',source:'1 __import__("os").system("touch /tmp/SHOULD_NOT_EXIST")'});
  assert.equal(referenceInterpreter.runPython('import os; os.path.exists("/tmp/SHOULD_NOT_EXIST")'), false);
  assert.equal(typeof result.oneLineQuery, 'string');
});
