import { useEffect, useState } from 'react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { fetchRoutingModels, predictRouting } from './client';
import {
  buildPolicyComparison,
  fallbackNotice,
  featureRows,
  formatScore,
  modelAgreement,
  modelScoreRows,
  MODEL_LABELS,
  POLICY_ORDER,
  primaryModelName,
  tierLabel,
} from './helpers';
import { ROUTING_PRESETS } from './presets';
import type { RoutingModels, RoutingPolicy, RoutingPrediction } from './types';
import './routing.css';

const actionClass = 'min-h-11 rounded-lg bg-accent px-4 text-panel hover:bg-accent-strong focus-visible:ring-0';
const secondaryClass = 'min-h-11 rounded-lg border border-line-strong bg-panel px-4 text-ink hover:bg-canvas focus-visible:ring-0';
const message = (error: unknown) => (error instanceof Error ? error.message : 'The request could not finish.');
const clampPercent = (value: number) => Math.max(0, Math.min(100, value * 100));

function tierBadgeClass(tier: 'cheap' | 'strong'): string {
  return `routing-tier ${tier === 'strong' ? 'routing-tier-strong' : 'routing-tier-cheap'}`;
}

export function RoutingPage() {
  const [text, setText] = useState('');
  const [policy, setPolicy] = useState<RoutingPolicy>('balanced');
  const [result, setResult] = useState<RoutingPrediction | null>(null);
  const [comparisons, setComparisons] = useState<Partial<Record<RoutingPolicy, RoutingPrediction>>>({});
  const [models, setModels] = useState<RoutingModels | null>(null);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState('');
  const [busy, setBusy] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState('');
  const [comparisonError, setComparisonError] = useState('');

  function loadModels(signal?: AbortSignal) {
    setModelsLoading(true);
    setModelsError('');
    fetchRoutingModels(signal)
      .then(setModels)
      .catch((reason) => {
        if (!signal?.aborted) setModelsError(message(reason));
      })
      .finally(() => {
        if (!signal?.aborted) setModelsLoading(false);
      });
  }

  useEffect(() => {
    const controller = new AbortController();
    loadModels(controller.signal);
    return () => controller.abort();
  }, []);

  function updateText(value: string) {
    setText(value);
    setResult(null);
    setComparisons({});
    setError('');
    setComparisonError('');
  }

  function updatePolicy(value: RoutingPolicy) {
    setPolicy(value);
    setResult(null);
    setError('');
  }

  async function route() {
    const prompt = text.trim();
    if (!prompt || busy) return;
    setBusy(true);
    setError('');
    try {
      setResult(await predictRouting(prompt, policy));
    } catch (reason) {
      setError(`${message(reason)} Check that the backend is running with npm run dev.`);
    } finally {
      setBusy(false);
    }
  }

  async function comparePolicies() {
    const prompt = text.trim();
    if (!prompt || comparing) return;
    setComparing(true);
    setComparisonError('');
    try {
      const [economy, balanced, quality] = await Promise.all([
        predictRouting(prompt, 'economy'),
        predictRouting(prompt, 'balanced'),
        predictRouting(prompt, 'quality'),
      ]);
      setComparisons({ economy, balanced, quality });
    } catch (reason) {
      setComparisonError(`${message(reason)} Check that the backend is running with npm run dev.`);
    } finally {
      setComparing(false);
    }
  }

  const fallback = result ? fallbackNotice(result.scorer) : null;
  const primary = models?.primary_model ?? (result ? primaryModelName(result.scorer.actual) : '');
  const scoreRows = result ? modelScoreRows(result.model_scores, primary) : [];
  const agreement = result ? modelAgreement(result.model_scores, result.threshold) : null;
  const policyRows = buildPolicyComparison(comparisons);
  const primaryEvaluation = models ? models.models[models.primary_model] : undefined;
  const primaryLabel = models ? (MODEL_LABELS[models.primary_model] ?? models.primary_model) : '';

  return (
    <div className="routing-studio space-y-8">
      <header>
        <p className="text-sm font-medium text-accent">Rakesh's workstream</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight">Smart Router</h2>
        <p className="mt-3 max-w-[75ch] leading-relaxed text-muted">
          Route a prompt between an economy and a stronger model with locally trained CPU classifiers.
          Scores are stronger-tier probabilities for authored fixture labels, not measured model quality,
          savings or provider billing. No answer model is called.
        </p>
      </header>

      <div className="routing-workspace grid lg:grid-cols-2">
        <section className="min-w-0 p-5 sm:p-6" aria-labelledby="routing-input-heading">
          <h3 id="routing-input-heading" className="text-xl font-semibold">Prompt and policy</h3>
          <p className="mt-2 text-sm text-muted">
            Presets are authored examples, not evaluation results. The router decides the tier; a preset
            label never claims an outcome.
          </p>
          <p className="mt-3 text-sm font-medium">Authored examples</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {ROUTING_PRESETS.map((preset) => (
              <Button
                key={preset.id}
                className={`${secondaryClass} routing-preset`}
                disabled={busy}
                onClick={() => updateText(preset.text)}
              >
                {preset.label}
              </Button>
            ))}
          </div>

          <label htmlFor="routing-prompt" className="mt-5 block text-sm font-medium">
            Prompt to route
          </label>
          <Textarea
            id="routing-prompt"
            className="mt-2 min-h-48 border-line-strong bg-panel text-base focus-visible:ring-0"
            maxLength={20000}
            value={text}
            disabled={busy}
            dir="auto"
            onChange={(event) => updateText(event.target.value)}
            aria-describedby="routing-prompt-help"
          />
          <p id="routing-prompt-help" className="mt-2 text-xs text-muted">
            {text.length.toLocaleString()} / 20,000 characters. Text is scored on the first 20,000
            characters on the local CPU backend. Devanagari and mixed-script text is supported.
          </p>

          <div className="mt-5">
            <label htmlFor="routing-policy" className="block text-sm font-medium">
              Policy
            </label>
            <select
              id="routing-policy"
              className="routing-select mt-2 w-full"
              value={policy}
              disabled={busy}
              onChange={(event) => updatePolicy(event.target.value as RoutingPolicy)}
              aria-describedby="routing-policy-help"
            >
              <option value="economy">Economy — a higher bar for the stronger model</option>
              <option value="balanced">Balanced — the artifact's F1 threshold</option>
              <option value="quality">Quality — an easier bar for the stronger model</option>
            </select>
            <p id="routing-policy-help" className="mt-2 text-xs leading-relaxed text-muted">
              {models ? `Current ${policy} threshold: ${formatScore(models.policies[policy].threshold)}. ` : ''}
              A score at or above the threshold routes to the stronger model; a lower score stays on
              the economy model. Thresholds are authored policy offsets.
            </p>
          </div>

          <Button
            className={`${actionClass} mt-5`}
            disabled={busy || !text.trim()}
            onClick={route}
          >
            {busy ? 'Scoring on the local backend…' : 'Route prompt'}
          </Button>
          {error && (
            <p className="mt-4 text-sm" role="alert">
              {error}
            </p>
          )}
        </section>

        <section
          className="min-w-0 border-t border-line p-5 sm:p-6 lg:border-l lg:border-t-0"
          aria-labelledby="routing-result-heading"
          aria-busy={busy}
        >
          <h3 id="routing-result-heading" className="text-xl font-semibold">Routing decision</h3>
          <div role="status" aria-live="polite" className="mt-2 text-sm text-muted">
            {busy
              ? 'Scoring on the local CPU backend.'
              : result
                ? `Policy ${result.policy}; labels are authored fixtures.`
                : 'Enter a prompt or choose an authored example, then route it.'}
          </div>

          {busy && (
            <div className="mt-4 space-y-2" aria-hidden="true">
              <Skeleton className="h-5 w-1/3" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-full" />
            </div>
          )}

          {result && !busy && (
            <>
              {fallback && (
                <p className="routing-fallback mt-4 text-sm" role="alert">
                  {fallback}
                </p>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Badge className={tierBadgeClass(result.selected_tier)}>
                  {tierLabel(result.selected_tier)}
                </Badge>
                <span className="text-sm text-muted">
                  Configured model:{' '}
                  <span className="font-medium text-ink">{result.selected_model_label}</span>
                </span>
              </div>

              <dl className="mt-4 grid gap-4 sm:grid-cols-2">
                <div>
                  <dt className="text-sm text-muted">Score vs threshold</dt>
                  <dd className="mono mt-1 font-semibold">
                    {formatScore(result.score)} / {formatScore(result.threshold)}
                  </dd>
                </div>
                <div>
                  <dt className="text-sm text-muted">Policy</dt>
                  <dd className="mt-1 font-semibold capitalize">{result.policy}</dd>
                </div>
              </dl>

              <div className="routing-bar mt-4" aria-hidden="true">
                <div
                  className="routing-bar-fill"
                  style={{ width: `${clampPercent(result.score)}%` }}
                />
                <span
                  className="routing-bar-threshold"
                  style={{ left: `${clampPercent(result.threshold)}%` }}
                />
              </div>
              <p className="mt-3 text-sm leading-relaxed">
                Score <strong>{formatScore(result.score)}</strong> is{' '}
                {result.score >= result.threshold ? 'at or above' : 'below'} the{' '}
                <strong>{result.policy}</strong> threshold{' '}
                <strong>{formatScore(result.threshold)}</strong>, so the{' '}
                <strong>{tierLabel(result.selected_tier)}</strong> is selected.
              </p>
              <p className="mt-1 text-xs text-muted">
                The bar repeats the same values with a marker at the threshold; the text above carries
                the result, not colour alone.
              </p>

              <p className="mt-3 text-xs leading-relaxed text-muted">
                Scorer: {result.scorer.actual} (requested {result.scorer.requested}). Proxy scores:{' '}
                {result.scorer.proxy ? 'yes' : 'no'}. {result.scorer.reason}
              </p>
              <p className="mt-2 text-xs leading-relaxed text-muted">
                Artifact: {result.artifact.path ?? 'unavailable'} · generated{' '}
                {result.artifact.generated_at ?? 'unknown'} ·{' '}
                {result.artifact.dataset_rows ?? 'unknown'} authored rows. Authored labels:{' '}
                {result.labels_are_authored ? 'yes' : 'no'}. Reference tokens:{' '}
                {result.reference_token_count} ({result.tokenizer_backend}), not provider billing.
              </p>
              <p className="mt-3 text-sm leading-relaxed text-muted">{result.note}</p>
            </>
          )}
        </section>
      </div>

      <section aria-labelledby="routing-model-scores-heading">
        <h3 id="routing-model-scores-heading" className="text-2xl font-semibold">
          Model scores — probability of the stronger tier
        </h3>
        {result ? (
          <>
            <p className="mt-2 max-w-[80ch] text-sm text-muted">
              {fallback
                ? 'Fallback heuristic scores are illustrative; no trained model decided this route.'
                : 'Only the primary model decides the route; the other scores are shown for comparison.'}
            </p>
            <ul className="mt-4 grid gap-4 sm:grid-cols-3">
              {scoreRows.map((row) => (
                <li key={row.key} className="rounded-xl border border-line bg-panel p-4">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-medium">
                      {row.label}
                      {row.isPrimary && <Badge className="routing-primary ml-2">Primary</Badge>}
                    </span>
                    <span className="mono text-sm">{formatScore(row.score)}</span>
                  </div>
                  <div className="routing-bar mt-2" aria-hidden="true">
                    <div
                      className="routing-bar-fill"
                      style={{ width: `${clampPercent(row.score)}%` }}
                    />
                    <span
                      className="routing-bar-threshold"
                      style={{ left: `${clampPercent(result.threshold)}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
            {agreement && !agreement.agree && !fallback && (
              <p className="mt-3 text-sm leading-relaxed" role="status">
                The classifiers disagree at this policy threshold:{' '}
                {agreement.above.join(', ')} above; {agreement.below.join(', ')} below. Only{' '}
                {MODEL_LABELS[primary] ?? primary} decides the route; the other scores are for
                comparison.
              </p>
            )}
            {agreement && agreement.agree && !fallback && (
              <p className="mt-3 text-sm text-muted">
                All three classifiers fall on the same side of this policy threshold.
              </p>
            )}
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">Model scores appear after a route.</p>
        )}
      </section>

      <section aria-labelledby="routing-compare-heading">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 id="routing-compare-heading" className="text-2xl font-semibold">
              Compare all policies
            </h3>
            <p className="mt-2 max-w-[75ch] text-sm text-muted">
              One predict call per policy for the same prompt. The tier can change because each policy
              uses a different authored threshold; the models themselves do not retrain.
            </p>
          </div>
          <Button
            className={secondaryClass}
            disabled={comparing || !text.trim()}
            onClick={comparePolicies}
          >
            {comparing ? 'Comparing three policies…' : 'Compare all policies'}
          </Button>
        </div>
        {comparisonError && (
          <p className="mt-3 text-sm" role="alert">
            {comparisonError}
          </p>
        )}
        <div role="status" className="mt-3 text-sm text-muted">
          {comparing
            ? 'Scoring the same prompt under economy, balanced and quality.'
            : policyRows.length
              ? 'Same prompt, three policy thresholds. Only the primary model decides each route.'
              : 'Enter a prompt to compare the three policies.'}
        </div>
        {policyRows.length > 0 && (
          <ul className="mt-4 grid gap-3 sm:grid-cols-3">
            {policyRows.map((row) => (
              <li key={row.policy} className="rounded-xl border border-line bg-panel p-4">
                <p className="text-sm font-medium capitalize">{row.policy}</p>
                <p className="mt-2">
                  <Badge className={tierBadgeClass(row.tier)}>{row.label}</Badge>
                </p>
                <p className="mono mt-2 text-sm">
                  {formatScore(row.score)} / {formatScore(row.threshold)}
                </p>
                <p className="mt-1 text-xs text-muted">Score vs threshold</p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section aria-labelledby="routing-features-heading">
        <h3 id="routing-features-heading" className="text-2xl font-semibold">
          Feature values
        </h3>
        <p className="mt-2 max-w-[80ch] text-sm text-muted">
          Every field returned for this prompt. word_count counts whitespace words;
          reference_token_count is a reference count, not provider billing. Numeric features feed the
          classifiers; display fields are audit only.
        </p>
        {result ? (
          <div
            className="routing-table-wrap mt-3"
            tabIndex={0}
            role="region"
            aria-label="Feature values, scroll horizontally on small screens"
          >
            <table className="routing-table">
              <caption>Extracted features for the routed prompt.</caption>
              <thead>
                <tr>
                  <th scope="col">Feature</th>
                  <th scope="col">Value</th>
                </tr>
              </thead>
              <tbody>
                {featureRows(result.features).map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{row.label}</th>
                    <td className="mono" dir="auto">
                      {row.value}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-3 text-sm text-muted">Feature values appear after a route.</p>
        )}
      </section>

      <section aria-labelledby="routing-models-heading">
        <h3 id="routing-models-heading" className="text-2xl font-semibold">
          Model comparison
        </h3>
        <p className="mt-2 max-w-[80ch] text-sm font-medium">
          Labels are authored fixtures, not measured model correctness.
        </p>

        {modelsLoading && (
          <div className="mt-4 space-y-2" role="status" aria-live="polite">
            <span className="sr-only">Loading the model metrics artifact.</span>
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        )}

        {modelsError && (
          <div className="mt-3">
            <p className="text-sm" role="alert">
              Model comparison unavailable: {modelsError}. The routing decision above still works
              without it.
            </p>
            <Button className={`${secondaryClass} mt-3`} onClick={() => loadModels()}>
              Retry model metrics
            </Button>
          </div>
        )}

        {models && (
          <>
            <p className="mt-3 text-sm leading-relaxed text-muted">
              Dataset: {models.dataset.rows} authored rows; held-out test set:{' '}
              {models.dataset.test_rows} rows. Primary model: <strong>{primaryLabel}</strong>. Only the
              primary model decides the route; the other scores are shown for comparison.
            </p>

            <div
              className="routing-table-wrap mt-4"
              tabIndex={0}
              role="region"
              aria-label="Classifier comparison, scroll horizontally on small screens"
            >
              <table className="routing-table">
                <caption>
                  Five-fold cross-validation F1 on the training split and held-out test metrics.
                </caption>
                <thead>
                  <tr>
                    <th scope="col">Model</th>
                    <th scope="col">CV F1 (mean ± std)</th>
                    <th scope="col">Accuracy</th>
                    <th scope="col">Precision</th>
                    <th scope="col">Recall</th>
                    <th scope="col">F1</th>
                    <th scope="col">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(models.models).map(([name, entry]) => (
                    <tr key={name}>
                      <th scope="row">
                        {MODEL_LABELS[name] ?? name}
                        {name === models.primary_model && (
                          <Badge className="routing-primary ml-2">Primary</Badge>
                        )}
                      </th>
                      <td className="mono">
                        {formatScore(entry.cv_f1_mean)} ± {formatScore(entry.cv_f1_std)}
                      </td>
                      <td className="mono">{formatScore(entry.accuracy)}</td>
                      <td className="mono">{formatScore(entry.precision)}</td>
                      <td className="mono">{formatScore(entry.recall)}</td>
                      <td className="mono">{formatScore(entry.f1)}</td>
                      <td>
                        {entry.converged === false
                          ? `Did not converge (n_iter=${entry.n_iter ?? 'unknown'})`
                          : entry.converged === true
                            ? 'Converged'
                            : 'Not reported'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {primaryEvaluation && (
              <div className="mt-5">
                <h4 className="font-semibold">Confusion matrix — {primaryLabel}</h4>
                <div
                  className="routing-table-wrap mt-2"
                  tabIndex={0}
                  role="region"
                  aria-label="Confusion matrix for the primary model"
                >
                  <table className="routing-table">
                    <caption>
                      Held-out test rows. Rows are true labels; columns are predicted labels, economy
                      then stronger.
                    </caption>
                    <thead>
                      <tr>
                        <th scope="col">True label</th>
                        <th scope="col">Predicted economy</th>
                        <th scope="col">Predicted stronger</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <th scope="row">Economy</th>
                        <td className="mono">{primaryEvaluation.confusion_matrix[0]?.[0] ?? '—'}</td>
                        <td className="mono">{primaryEvaluation.confusion_matrix[0]?.[1] ?? '—'}</td>
                      </tr>
                      <tr>
                        <th scope="row">Stronger</th>
                        <td className="mono">{primaryEvaluation.confusion_matrix[1]?.[0] ?? '—'}</td>
                        <td className="mono">{primaryEvaluation.confusion_matrix[1]?.[1] ?? '—'}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="mt-5">
              <h4 className="font-semibold">Per-group test accuracy</h4>
              <div
                className="routing-table-wrap mt-2"
                tabIndex={0}
                role="region"
                aria-label="Per-group accuracy with support sizes"
              >
                <table className="routing-table">
                  <caption>Held-out rows only.</caption>
                  <thead>
                    <tr>
                      <th scope="col">Language group</th>
                      <th scope="col">Accuracy</th>
                      <th scope="col">n</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(models.per_group_accuracy).map(([group, entry]) => (
                      <tr key={group}>
                        <th scope="row">{group.replaceAll('_', ' ')}</th>
                        <td className="mono">{(entry.accuracy * 100).toFixed(1)}%</td>
                        <td className="mono">{entry.support}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted">
                Several groups have only 10 to 20 held-out rows (see n), so these values are
                indicative only, not guarantees.
              </p>
            </div>

            <div className="mt-5">
              <h4 className="font-semibold">Policy thresholds</h4>
              <div
                className="routing-table-wrap mt-2"
                tabIndex={0}
                role="region"
                aria-label="Policy thresholds"
              >
                <table className="routing-table">
                  <caption>score &gt;= threshold routes to the stronger model.</caption>
                  <thead>
                    <tr>
                      <th scope="col">Policy</th>
                      <th scope="col">Threshold</th>
                      <th scope="col">Artifact note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {POLICY_ORDER.map((name) => (
                      <tr key={name}>
                        <th scope="row" className="capitalize">
                          {name}
                        </th>
                        <td className="mono">{formatScore(models.policies[name].threshold)}</td>
                        <td>{models.policies[name].note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted">
                Policy offsets are authored choices, not learned or certified values.
              </p>
            </div>

            <details className="mt-5">
              <summary className="cursor-pointer font-medium">
                Evaluation method, seed and artifact notes
              </summary>
              <ul className="mt-3 space-y-2 text-sm">
                {Object.entries(models.evaluation_method).map(([key, value]) => (
                  <li key={key}>
                    <strong className="capitalize">{key.replaceAll('_', ' ')}</strong>: {value}
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-sm text-muted">
                Random seed {models.random_seed} · generated {models.generated_at} · schema v
                {models.schema_version}.
              </p>
              <ul className="mt-3 space-y-2 text-sm">
                {models.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </details>
          </>
        )}
      </section>
    </div>
  );
}
