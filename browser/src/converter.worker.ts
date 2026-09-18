/// <reference lib="webworker" />
import {createRuntime} from './core/runtime';
import type {LoadPyodide, RuntimeManifest, ConversionInput} from './core/types';
const scope = self as unknown as DedicatedWorkerGlobalScope;
let runtime: Awaited<ReturnType<typeof createRuntime>> | null = null;
let starting = false;
async function asset(url: string): Promise<string> {
  const response = await fetch(url, {credentials: 'omit', cache: 'no-cache'});
  if (!response.ok) throw new Error('runtime_asset_unavailable');
  return response.text();
}
scope.onmessage = async (event: MessageEvent) => {
  const {id, kind} = event.data ?? {};
  if (!Number.isSafeInteger(id)) return;
  try {
    if (kind === 'init') {
      if (starting) throw new Error('runtime_initialization_in_progress');
      starting = true;
      const base = new URL(event.data.baseURL, scope.location.href);
      if (base.origin !== scope.location.origin) throw new Error('runtime_origin_invalid');
      const prefix = new URL('runtime/', base).href;
      scope.postMessage({kind: 'progress', message: 'Loading local conversion engine…'});
      const [manifestText, sourceText, cacheText] = await Promise.all([
        asset(prefix + 'manifest.json'), asset(prefix + 'python-sources.json'), asset(prefix + 'mesh-cache.json'),
      ]);
      const manifest = JSON.parse(manifestText) as RuntimeManifest;
      const {loadPyodide} = await import(/* @vite-ignore */ prefix + 'pyodide.mjs') as {loadPyodide: LoadPyodide};
      runtime = await createRuntime(loadPyodide, prefix, manifest, sourceText, cacheText);
      scope.fetch = (() => Promise.reject(new Error('conversion_network_disabled'))) as typeof fetch;
      scope.postMessage({id, kind: 'ready', manifest});
    } else if (kind === 'convert') {
      if (!runtime) throw new Error('runtime_not_ready');
      const output = runtime.convert(event.data.input as ConversionInput);
      scope.postMessage({id, kind: 'result', output});
    } else throw new Error('runtime_command_invalid');
  } catch (error) {
    const message = error instanceof Error ? error.message : '';
    const code = /^runtime_[a-z_]+$/.test(message) ? message : 'runtime_processing_failed';
    scope.postMessage({id, kind: 'error', code});
  }
};
