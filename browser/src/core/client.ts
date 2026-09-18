import type {ConversionEnvelope, ConversionInput, RuntimeManifest} from './types';
export class ConverterClient {
  private worker: Worker | null = null;
  private sequence = 0;
  private pending = new Map<number, {resolve: (v: any) => void; reject: (e: Error) => void; timer: ReturnType<typeof setTimeout>}>();
  private ready: Promise<RuntimeManifest> | null = null;
  private busy = false;
  constructor(private baseURL: string, private onProgress: (message: string) => void = () => {}) {}
  initialize(): Promise<RuntimeManifest> {
    if (this.ready) return this.ready;
    this.worker = new Worker(new URL('../converter.worker.ts', import.meta.url), {type: 'module'});
    this.worker.onmessage = ({data}) => {
      if (data.kind === 'progress') {this.onProgress(data.message); return;}
      const item = this.pending.get(data.id);
      if (!item) return;
      clearTimeout(item.timer); this.pending.delete(data.id);
      if (data.kind === 'error') item.reject(new Error(data.code));
      else item.resolve(data.kind === 'ready' ? data.manifest : data.output);
    };
    this.worker.onerror = () => this.reset('runtime_worker_failed');
    this.ready = this.request('init', {baseURL: this.baseURL}, 120000) as Promise<RuntimeManifest>;
    return this.ready;
  }
  private request(kind: string, payload: object, timeout: number): Promise<unknown> {
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.reset('runtime_timeout'), timeout);
      this.pending.set(id, {resolve, reject, timer});
      if (!this.worker) {clearTimeout(timer); this.pending.delete(id); reject(new Error('runtime_not_ready')); return;}
      this.worker.postMessage({id, kind, ...payload});
    });
  }
  async convert(input: ConversionInput): Promise<ConversionEnvelope> {
    if (this.busy) throw new Error('runtime_busy');
    this.busy = true;
    try {await this.initialize(); return await this.request('convert', {input}, 30000) as ConversionEnvelope;}
    finally {this.busy = false;}
  }
  reset(reason = 'runtime_cancelled'): void {
    this.worker?.terminate(); this.worker = null; this.ready = null; this.busy = false;
    for (const {reject, timer} of this.pending.values()) {clearTimeout(timer); reject(new Error(reason));}
    this.pending.clear();
  }
}
