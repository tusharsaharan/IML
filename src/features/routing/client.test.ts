import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchRoutingModels, predictRouting } from './client';

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

describe('routing API client', () => {
  it('posts text and policy to the relative predict URL', async () => {
    const body = { selected_tier: 'cheap', score: 0.021 };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(body));
    vi.stubGlobal('fetch', fetchMock);

    const result = await predictRouting('What is the capital of France?', 'balanced');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/routing/predict');
    expect(init.method).toBe('POST');
    expect(init.headers).toEqual({ 'content-type': 'application/json' });
    expect(JSON.parse(String(init.body))).toEqual({
      text: 'What is the capital of France?',
      policy: 'balanced',
    });
    expect(result).toEqual(body);
  });

  it('adds a timeout signal when the caller does not pass one', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal('fetch', fetchMock);

    await predictRouting('hello', 'economy');

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBeInstanceOf(AbortSignal);
    expect(init.signal?.aborted).toBe(false);
  });

  it('forwards an explicit caller signal unchanged', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();

    await predictRouting('hello', 'quality', controller.signal);

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.signal).toBe(controller.signal);
  });

  it('reads the metrics artifact from the relative models URL', async () => {
    const body = { primary_model: 'random_forest', policies: {} };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(body));
    vi.stubGlobal('fetch', fetchMock);

    expect(await fetchRoutingModels()).toEqual(body);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/routing/models');
    expect(init.method).toBeUndefined();
    expect(init.signal).toBeInstanceOf(AbortSignal);
  });

  it('reports a backend string detail instead of a generic status', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ detail: 'Trained routing artifact unavailable.' }, 503)),
    );

    await expect(fetchRoutingModels()).rejects.toThrow('Trained routing artifact unavailable.');
  });

  it('joins FastAPI validation detail messages', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            detail: [
              { loc: ['body', 'policy'], msg: 'Input should be one of: economy, balanced, quality.' },
            ],
          },
          422,
        ),
      ),
    );

    await expect(predictRouting('hello', 'balanced')).rejects.toThrow(
      'Input should be one of: economy, balanced, quality.',
    );
  });

  it('preserves the HTTP status when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('unavailable', { status: 502 })));

    await expect(fetchRoutingModels()).rejects.toThrow('Routing API returned 502.');
  });

  it('propagates an aborted or timed-out request', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockRejectedValue(
          new DOMException('The operation was aborted due to timeout', 'TimeoutError'),
        ),
    );

    await expect(predictRouting('hello', 'balanced')).rejects.toThrow(/timed out|timeout|aborted/i);
  });
});
