import { Treemap, ResponsiveContainer, Tooltip } from 'recharts';
import { useEffect, useRef, useState } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HeatmapData {
  [sector: string]: number;
}

interface TimelineEvent {
  title: string;
  url: string;
  published_at: string;
  sector: string;
  risk_signal: string;
  rate_signal: string;
  geo_signal: string;
  fx_state: string;
  sentiment: string;
  total_score: number;
}

interface TreemapNode {
  name: string;
  size: number;
  score: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreToColor(score: number): string {
  if (score >= 3) return '#10b981';
  if (score >= 1.5) return '#34d399';
  if (score >= 0.3) return '#6ee7b7';
  if (score > -0.3) return '#374151';
  if (score > -1.5) return '#fb923c';
  if (score > -3) return '#f87171';
  return '#ef4444';
}


function formatScore(score: number): string {
  return score >= 0 ? `+${score.toFixed(2)}` : score.toFixed(2);
}

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// ---------------------------------------------------------------------------
// Custom treemap cell
// ---------------------------------------------------------------------------

interface CellProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  score?: number;
}

const SectorCell = ({ x = 0, y = 0, width = 0, height = 0, name = '', score = 0 }: CellProps) => {
  const color = scoreToColor(score);
  const showLabel = width > 55 && height > 28;
  const showScore = width > 70 && height > 46;

  return (
    <g>
      <rect
        x={x + 1}
        y={y + 1}
        width={width - 2}
        height={height - 2}
        style={{ fill: color, stroke: '#0f172a', strokeWidth: 2 }}
      />
      {showLabel && (
        <>
          <text
            x={x + width / 2}
            y={y + height / 2 - (showScore ? 7 : 0)}
            textAnchor="middle"
            fill="#ffffff"
            fontSize={width > 100 ? 13 : 11}
            fontWeight="600"
            fontFamily="Inter, system-ui, sans-serif"
          >
            {name}
          </text>
          {showScore && (
            <text
              x={x + width / 2}
              y={y + height / 2 + 13}
              textAnchor="middle"
              fill="rgba(255,255,255,0.8)"
              fontSize={11}
              fontFamily="Inter, system-ui, sans-serif"
            >
              {formatScore(score)}
            </text>
          )}
        </>
      )}
    </g>
  );
};

// ---------------------------------------------------------------------------
// Main App
// ---------------------------------------------------------------------------

const API = '/api';
const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/pipeline`;
const REFRESH_MS = 30_000;

export default function App() {
  const [heatmap, setHeatmap] = useState<HeatmapData>({});
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [loading, setLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  // Fetch heatmap + timeline
  const fetchData = async () => {
    try {
      const [hmRes, tlRes] = await Promise.all([
        fetch(`${API}/heatmap`),
        fetch(`${API}/timeline?limit=20`),
      ]);
      if (hmRes.ok) setHeatmap(await hmRes.json());
      if (tlRes.ok) setEvents(await tlRes.json());
      setLastUpdated(new Date());
    } catch {
      // backend may not be up yet
    } finally {
      setLoading(false);
    }
  };

  // WebSocket — refetch on new scored event
  useEffect(() => {
    let reconnectTimer: ReturnType<typeof setTimeout>;

    const connect = () => {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setWsStatus('connected');
      ws.onclose = () => {
        setWsStatus('disconnected');
        reconnectTimer = setTimeout(connect, 5000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'event_scored' || msg.type === 'heatmap_updated') {
            fetchData();
          }
        } catch {}
      };

      // keep-alive ping every 25s
      const ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 25_000);
      ws.onclose = () => {
        clearInterval(ping);
        setWsStatus('disconnected');
        reconnectTimer = setTimeout(connect, 5000);
      };
    };

    connect();
    fetchData();
    const refreshTimer = setInterval(fetchData, REFRESH_MS);

    return () => {
      clearTimeout(reconnectTimer);
      clearInterval(refreshTimer);
      wsRef.current?.close();
    };
  }, []);

  // Build treemap data from heatmap
  const treemapData = [
    {
      name: 'root',
      children: Object.entries(heatmap).map(([sector, score]) => ({
        name: sector,
        size: Math.max(Math.abs(score), 0.4),
        score,
      })),
    },
  ];

  const hasData = Object.keys(heatmap).length > 0;

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Event-FX Sector Intelligence</h1>
          <p className="text-slate-400 text-sm mt-1">
            Macro sector pressure map — scored from live BBC news events via LLM pipeline
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-slate-500 text-xs">Updated {timeAgo(lastUpdated.toISOString())}</span>
          )}
          <div className="flex items-center gap-1.5">
            <div
              className={`w-2 h-2 rounded-full ${
                wsStatus === 'connected'
                  ? 'bg-green-400 animate-pulse'
                  : wsStatus === 'connecting'
                  ? 'bg-yellow-400 animate-pulse'
                  : 'bg-slate-500'
              }`}
            />
            <span className="text-xs text-slate-400">
              {wsStatus === 'connected' ? 'LIVE' : wsStatus === 'connecting' ? 'CONNECTING' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Sector Heatmap */}
        <div className="xl:col-span-2">
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider">
                Sector Pressure Map
              </h2>
              <span className="text-xs text-slate-500">
                Size = |impact|  ·  Green = tailwind  ·  Red = headwind
              </span>
            </div>

            {loading ? (
              <div className="flex items-center justify-center h-96 text-slate-500 text-sm">
                Loading sector data...
              </div>
            ) : !hasData ? (
              <div className="flex flex-col items-center justify-center h-96 text-slate-500 text-sm gap-2">
                <span>No scored events yet.</span>
                <span className="text-xs">Run the pipeline: POST /pipeline/run</span>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={460}>
                <Treemap
                  data={treemapData}
                  dataKey="size"
                  aspectRatio={16 / 9}
                  stroke="#0f172a"
                  content={<SectorCell />}
                >
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

          {/* Legend */}
          <div className="flex items-center justify-center gap-5 mt-3 text-xs text-slate-500 flex-wrap">
            {[
              { color: '#ef4444', label: 'Strong headwind (< −3)' },
              { color: '#f87171', label: 'Mild headwind' },
              { color: '#374151', label: 'Neutral' },
              { color: '#6ee7b7', label: 'Mild tailwind' },
              { color: '#10b981', label: 'Strong tailwind (> +3)' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: color }} />
                <span>{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Event Feed */}
        <div className="xl:col-span-1">
          <div className="bg-slate-900 rounded-xl border border-slate-800 p-4 h-full">
            <h2 className="text-sm font-medium text-slate-300 uppercase tracking-wider mb-3">
              Recent Events
            </h2>

            {events.length === 0 ? (
              <div className="text-slate-500 text-sm text-center py-12">
                No events yet — pipeline hasn't run.
              </div>
            ) : (
              <div className="flex flex-col gap-3 overflow-y-auto max-h-[500px] pr-1">
                {events.map((ev, i) => {
                  const fxTokens = ev.fx_state.split(' ').map((token) => {
                    const [ccy, val] = token.split(':');
                    return { ccy, val, pos: !val?.startsWith('-') };
                  });
                  return (
                    <a
                      key={i}
                      href={ev.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block bg-slate-800 hover:bg-slate-750 rounded-lg p-3 transition-colors border border-slate-700 hover:border-slate-600"
                    >
                      <p className="text-white text-xs font-medium leading-snug line-clamp-2 mb-2">
                        {ev.title}
                      </p>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {fxTokens.map(({ ccy, val, pos }) => (
                          <span
                            key={ccy}
                            className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-medium ${
                              pos ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'
                            }`}
                          >
                            {ccy} {val}
                          </span>
                        ))}
                        <span className={`text-[10px] ml-auto font-semibold ${ev.total_score >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatScore(ev.total_score)}
                        </span>
                      </div>
                      <p className="text-slate-600 text-[10px] mt-1.5">
                        {timeAgo(ev.published_at)}
                      </p>
                    </a>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
