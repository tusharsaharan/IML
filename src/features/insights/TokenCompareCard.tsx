import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import type { TokenizeItem, TokenizeResponse } from './types';
import { fetchTokenize } from './client';

const PRESETS = [
  {
    name: 'Library Renewal',
    variants: {
      English: 'How do I renew my library book online before the due date?',
      Hinglish: 'Meri library book online kaise renew hogi due date se pehle?',
      Hindi: 'पुस्तकालय की किताब नियत तिथि से पहले ऑनलाइन कैसे नवीकृत करें?',
    },
  },
  {
    name: 'Wi-Fi Issue',
    variants: {
      English: 'Campus Wi-Fi portal is not redirecting on my phone.',
      Hinglish: 'Campus Wi-Fi portal mere phone par redirect nahi ho raha.',
      Hindi: 'परिसर वाई-फाई पोर्टल मेरे फ़ोन पर काम नहीं कर रहा है।',
    },
  },
  {
    name: 'Assignment Submission',
    variants: {
      English: 'What is the late penalty for submitting Assignment 2 after deadline?',
      Hinglish: 'Assignment 2 deadline ke baad submit karne par kitni penalty lagegi?',
      Hindi: 'अंतिम तिथि के बाद असाइनमेंट २ जमा करने पर क्या दंड लगेगा?',
    },
  },
];

export function TokenCompareCard() {
  const [activePreset, setActivePreset] = useState(0);
  const [variants, setVariants] = useState(PRESETS[0].variants);
  const [data, setData] = useState<TokenizeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function runTokenize(targetVariants: Record<string, string>) {
    setLoading(true);
    setError('');
    fetchTokenize(undefined, targetVariants)
      .then(setData)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    runTokenize(PRESETS[0].variants);
  }, []);

  function handlePresetChange(idx: number) {
    setActivePreset(idx);
    setVariants(PRESETS[idx].variants);
    runTokenize(PRESETS[idx].variants);
  }

  function handleTextChange(lang: string, val: string) {
    const updated = { ...variants, [lang]: val };
    setVariants(updated);
  }

  const chartData = (data?.items || []).map((item: TokenizeItem) => ({
    language: item.label,
    Tokens: item.tokens,
    Characters: item.chars,
    'Tokens/Char': Number((item.tokens_per_char * 10).toFixed(1)), // scaled for visibility
  }));

  return (
    <Card className="panel p-6 space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="eyebrow">Multilingual Analysis</span>
          <h3 className="mt-1 text-xl font-semibold text-ink">Token Inflation: English vs Hinglish vs Hindi</h3>
          <p className="text-sm text-muted">
            Inspect how the same semantic request is tokenized across Romanized English, code-mixed Hinglish, and native Devanagari Hindi.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          {PRESETS.map((p, idx) => (
            <Button
              key={p.name}
              size="sm"
              variant={idx === activePreset ? 'default' : 'outline'}
              onClick={() => handlePresetChange(idx)}
              className="text-xs"
            >
              {p.name}
            </Button>
          ))}
        </div>
      </div>

      {/* Editable comparison boxes */}
      <div className="grid gap-4 lg:grid-cols-3">
        {(['English', 'Hinglish', 'Hindi'] as const).map((lang) => {
          const item = data?.items.find((i) => i.label === lang);
          return (
            <div key={lang} className="rounded-xl border border-line bg-canvas p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm text-ink">{lang}</span>
                {item && (
                  <span className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-semibold text-accent">
                    {item.tokens} tokens
                  </span>
                )}
              </div>

              <Textarea
                rows={3}
                value={variants[lang] || ''}
                onChange={(e) => handleTextChange(lang, e.target.value)}
                className="text-xs font-normal"
                placeholder={`Enter ${lang} prompt...`}
              />

              {item && (
                <div className="grid grid-cols-3 gap-1 pt-1 text-center text-[11px] text-muted border-t border-line">
                  <div>
                    <span className="block font-medium text-ink">{item.chars}</span>
                    <span>chars</span>
                  </div>
                  <div>
                    <span className="block font-medium text-ink">{item.tokens_per_char}</span>
                    <span>tok/char</span>
                  </div>
                  <div>
                    <span className="block font-medium text-ink">{Math.round(item.code_mix_ratio * 100)}%</span>
                    <span>code-mix</span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex justify-end">
        <Button size="sm" onClick={() => runTokenize(variants)} disabled={loading}>
          {loading ? 'Tokenizing...' : 'Re-calculate Token Counts'}
        </Button>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      {/* BarChart */}
      {data && (
        <div className="rounded-xl border border-line bg-white/50 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-semibold text-ink">Token & Character Comparison</h4>
            <span className="text-xs text-muted">Backend: {data.backend}</span>
          </div>
          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                <XAxis dataKey="language" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
                <Bar dataKey="Tokens" fill="#6366f1" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Characters" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="mt-2 text-[11px] text-muted italic">
            Note: Devanagari Hindi often requires 2–3 subword tokens per word in BPE/tiktoken vocabularies, significantly inflating input cost compared to English and Romanized Hinglish.
          </p>
        </div>
      )}
    </Card>
  );
}

