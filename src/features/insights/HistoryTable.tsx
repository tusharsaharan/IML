import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import type { HistoryItem } from './types';
import { fetchHistory } from './client';

export function HistoryTable() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [filterLang, setFilterLang] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchHistory(50)
      .then((data) => setItems(data.items))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const filteredItems = items.filter((item) => {
    if (filterLang !== 'all' && item.language !== filterLang) return false;
    return true;
  });

  const chartData = filteredItems
    .slice(0, 15)
    .reverse()
    .map((item, idx) => ({
      idx: `#${idx + 1}`,
      'Input Tokens': item.input_tokens,
      'Output Tokens': item.output_tokens,
      capped: Boolean(item.format_constraint || item.max_tokens_set),
    }));

  return (
    <Card className="panel p-6 space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <span className="eyebrow">Shared Store & Audit</span>
          <h3 className="mt-1 text-xl font-semibold text-ink">Request History & Pipeline Audit</h3>
          <p className="text-sm text-muted">
            Inspect request text, language, model route, cache status, prompt compression, and token counts.
          </p>
        </div>

        <div className="flex gap-1.5">
          {['all', 'en', 'hinglish', 'hi'].map((lang) => (
            <Button
              key={lang}
              size="sm"
              variant={filterLang === lang ? 'default' : 'outline'}
              onClick={() => setFilterLang(lang)}
              className="text-xs capitalize"
            >
              {lang === 'all' ? 'All Languages' : lang}
            </Button>
          ))}
        </div>
      </div>

      {/* Trend line chart */}
      <div className="rounded-xl border border-line bg-white/50 p-4">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-ink">Token Trend Across Recent Requests</h4>
          <span className="text-xs text-muted">Showing input vs output token consumption</span>
        </div>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
              <XAxis dataKey="idx" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
              <Legend wrapperStyle={{ fontSize: '12px' }} />
              <Line type="monotone" dataKey="Input Tokens" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
              <Line type="monotone" dataKey="Output Tokens" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* History Table */}
      <div className="overflow-x-auto rounded-xl border border-line bg-canvas">
        <table className="w-full text-left text-xs">
          <thead className="border-b border-line bg-white/60 text-muted uppercase tracking-wider text-[10px]">
            <tr>
              <th className="p-3">Request Text</th>
              <th className="p-3">Language</th>
              <th className="p-3">Route</th>
              <th className="p-3">Cache</th>
              <th className="p-3">Compressed</th>
              <th className="p-3 text-right">In Toks</th>
              <th className="p-3 text-right">Out Toks</th>
              <th className="p-3">Cap / Constraint</th>
              <th className="p-3">Source</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line font-mono text-[11px]">
            {loading ? (
              <tr>
                <td colSpan={9} className="p-6 text-center text-muted font-sans">
                  Loading request history...
                </td>
              </tr>
            ) : filteredItems.length === 0 ? (
              <tr>
                <td colSpan={9} className="p-6 text-center text-muted font-sans">
                  No requests found matching criteria.
                </td>
              </tr>
            ) : (
              filteredItems.map((item) => (
                <tr key={item.id} className="hover:bg-white/80 transition-colors">
                  <td className="p-3 font-sans max-w-xs truncate text-ink font-medium" title={item.text}>
                    {item.text}
                  </td>
                  <td className="p-3">
                    <Badge variant="outline" className="text-[10px] uppercase font-sans">
                      {item.language}
                    </Badge>
                  </td>
                  <td className="p-3 capitalize font-sans">{item.route || 'economy'}</td>
                  <td className="p-3 font-sans">
                    {item.cache_hit ? (
                      <Badge className="bg-emerald-100 text-emerald-800 border-emerald-300 text-[10px]">Hit</Badge>
                    ) : (
                      <span className="text-muted text-[10px]">Miss</span>
                    )}
                  </td>
                  <td className="p-3 font-sans">
                    {item.compressed ? (
                      <Badge className="bg-indigo-100 text-indigo-800 border-indigo-300 text-[10px]">Yes</Badge>
                    ) : (
                      <span className="text-muted text-[10px]">No</span>
                    )}
                  </td>
                  <td className="p-3 text-right font-semibold text-ink">{item.input_tokens}</td>
                  <td className="p-3 text-right font-semibold text-ink">{item.output_tokens}</td>
                  <td className="p-3 font-sans">
                    {item.format_constraint ? (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-800 border border-amber-200 text-[10px]">
                        {item.format_constraint}
                      </span>
                    ) : item.max_tokens_set ? (
                      <span className="rounded bg-amber-50 px-1.5 py-0.5 text-amber-800 border border-amber-200 text-[10px]">
                        max:{item.max_tokens_set}
                      </span>
                    ) : (
                      <span className="text-muted text-[10px]">none</span>
                    )}
                  </td>
                  <td className="p-3 font-sans">
                    <Badge variant="secondary" className="text-[10px]">
                      {item.source || 'fixture'}
                    </Badge>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}
    </Card>
  );
}

