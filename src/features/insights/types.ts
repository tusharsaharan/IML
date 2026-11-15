export interface TokenizeItem {
  label: string;
  text: string;
  tokens: number;
  chars: number;
  tokens_per_char: number;
  code_mix_ratio: number;
}

export interface TokenizeResponse {
  backend: string;
  items: TokenizeItem[];
  note: string;
}

export interface SummaryResponse {
  total_requests: number;
  recorded_in_store: number;
  fixture_requests: number;
  languages: Record<string, number>;
  average_code_mix: number;
  avg_tokens_saved_by_capping: number;
  tokenizer_backend: string;
  note: string;
}

export interface CapStrategy {
  strategy_id: string;
  label: string;
  format_constraint: string;
  max_tokens: number | null;
  prompt_sent: string;
  response: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  tokens_saved: number;
  percent_saved: number;
  cost_est_usd: number;
  cost_saved_usd: number;
}

export interface CapSample {
  id: string;
  topic: string;
  language: string;
  base_prompt: string;
  strategies: CapStrategy[];
}

export interface CapDemoResponse {
  kind: string;
  samples: CapSample[];
  supported_strategies: string[];
  note: string;
}

export interface HistoryItem {
  id: string;
  created_at?: string;
  text: string;
  language: string;
  route?: string;
  model?: string;
  cache_hit?: boolean;
  compressed?: boolean;
  input_tokens: number;
  output_tokens: number;
  max_tokens_set?: number | null;
  format_constraint?: string | null;
  cost_usd?: number;
  source?: string;
  notes?: string;
}

export interface HistoryResponse {
  items: HistoryItem[];
  total: number;
  note: string;
}

export interface CostEstimateResponse {
  input_tokens: number;
  estimated_output_tokens: number;
  unconstrained_output_tokens: number;
  output_tokens_saved: number;
  cost_usd: number;
  unconstrained_cost_usd: number;
  cost_saved_usd: number;
  rates_source: string;
  in_rate_per_1k_usd: number;
  out_rate_per_1k_usd: number;
  tokenizer_backend: string;
  note: string;
}

export interface ClusterPoint {
  id: string;
  text: string;
  language: string;
  route: string;
  cache_hit: boolean;
  compressed: boolean;
  input_tokens: number;
  output_tokens: number;
  format_constraint: string | null;
  pc1: number;
  pc2: number;
  cluster: number;
  cluster_label: string;
}

export interface ClusterSummary {
  cluster_id: number;
  label: string;
  count: number;
  avg_input_tokens: number;
  avg_output_tokens: number;
  cache_hits: number;
  description: string;
}

export interface ClusterResponse {
  points: ClusterPoint[];
  clusters: ClusterSummary[];
  explained_variance_ratio: number[];
  total_explained_variance: number;
  note: string;
}

export interface PredictLengthResponse {
  predicted_output_tokens: number;
  raw_linear_prediction: number;
  capped_by_max_tokens: boolean;
  model_type: string;
  training_samples: number;
  r2_score: number;
  mae_tokens: number;
  coefficients: Record<string, number>;
  intercept: number;
  note: string;
}

