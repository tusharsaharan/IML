import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { compressionRequest, chatRequest, downloadJson, highlightParts } from './client';
import { ResearchEvidence } from './ResearchEvidence';
import type { ComparisonRow, CompressionResult, ResearchEvidence as Evidence, Sample } from './types';
import './compression.css';

const actionClass = 'min-h-11 rounded-lg bg-accent px-4 text-panel hover:bg-accent-strong focus-visible:ring-0';
const secondaryClass = 'min-h-11 rounded-lg border border-line-strong bg-panel px-4 text-ink hover:bg-canvas focus-visible:ring-0';
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const message = (error: unknown) => error instanceof Error ? error.message : 'The request could not finish.';

export function CompressionPage() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [text, setText] = useState('');
  const [method, setMethod] = useState('heuristic');
  const [budget, setBudget] = useState(0.6);
  const [result, setResult] = useState<CompressionResult | null>(null);
  const [rows, setRows] = useState<ComparisonRow[]>([]);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [error, setError] = useState('');
  const [sampleError, setSampleError] = useState('');
  const [evidenceError, setEvidenceError] = useState('');
  const [comparisonError, setComparisonError] = useState('');
  const [busy, setBusy] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [copyMessage, setCopyMessage] = useState('');
  const stale = result !== null && (result.original !== text || result.requested_method !== method || result.budget !== budget);

  useEffect(() => {
    const controller = new AbortController();
    compressionRequest<{ samples: Sample[] }>('samples', { signal: controller.signal }).then((data) => {
      setSamples(data.samples);
      setText((value) => value || data.samples[0]?.text || '');
    }).catch((reason) => { if (!controller.signal.aborted) setSampleError(message(reason)); });
    compressionRequest<Evidence>('evidence', { signal: controller.signal }).then(setEvidence)
      .catch((reason) => { if (!controller.signal.aborted) setEvidenceError(message(reason)); });
    return () => controller.abort();
  }, []);

  async function analyze() {
    setBusy(true); setError(''); setCopyMessage('');
    try {
      setResult(await compressionRequest<CompressionResult>('analyze', {
        method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text, method, budget }),
      }));
    } catch (reason) { setError(`${message(reason)} Check that the backend is running with npm run dev.`); }
    finally { setBusy(false); }
  }

  async function compare() {
    setComparing(true); setComparisonError('');
    try { setRows((await compressionRequest<{ rows: ComparisonRow[] }>(`compare?budget=${budget}`)).rows); }
    catch (reason) { setComparisonError(message(reason)); }
    finally { setComparing(false); }
  }

  async function copy() {
    if (!result) return;
    try { await navigator.clipboard.writeText(result.compressed); setCopyMessage('Compressed text copied.'); }
    catch { setCopyMessage('Clipboard unavailable. Select the output or download its JSON.'); }
  }

  return (
    <div className="compression-studio space-y-8">
      <header>
        <p className="text-sm font-medium text-accent">Tushar Saharan's workstream</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight">Compression Studio</h2>
        <p className="mt-3 max-w-[70ch] leading-relaxed text-muted">Inspect what the imported compressor removes before a request is sent. Local execution and historical research are shown separately.</p>
      </header>

      <div className="compression-workspace grid lg:grid-cols-2">
        <section className="min-w-0 p-5 sm:p-6" aria-labelledby="prompt-heading">
          <h3 id="prompt-heading" className="text-xl font-semibold">Source prompt</h3>
          <p className="mt-2 text-sm text-muted">Presets are verbatim upstream regression examples, not evaluation results.</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {samples.map((sample) => <Button key={sample.id} className={secondaryClass} disabled={busy} onClick={() => { setText(sample.text); setError(''); }}>{sample.label}</Button>)}
          </div>
          {sampleError && <p className="mt-3 text-sm" role="alert">Presets unavailable: {sampleError}. You can still enter your own prompt.</p>}
          <label htmlFor="compression-prompt" className="mt-5 block text-sm font-medium">Text to compress</label>
          <Textarea id="compression-prompt" className="mt-2 min-h-48 border-line-strong bg-panel text-base focus-visible:ring-0" maxLength={12000} value={text} disabled={busy} onChange={(event) => setText(event.target.value)} aria-describedby="prompt-help" />
          <p id="prompt-help" className="mt-2 text-xs text-muted">{text.length.toLocaleString()} / 12,000 characters. Text stays on your configured backend; no answer-model calls are made.</p>
          <div className="mt-5 grid gap-5 sm:grid-cols-2">
            <div><label htmlFor="compression-method" className="block text-sm font-medium">Method</label><select id="compression-method" className="compression-select mt-2 w-full" value={method} disabled={busy} onChange={(event) => setMethod(event.target.value)}><option value="heuristic">Heuristic: guarded lexicon</option><option value="crf">CRF: imported sequence tagger</option></select></div>
            <div><label htmlFor="compression-budget" className="block text-sm font-medium">Token target: {Math.round(budget * 100)}% kept</label><input id="compression-budget" className="mt-2 min-h-11 w-full accent-accent" type="range" min="0.1" max="1" step="0.05" disabled={busy} value={budget} onChange={(event) => setBudget(Number(event.target.value))} aria-describedby="budget-help" /></div>
          </div>
          <p id="budget-help" className="mt-3 text-sm leading-relaxed text-muted">This is a measured target, not a strength control. Heuristic and CRF decisions are fixed; changing the target does not force token deletion. At 100%, the original is retained.</p>
          <Button className={`${actionClass} mt-5`} disabled={busy || !text.trim()} onClick={analyze}>{busy ? 'Running imported compressor…' : 'Analyze prompt'}</Button>
          {error && <p className="mt-4 text-sm" role="alert">{error}</p>}
        </section>

        <section className="min-w-0 border-t border-line p-5 sm:p-6 lg:border-t-0 lg:border-l" aria-labelledby="output-heading" aria-busy={busy}>
          <h3 id="output-heading" className="text-xl font-semibold">Compression audit</h3>
          <div role="status" aria-live="polite" className="mt-2 text-sm text-muted">{busy ? 'Running on the local backend.' : stale ? 'Inputs changed. This is the previous run; analyze again for current results.' : result ? `Actual method: ${result.method}. Local execution, not a historical benchmark.` : 'Choose a preset or enter a prompt, then analyze to inspect the real output.'}</div>
          {result && <>
            {result.fallback_reason && <p className="mt-4 rounded-lg border border-line-strong bg-canvas p-3 text-sm">Fallback: {result.fallback_reason}</p>}
            <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-4 border-y border-line py-4">
              <div><dt className="text-sm text-muted">Reference tokens</dt><dd className="mt-1 text-xl font-semibold">{result.original_tokens} to {result.compressed_tokens}</dd></div>
              <div><dt className="text-sm text-muted">Saved / kept</dt><dd className="mt-1 text-xl font-semibold">{result.saved_tokens} / {percent(result.compression_ratio)}</dd></div>
              <div><dt className="text-sm text-muted">Target check</dt><dd className="mt-1 font-medium">{result.budget_met ? 'Met' : 'Not met'} ({result.compressed_tokens}/{result.target_tokens})</dd></div>
            </dl>
            <p className="mt-3 text-xs text-muted">{result.tokenizer}. Counts are not provider billing. This call took {result.elapsed_ms.toFixed(2)} ms including counting/audit; not a throughput benchmark.</p>
            <h4 className="mt-5 font-semibold">Original with changes</h4>
            <p className="mt-1 text-xs text-muted">Struck through: removed. Underlined: tracked protection. Literal survival is checked below.</p>
            <p className="compression-text mt-3" dir="auto">{highlightParts(result.original, result.removed_spans, result.protected_spans).map((part, index) => part.kind === 'removed' ? <del key={index} className="compression-removed">{part.text}</del> : part.kind === 'protected' ? <mark key={index} className="compression-mark">{part.text}</mark> : <span key={index}>{part.text}</span>)}</p>
            <h4 className="mt-5 font-semibold">Compressed text</h4>
            <p className="compression-text mt-3 rounded-lg border border-line bg-canvas p-4" dir="auto">{result.compressed}</p>
            <p className="mt-3 text-sm text-muted">{result.note}</p>
            <div className="mt-4 flex flex-wrap gap-2"><Button className={secondaryClass} disabled={stale || busy} onClick={copy}>Copy text</Button><Button className={secondaryClass} disabled={stale || busy} onClick={() => downloadJson(result, 'compression-audit.json')}>Download audit</Button><Button className={secondaryClass} disabled={stale || busy} onClick={() => downloadJson(chatRequest(result), 'studio-chat-request.json')}>Export Studio request</Button></div>
            <p className="mt-2 text-xs text-muted">Studio handoff is not wired yet. Export follows the shared chat contract with compression disabled to avoid compressing twice; no answer is generated.</p>
            <p className="mt-2 text-sm" role="status">{copyMessage}</p>
            <details className="mt-4"><summary className="cursor-pointer font-medium">Protected content and algorithm drop records</summary>
              {result.protected_spans.length ? <ul className="mt-3 space-y-2 text-sm">{result.protected_spans.map((span) => <li key={`${span.start}-${span.end}`} className="break-words"><strong>{span.preserved ? 'Literal present' : 'Literal missing'}</strong>: {span.text} ({span.kind})</li>)}</ul> : <p className="mt-3 text-sm">No spans detected by the imported protection rules.</p>}
              <p className="mt-3 text-sm leading-relaxed text-muted">{result.limitations}</p>
              {result.drop_records.length ? <ul className="mt-4 space-y-2 text-sm">{result.drop_records.map((drop, index) => <li key={index}><code>{drop.token}</code>: {drop.category}, {drop.rule}</li>)}</ul> : <p className="mt-3 text-sm">No algorithm drop records. Source/output differences above may still include formatting or greeting removal.</p>}
              {result.added_spans.length > 0 && <p className="mt-3 text-sm">Output insertions/replacements: {result.added_spans.map((span) => JSON.stringify(span.text)).join(', ')}. These are text differences, not a semantic score.</p>}
              <a className="compression-link mt-4 inline-block text-sm" href={result.source_url} target="_blank" rel="noreferrer">Imported implementation and source commit</a>
            </details>
          </>}
        </section>
      </div>

      <section aria-labelledby="comparison-heading">
        <div className="flex flex-wrap items-center justify-between gap-4"><div><h3 id="comparison-heading" className="text-2xl font-semibold">Two methods, three regression examples</h3><p className="mt-2 text-sm text-muted">Generated by the local backend on demand. Not measured answer quality or a representative scale benchmark.</p></div><Button className={secondaryClass} disabled={comparing} onClick={compare}>{comparing ? 'Running six comparisons…' : 'Run method comparison'}</Button></div>
        {comparisonError && <p role="alert" className="mt-3 text-sm">{comparisonError}</p>}
        <div role="status" className="mt-3 text-sm text-muted">{comparing ? 'Running imported methods on upstream examples.' : rows.length ? `Completed ${rows.length} local runs at ${Math.round(rows[0].budget * 100)}% target. No answer models called.` : ''}</div>
        {rows.length > 0 && <div className="compression-table-wrap mt-3" tabIndex={0} role="region" aria-label="Local method comparison, scroll horizontally on small screens"><table className="compression-table"><caption>Actual output and fallbacks remain visible for every example.</caption><thead><tr><th scope="col">Example</th><th scope="col">Requested / actual</th><th scope="col">Tokens</th><th scope="col">Kept</th><th scope="col">Target</th><th scope="col">Output</th></tr></thead><tbody>{rows.map((row) => <tr key={`${row.sample_id}-${row.requested_method}`}><th scope="row"><a className="compression-link" href={row.sample_source_url} target="_blank" rel="noreferrer">{row.label}</a></th><td>{row.requested_method} / {row.method}{row.fallback_reason && <p className="mt-1 text-xs">{row.fallback_reason}</p>}</td><td>{row.original_tokens} to {row.compressed_tokens}</td><td>{percent(row.compression_ratio)}</td><td>{row.budget_met ? 'Met' : 'Not met'}</td><td className="min-w-64 break-words" dir="auto">{row.compressed}</td></tr>)}</tbody></table></div>}
      </section>

      {evidence ? <ResearchEvidence evidence={evidence} /> : <section className="compression-evidence"><h3 className="text-2xl font-semibold">Historical research evidence</h3><p className="mt-3 text-sm" role="status">{evidenceError ? `Evidence unavailable: ${evidenceError}` : 'Loading fingerprinted research evidence…'}</p>{evidenceError && <Button className={`${secondaryClass} mt-3`} onClick={() => { setEvidenceError(''); compressionRequest<Evidence>('evidence').then(setEvidence).catch((reason) => setEvidenceError(message(reason))); }}>Retry evidence</Button>}</section>}
    </div>
  );
}
