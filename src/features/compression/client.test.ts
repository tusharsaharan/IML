import { afterEach, describe, expect, it, vi } from 'vitest';
import { chatRequest, compressionRequest, highlightParts } from './client';
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
