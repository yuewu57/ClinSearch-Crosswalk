export type ValidationStatus = 'ok' | 'validation_failed' | 'manual_review_required';
export interface ConvertedRow {
  number: number; original: string; converted: string;
  audit_flags: string[]; validation_status: string; validation_errors: string[];
  output_number: number | null;
}
export interface ConversionResult {
  validation_status: ValidationStatus; rows: ConvertedRow[];
  final_line_number: number | null; final_query: string | null;
  warnings: string[]; audit_events: string[]; validation_errors: string[];
  removed_line_numbers: number[]; synthetic_rows: [number, string][];
}
export interface ConversionEnvelope {
  result: ConversionResult; strategyText: string; oneLineQuery: string;
  auditCsv: string; convertedRtf: string; inputWarnings: string[]; adapterError: string | null;
}
export type ConversionInput =
  | {mode: 'paste'; source: string; endDate?: string | null}
  | {mode: 'rtf'; dataBase64: string};
export interface RuntimeManifest {
  schemaVersion: number; product: string; browserVersion: string;
  implementation: string; pyodideVersion: string; pythonReferenceCommit: string;
  pythonSourceHashes: Record<string, string>; pythonBundleSha256: string;
  bridgeSha256: string; snapshotAdapterSha256: string;
  cacheSha256: string; cacheRecords: number; cacheLabelKeys: number;
  cacheKind: 'evaluation-cache' | 'full-descriptor-snapshot';
  cacheFile: string; evaluationCacheSha256: string;
  meshYear: number | null; cacheSource: string | null; mode: 'cache-only';
  buildStatus: string;
  limits: {inputBytes: number; rows: number; nesting: number; conversionTimeoutSeconds: number};
}
export interface PyodideInstance {
  version: string;
  FS: {mkdirTree(path: string): void; writeFile(path: string, value: string): void};
  globals: {set(name: string, value: string): void; delete(name: string): void};
  runPython(code: string): unknown;
}
export type LoadPyodide = (options: {indexURL: string; stdout: (s: string) => void; stderr: (s: string) => void}) => Promise<PyodideInstance>;
