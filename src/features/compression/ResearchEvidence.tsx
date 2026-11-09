import { useState } from 'react';
import type { ResearchEvidence as Evidence } from './types';

const percent = (value: number) => `${(value * 100).toFixed(2)}%`;
const pp = (value: number) => `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}`;

export function ResearchEvidence({ evidence }: { evidence: Evidence }) {
  const [target, setTarget] = useState(0.5);
  return (
    <section className="compression-evidence" aria-labelledby="research-heading">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-accent">Historical research, not this local run</p>
          <h3 id="research-heading" className="mt-2 text-2xl font-semibold">Your large-run development evidence</h3>
        </div>
        <a className="compression-link" href={evidence.results_url} target="_blank" rel="noreferrer">Read the original report</a>
      </div>
      <p className="mt-4 max-w-[75ch] leading-relaxed">
        {evidence.qa_records.toLocaleString()} answer records across {evidence.qa_items.toLocaleString()} questions and {evidence.source_passages} source passages.
        {' '}{evidence.stress_records.toLocaleString()} stress outputs across {evidence.stress_texts.toLocaleString()} texts.
        These are evaluation counts, not concurrent users or requests per second.
      </p>
      <p className="mt-3 max-w-[75ch] text-sm leading-relaxed text-muted">Candidate: {evidence.candidate}. The local methods above do not run this ranker.</p>
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <label htmlFor="evidence-target" className="font-medium">Historical context target</label>
        <select id="evidence-target" className="compression-select" value={target} onChange={(event) => setTarget(Number(event.target.value))}>
          {[0.75, 0.5, 0.33, 0.25].map((value) => <option key={value} value={value}>{Math.round(value * 100)}% kept</option>)}
        </select>
      </div>
      <div className="compression-table-wrap mt-4" tabIndex={0} role="region" aria-label="Historical model comparison, scroll horizontally on small screens">
        <table className="compression-table">
          <caption>Recorded QA accuracy, 900 questions per row. Invalid outputs remain in the denominator.</caption>
          <thead><tr><th scope="col">Answer model</th><th scope="col">Original</th><th scope="col">Candidate</th><th scope="col">BM25</th><th scope="col">LLMLingua-2</th><th scope="col">Candidate vs BM25 (pp), 95% CI</th><th scope="col">Context / full prompt kept</th><th scope="col">Invalid</th></tr></thead>
          <tbody>{evidence.rows.filter((row) => row.target === target).map((row) => (
            <tr key={row.model}><th scope="row">{row.model}</th><td>{percent(row.original_accuracy)}</td><td>{percent(row.candidate_accuracy)}</td><td>{percent(row.bm25_accuracy)}</td><td>{percent(row.llmlingua_accuracy)}</td><td>{pp(row.delta_vs_bm25)} [{pp(row.ci95[0])}, {pp(row.ci95[1])}]</td><td>{percent(row.context_kept)} / {percent(row.full_prompt_kept)}</td><td>{row.invalid}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <p className="mt-3 max-w-[75ch] text-sm leading-relaxed text-muted">{evidence.interpretation} The original-prompt column is included to show the actual compression/accuracy trade-off, not just wins against compressed baselines.</p>
      <h4 className="mt-6 text-lg font-semibold">What these results do not prove</h4>
      <ul className="mt-3 grid gap-2 pl-5 text-sm leading-relaxed md:grid-cols-2">
        {evidence.limits.map((limit) => <li className="list-disc" key={limit}>{limit}</li>)}
      </ul>
      <details className="mt-6">
        <summary className="cursor-pointer font-medium">Source fingerprints and full report, including stress failures</summary>
        <p className="mt-3 text-sm text-muted">{evidence.verification_scope}</p>
        <p className="mt-2 break-all text-sm">Pinned Research commit: <code>{evidence.provenance.commit}</code></p>
        <ul className="mt-3 grid gap-3 text-sm">
          {evidence.provenance.files.map((file) => <li key={file.file}><a className="compression-link" href={file.url} target="_blank" rel="noreferrer">{file.file}</a><code className="mt-1 block break-all text-xs text-muted">SHA-256: {file.sha256}</code></li>)}
        </ul>
        <a className="compression-link mt-4 inline-block" href={evidence.release_url} target="_blank" rel="noreferrer">Fingerprint archive and raw-data release</a>
        <pre className="mt-4 whitespace-pre-wrap break-words rounded-xl border border-line bg-panel p-4 text-sm leading-relaxed">{evidence.results_markdown}</pre>
      </details>
    </section>
  );
}
