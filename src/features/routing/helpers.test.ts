import { describe, expect, it } from 'vitest';
import {
  buildPolicyComparison,
  fallbackNotice,
  formatScore,
  modelAgreement,
  tierLabel,
} from './helpers';
import { ROUTING_PRESETS } from './presets';
import type { RoutingModelScores, RoutingScorer } from './types';

function scorer(overrides: Partial<RoutingScorer> = {}): RoutingScorer {
  return {
    requested: 'trained_random_forest',
    actual: 'trained_random_forest',
    proxy: false,
    reason: 'Primary model per the metrics artifact.',
    ...overrides,
  };
}

describe('routing labels and scores', () => {
  it('names both tiers without provider claims', () => {
    expect(tierLabel('cheap')).toBe('Economy model');
    expect(tierLabel('strong')).toBe('Stronger model');
  });

  it('formats scores to three decimals and never prints NaN', () => {
    expect(formatScore(0.5)).toBe('0.500');
    expect(formatScore(1)).toBe('1.000');
    expect(formatScore(0)).toBe('0.000');
    expect(formatScore(Number.NaN)).toBe('—');
  });
});

describe('fallbackNotice', () => {
  it('stays silent for a normal trained response', () => {
    expect(fallbackNotice(null)).toBeNull();
    expect(fallbackNotice(undefined)).toBeNull();
    expect(fallbackNotice(scorer())).toBeNull();
  });

  it('shows a notice whenever the proxy flag is set', () => {
    const notice = fallbackNotice(scorer({ proxy: true, actual: 'starter_heuristic' }));
    expect(notice).toContain('Fallback in use');
    expect(notice).toContain('not trained classifier outputs');
  });

  it('shows a notice for the starter heuristic even if proxy is false', () => {
    expect(fallbackNotice(scorer({ proxy: false, actual: 'starter_heuristic' }))).toContain(
      'Fallback in use',
    );
  });

  it('includes the backend reason when present', () => {
    const notice = fallbackNotice(
      scorer({ proxy: true, actual: 'starter_heuristic', reason: 'Artifacts are missing.' }),
    );
    expect(notice).toContain('Artifacts are missing.');
  });
});

describe('modelAgreement', () => {
  const scores: RoutingModelScores = {
    logistic_regression: 0.767,
    random_forest: 0.464,
    mlp: 0.378,
  };

  it('splits models at the threshold and reports disagreement', () => {
    expect(modelAgreement(scores, 0.5296)).toEqual({
      above: ['logistic_regression'],
      below: ['random_forest', 'mlp'],
      agree: false,
    });
  });

  it('counts a score equal to the threshold as above, like the backend', () => {
    expect(modelAgreement(scores, 0.464)).toEqual({
      above: ['logistic_regression', 'random_forest'],
      below: ['mlp'],
      agree: false,
    });
  });

  it('agrees when every model falls on the same side', () => {
    expect(modelAgreement({ logistic_regression: 0.1, random_forest: 0.2, mlp: 0.3 }, 0.5)).toEqual({
      above: [],
      below: ['logistic_regression', 'random_forest', 'mlp'],
      agree: true,
    });
    expect(modelAgreement({ logistic_regression: 0.9, random_forest: 0.8, mlp: 0.7 }, 0.5)).toEqual({
      above: ['logistic_regression', 'random_forest', 'mlp'],
      below: [],
      agree: true,
    });
  });
});

describe('buildPolicyComparison', () => {
  const result = (tier: 'cheap' | 'strong', score: number, threshold: number) => ({
    selected_tier: tier,
    score,
    threshold,
  });

  it('always orders rows economy, balanced, quality', () => {
    const rows = buildPolicyComparison({
      quality: result('strong', 0.4638, 0.3796),
      economy: result('cheap', 0.4638, 0.6796),
      balanced: result('cheap', 0.4638, 0.5296),
    });

    expect(rows.map((row) => row.policy)).toEqual(['economy', 'balanced', 'quality']);
    expect(rows.map((row) => row.tier)).toEqual(['cheap', 'cheap', 'strong']);
    expect(rows.map((row) => row.label)).toEqual(['Economy model', 'Economy model', 'Stronger model']);
    expect(rows.map((row) => row.threshold)).toEqual([0.6796, 0.5296, 0.3796]);
    expect(rows.every((row) => row.score === 0.4638)).toBe(true);
  });

  it('skips policies that have no result yet', () => {
    expect(buildPolicyComparison({ balanced: result('strong', 0.91, 0.5296) }).map((row) => row.policy))
      .toEqual(['balanced']);
    expect(buildPolicyComparison({})).toEqual([]);
  });
});

describe('routing presets', () => {
  it('has exactly five presets with unique ids and real text', () => {
    expect(ROUTING_PRESETS).toHaveLength(5);
    expect(new Set(ROUTING_PRESETS.map((preset) => preset.id)).size).toBe(5);
    expect(ROUTING_PRESETS.map((preset) => preset.id)).toEqual([
      'economy-short',
      'long-hinglish',
      'policy-flip',
      'mixed-script',
      'known-weak',
    ]);
    expect(ROUTING_PRESETS.every((preset) => preset.text.trim().length > 0)).toBe(true);
  });

  it('labels every preset as an authored example without claiming an outcome', () => {
    for (const preset of ROUTING_PRESETS) {
      expect(preset.label).toMatch(/authored example/i);
      expect(preset.label).not.toMatch(/\b(cheap|strong|economy|balanced|quality|tier)\b/i);
    }
    expect(ROUTING_PRESETS.find((preset) => preset.id === 'known-weak')?.label).toBe(
      'Authored example — a known weak case',
    );
  });
});
