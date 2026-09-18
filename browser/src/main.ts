import './styles.css';
import {initializeThemeControl} from './theme';
import {ConverterClient} from './core/client';
import type {ConversionEnvelope, ConversionInput, RuntimeManifest} from './core/types';
const baseURL = new URL(import.meta.env.BASE_URL, location.href).href;
const app = document.querySelector<HTMLDivElement>('#app')!;
app.innerHTML = `
<header class="site-header"><a class="brand" href="./" aria-label="ClinSearch-CrossWalk home"><span class="brand-mark" aria-hidden="true">→</span><span class="brand-name">ClinSearch-CrossWalk</span></a><div class="header-actions"><div class="header-meta"><span class="local-dot" aria-hidden="true"></span>Runs on your device<span class="preview-badge">DEVELOPMENT PREVIEW</span></div><label class="theme-control" for="theme"><span>Theme</span><select id="theme" aria-label="Colour theme"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></div></header>
<main><section class="intro"><div><p class="eyebrow">FOR REPRODUCIBLE EVIDENCE SYNTHESIS</p><h1>Same search intent.<br><span>A different search language.</span></h1><p class="lead">Translate an Ovid MEDLINE strategy into PubMed syntax.<br>Inspect the query, trace every change, and review the warnings.</p></div><aside class="intro-note"><span class="note-label">Ovid MEDLINE <span aria-hidden="true">→</span> PubMed</span><p>Deterministic conversion<br>Line-by-line audit<br>No account required</p></aside></section>
<div class="notice" id="preview-notice"><strong>Preview, not a published release.</strong> Uses the existing Python engine locally in your browser. Local checks do not establish retrieval equivalence or replace search peer review.</div>
<div class="workspace"><section class="card input-card" aria-labelledby="input-title"><div class="card-heading"><div><span class="step">01 / INPUT</span><h2 id="input-title">Your Ovid strategy</h2></div><button id="clear" class="text-button">Clear</button></div>
<div class="mode-buttons" role="group" aria-label="Input mode"><button id="mode-paste" aria-pressed="true">Paste strategy</button><button id="mode-rtf" aria-pressed="false">Upload RTF</button></div>
<div id="paste-panel"><label for="source" class="sr-only">Numbered Ovid MEDLINE strategy</label><textarea id="source" spellcheck="false" autocomplete="off" placeholder="1 asthma.tw.&#10;2 wheeze.tw.&#10;3 1 or 2"></textarea><p class="input-hint">Use one logical search row per line. Existing row numbers are preserved unless a rule requires renumbering.</p></div>
<div id="rtf-panel" hidden><label class="upload-zone" for="rtf"><span class="upload-symbol" aria-hidden="true">↑</span><strong>Select an RTF file</strong><span>Processed on this device • maximum 2 MiB</span><input type="file" id="rtf" accept=".rtf"></label><p id="file-name" class="input-hint">No file selected.</p><p class="input-hint">Use an Ovid export with reliable row numbers or an explicit Medline: section. Ambiguous content is rejected rather than guessed.</p></div>
<div class="example-row"><label for="example">Try an example</label><select id="example"><option value="">Choose a test case…</option><option value="basic">Basic Boolean strategy</option><option value="limit">Final LIMIT row</option><option value="date">Update-date removal</option><option value="invalid">Invalid frequency — blocked</option><option value="mesh">MeSH fallback warning</option></select></div>
<div class="input-actions"><button id="convert" class="primary-button">Convert to PubMed <span aria-hidden="true">→</span></button><button id="cancel" class="secondary-button" hidden>Cancel</button></div>
<p class="privacy-note">No conversion server, live MeSH requests or analytics. Hosting may log page requests; strategy content stays local. Do not enter patient or confidential information.</p></section>
<section class="card result-card" aria-labelledby="result-title"><div class="card-heading"><div><span class="step">02 / OUTPUT</span><h2 id="result-title">PubMed translation</h2></div><span id="state-pill" class="state-pill">Not run</span></div>
<div id="status" class="status-line" role="status" aria-live="polite">Ready when you are.</div><div id="empty-state" class="empty-state"><span aria-hidden="true">→</span><h3>A query you can inspect.</h3><p>Your final query and numbered strategy appear here.<br>Approximations are kept visible in the audit.</p></div>
<div id="results" hidden><div id="result-summary" class="result-summary"></div><label class="output-label" for="query">Final one-line PubMed query</label><textarea id="query" readonly spellcheck="false"></textarea><p id="query-note" class="input-hint"></p><div class="output-actions"><button id="copy" class="secondary-button" disabled>Copy query</button><button id="download-query" class="secondary-button" disabled>Download query</button><button id="download-report" class="text-button">Download report</button></div>
<details class="numbered"><summary>Numbered PubMed strategy</summary><pre id="numbered"></pre></details></div>
<div id="error-panel" class="error-panel" role="alert" hidden></div></section></div>
<section class="card audit-card" id="audit-section" hidden><div class="card-heading"><div><span class="step">03 / INSPECT</span><h2>Warnings & line-level audit</h2></div><button id="download-audit" class="secondary-button">Download audit CSV</button></div><p class="audit-explainer">Original row numbers remain in the audit, including removed rows. An <code>ok</code> status means the local validation gate passed, not that PubMed returned equivalent records.</p><div id="warning-list"></div><div class="table-scroll"><table><caption class="sr-only">Source rows, translated expressions, statuses and audit events</caption><thead><tr><th>Source row</th><th>Ovid source</th><th>PubMed output</th><th>Status & audit</th></tr></thead><tbody id="audit-body"></tbody></table></div></section>
<section class="about-grid"><div><h3>Keep the caveats with the query.</h3><p>Proximity, field mappings and omitted restrictions may broaden retrieval. Inspect the audit before using a translation in evidence synthesis.</p></div><div><h3>Local computation, explicit provenance.</h3><p>The static website loads a pinned Python/WebAssembly runtime once. The conversion itself then runs locally, using the bundled terminology cache only.</p></div><div><h3>A research utility, not search design.</h3><p>This tool translates an established strategy. It does not generate clinical concepts, screen studies or verify live PubMed results.</p></div></section>
<details class="provenance"><summary>Build & terminology provenance</summary><pre id="provenance-text">The runtime manifest will be shown after the first conversion.</pre></details>
<section class="paper-citation" aria-labelledby="associated-paper-title"><span class="paper-label">ASSOCIATED PAPER</span><h2 id="associated-paper-title">ClinSearch-Crosswalk: a recall-oriented, auditable clinical search translation framework for Ovid MEDLINE-to-PubMed conversion</h2><p class="paper-authors">Danqi Zhuang · Fang Qi · Xiaoyue Xi · Chris Robertson · Martin Halvey · Yue Wu</p><p class="paper-link-status">Paper link forthcoming.</p></section>
</main><footer><span>ClinSearch-CrossWalk · Development preview</span><nav><a href="https://github.com/yuewu57/ClinSearch-Crosswalk" target="_blank" rel="noopener noreferrer">Repository</a><a href="./LICENSE.txt" target="_blank" rel="noopener">Source licence</a><a href="./NOTICE.txt" target="_blank" rel="noopener">Notices</a><a href="./THIRD_PARTY_NOTICES.txt" target="_blank" rel="noopener">Runtime licences</a></nav></footer>`;
const el = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
initializeThemeControl(el<HTMLSelectElement>('theme'));
const source = el<HTMLTextAreaElement>('source');
const fileInput = el<HTMLInputElement>('rtf');
const status = el('status');
const copy = el<HTMLButtonElement>('copy');
const queryDownload = el<HTMLButtonElement>('download-query');
let mode: 'paste' | 'rtf' = 'paste';
let output: ConversionEnvelope | null = null;
let manifest: RuntimeManifest | null = null;
let busy = false;
let generation = 0;
const client = new ConverterClient(baseURL, message => {status.textContent = message;});
const examples: Record<string, string> = {
  basic: '1 asthma.tw.\n2 wheeze.tw.\n3 1 or 2',
  limit: '1 asthma.tw.\n2 cancer.tw.\n3 limit 1 to humans',
  date: '1 asthma.tw.\n2 2022*.dt.\n3 1 and 2',
  invalid: '1 cancer.ab./freq=x',
  mesh: '1 telepsychiatry/\n2 telepsychiatr*.ti,ab.\n3 1 or 2',
};
function invalidate() {
  generation++;
  if (busy) client.reset();
  setBusy(false); output = null;
  el('results').hidden = true; el('empty-state').hidden = false;
  el('audit-section').hidden = true; el('error-panel').hidden = true;
  el<HTMLTextAreaElement>('query').value = ''; el('numbered').textContent = '';
  el('audit-body').replaceChildren(); copy.disabled = true; queryDownload.disabled = true;
  el('state-pill').textContent = 'Not run'; el('state-pill').className = 'state-pill';
  status.textContent = 'Input changed. Convert to generate a new result.';
}
function setBusy(value: boolean) {
  busy = value; el<HTMLButtonElement>('convert').disabled = value;
  el('cancel').hidden = !value; source.disabled = value; fileInput.disabled = value;
  copy.disabled = value || !output?.oneLineQuery || output.result.validation_status !== 'ok';
  queryDownload.disabled = copy.disabled; el('status').classList.toggle('working', value);
}
function setMode(value: 'paste' | 'rtf') {
  invalidate(); mode = value;
  el('paste-panel').hidden = value !== 'paste'; el('rtf-panel').hidden = value !== 'rtf';
  el('mode-paste').setAttribute('aria-pressed', String(value === 'paste'));
  el('mode-rtf').setAttribute('aria-pressed', String(value === 'rtf'));
}
el('mode-paste').onclick = () => setMode('paste');
el('mode-rtf').onclick = () => setMode('rtf');
source.addEventListener('input', invalidate);
fileInput.addEventListener('change', () => {invalidate(); el('file-name').textContent = fileInput.files?.[0]?.name ?? 'No file selected.';});
el<HTMLSelectElement>('example').onchange = event => {
  const key = (event.target as HTMLSelectElement).value;
  if (!examples[key]) return; setMode('paste'); source.value = examples[key]; source.focus();
};
el('clear').onclick = () => {
  client.reset(); invalidate(); source.value = ''; fileInput.value = '';
  el('file-name').textContent = 'No file selected.'; source.focus();
  status.textContent = 'Cleared. The worker and its in-memory conversion state were discarded.';
};
el('cancel').onclick = () => {client.reset(); invalidate(); status.textContent = 'Cancelled. No query has been approved or submitted.';};
function addText(parent: HTMLElement, tag: string, text: string, className = '') {
  const node = document.createElement(tag); node.textContent = text;
  if (className) node.className = className; parent.append(node); return node;
}
function warningText(flag: string) {
  if (flag.includes('mesh_resolution_fallback_to_source_heading:')) return 'A heading was not verified by the bundled MeSH cache. The source-heading fallback is shown in the audit.';
  if (flag.includes('major_semantic_approximation')) return 'A rule intentionally changed retrieval scope. Inspect the affected source rows.';
  if (flag.includes('rtf_line_numbers_recovered')) return 'Row numbers were reconstructed from RTF paragraphs. Verify the recovered sequence.';
  if (flag.includes('plain_text_file_uploaded')) return 'This .rtf upload contained plain text. Its explicit Medline section was recovered.';
  return flag;
}
function render(value: ConversionEnvelope) {
  output = value; const result = value.result;
  const ok = result.validation_status === 'ok' && Boolean(value.oneLineQuery);
  el('results').hidden = false; el('empty-state').hidden = true; el('audit-section').hidden = false;
  el<HTMLTextAreaElement>('query').value = ok ? value.oneLineQuery : '';
  el('numbered').textContent = value.strategyText || '(No translated rows)';
  el('state-pill').textContent = ok ? 'Local checks passed' : 'Review required';
  el('state-pill').className = 'state-pill ' + (ok ? 'success' : 'failure');
  el('query-note').textContent = ok
    ? 'Locally checked; not submitted to PubMed. Review warnings before retrieval.'
    : 'No usable final query is offered. The numbered output, when present, is for diagnosis only.';
  const count = result.rows.filter(row => row.converted).length;
  el('result-summary').textContent = `${result.rows.length} source rows · ${count} surviving rows · ${result.removed_line_numbers.length} removed rows`;
  status.textContent = ok ? 'Conversion complete. Inspect the audit before using the query.' : 'Conversion blocked by the local validation gate.';
  const warnings = el('warning-list'); warnings.replaceChildren();
  const readable = [...new Set([...result.warnings.map(warningText), ...value.inputWarnings.map(warningText)])];
  if (result.audit_events.some(x => x.includes('approximation')) && !readable.some(x => x.includes('retrieval scope'))) readable.unshift('Some mappings are approximate. Inspect the source-row audit.');
  for (const message of readable) addText(warnings, 'p', message, 'warning-item');
  for (const error of result.validation_errors) addText(warnings, 'p', error, 'error-item');
  const table = el('audit-body'); table.replaceChildren();
  for (const row of result.rows) {
    const tr = document.createElement('tr');
    addText(tr, 'td', `#${row.number}${row.output_number !== null && row.output_number !== row.number ? ` → #${row.output_number}` : ''}`);
    addText(tr, 'td', row.original, 'code-cell');
    addText(tr, 'td', row.converted || 'Removed — see audit', 'code-cell');
    const audit = addText(tr, 'td', '', 'audit-cell'); addText(audit, 'strong', row.validation_status);
    for (const flag of [...row.audit_flags, ...row.validation_errors]) addText(audit, 'div', flag);
    table.append(tr);
  }
  copy.disabled = !ok; queryDownload.disabled = !ok;
}
function showError(message: string) {
  const panel = el('error-panel'); panel.hidden = false; panel.textContent = message;
  el('state-pill').textContent = 'Not completed'; status.textContent = 'No final query has been approved or submitted.';
}
function bytesToBase64(bytes: Uint8Array) {
  let binary = ''; for (let i = 0; i < bytes.length; i += 32768) binary += String.fromCharCode(...bytes.subarray(i, i + 32768)); return btoa(binary);
}
el('convert').onclick = async () => {
  invalidate(); const ticket = generation; let input: ConversionInput;
  try {
    if (mode === 'paste') {
      if (!source.value.trim()) {showError('Paste an Ovid MEDLINE strategy first.'); return;}
      if (new TextEncoder().encode(source.value).length > 2097152) {showError('The input exceeds the 2 MiB browser limit.'); return;}
      input = {mode: 'paste', source: source.value};
    } else {
      const file = fileInput.files?.[0];
      if (!file || !file.size || file.size > 2097152) {showError('Choose a non-empty RTF file no larger than 2 MiB.'); return;}
      input = {mode: 'rtf', dataBase64: bytesToBase64(new Uint8Array(await file.arrayBuffer()))};
    }
    if (ticket !== generation) return;
    setBusy(true); status.textContent = 'Preparing the local engine… First use downloads the runtime.';
    manifest = await client.initialize(); if (ticket !== generation) return;
    el('provenance-text').textContent = JSON.stringify(manifest, null, 2);
    el('preview-notice').textContent = manifest.cacheKind === 'full-descriptor-snapshot'
      ? `Development preview · Frozen MeSH ${manifest.meshYear} exact-resolution snapshot: ${manifest.cacheRecords.toLocaleString()} descriptors and ${manifest.cacheLabelKeys.toLocaleString()} exact preferred/entry-term labels. No live MeSH lookup or fuzzy matching; unresolved headings retain audited source-heading fallback. The 620-record evaluation cache remains separate and unchanged.`
      : manifest.cacheRecords
        ? `Development preview · Bundled MeSH ${manifest.meshYear ?? 'terminology'} evaluation cache: ${manifest.cacheRecords} verified exact records. Cache misses use audited source-heading fallback. Local checks do not establish PubMed retrieval equivalence.`
        : 'Development preview · The bundled MeSH cache is empty. Headings use audited source-heading fallback; verified label updates and pharmacological-action expansion are unavailable for uncached terms. Local checks do not establish PubMed retrieval equivalence.';
    status.textContent = 'Converting locally on this device…';
    const value = await client.convert(input); if (ticket === generation) render(value);
  } catch (error) {
    if (ticket !== generation) return;
    const code = error instanceof Error ? error.message : 'runtime_processing_failed';
    client.reset(); showError(code === 'runtime_timeout' ? 'The local processing time limit was reached. Try a smaller strategy or use the Python reference tool.' : `Local conversion could not complete (${code}). Retry, or use the Python reference tool.`);
  } finally {if (ticket === generation) setBusy(false);}
};
copy.onclick = async () => {
  if (copy.disabled || !output?.oneLineQuery) return;
  try {await navigator.clipboard.writeText(output.oneLineQuery); status.textContent = 'Final query copied. No query was submitted to PubMed.';}
  catch {el<HTMLTextAreaElement>('query').focus(); el<HTMLTextAreaElement>('query').select(); status.textContent = 'Clipboard permission unavailable. The query is selected for manual copying.';}
};
function download(content: string, name: string, mime: string) {
  const stamp = new Intl.DateTimeFormat('en-GB', {day:'2-digit',month:'2-digit',year:'numeric'}).format(new Date()).replaceAll('/','');
  const url = URL.createObjectURL(new Blob([content], {type: mime}));
  const a = document.createElement('a'); a.href = url;
  const extension = mime.startsWith('application/json') ? '.json' : mime.startsWith('text/csv') ? '.csv' : '.txt';
  a.download = `${name}_v1_YW_${stamp}${extension}`; document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
queryDownload.onclick = () => {if (!queryDownload.disabled && output) download(output.oneLineQuery + '\n','PubMed_query','text/plain;charset=utf-8');};
el('download-report').onclick = () => {if (output && !busy) download(JSON.stringify({provenance: manifest, ...output},null,2),'Crosswalk_report','application/json');};
el('download-audit').onclick = () => {
  if (!output || busy) return;
  // Neutralise spreadsheet formulas in exported CSV only; never change conversion semantics.
  const cells = (values: string[]) => values.map(value => '"' + (/^[=+\-@\t\r]/.test(value) ? "'" + value : value).replaceAll('"','""') + '"').join(',');
  const lines = [cells(['source_row','output_row','original','converted','status','audit_flags','validation_errors']), ...output.result.rows.map(row => cells([String(row.number),row.output_number === null ? '' : String(row.output_number),row.original,row.converted,row.validation_status,row.audit_flags.join('; '),row.validation_errors.join('; ')]))];
  download(lines.join('\r\n') + '\r\n','Crosswalk_audit','text/csv;charset=utf-8');
};
window.addEventListener('pagehide', () => client.reset());
