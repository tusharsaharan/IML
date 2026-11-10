export interface TextSpan {
  start: number;
  end: number;
  text: string;
  reason?: string;
  kind?: string;
  preserved?: boolean;
  candidate_preserved?: boolean;
}

export interface PhraseCheck {
  text: string;
  source_occurrences: number;
  candidate_occurrences: number;
  output_occurrences: number;
  preserved_in_candidate: boolean;
  preserved_in_output: boolean;
}

export interface CompressionCandidate {
  compressed: string;
  method: string;
  compressed_tokens: number;
  removed_spans: TextSpan[];
  added_spans: TextSpan[];
  drop_records: { token: string; category: string; rule: string }[];
  protected_preserved: boolean;
  fallback_reason: string | null;
}

export interface CompressionResult {
  original: string;
  compressed: string;
  requested_method: string;
  method: string;
  budget: number;
  target_tokens: number;
  budget_met: boolean;
  budget_tunable: boolean;
  budget_note: string;
  original_tokens: number;
  compressed_tokens: number;
  saved_tokens: number;
  compression_ratio: number;
  tokenizer: string;
  removed_spans: TextSpan[];
  added_spans: TextSpan[];
  protected_spans: TextSpan[];
  protected_preserved: boolean;
  drop_records: { token: string; category: string; rule: string }[];
  protected_phrases: string[];
  phrase_checks: PhraseCheck[];
  protection_fallback: boolean;
  compression_candidate: CompressionCandidate | null;
  fallback_reason: string | null;
  note: string;
  elapsed_ms: number;
  evidence_kind: string;
  source_commit: string;
  source_url: string;
  limitations: string;
}

export interface Sample {
  id: string;
  label: string;
  language: string;
  text: string;
  source_url: string;
}

export interface ComparisonRow extends CompressionResult {
  sample_id: string;
  label: string;
  sample_source_url: string;
}

export interface EvidenceRow {
  model: string;
  target: number;
  n: number;
  original_accuracy: number;
  candidate_accuracy: number;
  bm25_accuracy: number;
  llmlingua_accuracy: number;
  delta_vs_bm25: number;
  ci95: [number, number];
  context_kept: number;
  full_prompt_kept: number;
  invalid: number;
}

export interface ResearchEvidence {
  kind: string;
  verification_scope: string;
  qa_records: number;
  qa_items: number;
  source_passages: number;
  stress_texts: number;
  stress_records: number;
  interpretation: string;
  candidate: string;
  rows: EvidenceRow[];
  results_markdown: string;
  results_url: string;
  release_url: string;
  limits: string[];
  provenance: { commit: string; files: { file: string; sha256: string; url: string }[] };
}
