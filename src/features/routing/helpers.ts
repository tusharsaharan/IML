import type { RoutingModelScores, RoutingPolicy, RoutingScorer, RoutingTier } from './types';

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
