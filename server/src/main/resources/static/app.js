const statusEl = document.getElementById("status");
const runBtn = document.getElementById("runPipeline");
const refreshBtn = document.getElementById("refreshViews");
const categorySelect = document.getElementById("categorySelect");
const newsList = document.getElementById("newsList");
const marketHeatmapEl = document.getElementById("marketHeatmap");
const fxPredictionEl = document.getElementById("fxPrediction");
const insightTitleEl = document.getElementById("insightTitle");
const insightSummaryEl = document.getElementById("insightSummary");
const insightAnalysisEl = document.getElementById("insightAnalysis");
const insightFxEl = document.getElementById("insightFx");
const insightHeatmapEl = document.getElementById("insightHeatmap");
let selectedNewsId = "";
let lastHeatmapScores = {};

async function fetchJson(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Request failed");
  }
  return response.json();
}

function setStatus(message) {
  statusEl.textContent = message;
}

function setRunState() {
  runBtn.disabled = !selectedNewsId;
}

function setInsightEmpty(message) {
  if (insightTitleEl) {
    insightTitleEl.textContent = message || "No news selected.";
  }
  if (insightSummaryEl) {
    insightSummaryEl.textContent = "Select a news item to see the summary.";
  }
  if (insightAnalysisEl) {
    insightAnalysisEl.textContent = "No analysis yet.";
  }
  if (insightFxEl) {
    insightFxEl.textContent = "No FX rationale yet.";
  }
  if (insightHeatmapEl) {
    insightHeatmapEl.textContent = "No heatmap rationale yet.";
  }
}

function renderInsight(data, fallbackTitle) {
  if (!data) {
    setInsightEmpty();
    return;
  }
  if (insightTitleEl) {
    insightTitleEl.textContent = data.title || fallbackTitle || "Selected news";
  }
  if (insightSummaryEl) {
    insightSummaryEl.textContent = data.summary_ko || data.summary || "Summary unavailable.";
  }
  if (insightAnalysisEl) {
    insightAnalysisEl.textContent = data.analysis_reason || "No analysis yet.";
  }
  if (insightFxEl) {
    insightFxEl.textContent = data.fx_reason || "No FX rationale yet.";
  }
  if (insightHeatmapEl) {
    insightHeatmapEl.textContent = data.heatmap_reason || "No heatmap rationale yet.";
  }
}

async function loadInsight(rawEventId, fallbackTitle) {
  if (!rawEventId) {
    setInsightEmpty();
    return;
  }
  setStatus("Loading insight...");
  const start = performance.now();
  console.log("Loading insight for", rawEventId);
  if (insightSummaryEl) {
    insightSummaryEl.textContent = "Generating summary...";
  }
  if (insightAnalysisEl) {
    insightAnalysisEl.textContent = "Generating analysis...";
  }
  if (insightFxEl) {
    insightFxEl.textContent = "Generating FX rationale...";
  }
  if (insightHeatmapEl) {
    insightHeatmapEl.textContent = "Generating heatmap rationale...";
  }
  try {
    const data = await fetchJson(`/events/insight?raw_event_id=${encodeURIComponent(rawEventId)}`);
    console.log("Insight response", data);
    renderInsight(data, fallbackTitle);
    const elapsedMs = performance.now() - start;
    console.log(`Insight UI latency ${elapsedMs.toFixed(0)}ms`);
    setStatus(`Insight loaded (${(elapsedMs / 1000).toFixed(2)}s)`);
  } catch (err) {
    console.error("Insight error", err);
    renderInsight(
      {
        summary_ko: "Failed to generate summary.",
        analysis_reason: "Failed to generate analysis.",
        fx_reason: "Failed to generate FX rationale.",
        heatmap_reason: "Failed to generate heatmap rationale.",
      },
      fallbackTitle
    );
    const elapsedMs = performance.now() - start;
    console.log(`Insight UI error latency ${elapsedMs.toFixed(0)}ms`);
    setStatus(`Insight error: ${err.message}`);
  }
}

function renderNews(items) {
  if (!newsList) {
    return;
  }
  newsList.innerHTML = "";
  if (!items || !items.length) {
    newsList.innerHTML = "<div class=\"news-item\">No news items yet.</div>";
    setInsightEmpty();
    return;
  }
  items.forEach((item) => {
    const el = document.createElement("div");
    el.className = "news-item";
    el.dataset.id = item.id;

    const title = document.createElement("div");
    title.className = "news-item-title";
    title.textContent = item.title || "Untitled";

    const meta = document.createElement("div");
    meta.className = "news-item-meta";
    meta.textContent = `${item.published_at} - ${item.sector}`;

    const link = document.createElement("a");
    link.className = "news-item-link";
    link.href = item.url || "#";
    link.target = "_blank";
    link.rel = "noreferrer";
    link.textContent = item.url || "Open link";

    const summary = document.createElement("div");
    summary.className = "news-item-summary";
    summary.textContent = item.summary || "";

    el.appendChild(title);
    el.appendChild(meta);
    el.appendChild(link);
    el.appendChild(summary);

    el.addEventListener("click", () => {
      selectedNewsId = item.id;
      document.querySelectorAll(".news-item").forEach((node) => {
        node.classList.toggle("selected", node.dataset.id === item.id);
      });
      setRunState();
      loadInsight(item.id, item.title);
    });
    newsList.appendChild(el);
  });

  if (!selectedNewsId) {
    selectedNewsId = items[0].id;
  }
  document.querySelectorAll(".news-item").forEach((node) => {
    node.classList.toggle("selected", node.dataset.id === selectedNewsId);
  });
  setRunState();
  const selectedItem = items.find((item) => item.id === selectedNewsId) || items[0];
  loadInsight(selectedNewsId, selectedItem?.title);
}

async function loadNews(category) {
  if (!category) {
    if (newsList) {
      newsList.innerHTML = "";
    }
    return;
  }
  setStatus("Loading news...");
  try {
    const data = await fetchJson(`/news?category=${encodeURIComponent(category)}&limit=10`);
    renderNews(data);
    setStatus("News loaded.");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

function renderTimeline(items) {
  const container = document.getElementById("timeline");
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = "<div class=\"timeline-item\">No scored events yet.</div>";
    return;
  }
  items.forEach((item) => {
    const el = document.createElement("div");
    el.className = "timeline-item";
    el.innerHTML = `
      <a href="${item.url}" target="_blank" rel="noreferrer">${item.title}</a>
      <div class="timeline-meta">
        <span>${item.published_at}</span>
        <span>${item.sector}</span>
        <span>${item.risk_signal}</span>
        <span>${item.rate_signal}</span>
        <span>${item.geo_signal}</span>
        <span>${item.fx_state}</span>
        <span>${item.sentiment}</span>
        <span>Score ${item.total_score}</span>
      </div>
    `;
    container.appendChild(el);
  });
}

function renderHeatmap(map) {
  const container = document.getElementById("heatmap");
  container.innerHTML = "";
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    container.innerHTML = "<div class=\"heatmap-item\">No sector scores yet.</div>";
    return;
  }
  entries.forEach(([sector, score]) => {
    const el = document.createElement("div");
    el.className = "heatmap-item";
    el.innerHTML = `
      <span>${sector}</span>
      <span class="score">${score}</span>
    `;
    container.appendChild(el);
  });
}

function parseFxState(state) {
  const result = { USD: 0, JPY: 0, EUR: 0, EM: 0 };
  if (!state) {
    return result;
  }
  state.split(" ").forEach((chunk) => {
    const [key, value] = chunk.split(":");
    if (!key || value === undefined) {
      return;
    }
    const parsed = Number.parseFloat(value);
    if (!Number.isNaN(parsed) && key in result) {
      result[key] = parsed;
    }
  });
  return result;
}

function renderFxPrediction(items) {
  if (!fxPredictionEl) {
    return;
  }
  fxPredictionEl.innerHTML = "";
  if (!items.length) {
    fxPredictionEl.innerHTML = "<div class=\"fx-card\">No scored events yet.</div>";
    return;
  }
  const latest = items[0];
  const bias = parseFxState(latest.fx_state || "");
  const maxAbs = Math.max(1, ...Object.values(bias).map((value) => Math.abs(value)));
  const card = document.createElement("div");
  card.className = "fx-card";
  card.innerHTML = `
    <h3>${latest.title || "Latest event"}</h3>
    <div class="fx-meta"></div>
  `;
  ["USD", "JPY", "EUR", "EM"].forEach((currency) => {
    const value = bias[currency] || 0;
    const width = Math.round((Math.abs(value) / maxAbs) * 50);
    const row = document.createElement("div");
    row.className = "fx-row";
    const displayValue = value.toFixed(2);
    row.innerHTML = `
      <div>${currency}</div>
      <div class="fx-bar">
        <div class="fx-bar-fill ${value > 0 ? "positive" : value < 0 ? "negative" : "neutral"}" style="width: ${width}%"></div>
      </div>
      <div>${value >= 0 ? `+${displayValue}` : displayValue}</div>
    `;
    card.appendChild(row);
  });
  fxPredictionEl.appendChild(card);
}

async function refresh() {
  try {
    const [timeline, heatmap, categories] = await Promise.all([
      fetchJson("/timeline"),
      fetchJson("/heatmap"),
      fetchJson("/categories"),
    ]);
    renderTimeline(timeline);
    renderHeatmap(heatmap);
    lastHeatmapScores = heatmap || {};
    renderMarketHeatmap(lastHeatmapScores);
    renderFxPrediction(timeline);
    renderCategories(categories);
    if (selectedNewsId) {
      loadInsight(selectedNewsId);
    }
    setStatus("Views refreshed.");
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

runBtn.addEventListener("click", async () => {
  if (!selectedNewsId) {
    setStatus("Select a news item first.");
    return;
  }
  setStatus("Running pipeline for selected news...");
  try {
    const selected = encodeURIComponent(selectedNewsId);
    await fetchJson(`/pipeline/run_one?raw_event_id=${selected}`, { method: "POST" });
    setStatus("Pipeline complete.");
    await refresh();
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
});

refreshBtn.addEventListener("click", refresh);

refresh();
setInsightEmpty();

function renderCategories(items) {
  if (categorySelect) {
    if (!items || !items.length) {
      categorySelect.innerHTML = "<option value=\"\">No categories</option>";
      runBtn.disabled = true;
      return;
    }
    categorySelect.innerHTML = "<option value=\"\">Select a category</option>";
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.sector || "";
      option.textContent = item.sector || "Unknown";
      categorySelect.appendChild(option);
    });
  }
}

if (categorySelect) {
  categorySelect.addEventListener("change", () => {
    selectedNewsId = "";
    setRunState();
    setInsightEmpty("No news selected.");
    loadNews(categorySelect.value);
  });
}

setRunState();

function getHeatmapColor(change) {
  if (change >= 2) return "#10b981";
  if (change >= 1) return "#34d399";
  if (change > -1) return "#374151";
  if (change >= -2) return "#fb923c";
  if (change >= -3) return "#f87171";
  return "#ef4444";
}

function worstAspectRatio(row, rowArea, length) {
  if (!row.length) {
    return Infinity;
  }
  const maxArea = Math.max(...row.map((item) => item.area));
  const minArea = Math.min(...row.map((item) => item.area));
  const lengthSquared = length * length;
  return Math.max((lengthSquared * maxArea) / (rowArea * rowArea), (rowArea * rowArea) / (lengthSquared * minArea));
}

function layoutRow(row, x, y, width, height, rects) {
  const rowArea = row.reduce((sum, item) => sum + item.area, 0);
  if (width >= height) {
    const rowHeight = rowArea / width;
    let offsetX = x;
    row.forEach((item) => {
      const itemWidth = item.area / rowHeight;
      rects.push({
        ...item,
        x: offsetX,
        y,
        width: itemWidth,
        height: rowHeight,
      });
      offsetX += itemWidth;
    });
    return { x, y: y + rowHeight, width, height: height - rowHeight };
  }
  const rowWidth = rowArea / height;
  let offsetY = y;
  row.forEach((item) => {
    const itemHeight = item.area / rowWidth;
    rects.push({
      ...item,
      x,
      y: offsetY,
      width: rowWidth,
      height: itemHeight,
    });
    offsetY += itemHeight;
  });
  return { x: x + rowWidth, y, width: width - rowWidth, height };
}

function squarify(items, x, y, width, height) {
  const rects = [];
  let remaining = items.slice();
  let row = [];
  let container = { x, y, width, height };
  let shortSide = Math.min(width, height);

  while (remaining.length) {
    const item = remaining[0];
    const newRow = row.concat(item);
    const rowArea = newRow.reduce((sum, entry) => sum + entry.area, 0);
    if (row.length === 0 || worstAspectRatio(row, row.reduce((sum, entry) => sum + entry.area, 0), shortSide) >= worstAspectRatio(newRow, rowArea, shortSide)) {
      row = newRow;
      remaining = remaining.slice(1);
    } else {
      container = layoutRow(row, container.x, container.y, container.width, container.height, rects);
      shortSide = Math.min(container.width, container.height);
      row = [];
    }
  }
  if (row.length) {
    layoutRow(row, container.x, container.y, container.width, container.height, rects);
  }
  return rects;
}

function renderMarketHeatmap(scores) {
  if (!marketHeatmapEl) {
    return;
  }
  const entries = Object.entries(scores || {}).filter(([, value]) => Number.isFinite(value));
  if (!entries.length) {
    marketHeatmapEl.innerHTML = "<div class=\"heatmap-empty\">No sector scores yet.</div>";
    return;
  }
  const bounds = marketHeatmapEl.getBoundingClientRect();
  const width = bounds.width || 900;
  const height = bounds.height || 560;
  const totalSize = entries.reduce((sum, [, value]) => sum + Math.max(0.1, Math.abs(value)), 0);
  const items = entries
    .map(([sector, value]) => ({
      sector,
      value,
      area: (Math.max(0.1, Math.abs(value)) / totalSize) * width * height,
    }))
    .sort((a, b) => Math.abs(b.value) - Math.abs(a.value));
  const rects = squarify(items, 0, 0, width, height);
  marketHeatmapEl.innerHTML = "";
  rects.forEach((rect) => {
    const div = document.createElement("div");
    div.className = "treemap-item";
    div.style.left = `${rect.x}px`;
    div.style.top = `${rect.y}px`;
    div.style.width = `${rect.width}px`;
    div.style.height = `${rect.height}px`;
    div.style.background = getHeatmapColor(rect.value);
    const formatted = rect.value >= 0 ? `+${rect.value.toFixed(3)}` : rect.value.toFixed(3);
    const label = `${rect.sector}`;
    const maxLabelWidth = Math.max(1, rect.width - 12);
    const maxLabelHeight = Math.max(1, rect.height - 12);
    const approxFont = Math.min(
      14,
      Math.max(9, Math.floor(Math.min(maxLabelWidth / Math.max(6, label.length * 0.6), maxLabelHeight / 3)))
    );
    div.style.fontSize = `${approxFont}px`;
    div.title = `${rect.sector} ${formatted}`;
    div.innerHTML = `${label}<small>${formatted}</small>`;
    marketHeatmapEl.appendChild(div);
  });
}

renderMarketHeatmap(lastHeatmapScores);
window.addEventListener("resize", () => {
  renderMarketHeatmap(lastHeatmapScores);
});
