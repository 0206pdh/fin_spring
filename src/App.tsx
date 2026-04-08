import { useEffect, useState } from "react";

import { FXMarketChart } from "./components/FXMarketChart";
import { MarketHeatmap } from "./components/MarketHeatmap";

type ConnectionStatus = "connecting" | "connected" | "disconnected";

interface CategoryItem {
  sector: string;
  url: string;
}

interface NewsItem {
  id: string;
  title: string;
  url: string;
  published_at: string;
  sector: string;
  summary: string;
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

interface HeatmapData {
  [sector: string]: number;
}

interface InsightData {
  id: string;
  title: string;
  url: string;
  summary_ko: string;
  analysis_reason: string;
  fx_reason: string;
  heatmap_reason: string;
}

const API = "/api";
const WS_URL = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/ws/pipeline`;

function timeAgo(isoString: string | null): string {
  if (!isoString) {
    return "-";
  }
  const diffMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.max(0, Math.floor(diffMs / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export default function App() {
  const [categories, setCategories] = useState<CategoryItem[]>([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [newsItems, setNewsItems] = useState<NewsItem[]>([]);
  const [selectedNewsId, setSelectedNewsId] = useState("");
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [heatmap, setHeatmap] = useState<HeatmapData>({});
  const [insight, setInsight] = useState<InsightData | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("connecting");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [loadingNews, setLoadingNews] = useState(false);
  const [loadingInsight, setLoadingInsight] = useState(false);
  const [runningPipeline, setRunningPipeline] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let refreshTimer: number | undefined;
    let reconnectTimer: number | undefined;
    let pingTimer: number | undefined;
    let ws: WebSocket | null = null;

    const refreshDashboard = async () => {
      try {
        const [timelineData, heatmapData, categoryData] = await Promise.all([
          fetchJson<TimelineEvent[]>(`${API}/timeline?limit=20`),
          fetchJson<HeatmapData>(`${API}/heatmap`),
          fetchJson<CategoryItem[]>(`${API}/categories`),
        ]);
        setTimeline(timelineData);
        setHeatmap(heatmapData);
        setCategories(categoryData);
        setLastUpdated(new Date().toISOString());
        setError("");
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : "Dashboard refresh failed");
      } finally {
        setLoadingDashboard(false);
      }
    };

    const connect = () => {
      setConnectionStatus("connecting");
      ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setConnectionStatus("connected");
        pingTimer = window.setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send("ping");
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "event_scored" || message.type === "heatmap_updated") {
            void refreshDashboard();
          }
        } catch {
          // Ignore malformed keep-alive payloads.
        }
      };

      ws.onerror = () => {
        ws?.close();
      };

      ws.onclose = () => {
        setConnectionStatus("disconnected");
        if (pingTimer) window.clearInterval(pingTimer);
        reconnectTimer = window.setTimeout(connect, 5000);
      };
    };

    void refreshDashboard();
    connect();
    refreshTimer = window.setInterval(() => {
      void refreshDashboard();
    }, 30000);

    return () => {
      if (refreshTimer) window.clearInterval(refreshTimer);
      if (reconnectTimer) window.clearTimeout(reconnectTimer);
      if (pingTimer) window.clearInterval(pingTimer);
      ws?.close();
    };
  }, []);

  useEffect(() => {
    if (selectedCategory || categories.length === 0) {
      return;
    }
    setSelectedCategory(categories[0].sector);
  }, [categories, selectedCategory]);

  useEffect(() => {
    if (!selectedCategory) {
      setNewsItems([]);
      setSelectedNewsId("");
      setInsight(null);
      return;
    }

    let active = true;

    const loadNews = async () => {
      setLoadingNews(true);
      try {
        const items = await fetchJson<NewsItem[]>(
          `${API}/news?category=${encodeURIComponent(selectedCategory)}&limit=10`,
        );
        if (!active) return;
        setNewsItems(items);
        setSelectedNewsId((current) => {
          const exists = items.some((item) => item.id === current);
          return exists ? current : (items[0]?.id ?? "");
        });
        setError("");
      } catch (exc) {
        if (!active) return;
        setNewsItems([]);
        setSelectedNewsId("");
        setInsight(null);
        setError(exc instanceof Error ? exc.message : "News load failed");
      } finally {
        if (active) {
          setLoadingNews(false);
        }
      }
    };

    void loadNews();
    return () => {
      active = false;
    };
  }, [selectedCategory]);

  useEffect(() => {
    if (!selectedNewsId) {
      setInsight(null);
      return;
    }

    let active = true;
    const loadInsight = async () => {
      setLoadingInsight(true);
      try {
        const data = await fetchJson<InsightData>(
          `${API}/events/insight?raw_event_id=${encodeURIComponent(selectedNewsId)}`,
        );
        if (!active) return;
        setInsight(data);
        setError("");
      } catch (exc) {
        if (!active) return;
        setInsight(null);
        setError(exc instanceof Error ? exc.message : "Insight load failed");
      } finally {
        if (active) {
          setLoadingInsight(false);
        }
      }
    };

    void loadInsight();
    return () => {
      active = false;
    };
  }, [selectedNewsId]);

  const runSelectedPipeline = async () => {
    if (!selectedNewsId) {
      return;
    }
    setRunningPipeline(true);
    try {
      await fetchJson(`${API}/pipeline/run_one?raw_event_id=${encodeURIComponent(selectedNewsId)}`, {
        method: "POST",
      });
      const [timelineData, heatmapData, insightData] = await Promise.all([
        fetchJson<TimelineEvent[]>(`${API}/timeline?limit=20`),
        fetchJson<HeatmapData>(`${API}/heatmap`),
        fetchJson<InsightData>(`${API}/events/insight?raw_event_id=${encodeURIComponent(selectedNewsId)}`),
      ]);
      setTimeline(timelineData);
      setHeatmap(heatmapData);
      setInsight(insightData);
      setLastUpdated(new Date().toISOString());
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Pipeline run failed");
    } finally {
      setRunningPipeline(false);
    }
  };

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(200,228,255,0.18),_transparent_28%),linear-gradient(180deg,_#09111d_0%,_#0d1726_38%,_#131f31_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-[1480px] flex-col gap-8 px-4 py-6 sm:px-6 lg:px-10">
        <header className="grid gap-5 rounded-[28px] border border-white/10 bg-white/6 p-6 shadow-[0_30px_90px_rgba(2,8,20,0.45)] backdrop-blur md:grid-cols-[1.6fr_1fr]">
          <div className="space-y-4">
            <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/80">Event-FX Sector Intelligence</p>
            <div className="space-y-2">
              <h1 className="font-['Space_Grotesk',_'Segoe_UI',_sans-serif] text-3xl font-semibold tracking-tight text-white sm:text-5xl">
                Live macro event console for FX bias and sector pressure.
              </h1>
              <p className="max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">
                LangGraph LLM normalization, semantic dedupe, and rule-engine scoring are now wired into the live backend.
                This dashboard pulls timeline, heatmap, and rationale surfaces from the same runtime path.
              </p>
            </div>
          </div>

          <div className="grid gap-3 rounded-[22px] border border-cyan-200/15 bg-slate-950/45 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-[0.24em] text-slate-400">Connection</span>
              <span
                className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
                  connectionStatus === "connected"
                    ? "bg-emerald-400/14 text-emerald-200"
                    : connectionStatus === "connecting"
                      ? "bg-amber-300/14 text-amber-100"
                      : "bg-rose-400/14 text-rose-200"
                }`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    connectionStatus === "connected"
                      ? "bg-emerald-300"
                      : connectionStatus === "connecting"
                        ? "bg-amber-200"
                        : "bg-rose-300"
                  }`}
                />
                {connectionStatus.toUpperCase()}
              </span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 md:grid-cols-1 lg:grid-cols-3">
              <MetricCard label="Timeline" value={timeline.length.toString()} note="latest scored events" />
              <MetricCard label="Heatmap" value={Object.keys(heatmap).length.toString()} note="tracked sectors" />
              <MetricCard label="Updated" value={timeAgo(lastUpdated)} note="dashboard refresh" />
            </div>
            {error ? (
              <div className="rounded-2xl border border-rose-300/20 bg-rose-500/8 px-4 py-3 text-sm text-rose-100">
                {error}
              </div>
            ) : null}
          </div>
        </header>

        <section className="grid gap-8 xl:grid-cols-[1.6fr_1fr]">
          <div className="grid gap-8">
            <FXMarketChart events={timeline} loading={loadingDashboard} />
            <MarketHeatmap heatmap={heatmap} loading={loadingDashboard} />
          </div>

          <aside className="grid gap-8">
            <section className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5 shadow-[0_20px_60px_rgba(2,8,20,0.34)]">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Signal Feed</p>
                  <h2 className="mt-2 text-lg font-semibold text-white">News queue and insight runner</h2>
                </div>
                <button
                  type="button"
                  onClick={runSelectedPipeline}
                  disabled={!selectedNewsId || runningPipeline}
                  className="rounded-full border border-cyan-300/30 bg-cyan-300/12 px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-100 transition hover:bg-cyan-300/18 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {runningPipeline ? "Running" : "Run One"}
                </button>
              </div>

              <label className="mb-3 block text-xs uppercase tracking-[0.22em] text-slate-500">
                Category
              </label>
              <select
                value={selectedCategory}
                onChange={(event) => setSelectedCategory(event.target.value)}
                className="mb-5 w-full rounded-2xl border border-white/10 bg-slate-900/80 px-4 py-3 text-sm text-slate-100 outline-none transition focus:border-cyan-300/40"
              >
                {categories.map((item) => (
                  <option key={item.sector} value={item.sector}>
                    {item.sector}
                  </option>
                ))}
              </select>

              <div className="grid max-h-[420px] gap-3 overflow-y-auto pr-1">
                {loadingNews ? (
                  <PanelState message="Loading news..." />
                ) : newsItems.length === 0 ? (
                  <PanelState message="No news items loaded." />
                ) : (
                  newsItems.map((item) => {
                    const selected = item.id === selectedNewsId;
                    return (
                      <div
                        key={item.id}
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedNewsId(item.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedNewsId(item.id);
                          }
                        }}
                        className={`cursor-pointer rounded-[22px] border p-4 text-left transition ${
                          selected
                            ? "border-cyan-300/40 bg-cyan-300/10"
                            : "border-white/8 bg-white/[0.03] hover:border-white/16 hover:bg-white/[0.05]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-semibold leading-6 text-white">{item.title}</p>
                          <span className="rounded-full bg-slate-900/80 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-slate-400">
                            {item.sector}
                          </span>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-slate-400">{item.summary || "Summary unavailable."}</p>
                        <div className="mt-3 flex items-center justify-between text-[11px] uppercase tracking-[0.18em] text-slate-500">
                          <span>{timeAgo(item.published_at)}</span>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                            className="text-cyan-200 hover:text-cyan-100"
                          >
                            Source
                          </a>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </section>

            <section className="rounded-[26px] border border-white/10 bg-slate-950/45 p-5 shadow-[0_20px_60px_rgba(2,8,20,0.34)]">
              <div className="mb-4">
                <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Insight</p>
                <h2 className="mt-2 text-lg font-semibold text-white">LLM reasoning surface</h2>
              </div>

              {loadingInsight ? (
                <PanelState message="Loading event insight..." />
              ) : !insight ? (
                <PanelState message="Select a news item to inspect its reasoning." />
              ) : (
                <div className="grid gap-4">
                  <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-4">
                    <a
                      href={insight.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-base font-semibold leading-7 text-white hover:text-cyan-200"
                    >
                      {insight.title}
                    </a>
                    <p className="mt-3 text-sm leading-7 text-slate-300">{insight.summary_ko}</p>
                  </div>
                  <InsightBlock title="Analysis Reason" content={insight.analysis_reason} />
                  <InsightBlock title="FX Reason" content={insight.fx_reason} />
                  <InsightBlock title="Heatmap Reason" content={insight.heatmap_reason} />
                </div>
              )}
            </section>
          </aside>
        </section>

        <section className="rounded-[28px] border border-white/10 bg-slate-950/45 p-5 shadow-[0_20px_60px_rgba(2,8,20,0.34)]">
          <div className="mb-5 flex items-end justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.28em] text-slate-500">Timeline</p>
              <h2 className="mt-2 text-xl font-semibold text-white">Recent scored events</h2>
            </div>
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">Refreshed by WebSocket and 30s poll</p>
          </div>

          {loadingDashboard ? (
            <PanelState message="Loading timeline..." />
          ) : timeline.length === 0 ? (
            <PanelState message="No scored events yet." />
          ) : (
            <div className="grid gap-3">
              {timeline.map((item, index) => (
                <article
                  key={`${item.title}-${index}`}
                  className="grid gap-3 rounded-[22px] border border-white/8 bg-white/[0.03] p-4 lg:grid-cols-[1.8fr_1fr]"
                >
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-slate-500">
                      <span>{timeAgo(item.published_at)}</span>
                      <span className="rounded-full bg-slate-900/70 px-2 py-1 text-slate-300">{item.sector}</span>
                    </div>
                    <a href={item.url} target="_blank" rel="noreferrer" className="text-base font-semibold leading-7 text-white hover:text-cyan-200">
                      {item.title}
                    </a>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <SignalPill label="Risk" value={item.risk_signal} tone={signalTone(item.risk_signal)} />
                    <SignalPill label="Rates" value={item.rate_signal} tone={signalTone(item.rate_signal)} />
                    <SignalPill label="Geo" value={item.geo_signal} tone={signalTone(item.geo_signal)} />
                    <SignalPill label="Score" value={item.total_score.toFixed(2)} tone={item.total_score >= 0 ? "positive" : "negative"} />
                    <div className="sm:col-span-2 rounded-2xl border border-white/8 bg-slate-900/80 px-4 py-3">
                      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">FX State</p>
                      <p className="mt-2 text-sm font-medium text-slate-100">{item.fx_state}</p>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function MetricCard({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-[18px] border border-white/8 bg-white/[0.04] px-4 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-400">{note}</p>
    </div>
  );
}

function PanelState({ message }: { message: string }) {
  return (
    <div className="flex min-h-36 items-center justify-center rounded-[22px] border border-dashed border-white/10 bg-white/[0.03] px-4 text-sm text-slate-400">
      {message}
    </div>
  );
}

function InsightBlock({ title, content }: { title: string; content: string }) {
  return (
    <div className="rounded-[22px] border border-white/8 bg-white/[0.03] p-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{title}</p>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-200">{content || "No content."}</p>
    </div>
  );
}

function SignalPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "positive" | "negative" | "neutral";
}) {
  const toneClass =
    tone === "positive"
      ? "border-emerald-300/20 bg-emerald-300/10 text-emerald-100"
      : tone === "negative"
        ? "border-rose-300/20 bg-rose-300/10 text-rose-100"
        : "border-white/8 bg-white/[0.03] text-slate-200";

  return (
    <div className={`rounded-2xl border px-4 py-3 ${toneClass}`}>
      <p className="text-[11px] uppercase tracking-[0.18em] opacity-70">{label}</p>
      <p className="mt-2 text-sm font-semibold">{value}</p>
    </div>
  );
}

function signalTone(value: string): "positive" | "negative" | "neutral" {
  if (value === "risk_on" || value === "easing" || value === "deescalation") {
    return "positive";
  }
  if (value === "risk_off" || value === "tightening" || value === "escalation") {
    return "negative";
  }
  return "neutral";
}
