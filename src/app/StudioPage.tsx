import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

const sample = 'Yaar, can you please tell me ki library book renew karne ka last date kya hai? I am travelling this week.';

export function StudioPage() {
  const [text, setText] = useState(sample);
  const [result, setResult] = useState<string>('Run the pipeline after the team connects feature APIs.');

  async function run() {
    try {
      const res = await fetch('/api/v1/routing/predict', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text }) });
      const data = await res.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (error) {
      setResult(`Start the backend with npm run dev. ${String(error)}`);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[1.1fr_.9fr]">
      <Card className="panel p-6">
        <p className="eyebrow">Shared studio</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight">See how a request is optimised before it is answered.</h2>
        <p className="mt-3 max-w-2xl text-muted">This page will connect compression, routing, cache and usage reporting. Each team member builds an independent feature page and API; the studio integrates their outputs.</p>
        <Textarea className="mt-6 min-h-36 bg-white" value={text} onChange={(e) => setText(e.target.value)} />
        <div className="mt-4 flex gap-3"><Button onClick={run}>Check starter API</Button></div>
      </Card>
      <Card className="panel p-6">
        <p className="eyebrow">Pipeline output</p>
        <pre className="mono mt-4 overflow-auto rounded-2xl bg-[#162824] p-4 text-sm text-[#edf4f1]">{result}</pre>
      </Card>
    </div>
  );
}
