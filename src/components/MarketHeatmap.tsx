import { Treemap, ResponsiveContainer, Tooltip } from "recharts";
import { useEffect, useState } from "react";

interface HeatmapData {
  [sector: string]: number;
}

interface TreemapNode {
  name: string;
  size: number;
  score: number;
}

function scoreToColor(score: number): string {
  if (score >= 3)   return "#10b981";
  if (score >= 1.5) return "#34d399";
  if (score >= 0.3) return "#6ee7b7";
  if (score > -0.3) return "#374151";
  if (score > -1.5) return "#fb923c";
  if (score > -3)   return "#f87171";
  return "#ef4444";
}

function formatScore(score: number): string {
  return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
}

interface CellProps {
  x?: number; y?: number; width?: number; height?: number;
  name?: string; score?: number;
}

const SectorCell = ({ x = 0, y = 0, width = 0, height = 0, name = '', score = 0 }: CellProps) => {
  const color = scoreToColor(score);
  const showLabel = width > 55 && height > 28;
  const showScore = width > 70 && height > 46;
  return (
    <g>
      <rect x={x + 1} y={y + 1} width={width - 2} height={height - 2}
        style={{ fill: color, stroke: '#0f172a', strokeWidth: 2 }} />
      {showLabel && (
        <>
          <text x={x + width / 2} y={y + height / 2 - (showScore ? 7 : 0)}
            textAnchor="middle" fill="#ffffff" fontSize={width > 100 ? 13 : 11}
            fontWeight="600" fontFamily="Inter, system-ui, sans-serif">
            {name}
          </text>
          {showScore && (
            <text x={x + width / 2} y={y + height / 2 + 13}
              textAnchor="middle" fill="rgba(255,255,255,0.8)" fontSize={11}
              fontFamily="Inter, system-ui, sans-serif">
              {formatScore(score)}
            </text>
          )}
        </>
      )}
    </g>
  );
};

export function MarketHeatmap() {
  const [heatmap, setHeatmap] = useState<HeatmapData>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/heatmap')
      .then((r) => (r.ok ? r.json() : {}))
      .then((data: HeatmapData) => setHeatmap(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const treemapData = [{
    name: 'root',
    children: Object.entries(heatmap).map(([sector, score]) => ({
      name: sector,
      size: Math.max(Math.abs(score), 0.4),
      score,
    })),
  }];

  const hasData = Object.keys(heatmap).length > 0;

  return (
    <div className="w-full">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-semibold text-white">Sector Pressure Map</h2>
          <p className="text-slate-400 text-sm mt-1">Macro sector impact — scored from live BBC news via LLM</p>
        </div>
      </div>

      <div className="bg-slate-900 rounded-lg border border-slate-800 p-4">
        {loading ? (
          <div className="flex items-center justify-center h-[600px] text-slate-500 text-sm">
            Loading sector data…
          </div>
        ) : !hasData ? (
          <div className="flex flex-col items-center justify-center h-[600px] text-slate-500 text-sm gap-2">
            <span>No scored events yet.</span>
            <span className="text-xs">Run the pipeline: POST /pipeline/run</span>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={600}>
            <Treemap data={treemapData} dataKey="size" aspectRatio={16 / 9}
              stroke="#0f172a" content={<SectorCell />}>
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as TreemapNode;
                  return (
                    <div className="bg-slate-800 border border-slate-600 rounded px-3 py-2 text-sm shadow-xl">
                      <p className="font-semibold text-white">{d.name}</p>
                      <p className={`font-semibold mt-1 ${d.score >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatScore(d.score)}
                      </p>
                    </div>
                  );
                }}
              />
            </Treemap>
          </ResponsiveContainer>
        )}
      </div>

      <div className="mt-6 flex items-center justify-center gap-6 text-sm flex-wrap">
        {[
          { color: "#ef4444", label: "Strong headwind (< −3)" },
          { color: "#fb923c", label: "Mild headwind" },
          { color: "#374151", label: "Neutral" },
          { color: "#6ee7b7", label: "Mild tailwind" },
          { color: "#10b981", label: "Strong tailwind (> +3)" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: color }} />
            <span className="text-slate-400">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
