package com.finintel.app.llm;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

import org.springframework.stereotype.Service;

import com.finintel.app.model.NormalizedEvent;
import com.finintel.app.model.RawEvent;
import com.finintel.app.model.ScoredEvent;

@Service
public class InsightService {
    private static final String SUMMARY_SYSTEM_PROMPT =
        "You are a financial news summarizer. Summarize the provided news in Korean in 2-3 sentences. " +
        "Keep proper nouns and numbers. Avoid speculation.";

    private static final String SUMMARY_USER_TEMPLATE =
        "Summarize the following news in Korean in 2-3 sentences.\nNews:\n%s";

    private static final String ANALYSIS_SYSTEM_PROMPT =
        "You are a financial analyst. Explain why the analysis result is the way it is in Korean, " +
        "using 2-3 concise sentences. Avoid speculation.";

    private static final String ANALYSIS_USER_TEMPLATE =
        "Explain the analysis outcome in Korean in 2-3 sentences.\n" +
        "Event type: %s\n" +
        "Policy domain: %s\n" +
        "Risk signal: %s\n" +
        "Rate signal: %s\n" +
        "Geo signal: %s\n" +
        "Channels: %s\n" +
        "LLM rationale: %s\n" +
        "FX state: %s\n" +
        "Total score: %s";

    private static final String HEATMAP_SYSTEM_PROMPT =
        "You are a market strategist. Explain the heatmap outcome in Korean in 2-3 sentences, " +
        "referencing key sector winners/losers and signals. Avoid speculation.";

    private static final String HEATMAP_USER_TEMPLATE =
        "Explain the heatmap outcome in Korean in 2-3 sentences.\n" +
        "Top gainers: %s\n" +
        "Top losers: %s\n" +
        "Channels: %s\n" +
        "Event impacts: %s\n" +
        "Regime: %s";

    private static final String FX_SYSTEM_PROMPT =
        "You are an FX strategist. Explain the FX forecast outcome in Korean in 2-3 sentences, " +
        "based on the signals and channels. Avoid speculation.";

    private static final String FX_USER_TEMPLATE =
        "Explain the FX forecast outcome in Korean in 2-3 sentences.\n" +
        "FX state: %s\n" +
        "Risk signal: %s\n" +
        "Rate signal: %s\n" +
        "Geo signal: %s\n" +
        "Channels: %s\n" +
        "Regime: %s";

    private final LlmClient llmClient;
    private final NormalizeService normalizeService;

    public InsightService(LlmClient llmClient, NormalizeService normalizeService) {
        this.llmClient = llmClient;
        this.normalizeService = normalizeService;
    }

    public String summarizeNews(RawEvent rawEvent) {
        String text = normalizeService.extractDetailsText(rawEvent.getPayload());
        if (text.isBlank()) {
            text = rawEvent.getTitle() != null ? rawEvent.getTitle() : "";
        }
        if (text.isBlank()) {
            return "";
        }
        List<Map<String, String>> messages = List.of(
            Map.of("role", "system", "content", SUMMARY_SYSTEM_PROMPT),
            Map.of("role", "user", "content", String.format(SUMMARY_USER_TEMPLATE, text))
        );
        try {
            return readContent(llmClient.chat(messages));
        } catch (RuntimeException ex) {
            return "";
        }
    }

    public String generateAnalysis(NormalizedEvent normalized, ScoredEvent scored) {
        if (normalized == null && scored == null) {
            return "";
        }
        List<Map<String, String>> messages = List.of(
            Map.of("role", "system", "content", ANALYSIS_SYSTEM_PROMPT),
            Map.of("role", "user", "content", String.format(
                ANALYSIS_USER_TEMPLATE,
                normalized != null ? normalized.getEventType() : "unknown",
                normalized != null ? normalized.getPolicyDomain() : "unknown",
                normalized != null ? normalized.getRiskSignal() : "neutral",
                normalized != null ? normalized.getRateSignal() : "none",
                normalized != null ? normalized.getGeoSignal() : "none",
                normalized != null ? String.join(", ", normalized.getChannels()) : "",
                normalized != null ? normalized.getRationale() : "none",
                scored != null ? scored.getFxState() : "n/a",
                scored != null ? String.format("%.2f", scored.getTotalScore()) : "n/a"
            ))
        );
        try {
            return readContent(llmClient.chat(messages));
        } catch (RuntimeException ex) {
            return "";
        }
    }

    public String generateHeatmap(NormalizedEvent normalized, ScoredEvent scored) {
        if (scored == null || scored.getSectorScores() == null || scored.getSectorScores().isEmpty()) {
            return "";
        }
        List<Map.Entry<String, Double>> sorted = scored.getSectorScores().entrySet().stream()
            .sorted(Map.Entry.comparingByValue(Comparator.reverseOrder()))
            .collect(Collectors.toList());
        List<Map.Entry<String, Double>> positives = sorted.stream()
            .filter(entry -> entry.getValue() > 0)
            .limit(3)
            .collect(Collectors.toList());
        List<Map.Entry<String, Double>> negatives = new ArrayList<>(sorted);
        negatives.sort(Map.Entry.comparingByValue());
        negatives = negatives.stream().filter(entry -> entry.getValue() < 0).limit(3).collect(Collectors.toList());

        String topGainers = formatPairs(positives);
        String topLosers = formatPairs(negatives);

        List<Map<String, String>> messages = List.of(
            Map.of("role", "system", "content", HEATMAP_SYSTEM_PROMPT),
            Map.of("role", "user", "content", String.format(
                HEATMAP_USER_TEMPLATE,
                topGainers.isBlank() ? "none" : topGainers,
                topLosers.isBlank() ? "none" : topLosers,
                normalized != null ? String.join(", ", normalized.getChannels()) : "",
                normalized != null ? normalized.getSectorImpacts() : "{}",
                normalized != null ? normalized.getRegime() : "{}"
            ))
        );
        try {
            return readContent(llmClient.chat(messages));
        } catch (RuntimeException ex) {
            return "";
        }
    }

    public String generateFx(NormalizedEvent normalized, ScoredEvent scored) {
        if (scored == null) {
            return "";
        }
        List<Map<String, String>> messages = List.of(
            Map.of("role", "system", "content", FX_SYSTEM_PROMPT),
            Map.of("role", "user", "content", String.format(
                FX_USER_TEMPLATE,
                scored.getFxState() != null ? scored.getFxState() : "n/a",
                normalized != null ? normalized.getRiskSignal() : "neutral",
                normalized != null ? normalized.getRateSignal() : "none",
                normalized != null ? normalized.getGeoSignal() : "none",
                normalized != null ? String.join(", ", normalized.getChannels()) : "",
                normalized != null ? normalized.getRegime() : "{}"
            ))
        );
        try {
            return readContent(llmClient.chat(messages));
        } catch (RuntimeException ex) {
            return "";
        }
    }

    public String buildAnalysisFallback(NormalizedEvent normalized, ScoredEvent scored) {
        if (normalized == null && scored == null) {
            return "No analysis available yet. Run the pipeline first.";
        }
        List<String> parts = new ArrayList<>();
        if (normalized != null) {
            parts.add(String.format(
                "LLM classification: %s / %s. Signals: risk %s, rate %s, geo %s.",
                safe(normalized.getEventType(), "unknown"),
                safe(normalized.getPolicyDomain(), "unknown"),
                safe(normalized.getRiskSignal(), "neutral"),
                safe(normalized.getRateSignal(), "none"),
                safe(normalized.getGeoSignal(), "none")
            ));
            if (normalized.getChannels() != null && !normalized.getChannels().isEmpty()) {
                parts.add("Channels: " + String.join(", ", normalized.getChannels()) + ".");
            }
            if (normalized.getRationale() != null && !normalized.getRationale().isBlank()) {
                parts.add("Rationale: " + normalized.getRationale());
            }
        }
        if (scored != null) {
            parts.add(String.format("FX result: %s, total score %.2f.",
                safe(scored.getFxState(), "n/a"),
                scored.getTotalScore()));
        }
        return String.join("\n", parts).trim();
    }

    public String buildHeatmapFallback(NormalizedEvent normalized, ScoredEvent scored) {
        if (scored == null || scored.getSectorScores() == null || scored.getSectorScores().isEmpty()) {
            return "No heatmap result yet. Run the pipeline first.";
        }
        List<Map.Entry<String, Double>> sorted = scored.getSectorScores().entrySet().stream()
            .sorted(Map.Entry.comparingByValue(Comparator.reverseOrder()))
            .collect(Collectors.toList());
        List<Map.Entry<String, Double>> positives = sorted.stream()
            .filter(entry -> entry.getValue() > 0)
            .limit(3)
            .collect(Collectors.toList());
        List<Map.Entry<String, Double>> negatives = new ArrayList<>(sorted);
        negatives.sort(Map.Entry.comparingByValue());
        negatives = negatives.stream().filter(entry -> entry.getValue() < 0).limit(3).collect(Collectors.toList());

        List<String> lines = new ArrayList<>();
        lines.add("Heatmap blends FX bias, risk/rate/geo channels, and event impacts with regime adjustments.");
        if (normalized != null && normalized.getSectorImpacts() != null && !normalized.getSectorImpacts().isEmpty()) {
            String impacts = normalized.getSectorImpacts().entrySet().stream()
                .sorted((a, b) -> Integer.compare(Math.abs(b.getValue()), Math.abs(a.getValue())))
                .limit(3)
                .map(entry -> entry.getKey() + " " + String.format("%+d", entry.getValue()))
                .collect(Collectors.joining(", "));
            lines.add("Direct impacts: " + impacts + ".");
        }
        if (!positives.isEmpty()) {
            lines.add("Top gainers: " + formatPairs(positives) + ".");
        }
        if (!negatives.isEmpty()) {
            lines.add("Top losers: " + formatPairs(negatives) + ".");
        }
        return String.join("\n", lines).trim();
    }

    public String buildFxFallback(NormalizedEvent normalized, ScoredEvent scored) {
        if (scored == null) {
            return "No FX forecast yet. Run the pipeline first.";
        }
        List<String> signals = new ArrayList<>();
        if (normalized != null) {
            if (normalized.getRiskSignal() != null && !normalized.getRiskSignal().isBlank()) {
                signals.add("risk " + normalized.getRiskSignal());
            }
            if (normalized.getRateSignal() != null && !normalized.getRateSignal().isBlank()) {
                signals.add("rate " + normalized.getRateSignal());
            }
            if (normalized.getGeoSignal() != null && !normalized.getGeoSignal().isBlank()) {
                signals.add("geo " + normalized.getGeoSignal());
            }
        }
        String signalText = signals.isEmpty() ? "none" : String.join(", ", signals);
        return "FX state: " + safe(scored.getFxState(), "n/a") + ". Signals: " + signalText + ".";
    }

    private String readContent(Map<String, Object> response) {
        Object choices = response.get("choices");
        if (!(choices instanceof List<?> list) || list.isEmpty()) {
            return "";
        }
        Object choice0 = list.get(0);
        if (!(choice0 instanceof Map<?, ?> choiceMap)) {
            return "";
        }
        Object message = choiceMap.get("message");
        if (!(message instanceof Map<?, ?> msgMap)) {
            return "";
        }
        Object content = msgMap.get("content");
        return content != null ? content.toString().trim() : "";
    }

    private String formatPairs(List<Map.Entry<String, Double>> entries) {
        return entries.stream()
            .map(entry -> entry.getKey() + " " + String.format("%+.2f", entry.getValue()))
            .collect(Collectors.joining(", "));
    }

    private String safe(String value, String fallback) {
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value;
    }
}
