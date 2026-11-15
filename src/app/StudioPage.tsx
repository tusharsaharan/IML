import { useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Play, RotateCcw } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { runPipeline, type ChatRequest, type ChatResult } from '@/lib/pipeline';
import { browserScope } from '@/lib/session';

const PRESETS = [
  ['Hinglish support', 'Yaar basically mera hostel ka wifi bahut slow chal raha hai, please help me connect.'],
  ['English library', 'Hello sir, can you please explain how to renew my library book before the due date?'],
  ['Hindi assignment', 'असाइनमेंट जमा करने की अंतिम तिथि कहाँ देख सकते हैं?'],
] as const;
const INITIAL: ChatRequest = {
  text: PRESETS[0][1], language: 'auto', mode: 'demo',
  compression: { enabled: true, method: 'crf', budget: 0.6 },
  routing: { enabled: true, policy: 'balanced' }, cache: { enabled: true },
  output: { max_tokens: 120, format_constraint: null }, compare: false,
};
const selectClass = 'mt-1 w-full rounded-xl border border-line bg-white p-2 text-sm';

export function StudioPage() {
  const location = useLocation();
  const handoff = location.state?.studioRequest as ChatRequest | undefined;
  const [request, setRequest] = useState<ChatRequest>(() => handoff ? { ...INITIAL, ...handoff, output: INITIAL.output } : INITIAL);
  const [result, setResult] = useState<ChatResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [json, setJson] = useState(false);
  const [liveReady, setLiveReady] = useState(false);
  const [health, setHealth] = useState('Checking backend…');
  const [lastRequest, setLastRequest] = useState('');
  const stale = result !== null && lastRequest !== JSON.stringify(request);

  useEffect(() => {
    fetch('/api/v1/health').then(async response => {
      if (!response.ok) throw new Error('Backend unavailable');
      const data = await response.json();
      setLiveReady(data.live_ready === true);
      setHealth(data.live_ready ? 'Demo / configured live provider' : 'Local CPU demo · authored answers');
    }).catch(() => setHealth('Backend unavailable · start npm run dev'));
  }, []);

  async function run() {
    setBusy(true);
    setError('');
    setResult(null);
    const snapshot = JSON.stringify(request);
    try {
      setResult(await runPipeline(request, browserScope()));
      setLastRequest(snapshot);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Pipeline request failed.');
    } finally { setBusy(false); }
  }

  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><p className="eyebrow">One request. One pipeline.</p><h2 className="mt-2 text-3xl font-semibold tracking-tight">Request Studio</h2><p className="mt-2 max-w-2xl text-sm text-muted">Inspect answer reuse, prompt compression, model selection and usage in one server execution.</p></div>
      <Badge variant="outline">{health}</Badge>
    </div>
    <div className="grid items-start gap-6 lg:grid-cols-[0.95fr_1.15fr]">
      <Card className="panel space-y-5 p-5 sm:p-6">
        <div className="flex flex-wrap gap-2">{PRESETS.map(([label, text]) => <Button key={label} size="sm" variant="outline" disabled={busy} onClick={() => setRequest({ ...request, text, compression: { ...request.compression, protected_phrases: [] } })}>{label}</Button>)}</div>
        {handoff && <p className="rounded-xl border border-line bg-canvas p-3 text-sm">Loaded from Compression Studio. Compression is disabled to preserve the checked output.</p>}
        <fieldset disabled={busy} className="space-y-4 disabled:opacity-70">
          <div><label htmlFor="studio-prompt" className="text-sm font-medium">Your question</label><Textarea id="studio-prompt" value={request.text} maxLength={4000} rows={5} dir="auto" className="mt-2 bg-white" onChange={e => setRequest({ ...request, text: e.target.value })} /><p className="mt-1 text-xs text-muted">English, Hinglish or Hindi · {request.text.length}/4,000 characters</p></div>
          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs font-medium">Answer source<select aria-label="Answer source" className={selectClass} value={request.mode} onChange={e => setRequest({ ...request, mode: e.target.value as ChatRequest['mode'] })}><option value="demo">Authored demo</option><option value="live" disabled={!liveReady}>Live provider{!liveReady ? ' (configure server)' : ''}</option></select></label>
            <label className="text-xs font-medium">Language<select aria-label="Language" className={selectClass} value={request.language} onChange={e => setRequest({ ...request, language: e.target.value as ChatRequest['language'] })}>{['auto', 'en', 'hinglish', 'hi'].map(value => <option key={value}>{value}</option>)}</select></label>
            <label className="text-xs font-medium">Compression method<select aria-label="Compression method" className={selectClass} value={request.compression.method} onChange={e => setRequest({ ...request, compression: { ...request.compression, method: e.target.value as 'heuristic' | 'crf' } })}><option value="heuristic">Heuristic</option><option value="crf">CRF</option></select></label>
            <label className="text-xs font-medium">Routing policy<select aria-label="Routing policy" className={selectClass} value={request.routing.policy} onChange={e => setRequest({ ...request, routing: { ...request.routing, policy: e.target.value as ChatRequest['routing']['policy'] } })}>{['economy', 'balanced', 'quality'].map(value => <option key={value}>{value}</option>)}</select></label>
            <label className="text-xs font-medium">Output format<select aria-label="Output format" className={selectClass} value={request.output?.format_constraint ?? ''} onChange={e => setRequest({ ...request, output: { max_tokens: request.output!.max_tokens, format_constraint: (e.target.value || null) as NonNullable<ChatRequest['output']>['format_constraint'] } })}><option value="">No format instruction</option><option>3 bullets</option><option>JSON only</option><option>no preamble</option></select></label>
            <label className="text-xs font-medium">Maximum output tokens<input aria-label="Maximum output tokens" className={selectClass} type="number" min={1} max={4096} value={request.output?.max_tokens} onChange={e => setRequest({ ...request, output: { ...request.output!, max_tokens: Number(e.target.value) } })} /></label>
          </div>
          <div className="flex flex-wrap gap-4 border-t border-line pt-4 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={request.cache.enabled} onChange={e => setRequest({ ...request, cache: { ...request.cache, enabled: e.target.checked } })} />Reuse cache</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={request.compression.enabled} onChange={e => setRequest({ ...request, compression: { ...request.compression, enabled: e.target.checked } })} />Compress prompt</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={request.routing.enabled} onChange={e => setRequest({ ...request, routing: { ...request.routing, enabled: e.target.checked } })} />Smart routing</label>
          </div>
          <label className="flex items-start gap-2 text-xs text-muted"><input className="mt-0.5" type="checkbox" checked={request.cache.accept_semantic ?? false} onChange={e => setRequest({ ...request, cache: { ...request.cache, accept_semantic: e.target.checked } })} />Allow approximate answer reuse for this demo. Similarity can miss changed conditions; inspect the matched question.</label>
        </fieldset>
        <p className="text-xs leading-relaxed text-muted">Demo answers are authored support fixtures, with local formatting and reference-token caps. Live mode sends the compressed prompt, format instruction and output limit to the selected model. Compression targets do not guarantee a reduction.</p>
        <Button className="w-full" disabled={busy || !request.text.trim() || !Number.isInteger(request.output?.max_tokens) || request.output!.max_tokens < 1 || request.output!.max_tokens > 4096} onClick={run}><Play className="mr-2 h-4 w-4" />{busy ? 'Running pipeline…' : 'Run pipeline'}</Button>
        {error && <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      </Card>
      <div className="min-w-0 space-y-4" aria-live="polite">
        {!result ? <Card className="panel flex min-h-96 flex-col items-center justify-center gap-4 p-8 text-center"><div className="rounded-full bg-accent/10 p-4"><ArrowRight className="h-7 w-7 text-accent" /></div><h3 className="text-xl font-semibold">{busy ? 'Executing your request' : 'From question to answer'}</h3><p className="max-w-sm text-sm text-muted">Cache → compression → routing → answer → insights. Repeat an eligible question to see the cache skip generation.</p></Card> : <>
          {stale && <p role="status" className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">Inputs changed. The result below belongs to the previous run.</p>}
          <Card className="panel space-y-4 p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="eyebrow">Answer · request #{result.request_id}</span><Badge>{result.answer_source}</Badge></div>
            <p className="whitespace-pre-wrap break-words text-base leading-relaxed" dir="auto">{result.answer}</p>
            <p className="text-xs text-muted">{result.mode} · {result.language} · {result.model ?? 'cached answer; no model call'} · {result.elapsed_ms.toFixed(0)} ms</p>
            {result.output.demo_truncated && <p className="text-xs text-amber-800">Authored answer shortened locally to the reference-token cap; it may be incomplete.</p>}
            <div className="grid grid-cols-3 gap-2 border-t border-line pt-4 text-center">
              <Metric label="Reference input" value={result.cache.hit ? 'skipped' : `${result.usage.reference_original_tokens} → ${result.usage.reference_prompt_tokens}`} />
              <Metric label="Reference answer" value={`${result.usage.reference_output_tokens} tokens`} />
              <Metric label="Provider calls" value={result.provider_called ? '1' : '0'} />
            </div>
            <p className="text-xs text-muted">Tokenizer: {result.usage.tokenizer_backend}. Provider usage: {result.usage.provider.total_tokens ?? 'not reported'}. Cost: {result.cost.usd === null ? 'unknown; prices not configured' : `$${result.cost.usd.toFixed(6)}`} ({result.cost.basis.replaceAll('_', ' ')}).</p>
          </Card>
          <Card className="panel space-y-4 p-5 sm:p-6">
            <div className="flex items-center justify-between"><h3 className="font-semibold">Execution trace</h3><Button size="sm" variant="outline" onClick={() => setJson(!json)}>{json ? 'Show stages' : 'Inspect JSON'}</Button></div>
            {json ? <pre className="max-h-[560px] overflow-auto rounded-xl bg-ink p-4 text-xs text-white">{JSON.stringify(result, null, 2)}</pre> : <ol className="space-y-4">{result.trace.map((stage, index) => <li key={stage.stage} className="flex gap-3"><span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent/10 text-xs font-semibold text-accent">{index + 1}</span><div className="min-w-0"><div className="flex items-center gap-2"><h4 className="text-sm font-semibold capitalize">{stage.stage}</h4><Badge variant="outline">{stage.status}</Badge></div><p className="mt-1 text-xs leading-relaxed text-muted">{stage.note}</p>{stage.stage === 'compression' && result.compression && <p className="mt-2 whitespace-pre-wrap break-words rounded-xl bg-canvas p-3 text-xs" dir="auto">{result.compression.compressed}</p>}{stage.stage === 'routing' && result.routing && <p className="mt-1 text-xs">{result.routing.selected_tier} · score {result.routing.score.toFixed(3)} / threshold {result.routing.threshold.toFixed(3)} · {result.routing.policy}</p>}</div></li>)}</ol>}
            {result.cache.matched_question && <p className="rounded-xl border border-line p-3 text-xs">{result.cache.hit ? 'Reused question' : 'Nearest candidate'}: {result.cache.matched_question} · similarity {result.cache.similarity}. Similarity does not establish answer validity.</p>}
            <div className="flex flex-wrap gap-4 border-t border-line pt-3 text-xs"><Link className="text-accent underline" to={`/cache?scope=${encodeURIComponent(result.cache.scope)}`}>Manage this pipeline cache</Link><Link className="text-accent underline" to="/insights">View request history</Link></div>
            <p className="flex items-center gap-2 text-xs text-muted"><CheckCircle2 className="h-4 w-4 shrink-0" />Recorded in SQLite with answer provenance. {result.cache.stored ? 'Answer saved for eligible repeats.' : ''}</p>
          </Card>
          <Button variant="outline" disabled={busy || stale} onClick={run}><RotateCcw className="mr-2 h-4 w-4" />Repeat this request</Button>
        </>}
      </div>
    </div>
  </div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-canvas p-2"><span className="block text-[10px] text-muted">{label}</span><span className="mt-1 block text-sm font-semibold">{value}</span></div>;
}
