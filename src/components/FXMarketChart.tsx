import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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

function parseFxState(fxState: string): Record<string, number> {
  const result: Record<string, number> = {};
  for (const token of fxState.split(" ")) {
    const [currency, raw] = token.split(":");
    if (!currency || raw === undefined) {
      continue;
    }
    const value = Number.parseFloat(raw);
    if (!Number.isNaN(value)) {
      result[currency.toUpperCase()] = value;
    }
  }
  return result;
}

function buildChartData(events: TimelineEvent[]): ChartPoint[] {
  const ordered = [...events].reverse();
  let cumulativeUsd = 0;
  let cumulativeJpy = 0;
  let cumulativeEur = 0;
  let cumulativeEm = 0;

  return ordered.map((event) => {
    const fx = parseFxState(event.fx_state);
    cumulativeUsd = Number.parseFloat((cumulativeUsd + (fx.USD ?? 0)).toFixed(3));
    cumulativeJpy = Number.parseFloat((cumulativeJpy + (fx.JPY ?? 0)).toFixed(3));
    cumulativeEur = Number.parseFloat((cumulativeEur + (fx.EUR ?? 0)).toFixed(3));
    cumulativeEm = Number.parseFloat((cumulativeEm + (fx.EM ?? 0)).toFixed(3));

    return {
      label: event.title.length > 24 ? `${event.title.slice(0, 24)}...` : event.title,
      USD: cumulativeUsd,
      JPY: cumulativeJpy,
      EUR: cumulativeEur,
      EM: cumulativeEm,
    };
  });
}

export function FXMarketChart({
  events,
  loading,
}: {
  events: TimelineEvent[];
  loading: boolean;
}) {
  const data = buildChartData(events);

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-950/45 p-5 shadow-[0_20px_60px_rgba(2,8,20,0.34)]">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">FX Impact Curve</p>
          <h2 className="mt-2 font-['Space_Grotesk',_'Segoe_UI',_sans-serif] text-2xl font-semibold text-white">
            Cumulative currency bias from scored events
          </h2>
        </div>
        <p className="max-w-sm text-right text-xs leading-6 text-slate-400">
          Timeline events are converted into cumulative USD, JPY, EUR, and EM deltas from the live rule-engine output.
        </p>
      </div>

      <div className="rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,_rgba(15,23,42,0.88),_rgba(7,10,18,0.94))] p-4">
        {loading ? (
          <div className="flex h-[460px] items-center justify-center text-sm text-slate-400">Loading FX data...</div>
        ) : data.length === 0 ? (
          <div className="flex h-[460px] items-center justify-center text-sm text-slate-400">No scored events yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={460}>
            <LineChart data={data} margin={{ top: 20, right: 18, bottom: 76, left: 20 }}>
              <CartesianGrid stroke="#1f2a3d" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="#7b8798"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                axisLine={{ stroke: "#243147" }}
                tickLine={false}
                angle={-34}
                textAnchor="end"
                interval={0}
              />
              <YAxis
                stroke="#7b8798"
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                axisLine={{ stroke: "#243147" }}
                tickLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: "#101827",
                  border: "1px solid rgba(148, 163, 184, 0.18)",
                  borderRadius: 16,
                }}
                labelStyle={{ color: "#e2e8f0", fontSize: 11 }}
                itemStyle={{ color: "#cbd5e1", fontSize: 11 }}
                formatter={(value: number, name: string) => [
                  value >= 0 ? `+${value.toFixed(3)}` : value.toFixed(3),
                  name,
                ]}
              />
              <Line type="monotone" dataKey="USD" stroke="#5ab2ff" strokeWidth={2.6} dot={false} />
              <Line type="monotone" dataKey="JPY" stroke="#ff7fd1" strokeWidth={2.6} dot={false} />
              <Line type="monotone" dataKey="EUR" stroke="#ffb266" strokeWidth={2.6} dot={false} />
              <Line type="monotone" dataKey="EM" stroke="#6ae7b9" strokeWidth={2.6} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-slate-400">
        <LegendChip color="#5ab2ff" label="USD" />
        <LegendChip color="#ff7fd1" label="JPY" />
        <LegendChip color="#ffb266" label="EUR" />
        <LegendChip color="#6ae7b9" label="EM" />
      </div>
    </section>
  );
}

function LegendChip({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-0.5 w-6 rounded-full" style={{ backgroundColor: color }} />
      <span>{label}</span>
    </div>
  );
}
