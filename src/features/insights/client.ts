import type {
  CapDemoResponse,
  ClusterResponse,
  CostEstimateResponse,
  HistoryResponse,
  PredictLengthResponse,
  SummaryResponse,
  TokenizeResponse,
} from './types';

export async function insightsRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/insights/${path}`, {
    ...init,
    headers: {
      'content-type': 'application/json',
      ...init?.headers,
    },
    signal: init?.signal ?? AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    let detail = `Insights API error (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join(' ');
    } catch {
      // Keep HTTP status
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function fetchSummary(): Promise<SummaryResponse> {
  return insightsRequest<SummaryResponse>('summary');
}

export function fetchTokenize(text?: string, variants?: Record<string, string>): Promise<TokenizeResponse> {
  return insightsRequest<TokenizeResponse>('tokenize', {
    method: 'POST',
    body: JSON.stringify({ text: text || '', variants }),
  });
}

export function fetchCapDemo(): Promise<CapDemoResponse> {
  return insightsRequest<CapDemoResponse>('output-cap-demo');
}

export function fetchHistory(limit: number = 50): Promise<HistoryResponse> {
  return insightsRequest<HistoryResponse>(`history?limit=${limit}`);
}

export function fetchCostEstimate(payload: {
  text: string;
  estimated_output_tokens?: number;
  tier?: 'cheap' | 'premium';
  user_input_price_per_1k?: number;
  user_output_price_per_1k?: number;
  max_tokens_cap?: number;
  format_constraint?: string;
}): Promise<CostEstimateResponse> {
  return insightsRequest<CostEstimateResponse>('cost-estimate', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchClusters(): Promise<ClusterResponse> {
  return insightsRequest<ClusterResponse>('clusters');
}

export function fetchPredictLength(payload: {
  input_tokens: number;
  language: 'en' | 'hinglish' | 'hi';
  format_constraint?: string;
  max_tokens?: number;
}): Promise<PredictLengthResponse> {
  return insightsRequest<PredictLengthResponse>('predict-length', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

