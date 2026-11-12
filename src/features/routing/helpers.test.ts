import { describe, expect, it } from 'vitest';
import {
  buildPolicyComparison,
  fallbackNotice,
  featureRows,
  formatScore,
  modelAgreement,
  modelScoreRows,
  primaryModelName,
  tierLabel,
} from './helpers';
import { ROUTING_PRESETS } from './presets';
import type { RoutingFeatures, RoutingModelScores, RoutingScorer } from './types';

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

describe('model score and feature rows', () => {
  it('strips the trained prefix but leaves fallback names alone', () => {
    expect(primaryModelName('trained_random_forest')).toBe('random_forest');
    expect(primaryModelName('starter_heuristic')).toBe('starter_heuristic');
  });

  it('marks exactly the primary classifier and labels all three', () => {
    const rows = modelScoreRows(
      { logistic_regression: 0.767, random_forest: 0.464, mlp: 0.378 },
      'random_forest',
    );
    expect(rows.map((row) => row.label)).toEqual([
      'Logistic regression',
      'Random forest',
      'MLP (neural network)',
    ]);
    expect(rows.filter((row) => row.isPrimary).map((row) => row.key)).toEqual(['random_forest']);
  });

  it('labels every returned feature and explains counts and flags', () => {
    const features: RoutingFeatures = {
      char_length: 33,
      word_count: 5,
      devanagari_ratio: 0,
      latin_ratio: 1,
      code_mix_ratio: 0,
      roman_hindi_ratio: 0,
      lang_english: 1,
      lang_hinglish: 0,
      lang_mixed_script: 0,
      lang_hindi: 0,
      difficulty_entity_density: 0.2,
      difficulty_math_marker_count: 0,
      has_digits: 1,
      has_math_symbols: 0,
      has_code_markers: 0,
      has_email_or_amount: 0,
      language_group: 'english',
      reference_token_count: 10,
      tokenizer_backend: 'tiktoken_cl100k_base',
      truncated: false,
      token_count: 10,
      char_count: 33,
    };
    const rows = featureRows(features);
    expect(rows).toHaveLength(Object.keys(features).length);
    expect(rows.find((row) => row.key === 'word_count')?.label).toBe('Whitespace words');
    expect(rows.find((row) => row.key === 'reference_token_count')?.label).toContain(
      'not provider billing',
    );
    expect(rows.find((row) => row.key === 'truncated')).toEqual({
      key: 'truncated',
      label: 'Truncated at 20,000 characters',
      value: 'No',
    });
    expect(rows.every((row) => row.label.trim().length > 0)).toBe(true);
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
