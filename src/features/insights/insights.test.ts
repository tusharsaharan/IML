import { describe, expect, it } from 'vitest';
import { fetchSummary } from './client';

describe('insights client', () => {
  it('exposes fetchSummary function', () => {
    expect(typeof fetchSummary).toBe('function');
  });
});

