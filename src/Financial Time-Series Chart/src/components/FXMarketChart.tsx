import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip } from 'recharts';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TimelineEvent {
  title: string;
  published_at: string;
  fx_state: string;
}

interface ChartPoint {
  label: string;
  USD: number;
  JPY: number;
  EUR: number;
  EM: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseFxState(fx_state: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const token of fx_state.split(' ')) {
    const [ccy, raw] = token.split(':');
    if (ccy && raw !== undefined) {
      const val = parseFloat(raw);
      if (!isNaN(val)) result[ccy.toUpperCase()] = val;
    }
  }
  return result;
}

function buildChartData(events: TimelineEvent[]): ChartPoint[] {
  // Events from API are newest-first; reverse for left-to-right time order.
  const ordered = [...events].reverse();
  let cumUSD = 0, cumJPY = 0, cumEUR = 0, cumEM = 0;

  return ordered.map((ev) => {
    const fx = parseFxState(ev.fx_state);
    cumUSD = parseFloat((cumUSD + (fx['USD'] ?? 0)).toFixed(3));
    cumJPY = parseFloat((cumJPY + (fx['JPY'] ?? 0)).toFixed(3));
    cumEUR = parseFloat((cumEUR + (fx['EUR'] ?? 0)).toFixed(3));
    cumEM  = parseFloat((cumEM  + (fx['EM']  ?? 0)).toFixed(3));

    const label = ev.title.length > 22 ? ev.title.slice(0, 22) + '…' : ev.title;
    return { label, USD: cumUSD, JPY: cumJPY, EUR: cumEUR, EM: cumEM };
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function FXMarketChart() {
  const [data, setData] = useState<ChartPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/timeline?limit=20')
      .then((r) => (r.ok ? r.json() : []))
      .then((events: TimelineEvent[]) => {
        setData(buildChartData(events));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const hasData = data.length > 0;

  return (
    <div className="w-full max-w-6xl">
      <div className="mb-8">
        <h1 className="text-[#e8eaed] text-2xl tracking-tight mb-2">FX Cumulative Impact by Currency</h1>
        <p className="text-[#9aa0a6] text-sm font-light">Cumulative FX delta across scored macro events (USD, JPY, EUR, EM)</p>
      </div>

      <div className="bg-[#12161f] rounded-lg p-8 border border-[#1e2430]">
        {loading ? (
          <div className="flex items-center justify-center h-[500px] text-[#9aa0a6] text-sm">
            Loading FX data…
          </div>
        ) : !hasData ? (
          <div className="flex flex-col items-center justify-center h-[500px] text-[#9aa0a6] text-sm gap-2">
            <span>No scored events yet.</span>
            <span className="text-xs text-[#6e7681]">Run the pipeline: POST /pipeline/run</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={500}>
            <LineChart data={data} margin={{ top: 20, right: 30, bottom: 80, left: 60 }}>
              <CartesianGrid strokeDasharray="0" stroke="#1e2430" horizontal={true} vertical={false} />
              <XAxis
                dataKey="label"
                stroke="#9aa0a6"
                tick={{ fill: '#9aa0a6', fontSize: 10, fontWeight: 300 }}
                axisLine={{ stroke: '#1e2430' }}
                tickLine={false}
                angle={-40}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                stroke="#9aa0a6"
                tick={{ fill: '#9aa0a6', fontSize: 11, fontWeight: 300 }}
                axisLine={{ stroke: '#1e2430' }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{ background: '#1a1f2e', border: '1px solid #2a3040', borderRadius: 6 }}
                labelStyle={{ color: '#e8eaed', fontSize: 11, marginBottom: 4 }}
                itemStyle={{ fontSize: 11 }}
                formatter={(value: number, name: string) => [
                  value >= 0 ? `+${value.toFixed(3)}` : value.toFixed(3),
                  name,
                ]}
              />
              <Line type="monotone" dataKey="USD" stroke="#4a9eff" strokeWidth={2.5} dot={false} name="USD" />
              <Line type="monotone" dataKey="JPY" stroke="#ff4a9e" strokeWidth={2.5} dot={false} name="JPY" />
              <Line type="monotone" dataKey="EUR" stroke="#ff9a4a" strokeWidth={2.5} dot={false} name="EUR" />
              <Line type="monotone" dataKey="EM"  stroke="#4aff9e" strokeWidth={2.5} dot={false} name="EM" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {hasData && (
        <div className="flex items-center gap-6 mt-4 flex-wrap">
          {[
            { color: '#4a9eff', label: 'USD' },
            { color: '#ff4a9e', label: 'JPY' },
            { color: '#ff9a4a', label: 'EUR' },
            { color: '#4aff9e', label: 'EM' },
          ].map(({ color, label }) => (
            <div key={label} className="flex items-center gap-2">
              <div className="w-5 h-0.5" style={{ backgroundColor: color }} />
              <span className="text-[#9aa0a6] text-xs font-light">{label}</span>
            </div>
          ))}
          <span className="text-[#6e7681] text-xs ml-auto">Source: live BBC news via LLM pipeline</span>
        </div>
      )}
    </div>
  );
}
