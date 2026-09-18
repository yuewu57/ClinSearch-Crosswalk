import type {ConversionInput, ConversionEnvelope, RuntimeManifest, LoadPyodide} from './types';

export async function sha256(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)))
    .map(x => x.toString(16).padStart(2, '0')).join('');
}

/** The mounted Python sources are generated from the frozen reference, not reimplemented. */
export async function createRuntime(
  load: LoadPyodide,
  indexURL: string,
  manifest: RuntimeManifest,
  sourceText: string,
  cacheText: string,
) {
  if (manifest.schemaVersion !== 1 || manifest.mode !== 'cache-only') {
    throw new Error('runtime_manifest_invalid');
  }
  if (await sha256(sourceText) !== manifest.pythonBundleSha256) {
    throw new Error('runtime_source_integrity_failed');
  }
  if (await sha256(cacheText) !== manifest.cacheSha256) {
    throw new Error('runtime_cache_integrity_failed');
  }

  const source = JSON.parse(sourceText) as {schemaVersion: number; files: Record<string, string>};
  if (source.schemaVersion !== 1) throw new Error('runtime_source_schema_invalid');

  const snapshotModule = 'mesh_snapshot_resolver_v1_YW_18092026.py';
  for (const [file, content] of Object.entries(source.files)) {
    const allowed =
      file === 'browser_bridge.py' ||
      file === snapshotModule ||
      /^ovid_pubmed_converter\/[a-z_][a-z0-9_]*\.py$/.test(file);
    if (!allowed) throw new Error('runtime_source_path_invalid');

    const expected =
      file === 'browser_bridge.py'
        ? manifest.bridgeSha256
        : file === snapshotModule
          ? manifest.snapshotAdapterSha256
          : manifest.pythonSourceHashes[`src/${file}`];
    if (!expected || await sha256(content) !== expected) {
      throw new Error('runtime_module_integrity_failed');
    }
  }

  const expectedModuleCount =
    Object.keys(manifest.pythonSourceHashes).length + 2;
  if (Object.keys(source.files).length !== expectedModuleCount) {
    throw new Error('runtime_module_missing');
  }

  const py = await load({indexURL, stdout: () => {}, stderr: () => {}});
  if (py.version !== manifest.pyodideVersion) throw new Error('runtime_version_mismatch');

  py.FS.mkdirTree('/home/crosswalk/ovid_pubmed_converter');
  for (const [file, content] of Object.entries(source.files)) {
    py.FS.writeFile(`/home/crosswalk/${file}`, content);
  }

  py.runPython(
    'import sys\n' +
    'sys.path.insert(0, "/home/crosswalk")\n' +
    'from browser_bridge import initialize_cache_json as _crosswalk_initialize_cache\n' +
    'from browser_bridge import run_request_json as _crosswalk_convert'
  );
  py.globals.set('_crosswalk_cache', cacheText);
  try {
    const initialized = py.runPython('_crosswalk_initialize_cache(_crosswalk_cache)');
    if (initialized !== true) throw new Error('runtime_cache_initialization_failed');
  } finally {
    py.globals.delete('_crosswalk_cache');
  }

  return {
    manifest,
    convert(input: ConversionInput): ConversionEnvelope {
      py.globals.set('_crosswalk_input', JSON.stringify(input));
      try {
        const value = py.runPython('_crosswalk_convert(_crosswalk_input)');
        if (typeof value !== 'string') throw new Error('runtime_result_invalid');
        return JSON.parse(value) as ConversionEnvelope;
      } finally {
        py.globals.delete('_crosswalk_input');
      }
    },
  };
}
