package com.finintel.app.llm;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Service;

import com.finintel.app.model.NormalizedEvent;
import com.finintel.app.model.RawEvent;

@Service
public class NormalizeService {
    private static final org.slf4j.Logger logger = org.slf4j.LoggerFactory.getLogger(NormalizeService.class);
    private static final String SYSTEM_PROMPT =
        "You are an event normalizer for macro, geopolitics, and policy news. " +
        "Read the full input as one document and return a single JSON object " +
        "covering the overall event. Return a single valid JSON object with the " +
        "schema exactly as requested. Do not include any extra text before or " +
        "after the JSON. Always end the response with a closing brace }.";

    private static final String USER_TEMPLATE = "\n" +
        "Raw event title: %s\n" +
        "Sector tag: %s\n" +
        "Published at: %s\n" +
        "Category url: %s\n" +
        "Details: %s\n\n" +
        "Extract a normalized event JSON with this schema:\n" +
        "{\n" +
        "  \"event_type\": \"string\",\n" +
        "  \"policy_domain\": \"monetary|fiscal|geopolitics|industry\",\n" +
        "  \"risk_signal\": \"risk_on|risk_off|neutral\",\n" +
        "  \"rate_signal\": \"tightening|easing|none\",\n" +
        "  \"geo_signal\": \"escalation|deescalation|none\",\n" +
        "  \"channels\": [\"string\"],\n" +
        "  \"confidence\": 0.0,\n" +
        "  \"regime\": {\n" +
        "    \"risk_sentiment\": \"risk_on|risk_off|neutral\",\n" +
        "    \"volatility\": \"low|elevated|high\",\n" +
        "    \"liquidity\": \"loose|neutral|tight\"\n" +
        "  },\n" +
        "  \"keywords\": [\"string\"],\n" +
        "  \"rationale\": \"string\"\n" +
        "}\n\n" +
        "Constraints:\n" +
        "- Do not include extra keys beyond the schema.\n" +
        "- Read the full input once (not per sentence or per paragraph).\n" +
        "- Return exactly one JSON object for the overall event. Do not repeat keys.\n" +
        "- Always end the response with a closing brace }.\n" +
        "- policy_domain must be one of: monetary, fiscal, geopolitics, industry.\n" +
        " - risk_signal must be one of: risk_on, risk_off, neutral.\n" +
        " - rate_signal must be one of: tightening, easing, none.\n" +
        " - geo_signal must be one of: escalation, deescalation, none.\n" +
        " - channels must be selected from: risk_off, risk_on, rate_tightening, rate_easing, geo_escalation, geo_deescalation.\n" +
        " - confidence must be between 0 and 1.\n" +
        " - regime must include risk_sentiment, volatility, and liquidity with the allowed values above.\n" +
        " - keywords must be a short list of salient terms from the article.\n" +
        "- rationale must explicitly justify why risk_signal and geo_signal are chosen based on concrete evidence.\n\n" +
        "Risk assessment rules:\n" +
        "- risk_signal is NOT determined only by event_type.\n" +
        "- regulation_update can be risk_off if:\n" +
        "  * legal enforcement, investigation, fines, or bans are mentioned\n" +
        "  * strong public backlash or reputational damage is described\n" +
        "  * multiple countries or regulators are involved\n" +
        "- regulation_update is neutral ONLY if it is a routine or clarifying policy change.\n\n" +
        "Geo assessment rules:\n" +
        "- geo_signal is escalation if:\n" +
        "  * multiple countries, regions, or global regulators are involved\n" +
        "  * cross-border enforcement, bans, or coordinated actions are mentioned\n" +
        "- geo_signal is none ONLY if the event is confined to a single country or company.\n\n" +
        "Before producing the final JSON, internally evaluate:\n" +
        "1. Is this event likely to increase uncertainty or regulatory pressure?\n" +
        "2. Does it introduce downside risk to a sector or platform?\n" +
        "3. Is the impact localized or global?\n" +
        "- event_type must be one of:\n" +
        "  geopolitics_conflict, war_escalation, terror_attack, monetary_tightening,\n" +
        "  inflation_hot, banking_stress, trade_sanction, recession_signal,\n" +
        "  monetary_easing, stimulus, inflation_cooling, earnings_positive, ceasefire,\n" +
        "  policy_stability, regulation_update.\n" +
        "- event_type implies risk_signal (use these pairs):\n" +
        "  geopolitics_conflict=risk_off, war_escalation=risk_off, terror_attack=risk_off,\n" +
        "  monetary_tightening=risk_off, inflation_hot=risk_off, banking_stress=risk_off,\n" +
        "  trade_sanction=risk_off, recession_signal=risk_off, monetary_easing=risk_on,\n" +
        "  stimulus=risk_on, inflation_cooling=risk_on, earnings_positive=risk_on,\n" +
        "  ceasefire=risk_on, policy_stability=neutral, regulation_update=neutral.\n" +
        "- If unsure, choose policy_stability and neutral signals.\n\n" +
        "Example output (format only, values must be from allowed lists):\n" +
        "{\n" +
        "  \"event_type\": \"policy_stability\",\n" +
        "  \"policy_domain\": \"industry\",\n" +
        "  \"risk_signal\": \"neutral\",\n" +
        "  \"rate_signal\": \"none\",\n" +
        "  \"geo_signal\": \"none\",\n" +
        "  \"channels\": [\"risk_off\"],\n" +
        "  \"confidence\": 0.6,\n" +
        "  \"regime\": {\n" +
        "    \"risk_sentiment\": \"neutral\",\n" +
        "    \"volatility\": \"elevated\",\n" +
        "    \"liquidity\": \"neutral\"\n" +
        "  },\n" +
        "  \"keywords\": [\"policy\", \"markets\"],\n" +
        "  \"rationale\": \"Article lacks clear macro shocks, so defaults to policy stability.\"\n" +
        "}";

    private static final Map<String, String> EVENT_TYPE_RISK_SIGNAL = Map.ofEntries(
        Map.entry("geopolitics_conflict", "risk_off"),
        Map.entry("war_escalation", "risk_off"),
        Map.entry("terror_attack", "risk_off"),
        Map.entry("monetary_tightening", "risk_off"),
        Map.entry("inflation_hot", "risk_off"),
        Map.entry("banking_stress", "risk_off"),
        Map.entry("trade_sanction", "risk_off"),
        Map.entry("recession_signal", "risk_off"),
        Map.entry("monetary_easing", "risk_on"),
        Map.entry("stimulus", "risk_on"),
        Map.entry("inflation_cooling", "risk_on"),
        Map.entry("earnings_positive", "risk_on"),
        Map.entry("ceasefire", "risk_on"),
        Map.entry("policy_stability", "neutral"),
        Map.entry("regulation_update", "neutral")
    );

    private static final Set<String> ALLOWED_EVENT_TYPES = EVENT_TYPE_RISK_SIGNAL.keySet();
    private static final Set<String> ALLOWED_POLICY_DOMAINS = Set.of("monetary", "fiscal", "geopolitics", "industry");
    private static final Set<String> ALLOWED_RISK_SIGNALS = Set.of("risk_on", "risk_off", "neutral");
    private static final Set<String> ALLOWED_RATE_SIGNALS = Set.of("tightening", "easing", "none");
    private static final Set<String> ALLOWED_GEO_SIGNALS = Set.of("escalation", "deescalation", "none");

    private final LlmClient llmClient;

    public NormalizeService(LlmClient llmClient) {
        this.llmClient = llmClient;
    }

    public NormalizedEvent normalizeEvent(RawEvent rawEvent) {
        String[] detailSummary = detailsSummary(rawEvent.getPayload());
        String userPrompt = String.format(USER_TEMPLATE,
            safe(rawEvent.getTitle()),
            safe(rawEvent.getSector()),
            rawEvent.getPublishedAt(),
            detailSummary[1],
            detailSummary[0]
        );

        List<Map<String, String>> messages = new ArrayList<>();
        messages.add(Map.of("role", "system", "content", SYSTEM_PROMPT));
        messages.add(Map.of("role", "user", "content", userPrompt));

        Map<String, Object> data;
        try {
            data = llmClient.extractJson(messages);
        } catch (RuntimeException ex) {
            logger.warn("LLM normalization failed, falling back to defaults: {}", ex.getMessage());
            data = new HashMap<>();
        }

        String eventType = normalizeToken(data.get("event_type"), "policy_stability");
        String policyDomain = normalizeToken(data.get("policy_domain"), "industry");
        String riskSignal = normalizeToken(data.get("risk_signal"), "neutral");
        String rateSignal = normalizeToken(data.get("rate_signal"), "none");
        String geoSignal = normalizeToken(data.get("geo_signal"), "none");

        if (!ALLOWED_EVENT_TYPES.contains(eventType)) {
            eventType = "policy_stability";
        }
        if (!ALLOWED_POLICY_DOMAINS.contains(policyDomain)) {
            policyDomain = "industry";
        }
        if (!ALLOWED_RISK_SIGNALS.contains(riskSignal)) {
            riskSignal = "neutral";
        }
        if (!ALLOWED_RATE_SIGNALS.contains(rateSignal)) {
            rateSignal = "none";
        }
        if (!ALLOWED_GEO_SIGNALS.contains(geoSignal)) {
            geoSignal = "none";
        }

        if ("neutral".equals(riskSignal)) {
            String mapped = EVENT_TYPE_RISK_SIGNAL.get(eventType);
            if (mapped != null) {
                riskSignal = mapped;
            }
        }

        NormalizedEvent normalized = new NormalizedEvent();
        normalized.setRawEventId(rawEvent.getId());
        normalized.setEventType(eventType);
        normalized.setPolicyDomain(policyDomain);
        normalized.setRiskSignal(riskSignal);
        normalized.setRateSignal(rateSignal);
        normalized.setGeoSignal(geoSignal);
        normalized.setSectorImpacts(readIntMap(data.get("sector_impacts")));
        normalized.setSentiment(safe(data.get("sentiment"), "neutral"));
        normalized.setRationale(safe(data.get("rationale"), "").trim());
        normalized.setChannels(readStringList(data.get("channels")));
        normalized.setConfidence(readDouble(data.get("confidence"), 0.6));
        normalized.setRegime(readStringMap(data.get("regime")));
        return normalized;
    }

    public String extractDetailsText(Map<String, Object> payload) {
        String[] summary = detailsSummary(payload);
        return summary[0];
    }

    private String[] detailsSummary(Map<String, Object> payload) {
        String categoryUrl = "";
        if (payload != null && payload.get("category_url") != null) {
            categoryUrl = payload.get("category_url").toString();
        }
        Object details = payload != null ? payload.get("details") : null;
        if (!(details instanceof Map<?, ?> detailMap)) {
            return new String[] {"", categoryUrl};
        }
        List<String> fields = List.of("title", "headline", "description", "summary", "body", "content", "text");
        List<String> parts = new ArrayList<>();
        for (String key : fields) {
            Object value = detailMap.get(key);
            if (value != null && !value.toString().isBlank()) {
                parts.add(value.toString());
            }
        }
        for (String containerKey : List.of("article", "data", "result")) {
            Object container = detailMap.get(containerKey);
            if (container instanceof Map<?, ?> containerMap) {
                for (String key : fields) {
                    Object value = containerMap.get(key);
                    if (value != null && !value.toString().isBlank()) {
                        parts.add(value.toString());
                    }
                }
            }
        }
        if (parts.isEmpty()) {
            return new String[] {"", categoryUrl};
        }
        List<String> trimmed = new ArrayList<>();
        for (int i = 0; i < Math.min(parts.size(), 3); i++) {
            String text = parts.get(i).trim();
            if (text.length() > 350) {
                text = text.substring(0, 350);
            }
            trimmed.add(text);
        }
        String summary = String.join(" | ", trimmed);
        if (summary.length() > 900) {
            summary = summary.substring(0, 900);
        }
        return new String[] {summary, categoryUrl};
    }

    private String normalizeToken(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String normalized = value.toString().trim().toLowerCase().replace("-", "_").replace(" ", "_");
        return normalized.isBlank() ? fallback : normalized;
    }

    private String safe(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String text = value.toString();
        return text.isBlank() ? fallback : text;
    }

    private String safe(String value) {
        return value == null ? "" : value;
    }

    private Map<String, Integer> readIntMap(Object value) {
        if (!(value instanceof Map<?, ?> map)) {
            return new HashMap<>();
        }
        Map<String, Integer> result = new HashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            String key = entry.getKey().toString();
            Object v = entry.getValue();
            try {
                result.put(key, Integer.parseInt(v.toString()));
            } catch (NumberFormatException ex) {
                // ignore
            }
        }
        return result;
    }

    private Map<String, String> readStringMap(Object value) {
        if (!(value instanceof Map<?, ?> map)) {
            return new HashMap<>();
        }
        Map<String, String> result = new HashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            result.put(entry.getKey().toString(), entry.getValue() == null ? "" : entry.getValue().toString());
        }
        return result;
    }

    private List<String> readStringList(Object value) {
        List<String> result = new ArrayList<>();
        if (!(value instanceof List<?> list)) {
            return result;
        }
        for (Object item : list) {
            if (item != null && !item.toString().isBlank()) {
                result.add(item.toString());
            }
        }
        return result;
    }

    private double readDouble(Object value, double fallback) {
        if (value == null) {
            return fallback;
        }
        try {
            return Double.parseDouble(value.toString());
        } catch (NumberFormatException ex) {
            return fallback;
        }
    }
}
