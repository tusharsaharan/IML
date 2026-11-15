import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import type { CostEstimateResponse } from './types';
import { fetchCostEstimate } from './client';

export function CostEstimatorCard() {
  const [text, setText] = useState('How do I renew my library book online before the due date?');
  const [outputTokens, setOutputTokens] = useState(100);
  const [tier, setTier] = useState<'cheap' | 'premium'>('cheap');
  const [formatConstraint, setFormatConstraint] = useState<string>('3 bullets');
  const [maxTokensCap, setMaxTokensCap] = useState<number | undefined>(50);
  const [useCustomPrices, setUseCustomPrices] = useState(false);
  const [customInPrice, setCustomInPrice] = useState(0.0001);
  const [customOutPrice, setCustomOutPrice] = useState(0.0004);

  const [result, setResult] = useState<CostEstimateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function calculate() {
    setLoading(true);
    setError('');
    fetchCostEstimate({
      text,
      estimated_output_tokens: outputTokens,
      tier,
      format_constraint: formatConstraint !== 'none' ? formatConstraint : undefined,
      max_tokens_cap: maxTokensCap || undefined,
      user_input_price_per_1k: useCustomPrices ? customInPrice : undefined,
      user_output_price_per_1k: useCustomPrices ? customOutPrice : undefined,
    })
      .then(setResult)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    calculate();
  }, [tier, formatConstraint, maxTokensCap, useCustomPrices]);

  const inrRate = 83.5;

  return (
    <Card className="panel p-6 space-y-6">
      <div>
        <span className="eyebrow">Financial Impact</span>
        <h3 className="mt-1 text-xl font-semibold text-ink">Cost Estimator & Capping Savings</h3>
        <p className="text-sm text-muted">
          Transparently separates reference token counts, standard catalog model rates, and user-supplied pricing assumptions.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Input Parameters */}
        <div className="lg:col-span-7 space-y-4">
          <div>
            <label className="text-xs font-semibold text-ink">Input Query Text</label>
            <Textarea
              rows={2}
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="mt-1 text-xs"
              placeholder="Enter sample query..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-ink">Unconstrained Output (tokens)</label>
              <Input
                type="number"
                min={10}
                max={4000}
                value={outputTokens}
                onChange={(e) => setOutputTokens(Number(e.target.value))}
                className="mt-1 text-xs"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-ink">Hard Cap (max_tokens limit)</label>
              <Input
                type="number"
                min={10}
                max={4000}
                value={maxTokensCap ?? ''}
                placeholder="Optional max_tokens"
                onChange={(e) => setMaxTokensCap(e.target.value ? Number(e.target.value) : undefined)}
                className="mt-1 text-xs"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-ink">Format Constraint</label>
              <select
                value={formatConstraint}
                onChange={(e) => setFormatConstraint(e.target.value)}
                aria-label="Format Constraint"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm"
              >
                <option value="none">None (Default wordy response)</option>
                <option value="3 bullets">3 bullets (~50% token reduction)</option>
                <option value="JSON only">JSON only (~55% token reduction)</option>
                <option value="no preamble">No preamble / 1 line (~65% reduction)</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-ink">Model Catalog Tier</label>
              <div className="mt-1 flex gap-2">
                <Button
                  size="sm"
                  type="button"
                  variant={tier === 'cheap' ? 'default' : 'outline'}
                  onClick={() => setTier('cheap')}
                  className="w-1/2 text-xs"
                >
                  Economy Tier
                </Button>
                <Button
                  size="sm"
                  type="button"
                  variant={tier === 'premium' ? 'default' : 'outline'}
                  onClick={() => setTier('premium')}
                  className="w-1/2 text-xs"
                >
                  Quality Tier
                </Button>
              </div>
            </div>
          </div>

          {/* User-supplied pricing override toggle */}
          <div className="rounded-lg border border-line bg-canvas p-3 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-ink">Override with Custom Pricing Assumptions</span>
              <Button
                size="sm"
                variant="ghost"
                className="h-6 text-[11px]"
                onClick={() => setUseCustomPrices(!useCustomPrices)}
              >
                {useCustomPrices ? 'Use Catalog Rates' : 'Edit Custom Rates'}
              </Button>
            </div>
            {useCustomPrices && (
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="text-[11px] text-muted">Input USD / 1K tokens</label>
                  <Input
                    type="number"
                    step="0.00001"
                    value={customInPrice}
                    onChange={(e) => setCustomInPrice(Number(e.target.value))}
                    className="mt-1 h-8 text-xs"
                  />
                </div>
                <div>
                  <label className="text-[11px] text-muted">Output USD / 1K tokens</label>
                  <Input
                    type="number"
                    step="0.00001"
                    value={customOutPrice}
                    onChange={(e) => setCustomOutPrice(Number(e.target.value))}
                    className="mt-1 h-8 text-xs"
                  />
                </div>
              </div>
            )}
          </div>

          <Button onClick={calculate} disabled={loading} size="sm">
            {loading ? 'Estimating...' : 'Recalculate Estimate'}
          </Button>
          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>

        {/* Results Card */}
        <div className="lg:col-span-5 flex flex-col justify-between rounded-xl border border-line bg-white/70 p-5 space-y-4">
          {result ? (
            <>
              <div>
                <div className="flex items-center justify-between border-b border-line pb-3">
                  <div>
                    <h4 className="text-base font-semibold text-ink">Estimated Cost</h4>
                    <span className="text-xs text-muted">Source: {result.rates_source}</span>
                  </div>
                  <Badge variant="secondary" className="text-xs">
                    {result.tokenizer_backend}
                  </Badge>
                </div>

                <div className="mt-4 space-y-3">
                  <div className="flex items-baseline justify-between">
                    <span className="text-xs text-muted">Cost per request:</span>
                    <span className="text-xl font-bold text-ink">
                      ${result.cost_usd.toFixed(6)}
                    </span>
                  </div>

                  <div className="flex items-baseline justify-between text-xs">
                    <span className="text-muted">Unconstrained cost:</span>
                    <span className="line-through text-muted">
                      ${result.unconstrained_cost_usd.toFixed(6)}
                    </span>
                  </div>

                  <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold text-emerald-800">Savings per 10k requests:</span>
                      <span className="font-bold text-emerald-700 text-sm">
                        ${(result.cost_saved_usd * 10000).toFixed(2)} (₹
                        {(result.cost_saved_usd * 10000 * inrRate).toFixed(1)})
                      </span>
                    </div>
                    <div className="mt-1 flex justify-between text-[11px] text-emerald-700">
                      <span>Tokens saved per call:</span>
                      <span>{result.output_tokens_saved} tokens</span>
                    </div>
                  </div>

                  <div className="pt-2 text-[11px] text-muted space-y-1">
                    <div className="flex justify-between">
                      <span>Input tokens:</span>
                      <span className="font-medium text-ink">{result.input_tokens}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Effective output tokens:</span>
                      <span className="font-medium text-ink">{result.estimated_output_tokens}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Input rate / 1k:</span>
                      <span>${result.in_rate_per_1k_usd.toFixed(6)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Output rate / 1k:</span>
                      <span>${result.out_rate_per_1k_usd.toFixed(6)}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="rounded bg-canvas p-2.5 text-[10px] text-muted border border-line">
                {result.note}
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">
              Loading cost projection...
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

