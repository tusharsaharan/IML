import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { OutputCapCard } from './OutputCapCard';
import { TokenCompareCard } from './TokenCompareCard';
import { CostEstimatorCard } from './CostEstimatorCard';
import { HistoryTable } from './HistoryTable';
import { ClusterViz } from './ClusterViz';
import { LengthPredictor } from './LengthPredictor';
import type { SummaryResponse } from './types';
import { fetchSummary } from './client';

export function InsightsPage() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [activeTab, setActiveTab] = useState<'all' | 'cap' | 'tokens' | 'cost' | 'history' | 'ml'>('all');

  useEffect(() => {
    fetchSummary().then(setSummary).catch(() => {});
  }, []);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header Card */}
      <Card className="panel p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="eyebrow">Aman &bull; Workstream 4</span>
              <Badge variant="secondary" className="bg-emerald-100 text-emerald-800 border-emerald-300 text-xs">
                Point 2: Cap the output
              </Badge>
            </div>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-ink">Token & Cost Insights Workspace</h2>
            <p className="mt-1 text-sm text-muted">
              Analyze token usage, cost trade-offs, language tokenization inflation, and the impact of output length/format constraints.
            </p>
          </div>

          {/* Quick KPI stats */}
          {summary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              <div className="rounded-xl border border-line bg-canvas p-2.5">
                <span className="block text-xs text-muted">Audited Requests</span>
                <span className="text-lg font-bold text-ink">{summary.total_requests}</span>
              </div>
              <div className="rounded-xl border border-line bg-canvas p-2.5">
                <span className="block text-xs text-muted">Avg Tokens Saved</span>
                <span className="text-lg font-bold text-emerald-700">↓ {summary.avg_tokens_saved_by_capping}</span>
              </div>
              <div className="rounded-xl border border-line bg-canvas p-2.5">
                <span className="block text-xs text-muted">Code-Mix Ratio</span>
                <span className="text-lg font-bold text-ink">{Math.round(summary.average_code_mix * 100)}%</span>
              </div>
              <div className="rounded-xl border border-line bg-canvas p-2.5">
                <span className="block text-xs text-muted">Tokenizer</span>
                <span className="text-xs font-semibold text-accent truncate block mt-1" title={summary.tokenizer_backend}>
                  {summary.tokenizer_backend.replace('tiktoken_', '')}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Section Navigation Pills */}
        <div className="mt-6 flex flex-wrap gap-2 border-t border-line pt-4">
          {[
            ['all', 'Complete View'],
            ['cap', '🎯 Cap the Output (Point 2)'],
            ['tokens', 'Multilingual Tokens'],
            ['cost', 'Cost Estimator'],
            ['history', 'Request History'],
            ['ml', 'ML & Clustering'],
          ].map(([tabKey, label]) => (
            <Button
              key={tabKey}
              size="sm"
              variant={activeTab === tabKey ? 'default' : 'outline'}
              onClick={() => setActiveTab(tabKey as typeof activeTab)}
              className="text-xs"
            >
              {label}
            </Button>
          ))}
        </div>
      </Card>

      {/* Main Content Sections */}
      {(activeTab === 'all' || activeTab === 'cap') && (
        <section id="cap-output">
          <OutputCapCard />
        </section>
      )}

      {(activeTab === 'all' || activeTab === 'tokens') && (
        <section id="multilingual-tokens">
          <TokenCompareCard />
        </section>
      )}

      {(activeTab === 'all' || activeTab === 'cost') && (
        <section id="cost-estimator">
          <CostEstimatorCard />
        </section>
      )}

      {(activeTab === 'all' || activeTab === 'history') && (
        <section id="history-audit">
          <HistoryTable />
        </section>
      )}

      {(activeTab === 'all' || activeTab === 'ml') && (
        <div className="space-y-6">
          <section id="pca-clustering">
            <ClusterViz />
          </section>
          <section id="length-predictor">
            <LengthPredictor />
          </section>
        </div>
      )}
    </div>
  );
}
