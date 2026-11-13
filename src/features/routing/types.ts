/** Types for the real /api/v1/routing responses. Labels are authored fixtures. */

export type RoutingTier = 'cheap' | 'strong';
export type RoutingPolicy = 'economy' | 'balanced' | 'quality';
export type LanguageGroup = 'english' | 'hinglish' | 'mixed_script' | 'hindi' | 'unknown';

export interface RoutingFeatures {
  char_length: number;
  word_count: number;
  devanagari_ratio: number;
  latin_ratio: number;
  code_mix_ratio: number;
  roman_hindi_ratio: number;
  lang_english: number;
  lang_hinglish: number;
  lang_mixed_script: number;
  lang_hindi: number;
  difficulty_entity_density: number;
  difficulty_math_marker_count: number;
  has_digits: number;
  has_math_symbols: number;
  has_code_markers: number;
  has_email_or_amount: number;
  language_group: LanguageGroup;
  reference_token_count: number;
  tokenizer_backend: string;
  truncated: boolean;
  // Legacy starter keys, still returned alongside the extracted features.
  token_count: number;
  char_count: number;
}

export interface RoutingModelScores {
  logistic_regression: number;
  random_forest: number;
  mlp: number;
}

export interface RoutingScorer {
  requested: string;
  actual: string;
  proxy: boolean;
  reason: string;
}

export interface RoutingArtifact {
  path: string | null;
  generated_at: string | null;
  dataset_rows: number | null;
}

/** One feature's signed contribution to a logistic-regression logit. */
export interface RoutingLogregFeature {
  feature: string;
  value: number;
  contribution: number;
  direction: 'toward_stronger' | 'toward_economy';
}

/**
 * Per-request attribution for a logistic-regression decision. Only returned
 * when logistic regression is the primary model and its coefficient artifact
 * is available; never fabricated for another classifier.
 */
export interface RoutingLogregExplanation {
  method: 'logistic_regression_contribution';
  model: string;
  is_request_specific: true;
  bias: number;
  features: RoutingLogregFeature[];
  /** Sum of every contribution outside the returned top 5. */
  other_contribution: number;
  logit: number;
  probability: number;
  note: string;
}

/** One item in a per-request occlusion explanation. */
export interface RoutingOcclusionItem {
  feature: string;
  /** Numeric feature value, or the language-group string for `language_group`. */
  value: string | number;
  contribution: number;
  direction: 'toward_stronger' | 'toward_economy';
}

/**
 * Per-request one-feature-at-a-time occlusion against the training mean, for
 * whichever model is primary. `base_score` is the score with no occlusion.
 */
export interface RoutingOcclusionExplanation {
  method: 'occlusion_vs_training_mean';
  model: string;
  is_request_specific: true;
  base_score: number;
  items: RoutingOcclusionItem[];
  note: string;
}

/** Explicit "no attribution available" payload (fallback or missing means). */
export interface RoutingUnavailableExplanation {
  method: 'unavailable';
  model: null;
  is_request_specific: false;
  features: [];
  reason: string;
  note: string;
}

export type RoutingExplanationDetail =
  | RoutingLogregExplanation
  | RoutingOcclusionExplanation
  | RoutingUnavailableExplanation;

export interface RoutingPrediction {
  selected_tier: RoutingTier;
  selected_model_label: string;
  score: number;
  threshold: number;
  policy: RoutingPolicy;
  features: RoutingFeatures;
  model_scores: RoutingModelScores;
  explanation: string[];
  explanation_detail: RoutingExplanationDetail;
  note: string;
  scorer: RoutingScorer;
  artifact: RoutingArtifact;
  labels_are_authored: boolean;
  reference_token_count: number;
  tokenizer_backend: string;
  compressed_token_count?: number;
}

export interface ModelSupport {
  economy: number;
  stronger: number;
  total: number;
}

/** One trained classifier's held-out evaluation in routing_metrics.json. */
export interface ModelEvaluation {
  accuracy: number;
  precision: number;
  recall: number;
  f1: number;
  confusion_matrix: number[][];
  support: ModelSupport;
  cv_f1_mean: number;
  cv_f1_std: number;
  params: Record<string, unknown>;
  converged?: boolean;
  n_iter?: number;
}

export interface RoutingDatasetInfo {
  path: string;
  sha256: string;
  rows: number;
  train_rows: number;
  test_rows: number;
  class_counts: Record<string, number>;
  group_counts: Record<string, number>;
  label_source_note: string;
}

export interface RoutingPolicyThreshold {
  threshold: number;
  note: string;
}

/** The metrics artifact returned by GET /api/v1/routing/models. */
export interface RoutingModels {
  schema_version: number;
  generated_at: string;
  random_seed: number;
  library_versions: Record<string, string>;
  dataset: RoutingDatasetInfo;
  evaluation_method: Record<string, string>;
  feature_names: string[];
  models: Record<string, ModelEvaluation>;
  primary_model: string;
  threshold: { value: number; method: string; out_of_fold_f1: number };
  policies: Record<RoutingPolicy, RoutingPolicyThreshold>;
  per_group_accuracy: Record<string, { accuracy: number; support: number }>;
  notes: string[];
}
