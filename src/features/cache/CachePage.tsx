import { Card } from '@/components/ui/card';

export function CachePage() {
  return (
    <Card className="panel p-6">
      <p className="eyebrow">Shivam</p>
      <h2 className="mt-2 text-2xl font-semibold">Memory & Cache</h2>
      <p className="mt-3 text-muted">Build exact and semantic answer reuse here. Show similarity, matched entries and cache actions. Connect to <code>/api/v1/cache/*</code>.</p>
    </Card>
  );
}
