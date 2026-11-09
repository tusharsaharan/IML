import { useCallback, useEffect, useState } from 'react';
import { AlertCircle, Database, LoaderCircle, RefreshCw, Search, Sparkles, Trash2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';

type CacheEntry = {
  id: number;
  question: string;
  answer: string;
  language: string;
  source: string;
  created_at: string;
};

type LookupResult = {
  hit: boolean;
  match_type: 'exact' | 'semantic' | 'none';
  similarity: number;
  matched_question: string | null;
  answer: string | null;
  source: string | null;
  cache_id?: number | null;
  threshold?: number;
  note: string;
};

type CacheStats = { total_lookups: number; exact_hits: number; semantic_hits: number; misses: number };
const emptyStats: CacheStats = { total_lookups: 0, exact_hits: 0, semantic_hits: 0, misses: 0 };
const demoQuestions = [
  { label: 'Exact', text: 'How can I renew a library book?' },
  { label: 'Hinglish paraphrase', text: 'library ki book renew kaise karu' },
  { label: 'Different details', text: 'Can I change my exam date because I missed the bus?' },
];

async function cacheApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/cache/${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    signal: init?.signal ?? AbortSignal.timeout(15000),
  });
  if (!response.ok) {
    let message = `Cache API returned ${response.status}.`;
    try {
      const body = await response.json() as { detail?: string };
      if (body.detail) message = body.detail;
    } catch { /* Keep the HTTP status when the response has no JSON body. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function CachePage() {
  const [question, setQuestion] = useState('How do I renew my library book?');
  const [result, setResult] = useState<LookupResult | null>(null);
  const [entries, setEntries] = useState<CacheEntry[]>([]);
  const [stats, setStats] = useState(emptyStats);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    const [entryData, statsData] = await Promise.all([
      cacheApi<{ items: CacheEntry[] }>('entries'),
      cacheApi<CacheStats>('stats'),
    ]);
    setEntries(entryData.items);
    setStats(statsData);
  }, []);

  useEffect(() => {
    void refresh().catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Could not load cache data.'));
  }, [refresh]);

  async function run(action: string, callback: () => Promise<void>) {
    setBusy(action);
    setError('');
    try {
      await callback();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Cache request failed.');
    } finally {
      setBusy('');
    }
  }

  function lookup() {
    return run('lookup', async () => {
      const data = await cacheApi<LookupResult>('lookup', { method: 'POST', body: JSON.stringify({ text: question, language: 'auto' }) });
      setResult(data);
      await refresh();
    });
  }

  function seed() {
    return run('seed', async () => {
      await cacheApi('seed', { method: 'POST' });
      await refresh();
    });
  }

  function removeEntry(id: number) {
    return run(`delete-${id}`, async () => {
      await cacheApi(`entries/${id}`, { method: 'DELETE' });
      await refresh();
    });
  }

  function clearCache() {
    return run('clear', async () => {
      await cacheApi('entries', { method: 'DELETE' });
      setResult(null);
      await refresh();
    });
  }

  const metrics = [
    { label: 'Lookups', value: stats.total_lookups },
    { label: 'Exact hits', value: stats.exact_hits },
    { label: 'Semantic hits', value: stats.semantic_hits },
    { label: 'Misses', value: stats.misses },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Shivam · Answer reuse</p>
          <h2 className="mt-2 text-3xl font-semibold">Memory &amp; Cache</h2>
          <p className="mt-2 max-w-2xl text-muted">Try an exact question or a paraphrase. Near matches show their similarity and matched question so you can check them before reuse.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void run('refresh', refresh)} disabled={Boolean(busy)}><RefreshCw /> Refresh</Button>
          <Button onClick={() => void seed()} disabled={Boolean(busy)}><Database /> Seed demo FAQs</Button>
        </div>
      </div>

      {error && <div role="alert" className="flex items-center gap-2 rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-800"><AlertCircle className="size-4 shrink-0" />{error}</div>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Cache lookup counters">
        {metrics.map((metric) => <Card key={metric.label} className="panel p-4">
          <p className="text-sm text-muted">{metric.label}</p>
          <p className="mono mt-1 text-3xl font-semibold">{metric.value}</p>
        </Card>)}
      </section>

      <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
        <Card className="panel p-5 sm:p-6">
          <div className="flex items-center gap-2"><Search className="size-5 text-accent" /><h3 className="text-xl font-semibold">Ask the cache</h3></div>
          <p className="mt-1 text-sm text-muted">Normalization ignores case, punctuation and repeated spaces. Similarity uses deterministic CPU hash vectors; no model download is needed.</p>
          <Textarea className="mt-4 min-h-28" value={question} onChange={(event) => setQuestion(event.target.value)} aria-label="Question to look up" placeholder="Ask a support question…" />
          <div className="mt-2 flex flex-wrap items-center gap-1 text-xs text-muted" aria-label="Demo cases">
            <span className="mr-1">Try:</span>
            {demoQuestions.map((demo) => <Button key={demo.label} size="sm" variant="ghost" className="h-7 px-2" onClick={() => setQuestion(demo.text)}>{demo.label}</Button>)}
          </div>
          <Button className="mt-3" onClick={() => void lookup()} disabled={!question.trim() || Boolean(busy)}>
            {busy === 'lookup' ? <LoaderCircle className="animate-spin" /> : <Search />} Look up answer
          </Button>

          {result && <div className="mt-5 rounded-2xl border border-line bg-white/70 p-4" aria-live="polite">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={result.match_type === 'none' ? 'secondary' : 'default'}>{result.match_type === 'none' ? 'Cache miss' : `${result.match_type} hit`}</Badge>
              {result.match_type !== 'none' && <span className="mono text-sm text-muted">Similarity {(result.similarity * 100).toFixed(1)}%</span>}
              {result.source && <span className="text-xs text-muted">Source: {result.source}</span>}
            </div>
            {result.matched_question && <p className="mt-3 text-sm"><span className="font-semibold">Matched question:</span> {result.matched_question}</p>}
            {result.answer && <div className="mt-3 border-t border-line pt-3"><p className="eyebrow text-[10px]">Cached answer</p><p className="mt-1 leading-relaxed">{result.answer}</p></div>}
            {result.note && <p className="mt-3 text-xs text-muted">{result.note}</p>}
          </div>}
        </Card>

        <Card className="panel p-5 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2"><Sparkles className="size-5 text-warm" /><h3 className="text-xl font-semibold">Saved answers</h3><Badge variant="secondary">{entries.length}</Badge></div>
            <Button variant="outline" size="sm" onClick={() => void clearCache()} disabled={!entries.length || Boolean(busy)}><Trash2 /> Clear cache</Button>
          </div>
          {entries.length === 0 ? <div className="mt-5 rounded-xl border border-dashed border-line p-6 text-center text-sm text-muted">No cached answers yet. Seed the authored demo FAQs to try exact, paraphrase and miss cases.</div> :
            <ul className="mt-4 divide-y divide-line">
              {entries.map((entry) => <li key={entry.id} className="flex items-start justify-between gap-3 py-4 first:pt-0 last:pb-0">
                <div className="min-w-0"><p className="font-medium">{entry.question}</p><p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted">{entry.answer}</p><p className="mt-2 text-xs text-muted">{entry.language} · {entry.source}</p></div>
                <Button variant="ghost" size="icon" aria-label={`Delete ${entry.question}`} onClick={() => void removeEntry(entry.id)} disabled={Boolean(busy)}><Trash2 className="text-muted" /></Button>
              </li>)}
            </ul>}
        </Card>
      </div>
      <p className="text-xs text-muted">Semantic scores are similarity signals, not proof that two questions mean the same thing. Review the matched question before using a near-match answer.</p>
    </div>
  );
}
