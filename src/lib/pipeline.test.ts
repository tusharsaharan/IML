import { afterEach, describe, expect, it, vi } from 'vitest';
import { runPipeline, type ChatRequest } from './pipeline';

const request: ChatRequest = {
  text: 'wifi is slow', language: 'auto', mode: 'demo',
  compression: { enabled: false, method: 'crf', budget: 0.6 },
  routing: { enabled: true, policy: 'quality' }, cache: { enabled: true },
  output: { max_tokens: 40, format_constraint: '3 bullets' }, compare: false,
};
afterEach(() => vi.unstubAllGlobals());

describe('server pipeline client', () => {
  it('sends one request including stage switches and scope; preserves the server result', async () => {
    const output = { answer: 'authored fixture', answer_source: 'authored-demo', request_id: 12 };
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify(output)));
    vi.stubGlobal('fetch', fetcher);
    expect(await runPipeline(request, 'browser-test')).toEqual(output);
    expect(fetcher).toHaveBeenCalledOnce();
    const [url, init] = fetcher.mock.calls[0];
    expect(url).toBe('/api/v1/chat');
    expect(JSON.parse(init.body)).toEqual(request);
    expect(init.headers['X-Cache-Scope']).toBe('browser-test');
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('surfaces provider failure without inventing results', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Provider unavailable' }), { status: 502 })));
    await expect(runPipeline(request, 'test')).rejects.toThrow('Provider unavailable');
  });

  it('reports validation errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ msg: 'Invalid max_tokens' }] }), { status: 422 })));
    await expect(runPipeline(request, 'test')).rejects.toThrow('Invalid max_tokens');
  });

  it('retains HTTP status for an unavailable non-JSON backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('offline', { status: 503 })));
    await expect(runPipeline(request, 'test')).rejects.toThrow('HTTP 503');
  });

  it('propagates network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(runPipeline(request, 'test')).rejects.toThrow('Failed to fetch');
  });
});
