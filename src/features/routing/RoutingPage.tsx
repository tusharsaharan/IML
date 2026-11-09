import { Card } from '@/components/ui/card';

export function RoutingPage() {
  return (
    <Card className="panel p-6">
      <p className="eyebrow">Rakesh</p>
      <h2 className="mt-2 text-2xl font-semibold">Smart Router</h2>
      <p className="mt-3 text-muted">Build routing controls, feature explanations and model comparisons here. Connect to <code>/api/v1/routing/predict</code>.</p>
    </Card>
  );
}
