import { Card } from '@/components/ui/card';

export function InsightsPage() {
  return (
    <Card className="panel p-6">
      <p className="eyebrow">Aman</p>
      <h2 className="mt-2 text-2xl font-semibold">Token & Cost Insights</h2>
      <p className="mt-3 text-muted">Build token comparisons, request history, charts and simple model summaries here. Connect to <code>/api/v1/insights/*</code>.</p>
    </Card>
  );
}
