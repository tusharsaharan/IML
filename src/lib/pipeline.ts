export interface ChatRequest {
  text: string;
  language: 'auto' | 'en' | 'hinglish' | 'hi';
  mode: 'demo' | 'live';
  compression: { enabled: boolean; method: 'heuristic' | 'crf'; budget: number; protected_phrases?: string[] };
  routing: { enabled: boolean; policy: 'economy' | 'balanced' | 'quality' };
  cache: { enabled: boolean; accept_semantic?: boolean };
  output?: { max_tokens: number; format_constraint: '3 bullets' | 'JSON only' | 'no preamble' | null };
  compare: false;
}

export interface ChatResult {
  request_id: number;
  mode: 'demo' | 'live';
  language: string;
  answer: string;
  answer_source: string;
  origin_source: string;
  model: string | null;
  provider_called: boolean;
  elapsed_ms: number;
  cache: { hit: boolean; candidate_hit: boolean; match_type: string; similarity?: number; matched_question?: string; note?: string; scope: string; stored: boolean };
  compression: { original_tokens: number; compressed_tokens: number; compressed: string; method: string; fallback_reason?: string } | null;
  routing: { selected_tier: string; selected_model_label: string; score: number; threshold: number; policy: string; note: string } | null;
  prediction: { predicted_output_tokens: number; note: string } | null;
  output: { max_tokens: number; format_constraint: string | null; demo_truncated: boolean; note: string };
  usage: { reference_original_tokens: number; reference_prompt_tokens: number; reference_sent_tokens: number; reference_output_tokens: number; input_tokens_saved: number; tokenizer_backend: string; provider: { prompt_tokens: number | null; completion_tokens: number | null; total_tokens: number | null } };
  cost: { usd: number | null; basis: string; note: string };
  trace: { stage: string; status: string; note: string }[];
}

export async function runPipeline(request: ChatRequest, scope: string): Promise<ChatResult> {
  const response = await fetch('/api/v1/chat', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Cache-Scope': scope },
    body: JSON.stringify(request), signal: AbortSignal.timeout(90000),
  });
  if (!response.ok) {
    let message = `Pipeline returned HTTP ${response.status}.`;
    try {
      const body = await response.json();
      if (typeof body.detail === 'string') message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((item: { msg: string }) => item.msg).join(' ');
    } catch { /* Preserve HTTP status for non-JSON errors. */ }
    throw new Error(message);
  }
  return response.json();
}
