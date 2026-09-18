/** Assemble the self-hosted browser runtime. Never copy fixtures into production assets. */
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir, readdir, copyFile, rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const repo = path.resolve(root, '..');
const runtime = path.join(root, 'public/runtime');
const sha = value => createHash('sha256').update(value).digest('hex');
const canonical = value => value.replace(/\r\n/g, '\n');

await rm(runtime, {recursive: true, force: true});
await mkdir(runtime, {recursive: true});

const pkg = JSON.parse(await readFile(path.join(root, 'package.json'), 'utf8'));
const pyodideDir = path.join(root, 'node_modules/pyodide');
const runtimePackage = JSON.parse(await readFile(path.join(pyodideDir, 'package.json'), 'utf8'));
if (runtimePackage.version !== pkg.dependencies.pyodide) throw new Error('Pyodide lock mismatch');

const pyodideFiles = [
  'pyodide.mjs',
  'pyodide.asm.js',
  'pyodide.asm.wasm',
  'python_stdlib.zip',
  'pyodide-lock.json',
];
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

sources['browser_bridge.py'] = canonical(
  await readFile(path.join(root, 'python/browser_bridge.py'), 'utf8')
);
const snapshotModule = 'mesh_snapshot_resolver_v1_YW_18092026.py';
sources[snapshotModule] = canonical(
  await readFile(path.join(root, 'python', snapshotModule), 'utf8')
);

const sourceJson = JSON.stringify({schemaVersion: 1, files: sources});
await writeFile(path.join(runtime, 'python-sources.json'), sourceJson);

const resources = path.join(repo, 'resources');
const candidates = (await readdir(resources))
  .filter(x => /^mesh_resolution_cache_v20_v1_YW_.*\.json$/.test(x))
  .sort();
const selected = process.env.MESH_CACHE_PATH
  ? path.resolve(repo, process.env.MESH_CACHE_PATH)
  : path.join(resources, candidates.at(-1) || 'mesh_resolution_cache_v20_v1.json');

const cacheRaw = await readFile(selected);
const cacheText = cacheRaw.toString('utf8');
const cache = JSON.parse(cacheText);
const fullSnapshot = cache.schema_version === 2;

if (fullSnapshot) {
  execFileSync(process.env.PYTHON || 'python', [
    path.join(repo, 'scripts/validate_frozen_mesh2026_browser_snapshot.py'),
    '--repo-root', repo,
    '--snapshot', selected,
  ], {stdio: 'inherit'});
} else {
  if (
    cache.schema_version !== 1 ||
    !cache.records ||
    typeof cache.records !== 'object' ||
    Array.isArray(cache.records)
  ) throw new Error('Invalid production cache');
  for (const record of Object.values(cache.records)) {
    if (JSON.stringify(record).match(/FIXTURE_|fixture:\/\//i)) {
      throw new Error('Synthetic fixture metadata must not enter production');
    }
    if (
      record.status !== 'resolved' ||
      !record.canonical_label ||
      !record.record_class ||
      !/^D\d+$/.test(record.descriptor_id ?? '')
    ) throw new Error('Production record missing verified MeSH provenance');
  }
}

await writeFile(path.join(runtime, 'mesh-cache.json'), cacheRaw);

const evaluationCache = await readFile(
  path.join(resources, 'mesh_resolution_cache_v20_v1_YW_18092026.json')
);
const cacheRecords = fullSnapshot
  ? Object.keys(cache.descriptors).length
  : Object.keys(cache.records).length;
const cacheLabelKeys = fullSnapshot
  ? cache.counts.all_label_keys
  : cacheRecords;

const manifest = {
  schemaVersion: 1,
  product: 'ClinSearch-Crosswalk',
  browserVersion: pkg.version,
  implementation: 'TypeScript interface + unchanged Python in WebAssembly',
  pyodideVersion: runtimePackage.version,
  pythonReferenceCommit: baseline.referenceCommit,
  pythonSourceHashes: sourceHashes,
  pythonBundleSha256: sha(sourceJson),
  bridgeSha256: sha(sources['browser_bridge.py']),
  snapshotAdapterSha256: sha(sources[snapshotModule]),
  cacheSha256: sha(cacheRaw),
  cacheRecords,
  cacheLabelKeys,
  cacheKind: fullSnapshot ? 'full-descriptor-snapshot' : 'evaluation-cache',
  cacheFile: fullSnapshot
    ? 'mesh2026_exact_snapshot_v1_YW_18092026.json'
    : path.basename(selected),
  evaluationCacheSha256: sha(evaluationCache),
  meshYear: cache.mesh_year ?? null,
  cacheSource: cache.source ?? null,
  mode: 'cache-only',
  buildStatus: 'development-preview',
  limits: {
    inputBytes: 2097152,
    rows: 1000,
    nesting: 100,
    conversionTimeoutSeconds: 30,
  },
};
await writeFile(
  path.join(runtime, 'manifest.json'),
  JSON.stringify(manifest, null, 2) + '\n'
);

for (const file of ['LICENSE', 'NOTICE']) {
  await copyFile(path.join(repo, file), path.join(root, 'public', `${file}.txt`));
}
for (const [name, size] of Object.entries(fileSizes)) {
  if (size >= 25 * 1024 * 1024) throw new Error(`${name} exceeds static asset limit`);
}

console.log(
  `Prepared browser runtime: ${Object.keys(sourceHashes).length} unchanged Python modules; ` +
  (fullSnapshot
    ? `${cacheRecords} MeSH descriptors / ${cacheLabelKeys} exact labels.`
    : `${cacheRecords} evaluation-cache records.`)
);
