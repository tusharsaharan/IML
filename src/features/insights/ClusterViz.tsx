import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts';
import type { ClusterPoint, ClusterResponse } from './types';
import { fetchClusters } from './client';

const CLUSTER_COLORS = ['#10b981', '#6366f1', '#f59e0b'];

export function ClusterViz() {
  const [data, setData] = useState<ClusterResponse | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<ClusterPoint | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchClusters()
      .then((res) => {
        setData(res);
        if (res.points.length > 0) setSelectedPoint(res.points[0]);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <Card className="panel p-6 space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <span className="eyebrow">ML Angle</span>
          <Badge variant="outline" className="text-xs">
            Unsupervised Learning (PCA + K-Means)
          </Badge>
        </div>
        <h3 className="mt-1 text-xl font-semibold text-ink">Request Feature Space & Clustering</h3>
        <p className="text-sm text-muted">
          Dimensionality reduction (PCA to 2 components) and K-Means (k=3) over token counts, code-mixing, cache status, and routing tiers.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Scatter plot */}
        <div className="lg:col-span-7 rounded-xl border border-line bg-white/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-ink">2D Principal Component Projection</h4>
            {data && (
              <span className="text-xs text-muted">
                Explained Variance: {(data.total_explained_variance * 100).toFixed(1)}% (PC1: {(data.explained_variance_ratio[0] * 100).toFixed(1)}%, PC2: {(data.explained_variance_ratio[1] * 100).toFixed(1)}%)
              </span>
            )}
          </div>

          <div className="h-64 w-full">
            {loading ? (
              <div className="flex h-full items-center justify-center text-xs text-muted">Computing PCA...</div>
            ) : data && data.points.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <ScatterChart margin={{ top: 15, right: 20, bottom: 20, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis
                    type="number"
                    dataKey="pc1"
                    name="PC1 (Token Scale & Complexity)"
                    tick={{ fontSize: 11 }}
                    label={{ value: 'PC1 (Token Scale)', position: 'insideBottom', offset: -10, fontSize: 11 }}
                  />
                  <YAxis
                    type="number"
                    dataKey="pc2"
                    name="PC2 (Code-mix & Route Tier)"
                    tick={{ fontSize: 11 }}
                    label={{ value: 'PC2 (Code-mix / Route)', angle: -90, position: 'insideLeft', fontSize: 11 }}
                  />
                  <ZAxis range={[70, 70]} />
                  <Tooltip
                    content={({ payload }) => {
                      if (!payload || !payload[0]) return null;
                      const pt = payload[0].payload as ClusterPoint;
                      return (
                        <div className="rounded-lg border border-line bg-panel p-2 shadow-sm text-xs font-sans">
                          <p className="font-semibold text-ink">{pt.text}</p>
                          <p className="text-muted mt-1">Cluster: <span className="font-medium text-ink">{pt.cluster_label}</span></p>
                          <p className="text-muted">In: {pt.input_tokens} | Out: {pt.output_tokens} tok</p>
                          <p className="text-muted">Lang: {pt.language} | Route: {pt.route}</p>
                        </div>
                      );
                    }}
                  />
                  <Scatter
                    data={data.points}
                    onClick={(entry) => setSelectedPoint(entry as unknown as ClusterPoint)}
                    cursor="pointer"
                  >
                    {data.points.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={CLUSTER_COLORS[entry.cluster % CLUSTER_COLORS.length]}
                      />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
            ) : null}
          </div>
        </div>

        {/* Selected Point & Cluster Profiles */}
        <div className="lg:col-span-5 flex flex-col justify-between rounded-xl border border-line bg-white/70 p-4 text-xs space-y-4">
          <div>
            <h4 className="font-semibold text-sm text-ink mb-2">Cluster Profiles</h4>
            <div className="space-y-2">
              {data?.clusters.map((c) => (
                <div
                  key={c.cluster_id}
                  className="rounded-lg border border-line bg-canvas p-2.5 space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 rounded-full"
                        style={{ backgroundColor: CLUSTER_COLORS[c.cluster_id % CLUSTER_COLORS.length] }}
                      />
                      <span className="font-semibold text-ink">{c.label}</span>
                    </div>
                    <Badge variant="secondary" className="text-[10px]">
                      {c.count} items
                    </Badge>
                  </div>
                  <p className="text-[11px] text-muted">{c.description}</p>
                  <div className="flex gap-4 text-[10px] text-muted pt-1 border-t border-line/50">
                    <span>Avg In: <strong className="text-ink">{c.avg_input_tokens}</strong></span>
                    <span>Avg Out: <strong className="text-ink">{c.avg_output_tokens}</strong></span>
                    <span>Cache Hits: <strong className="text-ink">{c.cache_hits}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {selectedPoint && (
            <div className="rounded-lg border border-line bg-panel p-3">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
                Selected Point Inspection
              </span>
              <p className="mt-1 font-medium text-ink truncate">&ldquo;{selectedPoint.text}&rdquo;</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-[11px] text-muted">
                <div>Language: <strong className="text-ink">{selectedPoint.language}</strong></div>
                <div>Route: <strong className="text-ink">{selectedPoint.route}</strong></div>
                <div>Input Tokens: <strong className="text-ink">{selectedPoint.input_tokens}</strong></div>
                <div>Output Tokens: <strong className="text-ink">{selectedPoint.output_tokens}</strong></div>
                <div>Format Cap: <strong className="text-ink">{selectedPoint.format_constraint || 'none'}</strong></div>
                <div>Cache Hit: <strong className="text-ink">{selectedPoint.cache_hit ? 'Yes' : 'No'}</strong></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}
    </Card>
  );
}

