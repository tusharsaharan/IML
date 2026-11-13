import type {
  RoutingExplanationDetail,
  RoutingFeatures,
  RoutingModelScores,
  RoutingPolicy,
  RoutingScorer,
  RoutingTier,
} from './types';

export const POLICY_ORDER: RoutingPolicy[] = ['economy', 'balanced', 'quality'];

export function tierLabel(tier: RoutingTier): string {
  return tier === 'strong' ? 'Stronger model' : 'Economy model';
}

export function formatScore(value: number): string {
  return Number.isFinite(value) ? value.toFixed(3) : '—';
}

/**
 * True when the backend used the labelled starter heuristic instead of a
 * trained classifier. Returns a visible notice, or null for a normal response.
 */
export function fallbackNotice(scorer: RoutingScorer | null | undefined): string | null {
  if (!scorer) return null;
  if (!scorer.proxy && scorer.actual !== 'starter_heuristic') return null;
  const reason = scorer.reason?.trim();
  const base = 'Fallback in use — these scores are illustrative, not trained classifier outputs.';
  return reason ? `${base} ${reason}` : base;
}

export interface ModelAgreement {
  above: string[];
  below: string[];
  agree: boolean;
}

/**
 * Splits model scores at the policy threshold. A score equal to the threshold
 * counts as above, matching the backend's `score >= threshold` rule.
 */
export function modelAgreement(
  model_scores: RoutingModelScores,
  threshold: number,
): ModelAgreement {
  const entries = Object.entries(model_scores);
  const above = entries.filter(([, score]) => score >= threshold).map(([name]) => name);
  const below = entries.filter(([, score]) => score < threshold).map(([name]) => name);
  return { above, below, agree: above.length === 0 || below.length === 0 };
}

export const MODEL_LABELS: Record<string, string> = {
  logistic_regression: 'Logistic regression',
  random_forest: 'Random forest',
  mlp: 'MLP (neural network)',
};

/** `trained_random_forest` -> `random_forest`; other values pass through. */
export function primaryModelName(actual: string): string {
  const prefix = 'trained_';
  return actual.startsWith(prefix) ? actual.slice(prefix.length) : actual;
}

export interface ModelScoreRow {
  key: string;
  label: string;
  score: number;
  isPrimary: boolean;
}

export function modelScoreRows(
  model_scores: RoutingModelScores,
  primary: string,
): ModelScoreRow[] {
  return Object.entries(model_scores).map(([key, score]) => ({
    key,
    label: MODEL_LABELS[key] ?? key.replaceAll('_', ' '),
    score,
    isPrimary: key === primary,
  }));
}

export const FEATURE_LABELS: Record<string, string> = {
  char_length: 'Characters',
  word_count: 'Whitespace words',
  devanagari_ratio: 'Devanagari share of letters',
  latin_ratio: 'Latin share of letters',
  code_mix_ratio: 'Code-mixed token share',
  roman_hindi_ratio: 'Roman-Hindi token share',
  lang_english: 'English flag (1 = yes)',
  lang_hinglish: 'Hinglish flag (1 = yes)',
  lang_mixed_script: 'Mixed-script flag (1 = yes)',
  lang_hindi: 'Hindi flag (1 = yes)',
  difficulty_entity_density: 'Entity density (difficulty)',
  difficulty_math_marker_count: 'Math markers',
  has_digits: 'Contains digits (1 = yes)',
  has_math_symbols: 'Contains math symbols (1 = yes)',
  has_code_markers: 'Contains code markers (1 = yes)',
  has_email_or_amount: 'Contains email or amount (1 = yes)',
  language_group: 'Language group',
  reference_token_count: 'Reference token count, not provider billing',
  tokenizer_backend: 'Tokenizer backend',
  truncated: 'Truncated at 20,000 characters',
  token_count: 'Legacy token_count (same as reference count)',
  char_count: 'Legacy char_count (same as characters)',
};

export interface FeatureRow {
  key: string;
  label: string;
  value: string;
}

export function formatFeatureValue(value: string | number | boolean): string {
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return String(value);
}

/** Every feature the backend returned, in its response order. */
export function featureRows(features: RoutingFeatures): FeatureRow[] {
  return Object.entries(features).map(([key, value]) => ({
    key,
    label: FEATURE_LABELS[key] ?? key.replaceAll('_', ' '),
    value: formatFeatureValue(value),
  }));
}

export const EXPLANATION_METHOD_LABELS = {
  logistic_regression_contribution: 'Per-request logistic-regression contribution',
  occlusion_vs_training_mean: 'Per-request occlusion against the training average',
  unavailable: 'No explanation available',
} as const;

export function explanationMethodLabel(detail: RoutingExplanationDetail): string {
  return EXPLANATION_METHOD_LABELS[detail.method];
}

export function featureLabel(key: string): string {
  return FEATURE_LABELS[key] ?? key.replaceAll('_', ' ');
}

/** `+0.482`, `-0.111`; a signed number so "toward stronger" is visible as text. */
export function formatSigned(value: number): string {
  if (!Number.isFinite(value)) return '—';
  return `${value >= 0 ? '+' : ''}${value.toFixed(3)}`;
}

export type ExplanationDirection = 'toward_stronger' | 'toward_economy';

export interface ExplanationRow {
  key: string;
  label: string;
  /** The request value for this row; `language_group` uses the group string. */
  value: string;
  direction: ExplanationDirection;
  /** Plain-text direction, so colour is never the only signal. */
  directionLabel: string;
  /** Signed contribution, already formatted. */
  amount: string;
  /** 0..1 magnitude relative to the largest row, for a decorative bar. */
  share: number;
}

function joinNames(names: string[]): string {
  if (names.length <= 1) return names.join('');
  return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

function pushLabels(
  rows: Array<{ feature: string; direction: ExplanationDirection }>,
  direction: ExplanationDirection,
): string[] {
  return rows
    .filter((row) => row.direction === direction)
    .slice(0, 2)
    .map((row) => featureLabel(row.feature));
}

function pushesClause(stronger: string[], economy: string[]): string {
  return [
    stronger.length ? `toward the stronger model from ${joinNames(stronger)}` : '',
    economy.length ? `toward economy from ${joinNames(economy)}` : '',
  ].filter(Boolean).join(', and ');
}

export function explanationRows(detail: RoutingExplanationDetail): ExplanationRow[] {
  if (detail.method === 'unavailable') return [];
  const rows = detail.method === 'occlusion_vs_training_mean' ? detail.items : detail.features;
  const max = rows.reduce(
    (top, row) => Math.max(top, Math.abs(row.contribution)),
    0,
  );
  return rows.map((row) => ({
    key: row.feature,
    label: featureLabel(row.feature),
    value: formatFeatureValue(row.value),
    direction: row.direction,
    directionLabel:
      row.direction === 'toward_stronger'
        ? 'Pushes toward stronger model'
        : 'Pushes toward economy',
    amount: formatSigned(row.contribution),
    share: max > 0 ? Math.abs(row.contribution) / max : 0,
  }));
}

/**
 * One data-driven sentence. Both per-request methods name the strongest push
 * each way; occlusion also states its base score. Unavailable repeats the
 * backend reason instead of inventing one.
 */
export function explanationSummary(detail: RoutingExplanationDetail): string {
  if (detail.method === 'unavailable') {
    return `No route explanation is available: ${detail.reason}`;
  }
  const stronger = pushLabels(
    detail.method === 'occlusion_vs_training_mean' ? detail.items : detail.features,
    'toward_stronger',
  );
  const economy = pushLabels(
    detail.method === 'occlusion_vs_training_mean' ? detail.items : detail.features,
    'toward_economy',
  );
  const clause = pushesClause(stronger, economy);
  if (detail.method === 'occlusion_vs_training_mean') {
    const base = detail.base_score.toFixed(3);
    if (!clause) {
      return `Compared with the training average (base stronger-tier score ${base}), no top item moved this route materially.`;
    }
    return `Compared with the training average (base stronger-tier score ${base}), the strongest pushes ${clause}.`;
  }
  const score = detail.probability.toFixed(3);
  if (!clause) {
    return `Logistic-regression stronger-tier score ${score}; no top feature moved it materially.`;
  }
  return `Logistic-regression stronger-tier score ${score}, with the strongest pushes ${clause}.`;
}

export interface PolicyResultLike {
  selected_tier: RoutingTier;
  score: number;
  threshold: number;
}

export interface PolicyComparisonRow {
  policy: RoutingPolicy;
  tier: RoutingTier;
  label: string;
  score: number;
  threshold: number;
}

/** One row per requested policy, always in economy / balanced / quality order. */
export function buildPolicyComparison(
  results: Partial<Record<RoutingPolicy, PolicyResultLike>>,
): PolicyComparisonRow[] {
  return POLICY_ORDER.flatMap((policy) => {
    const result = results[policy];
    if (!result) return [];
    return [{
      policy,
      tier: result.selected_tier,
      label: tierLabel(result.selected_tier),
      score: result.score,
      threshold: result.threshold,
    }];
  });
}
