/** Assemble a self-hosted runtime. Never copy fixtures into production assets. */
import { createHash } from 'node:crypto';
import { readFile, writeFile, mkdir, readdir, copyFile, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const repo = path.resolve(root, '..');
const runtime = path.join(root, 'public/runtime');
const sha = (value) => createHash('sha256').update(value).digest('hex');
const canonical = (value) => value.replace(/\r\n/g, '\n');
await rm(runtime, {recursive: true, force: true});
await mkdir(runtime, {recursive: true});
const pkg = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const pyodideDir = path.join(root, 'node_modules/pyodide');
const runtimePackage = JSON.parse(await readFile(path.join(pyodideDir, 'package.json'), 'utf8'));
if (runtimePackage.version !== pkg.dependencies.pyodide) throw new Error('Pyodide lock mismatch');
const pyodideFiles = ['pyodide.mjs', 'pyodide.asm.js', 'pyodide.asm.wasm', 'python_stdlib.zip', 'pyodide-lock.json'];
const fileSizes = {};
for (const file of pyodideFiles) {
  await copyFile(path.join(pyodideDir, file), path.join(runtime, file));
  fileSizes[file] = (await readFile(path.join(runtime, file))).length;
}
const sources = {};
const sourceHashes = {};
for (const name of (await readdir(path.join(repo, 'src/ovid_pubmed_converter'))).sort()) {
  if (!name.endsWith('.py')) continue;
  const relative = `ovid_pubmed_converter/${name}`;
  sources[relative] = canonical(await readFile(path.join(repo, 'src', relative), 'utf8'));
  sourceHashes[`src/${relative}`] = sha(sources[relative]);
}
const baseline = JSON.parse(await readFile(path.join(root, 'parity/reference-manifest.json'), 'utf8'));
if (JSON.stringify(sourceHashes) !== JSON.stringify(baseline.sourceHashes)) {
  throw new Error('Python reference changed. Review and regenerate the parity baseline before building.');
}
sources['browser_bridge.py'] = canonical(await readFile(path.join(root, 'python/browser_bridge.py'), 'utf8'));
const sourceJson = JSON.stringify({schemaVersion: 1, files: sources});
await writeFile(path.join(runtime, 'python-sources.json'), sourceJson);
const resources = path.join(repo, 'resources');
const candidates = (await readdir(resources)).filter(x => /^mesh_resolution_cache_v20_v1_YW_.*\.json$/.test(x)).sort();
const selected = process.env.MESH_CACHE_PATH
  ? path.resolve(repo, process.env.MESH_CACHE_PATH)
  : path.join(resources, candidates.at(-1) || 'mesh_resolution_cache_v20_v1.json');
const cache = JSON.parse(await readFile(selected, 'utf8'));
if (cache.schema_version !== 1 || !cache.records || typeof cache.records !== 'object' || Array.isArray(cache.records)) throw new Error('Invalid production cache');
for (const record of Object.values(cache.records)) {
  if (JSON.stringify(record).match(/FIXTURE_|fixture:\/\//i)) throw new Error('Synthetic fixture metadata must not enter production');
  if (record.status !== 'resolved' || !record.canonical_label || !record.record_class || !/^D\d+$/.test(record.descriptor_id ?? '')) throw new Error('Production record missing verified MeSH provenance');
}
const cacheJson = JSON.stringify(cache);
await writeFile(path.join(runtime, 'mesh-cache.json'), cacheJson);
const manifest = {
  schemaVersion: 1, product: 'ClinSearch-Crosswalk', browserVersion: pkg.version,
  implementation: 'TypeScript interface + unchanged Python in WebAssembly',
  pyodideVersion: runtimePackage.version,
  pythonReferenceCommit: baseline.referenceCommit,
  pythonSourceHashes: sourceHashes,
  pythonBundleSha256: sha(sourceJson), bridgeSha256: sha(sources['browser_bridge.py']),
  cacheSha256: sha(cacheJson), cacheRecords: Object.keys(cache.records).length,
  meshYear: cache.mesh_year ?? null, cacheSource: cache.source ?? null,
  mode: 'cache-only', buildStatus: 'development-preview',
  limits: {inputBytes: 2097152, rows: 1000, nesting: 100, conversionTimeoutSeconds: 30},
};
await writeFile(path.join(runtime, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
for (const file of ['LICENSE', 'NOTICE']) await copyFile(path.join(repo, file), path.join(root, 'public', `${file}.txt`));
for (const [name, size] of Object.entries(fileSizes)) if (size >= 25 * 1024 * 1024) throw new Error(`${name} exceeds static asset limit`);
console.log(`Prepared browser runtime: ${Object.keys(sources).length - 1} unchanged Python modules; ${manifest.cacheRecords} production cache records.`);
if (!manifest.cacheRecords) console.warn('PREVIEW: production MeSH cache is empty. Audited fallback only; no verified terminology expansion.');
