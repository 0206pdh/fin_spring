package com.finintel.app.api;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

import com.finintel.app.ingest.ApNewsIngestService;
import com.finintel.app.llm.InsightService;
import com.finintel.app.llm.NormalizeService;
import com.finintel.app.model.NormalizedEvent;
import com.finintel.app.model.RawEvent;
import com.finintel.app.model.ScoredEvent;
import com.finintel.app.rules.RulesEngine;
import com.finintel.app.store.EventStore;

@Controller
public class ApiController {
    private static final Logger logger = LoggerFactory.getLogger(ApiController.class);

    private final EventStore eventStore;
    private final ApNewsIngestService ingestService;
    private final NormalizeService normalizeService;
    private final RulesEngine rulesEngine;
    private final InsightService insightService;

    public ApiController(EventStore eventStore, ApNewsIngestService ingestService,
            NormalizeService normalizeService, RulesEngine rulesEngine, InsightService insightService) {
        this.eventStore = eventStore;
        this.ingestService = ingestService;
        this.normalizeService = normalizeService;
        this.rulesEngine = rulesEngine;
        this.insightService = insightService;
    }

    @GetMapping("/")
    public String index() {
        return "forward:/index.html";
    }

    @GetMapping("/health")
    @ResponseBody
    public Map<String, String> health() {
        return Map.of("status", "ok");
    }

    @GetMapping("/categories")
    @ResponseBody
    public List<Map<String, String>> categories() {
        return ingestService.getCategories();
    }

    @GetMapping("/news")
    @ResponseBody
    public List<Map<String, Object>> news(@RequestParam("category") String category,
            @RequestParam(value = "limit", defaultValue = "10") int limit) {
        List<RawEvent> events = ingestService.fetchRawEvents(category, limit);
        eventStore.saveRawEvents(events);

        List<Map<String, Object>> response = new ArrayList<>();
        for (RawEvent event : events) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", event.getId());
            row.put("title", event.getTitle());
            row.put("url", event.getUrl());
            OffsetDateTime published = event.getPublishedAt();
            row.put("published_at", published != null ? published.toString() : null);
            row.put("sector", event.getSector());
            row.put("summary", newsSummary(event.getPayload()));
            response.add(row);
        }
        return response;
    }

    @PostMapping("/ingest/run")
    @ResponseBody
    public Map<String, Integer> ingestRun(@RequestParam(value = "category", required = false) String category,
            @RequestParam(value = "limit_per_category", defaultValue = "10") int limitPerCategory) {
        List<RawEvent> events = ingestService.fetchRawEvents(category, limitPerCategory);
        int inserted = eventStore.saveRawEvents(events);
        logger.info("Ingestion complete fetched={} inserted={}", events.size(), inserted);
        return Map.of("fetched", events.size(), "inserted", inserted);
    }

    @PostMapping("/events/normalize")
    @ResponseBody
    public Map<String, Integer> normalizeEvents(@RequestParam(value = "limit", defaultValue = "50") int limit) {
        List<RawEvent> rawEvents = eventStore.fetchUnprocessedRawEvents(limit);
        int count = 0;
        for (RawEvent rawEvent : rawEvents) {
            NormalizedEvent normalized = normalizeService.normalizeEvent(rawEvent);
            eventStore.saveNormalized(normalized);
            count++;
        }
        logger.info("Normalization complete normalized={}", count);
        return Map.of("normalized", count);
    }

    @PostMapping("/events/score")
    @ResponseBody
    public Map<String, Integer> scoreEvents(@RequestParam(value = "limit", defaultValue = "50") int limit) {
        List<NormalizedEvent> normalizedEvents = eventStore.fetchUnscoredEvents(limit);
        int count = 0;
        for (NormalizedEvent normalized : normalizedEvents) {
            ScoredEvent scored = rulesEngine.scoreEvent(normalized);
            eventStore.saveScored(scored);
            count++;
        }
        logger.info("Scoring complete scored={}", count);
        return Map.of("scored", count);
    }

    @PostMapping("/pipeline/run")
    @ResponseBody
    public Map<String, Integer> pipelineRun(
            @RequestParam(value = "category", required = false) String category,
            @RequestParam(value = "limit_per_category", defaultValue = "10") int limitPerCategory,
            @RequestParam(value = "limit", defaultValue = "50") int limit) {
        List<RawEvent> events = ingestService.fetchRawEvents(category, limitPerCategory);
        int inserted = eventStore.saveRawEvents(events);

        List<RawEvent> rawEvents = eventStore.fetchUnprocessedRawEvents(limit);
        int normalizedCount = 0;
        for (RawEvent rawEvent : rawEvents) {
            NormalizedEvent normalized = normalizeService.normalizeEvent(rawEvent);
            eventStore.saveNormalized(normalized);
            normalizedCount++;
        }

        List<NormalizedEvent> normalizedEvents = eventStore.fetchUnscoredEvents(limit);
        int scoredCount = 0;
        for (NormalizedEvent normalized : normalizedEvents) {
            ScoredEvent scored = rulesEngine.scoreEvent(normalized);
            eventStore.saveScored(scored);
            scoredCount++;
        }

        logger.info("Pipeline complete fetched={} inserted={} normalized={} scored={}",
            events.size(), inserted, normalizedCount, scoredCount);

        Map<String, Integer> response = new LinkedHashMap<>();
        response.put("fetched", events.size());
        response.put("inserted", inserted);
        response.put("normalized", normalizedCount);
        response.put("scored", scoredCount);
        return response;
    }

    @PostMapping("/pipeline/run_one")
    @ResponseBody
    public Map<String, Integer> pipelineRunOne(@RequestParam("raw_event_id") String rawEventId) {
        RawEvent rawEvent = eventStore.fetchRawEvent(rawEventId);
        if (rawEvent == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Raw event not found");
        }
        eventStore.resetScoredData();

        Map<String, String> details = Map.of();
        try {
            details = ingestService.fetchArticleDetails(rawEvent.getUrl());
        } catch (RuntimeException ex) {
            logger.warn("Article detail fetch failed: {}", ex.getMessage());
        }

        if (details != null && !details.isEmpty()) {
            Map<String, Object> payload = rawEvent.getPayload();
            if (payload != null) {
                Map<String, Object> detailsPayload = new LinkedHashMap<>();
                detailsPayload.put("title", details.getOrDefault("title", ""));
                detailsPayload.put("summary", details.getOrDefault("summary", ""));
                detailsPayload.put("text", details.getOrDefault("text", ""));
                payload.put("details", detailsPayload);

                if (details.get("published_at") != null) {
                    Object item = payload.get("item");
                    if (item instanceof Map<?, ?> itemMap) {
                        Map<String, Object> updated = new LinkedHashMap<>();
                        for (Map.Entry<?, ?> entry : itemMap.entrySet()) {
                            if (entry.getKey() != null) {
                                updated.put(entry.getKey().toString(), entry.getValue());
                            }
                        }
                        updated.put("published_at", details.get("published_at"));
                        payload.put("item", updated);
                    }
                }
                if (details.get("title") != null && !details.get("title").isBlank()) {
                    rawEvent.setTitle(details.get("title"));
                }
            }
        }

        NormalizedEvent normalized = normalizeService.normalizeEvent(rawEvent);
        eventStore.saveNormalized(normalized);
        ScoredEvent scored = rulesEngine.scoreEvent(normalized);
        eventStore.saveScored(scored);
        logger.info("Pipeline single complete raw_event_id={}", rawEventId);
        return Map.of("normalized", 1, "scored", 1);
    }

    @GetMapping("/timeline")
    @ResponseBody
    public List<Map<String, Object>> timeline(@RequestParam(value = "limit", defaultValue = "50") int limit) {
        return eventStore.listTimeline(limit);
    }

    @GetMapping("/heatmap")
    @ResponseBody
    public Map<String, Double> heatmap() {
        return eventStore.sectorHeatmap();
    }

    @GetMapping("/graph")
    @ResponseBody
    public List<Map<String, Object>> graph(@RequestParam(value = "limit", defaultValue = "100") int limit) {
        return eventStore.graphEdges(limit);
    }

    @GetMapping("/events/insight")
    @ResponseBody
    public Map<String, String> eventInsight(@RequestParam("raw_event_id") String rawEventId) {
        RawEvent rawEvent = eventStore.fetchRawEvent(rawEventId);
        if (rawEvent == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Raw event not found");
        }

        NormalizedEvent normalized = eventStore.fetchNormalizedEvent(rawEventId);
        ScoredEvent scored = eventStore.fetchScoredEvent(rawEventId);

        String summary = insightService.summarizeNews(rawEvent);
        if (summary.isBlank()) {
            summary = newsSummary(rawEvent.getPayload());
            if (summary.isBlank()) {
                summary = rawEvent.getTitle() != null ? rawEvent.getTitle() : "No summary available.";
            }
        }

        String analysis = insightService.generateAnalysis(normalized, scored);
        if (analysis.isBlank()) {
            analysis = insightService.buildAnalysisFallback(normalized, scored);
        }

        String fx = insightService.generateFx(normalized, scored);
        if (fx.isBlank()) {
            fx = insightService.buildFxFallback(normalized, scored);
        }

        String heatmap = insightService.generateHeatmap(normalized, scored);
        if (heatmap.isBlank()) {
            heatmap = insightService.buildHeatmapFallback(normalized, scored);
        }

        Map<String, String> response = new LinkedHashMap<>();
        response.put("id", rawEvent.getId());
        response.put("title", rawEvent.getTitle());
        response.put("url", rawEvent.getUrl());
        response.put("summary_ko", summary);
        response.put("analysis_reason", analysis);
        response.put("fx_reason", fx);
        response.put("heatmap_reason", heatmap);
        return response;
    }

    private String newsSummary(Map<String, Object> payload) {
        if (payload == null) {
            return "";
        }
        Object details = payload.get("details");
        Object item = payload.get("item");
        List<String> fields = List.of("summary", "description", "headline", "title", "body", "content", "text");
        for (Object source : List.of(details, item)) {
            if (source instanceof Map<?, ?> map) {
                for (String key : fields) {
                    Object value = map.get(key);
                    if (value != null && !value.toString().isBlank()) {
                        String text = value.toString();
                        return text.length() > 240 ? text.substring(0, 240) : text;
                    }
                }
            }
        }
        return "";
    }
}
