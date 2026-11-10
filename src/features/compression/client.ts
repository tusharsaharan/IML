import type { CompressionResult, TextSpan } from './types';

export async function compressionRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/compression/${path}`, {
    ...init,
    signal: init?.signal ?? AbortSignal.timeout(30000),
  });
  if (!response.ok) {
    let detail = `Compression API returned ${response.status}.`;
    try {
      const body: { detail?: unknown } = await response.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join(' ');
    } catch { /* Keep the HTTP status if the backend did not return JSON. */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export interface HighlightPart {
  text: string;
  kind: 'plain' | 'removed' | 'protected';
}

export function phraseSelection(value: string, text: string): { phrases: string[]; error: string } {
  // Preserve literal whitespace and Unicode; blank lines are not selections.
  const lines = value.split(/\r?\n/).filter((line) => line.trim());
  const phrases = [...new Set(lines)];
  if (lines.length > 20) return { phrases, error: 'Choose at most 20 phrases, one per line.' };
  if (phrases.some((phrase) => Array.from(phrase).length > 200)) {
    return { phrases, error: 'Each phrase must be at most 200 characters.' };
  }
  const missing = phrases.find((phrase) => !text.includes(phrase));
  return { phrases, error: missing === undefined ? '' : `Phrase not found exactly in the source prompt: ${JSON.stringify(missing)}.` };
}

export function resultIsStale(result: CompressionResult | null, text: string, method: string,
  budget: number, phrases: string[]): boolean {
  return result !== null && (result.original !== text || result.requested_method !== method || result.budget !== budget
    || JSON.stringify(result.protected_phrases ?? []) !== JSON.stringify(phrases));
}

export function acceptPhraseResult(result: CompressionResult, phrases: string[]): CompressionResult {
  if (phrases.length && (JSON.stringify(result.protected_phrases) !== JSON.stringify(phrases)
    || !Array.isArray(result.phrase_checks) || result.phrase_checks.length !== phrases.length)) {
    throw new Error('The running backend does not support these phrase checks. Restart npm run dev and analyze again.');
  }
  return result;
}

export function highlightParts(text: string, removed: TextSpan[], protectedSpans: TextSpan[]): HighlightPart[] {
  // Python offsets count Unicode code points; JavaScript slice counts UTF-16.
  const chars = Array.from(text);
  const boundaries = [...new Set([0, chars.length, ...[...removed, ...protectedSpans]
    .flatMap((span) => [span.start, span.end])])].sort((a, b) => a - b);
  return boundaries.slice(0, -1).map((start, index) => {
    const end = boundaries[index + 1];
    const isRemoved = removed.some((span) => start >= span.start && end <= span.end);
    const isProtected = protectedSpans.some((span) => start >= span.start && end <= span.end);
    return { text: chars.slice(start, end).join(''), kind: isRemoved ? 'removed' : isProtected ? 'protected' : 'plain' };
  });
}

export function chatRequest(result: CompressionResult) {
  // Export the documented request only. No shared chat endpoint is available yet.
  return {
    text: result.compressed, language: 'auto', mode: 'demo',
    compression: { enabled: false, method: result.requested_method, budget: result.budget },
    routing: { enabled: true, policy: 'balanced' }, cache: { enabled: true }, compare: false,
  };
}

export function downloadJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
