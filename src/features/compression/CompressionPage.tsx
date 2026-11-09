import { Card } from '@/components/ui/card';

export function CompressionPage() {
  return (
    <Card className="panel p-6">
      <p className="eyebrow">Tushar</p>
      <h2 className="mt-2 text-2xl font-semibold">Compression Studio</h2>
      <p className="mt-3 text-muted">Build the prompt-compression workspace here. Compare methods, show removed/protected spans, and connect to <code>/api/v1/compression/analyze</code>.</p>
    </Card>
  );
}
