import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import type { CapSample, CapStrategy } from './types';
import { fetchCapDemo } from './client';

export function OutputCapCard() {
  const [samples, setSamples] = useState<CapSample[]>([]);
  const [selectedSampleIndex, setSelectedSampleIndex] = useState(0);
  const [activeStrategy, setActiveStrategy] = useState<CapStrategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCapDemo()
      .then((data) => {
        setSamples(data.samples);
        if (data.samples.length > 0) {
          setActiveStrategy(data.samples[0].strategies[1] || data.samples[0].strategies[0]);
        }
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const currentSample = samples[selectedSampleIndex];

  if (loading) {
    return (
      <Card className="panel p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-1/3 rounded bg-line" />
          <div className="h-24 rounded bg-line/50" />
        </div>
      </Card>
    );
  }

  if (error || !currentSample) {
    return (
      <Card className="panel p-6 border-red-300">
        <p className="text-red-700">Failed to load Output Capping demonstration: {error}</p>
      </Card>
    );
  }

  const chartData = currentSample.strategies.map((s) => ({
    name: s.label.replace('Format constraint: ', '').replace('Hard Token Cap ', ''),
    'Output Tokens': s.output_tokens,
    'Tokens Saved': s.tokens_saved,
    percent: s.percent_saved,
  }));

  return (
    <Card className="panel p-6 space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="eyebrow">Task Focus</span>
            <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 border-emerald-300 text-xs">
              Point 2: Cap the Output
            </Badge>
          </div>
          <h3 className="mt-1 text-xl font-semibold text-ink">Output Length & Format Capping Analyzer</h3>
          <p className="text-sm text-muted">
            Ask for a specific format (<code className="rounded bg-canvas px-1 py-0.5">3 bullets</code>,{' '}
            <code className="rounded bg-canvas px-1 py-0.5">JSON only</code>,{' '}
            <code className="rounded bg-canvas px-1 py-0.5">no preamble</code>) and set a{' '}
            <code className="rounded bg-canvas px-1 py-0.5">max_tokens</code> limit to eliminate runaway generation costs.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {samples.map((s, idx) => (
            <Button
              key={s.id}
              size="sm"
              variant={idx === selectedSampleIndex ? 'default' : 'outline'}
              onClick={() => {
                setSelectedSampleIndex(idx);
                setActiveStrategy(s.strategies[1] || s.strategies[0]);
              }}
              className="text-xs"
            >
              {s.topic}
            </Button>
          ))}
        </div>
      </div>

      {/* Hero comparison cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {currentSample.strategies.map((strat) => {
          const isSelected = activeStrategy?.strategy_id === strat.strategy_id;
          const isUnconstrained = strat.strategy_id === 'unconstrained';
          return (
            <div
              key={strat.strategy_id}
              onClick={() => setActiveStrategy(strat)}
              className={`cursor-pointer rounded-xl border p-4 transition-all ${
                isSelected
                  ? 'border-accent bg-accent/5 ring-2 ring-accent/30 shadow-md'
                  : 'border-line bg-canvas hover:border-line-strong'
              }`}
            >
              <div className="flex items-center justify-between text-xs">
                <span className="font-semibold text-ink">{strat.label}</span>
                {strat.max_tokens ? (
                  <Badge variant="outline" className="text-[10px]">
                    max: {strat.max_tokens}
                  </Badge>
                ) : (
                  <Badge variant="secondary" className="text-[10px]">
                    no limit
                  </Badge>
                )}
              </div>

              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-2xl font-bold text-ink">{strat.output_tokens}</span>
                <span className="text-xs text-muted">completion tokens</span>
              </div>

              <div className="mt-2 text-xs">
                {isUnconstrained ? (
                  <span className="text-muted">Baseline cost: ${(strat.cost_est_usd * 1000).toFixed(4)}/1k reqs</span>
                ) : (
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-emerald-700">↓ {strat.percent_saved.toFixed(1)}% saved</span>
                    <span className="text-muted">{(strat.tokens_saved)} tok saved</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Chart & Active Strategy Inspector */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7 rounded-xl border border-line bg-white/50 p-4">
          <h4 className="text-sm font-semibold text-ink mb-1">Token Reduction per Capping Strategy</h4>
          <p className="text-xs text-muted mb-4">
            Notice how format constraints like &apos;3 bullets&apos; cut tokens by ~60% without needing hard truncate errors.
          </p>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} angle={-15} textAnchor="end" interval={0} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val: any, name: any) => [
                    `${val ?? 0} tokens`,
                    name ?? '',
                  ]}
                  contentStyle={{ borderRadius: '8px', fontSize: '12px' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }} />
                <Bar dataKey="Output Tokens" fill="#f97316" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Tokens Saved" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {activeStrategy && (
          <div className="lg:col-span-5 flex flex-col justify-between rounded-xl border border-line bg-white/70 p-4 text-xs">
            <div>
              <div className="flex items-center justify-between border-b border-line pb-2 mb-3">
                <span className="font-semibold text-sm text-ink">{activeStrategy.label}</span>
                <span className="text-emerald-700 font-medium">
                  {activeStrategy.percent_saved > 0 ? `-${activeStrategy.percent_saved}% tokens` : 'Baseline'}
                </span>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="text-[11px] font-semibold text-muted uppercase tracking-wider">
                    Prompt Sent with Constraints
                  </label>
                  <p className="mt-1 rounded bg-canvas p-2 font-mono text-[11px] text-ink border border-line">
                    {activeStrategy.prompt_sent}
                  </p>
                </div>

                <div>
                  <label className="text-[11px] font-semibold text-muted uppercase tracking-wider">
                    Response Preview
                  </label>
                  <div className="mt-1 max-h-36 overflow-y-auto rounded bg-canvas p-2 text-[11px] text-ink leading-relaxed border border-line whitespace-pre-line">
                    {activeStrategy.response}
                  </div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-line grid grid-cols-3 gap-2 text-center">
              <div className="rounded bg-canvas/60 p-2 border border-line">
                <span className="block text-muted text-[10px]">Input Toks</span>
                <span className="font-semibold text-ink">{activeStrategy.input_tokens}</span>
              </div>
              <div className="rounded bg-canvas/60 p-2 border border-line">
                <span className="block text-muted text-[10px]">Output Toks</span>
                <span className="font-semibold text-ink">{activeStrategy.output_tokens}</span>
              </div>
              <div className="rounded bg-canvas/60 p-2 border border-line">
                <span className="block text-muted text-[10px]">Cost / call</span>
                <span className="font-semibold text-ink">
                  ${(activeStrategy.cost_est_usd).toFixed(6)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-lg bg-canvas p-3 border border-line text-xs text-muted flex items-start gap-2">
        <span className="font-semibold text-ink">Course takeaway:</span>
        <span>
          Output tokens cost 4× input tokens on standard providers. Setting length ceilings (<code className="bg-white px-1">max_tokens</code>)
          and specifying tight output contracts (<code className="bg-white px-1">&quot;3 bullets&quot;</code>, <code className="bg-white px-1">&quot;JSON only&quot;</code>)
          is the most effective lever to control token consumption.
        </span>
      </div>
    </Card>
  );
}
