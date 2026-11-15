import { describe, expect, it } from 'vitest';
import { fetchSummary, fetchCapDemo, fetchCostEstimate, fetchTokenize } from '@/features/insights/client';
import { predictRouting, fetchRoutingModels } from '@/features/routing/client';
import { compressionRequest } from '@/features/compression/client';
import { InsightsPage } from '@/features/insights/InsightsPage';
import { CompressionPage } from '@/features/compression/CompressionPage';
import { RoutingPage } from '@/features/routing/RoutingPage';
import { CachePage } from '@/features/cache/CachePage';
import { StudioPage } from '@/app/StudioPage';
import { App } from '@/app/App';

describe('Unified Project Architecture Verification', () => {
  it('exports all 5 application pages cleanly', () => {
    expect(typeof App).toBe('function');
    expect(typeof StudioPage).toBe('function');
    expect(typeof CompressionPage).toBe('function');
    expect(typeof RoutingPage).toBe('function');
    expect(typeof CachePage).toBe('function');
    expect(typeof InsightsPage).toBe('function');
  });

  it('exposes API client helpers across all integrated features', () => {
    // Compression
    expect(typeof compressionRequest).toBe('function');

    // Routing
    expect(typeof predictRouting).toBe('function');
    expect(typeof fetchRoutingModels).toBe('function');

    // Insights & Output Capping (Pillar 2)
    expect(typeof fetchSummary).toBe('function');
    expect(typeof fetchCapDemo).toBe('function');
    expect(typeof fetchCostEstimate).toBe('function');
    expect(typeof fetchTokenize).toBe('function');
  });
});
