import { afterEach, describe, expect, it, vi } from 'vitest';
import { acceptPhraseResult, chatRequest, compressionRequest, highlightParts, phraseSelection, resultIsStale } from './client';
import type { CompressionResult } from './types';

afterEach(() => vi.unstubAllGlobals());

describe('compression audit highlighting', () => {
  it('reconstructs original text and keeps removed/protected labels distinct', () => {
    const text = 'yaar user@example.com';
    const parts = highlightParts(text, [{ start: 0, end: 5, text: 'yaar ' }], [{ start: 5, end: 21, text: 'user@example.com' }]);
    expect(parts.map((part) => part.text).join('')).toBe(text);
    expect(parts.map((part) => part.kind)).toEqual(['removed', 'protected']);
  });

  it('maps Python Unicode offsets correctly after emoji and Hindi text', () => {
    const text = '🙂 मेरा mail user@example.com';
    const start = Array.from('🙂 मेरा mail ').length;
    const parts = highlightParts(text, [], [{ start, end: start + 16, text: 'user@example.com' }]);
    expect(parts.find((part) => part.kind === 'protected')?.text).toBe('user@example.com');
    expect(parts.map((part) => part.text).join('')).toBe(text);
  });

  it('shows removal even when a tracked protected span was lost', () => {
    expect(highlightParts('not', [{ start: 0, end: 3, text: 'not' }], [{ start: 0, end: 3, text: 'not', preserved: false }])[0].kind).toBe('removed');
  });
});

describe('optional Studio literal check', () => {
  const result = { original: 'yaar wifi', compressed: 'yaar wifi', requested_method: 'crf', budget: 0.6,
    protected_phrases: ['yaar'], protection_fallback: true,
    compression_candidate: { compressed: 'wifi', method: 'crf' } } as CompressionResult;

  it('preserves literal spaces, Unicode, order, and deduplicates without normalizing', () => {
    expect(phraseSelection(' wifi \r\nमेरा\n\n wifi ', '🙂 मेरा wifi है')).toEqual({ phrases: [' wifi ', 'मेरा'], error: '' });
    expect(phraseSelection('\n  \n', 'wifi')).toEqual({ phrases: [], error: '' });
  });

  it('requires exact case and whitespace, without Unicode normalization', () => {
    expect(phraseSelection('Wifi', 'wifi').error).toContain('not found exactly');
    expect(phraseSelection(' wifi ', 'wifi').error).toContain('not found exactly');
    expect(phraseSelection('é', 'e\u0301').error).toContain('not found exactly');
  });

  it('validates phrase count and Unicode code-point length', () => {
    expect(phraseSelection(Array(21).fill('wifi').join('\n'), 'wifi').error).toContain('at most 20');
    expect(phraseSelection('🙂'.repeat(200), '🙂'.repeat(200)).error).toBe('');
    expect(phraseSelection('🙂'.repeat(201), '🙂'.repeat(201)).error).toContain('200 characters');
  });

  it('marks additions, removals, and edits to selected phrases stale', () => {
    expect(resultIsStale(result, 'yaar wifi', 'crf', 0.6, ['yaar'])).toBe(false);
    for (const phrases of [[], ['wifi'], ['yaar', 'wifi']]) {
      expect(resultIsStale(result, 'yaar wifi', 'crf', 0.6, phrases)).toBe(true);
    }
    expect(resultIsStale(result, 'yaar wifi!', 'crf', 0.6, ['yaar'])).toBe(true);
    expect(resultIsStale(result, 'yaar wifi', 'heuristic', 0.6, ['yaar'])).toBe(true);
    expect(resultIsStale(result, 'yaar wifi', 'crf', 1, ['yaar'])).toBe(true);
    expect(resultIsStale(null, 'yaar wifi', 'crf', 0.6, ['yaar'])).toBe(false);
  });

  it('exports the retained original, never the rejected candidate or new chat fields', () => {
    const request = chatRequest(result);
    expect(request.text).toBe(result.original);
    expect(request.text).not.toBe(result.compression_candidate?.compressed);
    expect(request.compression.enabled).toBe(false);
    expect(request.compression).not.toHaveProperty('protected_phrases');
  });

  it('rejects an older backend that silently ignores requested phrases', () => {
    const oldResult = { original: 'yaar wifi', compressed: 'wifi' } as CompressionResult;
    expect(() => acceptPhraseResult(oldResult, ['yaar'])).toThrow('Restart npm run dev');
    expect(acceptPhraseResult(oldResult, [])).toBe(oldResult);
  });

  it('accepts only an acknowledged selection with corresponding checks', () => {
    const accepted = { ...result, phrase_checks: [{ text: 'yaar', preserved_in_output: true }] } as CompressionResult;
    expect(acceptPhraseResult(accepted, ['yaar'])).toBe(accepted);
    expect(() => acceptPhraseResult(accepted, ['wifi'])).toThrow('phrase checks');
    expect(() => acceptPhraseResult({ ...accepted, phrase_checks: [] }, ['yaar'])).toThrow('phrase checks');
  });

  it('highlights overlapping custom and automatic spans without duplicating text', () => {
    const text = '🙂 मेरा wifi';
    const spans = [{ start: 2, end: 6, text: 'मेरा', kind: 'user_phrase' },
      { start: 2, end: 11, text: 'मेरा wifi', kind: 'user_phrase' }];
    const parts = highlightParts(text, [], spans);
    expect(parts.map((part) => part.text).join('')).toBe(text);
    expect(parts.filter((part) => part.kind === 'protected').map((part) => part.text).join('')).toBe('मेरा wifi');
  });
});

describe('API and handoff', () => {
  it('does not compress a Studio request twice or generate an answer', () => {
    const request = chatRequest({ compressed: 'wifi slow', requested_method: 'crf', budget: 0.6 } as CompressionResult);
    expect(request.text).toBe('wifi slow');
    expect(request.compression.enabled).toBe(false);
    expect(request.mode).toBe('demo');
  });

  it('reports backend validation errors rather than showing them as results', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: 'Enter nonblank text.' }] }), { status: 422 })));
    await expect(compressionRequest('analyze')).rejects.toThrow('Enter nonblank text.');
  });

  it('preserves an HTTP status if error content is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 503 })));
    await expect(compressionRequest('evidence')).rejects.toThrow('503');
  });

  it('returns real backend data without generating client-side metric substitutes', async () => {
    const body = { method: 'crf', original_tokens: 14, compressed_tokens: 10 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify(body))));
    expect(await compressionRequest('analyze')).toEqual(body);
  });
});
