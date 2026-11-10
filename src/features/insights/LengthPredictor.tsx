import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { PredictLengthResponse } from './types';
import { fetchPredictLength } from './client';

export function LengthPredictor() {
  const [inputTokens, setInputTokens] = useState(15);
  const [language, setLanguage] = useState<'en' | 'hinglish' | 'hi'>('en');
  const [formatConstraint, setFormatConstraint] = useState<string>('3 bullets');
  const [maxTokens, setMaxTokens] = useState<number | undefined>(40);

  const [res, setRes] = useState<PredictLengthResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function runPrediction() {
    setLoading(true);
    setError('');
    fetchPredictLength({
      input_tokens: inputTokens,
      language,
      format_constraint: formatConstraint !== 'none' ? formatConstraint : undefined,
      max_tokens: maxTokens,
    })
      .then(setRes)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    runPrediction();
  }, [language, formatConstraint, maxTokens]);

  return (
    <Card className="panel p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <span className="eyebrow">ML Angle</span>
          <Badge variant="outline" className="text-xs">
            Supervised Regression
          </Badge>
        </div>
        <h3 className="mt-1 text-xl font-semibold text-ink">Output Length Predictor (Ridge Regression)</h3>
        <p className="text-sm text-muted">
          Linear model estimating response token length based on prompt length, language script, format restrictions, and hard max_token bounds.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Controls */}
        <div className="lg:col-span-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-ink">Input Prompt Tokens</label>
              <Input
                type="number"
                min={1}
                max={500}
                value={inputTokens}
                onChange={(e) => setInputTokens(Number(e.target.value))}
                className="mt-1 text-xs"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-ink">Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value as 'en' | 'hinglish' | 'hi')}
                aria-label="Language"
                className="mt-1 flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-xs shadow-sm"
              >
                <option value="en">English (en)</option>
                <option value="hinglish">Hinglish</option>
                <option value="hi">Hindi (hi)</option>
              </select>
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
                <option value="none">None</option>
                <option value="3 bullets">3 bullets</option>
                <option value="JSON only">JSON only</option>
                <option value="no preamble">No preamble / brief</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-ink">Hard Token Limit (max_tokens)</label>
              <Input
                type="number"
                min={5}
                max={500}
                value={maxTokens ?? ''}
                placeholder="No max limit"
                onChange={(e) => setMaxTokens(e.target.value ? Number(e.target.value) : undefined)}
                className="mt-1 text-xs"
              />
            </div>
          </div>

          <Button size="sm" onClick={runPrediction} disabled={loading}>
            {loading ? 'Predicting...' : 'Predict Output Tokens'}
          </Button>

          {error && <p className="text-xs text-red-600">{error}</p>}
        </div>

        {/* Prediction & Coefficients */}
        <div className="lg:col-span-6 rounded-xl border border-line bg-white/70 p-5 space-y-4">
          {res ? (
            <>
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div>
                  <h4 className="text-sm font-semibold text-ink">Model Output</h4>
                  <span className="text-xs text-muted">{res.model_type}</span>
                </div>
                <div className="text-right">
                  <span className="text-2xl font-bold text-ink">{res.predicted_output_tokens}</span>
                  <span className="block text-[10px] text-muted">est. output tokens</span>
                </div>
              </div>

              {res.capped_by_max_tokens && (
                <div className="rounded bg-amber-50 border border-amber-200 p-2 text-xs text-amber-800">
                  Raw regression prediction was {res.raw_linear_prediction} tokens, capped down to max_tokens = {maxTokens}.
                </div>
              )}

              {/* Evaluation Metrics */}
              <div className="grid grid-cols-3 gap-2 text-center text-xs">
                <div className="rounded bg-canvas p-2 border border-line">
                  <span className="block text-muted text-[10px]">R² Score</span>
                  <span className="font-semibold text-ink">{res.r2_score}</span>
                </div>
                <div className="rounded bg-canvas p-2 border border-line">
                  <span className="block text-muted text-[10px]">Mean Abs Error</span>
                  <span className="font-semibold text-ink">{res.mae_tokens} tokens</span>
                </div>
                <div className="rounded bg-canvas p-2 border border-line">
                  <span className="block text-muted text-[10px]">Training Samples</span>
                  <span className="font-semibold text-ink">{res.training_samples}</span>
                </div>
              </div>

              {/* Coefficients */}
              <div>
                <span className="text-[11px] font-semibold text-muted uppercase tracking-wider">
                  Model Feature Weights (Coefficients)
                </span>
                <div className="mt-1 grid grid-cols-2 gap-1.5 text-[11px] font-mono">
                  {Object.entries(res.coefficients).map(([feat, coef]) => (
                    <div key={feat} className="flex justify-between rounded bg-canvas px-2 py-1 border border-line">
                      <span className="truncate text-muted">{feat}:</span>
                      <span className={coef < 0 ? 'text-emerald-700 font-semibold' : 'text-ink font-semibold'}>
                        {coef > 0 ? `+${coef}` : coef}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <p className="text-[10px] text-muted">{res.note}</p>
            </>
          ) : (
            <div className="flex h-full items-center justify-center text-xs text-muted">
              Loading prediction...
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}

