import { describe, expect, it } from 'vitest';
import {
  buildPolicyComparison,
  explanationMethodLabel,
  explanationRows,
  explanationSummary,
  fallbackNotice,
  featureRows,
  formatScore,
  formatSigned,
  modelAgreement,
  modelScoreRows,
  primaryModelName,
  tierLabel,
} from './helpers';
import { ROUTING_PRESETS } from './presets';
import type {
  RoutingFeatures,
  RoutingLogregExplanation,
  RoutingModelScores,
  RoutingOcclusionExplanation,
  RoutingScorer,
  RoutingUnavailableExplanation,
} from './types';

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

describe('explanation panel helpers', () => {
  const logreg: RoutingLogregExplanation = {
    method: 'logistic_regression_contribution',
    model: 'logistic_regression',
    is_request_specific: true,
    bias: -0.292,
    features: [
      {
        feature: 'has_digits',
        value: 1,
        contribution: 0.482,
        direction: 'toward_stronger',
      },
      {
        feature: 'roman_hindi_ratio',
        value: 0.25,
        contribution: -0.311,
        direction: 'toward_economy',
      },
      {
        feature: 'difficulty_math_marker_count',
        value: 2,
        contribution: 0.207,
        direction: 'toward_stronger',
      },
    ],
    other_contribution: -0.176,
    logit: -0.09,
    probability: 0.478,
    note: 'Explains the logistic-regression score; labels are authored fixtures.',
  };

  const occlusion: RoutingOcclusionExplanation = {
    method: 'occlusion_vs_training_mean',
    model: 'random_forest',
    is_request_specific: true,
    base_score: 0.412,
    items: [
      {
        feature: 'has_digits',
        value: 1,
        contribution: 0.182,
        direction: 'toward_stronger',
      },
      {
        feature: 'language_group',
        value: 'hinglish',
        contribution: -0.131,
        direction: 'toward_economy',
      },
      {
        feature: 'difficulty_math_marker_count',
        value: 2,
        contribution: 0.077,
        direction: 'toward_stronger',
      },
    ],
    note: 'Approximate: one-feature-at-a-time comparison against the training average. Labels are authored fixtures.',
  };

  const unavailable: RoutingUnavailableExplanation = {
    method: 'unavailable',
    model: null,
    is_request_specific: false,
    features: [],
    reason: 'Trained routing artifacts are unavailable.',
    note: 'No per-request feature attribution is available.',
  };

  it('labels the method without implying more than it does', () => {
    expect(explanationMethodLabel(logreg)).toContain('Per-request');
    expect(explanationMethodLabel(occlusion)).toContain('occlusion');
    expect(explanationMethodLabel(unavailable)).toContain('No explanation');
  });

  it('signs contributions and states direction in text, not colour', () => {
    expect(formatSigned(0.482)).toBe('+0.482');
    expect(formatSigned(-0.311)).toBe('-0.311');
    expect(formatSigned(0)).toBe('+0.000');

    const rows = explanationRows(logreg);
    expect(rows.map((row) => row.amount)).toEqual(['+0.482', '-0.311', '+0.207']);
    expect(rows.map((row) => row.directionLabel)).toEqual([
      'Pushes toward stronger model',
      'Pushes toward economy',
      'Pushes toward stronger model',
    ]);
    expect(rows[0].value).toBe('1');
    expect(rows[0].label).toBe('Contains digits (1 = yes)');
  });

  it('builds one sentence naming the strongest push each way', () => {
    const summary = explanationSummary(logreg);
    expect(summary).toContain('0.478');
    expect(summary).toContain('toward the stronger model from');
    expect(summary).toContain('Contains digits (1 = yes) and Math markers');
    expect(summary).toContain('toward economy from Roman-Hindi token share');
    expect(summary.endsWith('.')).toBe(true);
    expect(summary).not.toContain('. ');
  });

  it('omits the economy clause when nothing pushes that way', () => {
    const summary = explanationSummary({
      ...logreg,
      features: logreg.features.filter((row) => row.direction === 'toward_stronger'),
    });
    expect(summary).not.toContain('toward economy');
    expect(summary).toContain('Contains digits');
  });

  it('renders occlusion items with values, signed contributions and text direction', () => {
    const rows = explanationRows(occlusion);
    expect(rows.map((row) => row.key)).toEqual([
      'has_digits',
      'language_group',
      'difficulty_math_marker_count',
    ]);
    expect(rows.map((row) => row.amount)).toEqual(['+0.182', '-0.131', '+0.077']);
    expect(rows.map((row) => row.directionLabel)).toEqual([
      'Pushes toward stronger model',
      'Pushes toward economy',
      'Pushes toward stronger model',
    ]);
    expect(rows[1].label).toBe('Language group');
    expect(rows[1].value).toBe('hinglish');
  });

  it('describes occlusion against the training average, not global importance', () => {
    const summary = explanationSummary(occlusion);
    expect(summary).toContain('0.412');
    expect(summary).toContain('training average');
    expect(summary).toContain('toward the stronger model from');
    expect(summary).toContain('toward economy from Language group');
    expect(summary.endsWith('.')).toBe(true);
    expect(summary).not.toContain('. ');
  });

  it('repeats the backend reason when no explanation is available', () => {
    expect(explanationRows(unavailable)).toEqual([]);
    expect(explanationSummary(unavailable)).toContain('Trained routing artifacts are unavailable.');
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
