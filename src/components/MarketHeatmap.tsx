import { ResponsiveContainer, Tooltip, Treemap } from "recharts";

interface HeatmapData {
  [sector: string]: number;
}

interface TreemapNode {
  name: string;
  size: number;
  score: number;
}

function scoreToColor(score: number): string {
  if (score >= 3) return "#0fb981";
  if (score >= 1.5) return "#42d39f";
  if (score >= 0.3) return "#86efc5";
  if (score > -0.3) return "#334155";
  if (score > -1.5) return "#fb923c";
  if (score > -3) return "#f87171";
  return "#ef4444";
}

function formatScore(score: number): string {
  return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
}

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  score?: number;
}

function SectorCell({
  x = 0,
  y = 0,
  width = 0,
  height = 0,
  name = "",
  score = 0,
}: CellProps) {
  const color = scoreToColor(score);
  const showLabel = width > 56 && height > 28;
  const showScore = width > 70 && height > 46;

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={Math.max(0, width - 2)}
        height={Math.max(0, height - 2)}
        style={{ fill: color, stroke: "#08101d", strokeWidth: 2 }}
      />
      {showLabel ? (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - (showScore ? 8 : 0)}
            textAnchor="middle"
            fill="#f8fafc"
            fontSize={width > 120 ? 13 : 11}
            fontWeight="600"
            fontFamily="Segoe UI, sans-serif"
          >
            {name}
          </text>
          {showScore ? (
            <text
              x={x + width / 2}
              y={y + height / 2 + 13}
              textAnchor="middle"
              fill="rgba(248,250,252,0.82)"
              fontSize={11}
              fontFamily="Segoe UI, sans-serif"
            >
              {formatScore(score)}
            </text>
          ) : null}
        </>
      ) : null}
    </g>
  );
}

export function MarketHeatmap({
  heatmap,
  loading,
}: {
  heatmap: HeatmapData;
  loading: boolean;
}) {
  const hasData = Object.keys(heatmap).length > 0;
  const treemapData = [
    {
      name: "root",
      children: Object.entries(heatmap).map(([sector, score]) => ({
        name: sector,
        size: Math.max(Math.abs(score), 0.4),
        score,
      })),
    },
  ];

  return (
    <section className="rounded-[28px] border border-white/10 bg-slate-950/45 p-5 shadow-[0_20px_60px_rgba(2,8,20,0.34)]">
      <div className="mb-5 flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Pressure Map</p>
          <h2 className="mt-2 font-['Space_Grotesk',_'Segoe_UI',_sans-serif] text-2xl font-semibold text-white">
            Sector impact heatmap from live scored events
          </h2>
        </div>
        <p className="max-w-sm text-right text-xs leading-6 text-slate-400">
          Tile size follows absolute impact. Green indicates tailwind, red indicates headwind.
        </p>
      </div>

      <div className="rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,_rgba(15,23,42,0.88),_rgba(7,10,18,0.94))] p-4">
        {loading ? (
          <div className="flex h-[560px] items-center justify-center text-sm text-slate-400">Loading sector data...</div>
        ) : !hasData ? (
          <div className="flex h-[560px] items-center justify-center text-sm text-slate-400">No scored events yet.</div>
        ) : (
          <ResponsiveContainer width="100%" height={560}>
            <Treemap data={treemapData} dataKey="size" aspectRatio={16 / 9} stroke="#08101d" content={<SectorCell />}>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) {
                    return null;
                  }
                  const data = payload[0].payload as TreemapNode;
                  return (
                    <div className="rounded-2xl border border-white/10 bg-slate-950/92 px-4 py-3 text-sm shadow-2xl">
                      <p className="font-semibold text-white">{data.name}</p>
                      <p className={`mt-1 font-semibold ${data.score >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                        {formatScore(data.score)}
                      </p>
                    </div>
                  );
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-5 text-xs text-slate-400">
        <LegendSwatch color="#ef4444" label="Strong headwind" />
        <LegendSwatch color="#fb923c" label="Mild headwind" />
        <LegendSwatch color="#334155" label="Neutral" />
        <LegendSwatch color="#86efc5" label="Mild tailwind" />
        <LegendSwatch color="#0fb981" label="Strong tailwind" />
      </div>
    </section>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-3.5 w-3.5 rounded-sm" style={{ backgroundColor: color }} />
      <span>{label}</span>
    </div>
  );
}
