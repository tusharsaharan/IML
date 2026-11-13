import type { RoutingModels, RoutingPolicy, RoutingPrediction } from './types';

export const ROUTING_TIMEOUT_MS = 30000;

async function routingRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/routing/${path}`, {
    ...init,
    signal: init?.signal ?? AbortSignal.timeout(ROUTING_TIMEOUT_MS),
  });
  if (!response.ok) {
    let detail = `Routing API returned ${response.status}.`;
    try {
      const body: { detail?: unknown } = await response.json();
      if (typeof body.detail === 'string') detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((item) => item.msg).join(' ');
    } catch { /* Keep the HTTP status if the backend did not return JSON. */ }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export function predictRouting(
  text: string,
  policy: RoutingPolicy,
  signal?: AbortSignal,
): Promise<RoutingPrediction> {
  return routingRequest<RoutingPrediction>('predict', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ text, policy }),
    signal,
  });
}

export function fetchRoutingModels(signal?: AbortSignal): Promise<RoutingModels> {
  return routingRequest<RoutingModels>('models', { signal });
}
