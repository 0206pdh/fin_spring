package com.finintel.app.rules;

import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.finintel.app.model.NormalizedEvent;
import com.finintel.app.model.ScoredEvent;

@Component
public class RulesEngine {
    public ScoredEvent scoreEvent(NormalizedEvent event) {
        List<String> channels = normalizeChannels(event);
        double confidence = normalizeConfidence(event.getConfidence());
        Map<String, String> regime = normalizeRegime(event.getRegime());
        Map<String, Double> baseline = event.getBaseline() != null ? event.getBaseline() : new HashMap<>();

        Map<String, Double> fxDelta = Weights.computeFxDelta(channels, confidence);
        String fxState = formatFxState(fxDelta);
        Map<String, Double> sectorDelta = Weights.computeSectorDeltaFromFx(fxDelta);
        sectorDelta = Weights.applyRiskSectorRules(sectorDelta, channels, confidence);
        sectorDelta = applyEventImpacts(sectorDelta, event.getSectorImpacts(), confidence);
        Map<String, Double> sectorScores = Weights.combineBaselineDelta(baseline, sectorDelta, regime);
        double totalScore = sectorScores.values().stream().mapToDouble(Double::doubleValue).sum();

        ScoredEvent scored = new ScoredEvent();
        scored.setRawEventId(event.getRawEventId());
        scored.setEventType(event.getEventType());
        scored.setPolicyDomain(event.getPolicyDomain());
        scored.setRiskSignal(event.getRiskSignal());
        scored.setRateSignal(event.getRateSignal());
        scored.setGeoSignal(event.getGeoSignal());
        scored.setSectorImpacts(event.getSectorImpacts());
        scored.setSentiment(event.getSentiment());
        scored.setRationale(event.getRationale());
        scored.setFxState(fxState);
        scored.setSectorScores(sectorScores);
        scored.setTotalScore(totalScore);
        scored.setCreatedAt(OffsetDateTime.now());
        scored.setChannels(new ArrayList<>(channels));
        scored.setConfidence(confidence);
        scored.setRegime(new HashMap<>(regime));
        scored.setBaseline(new HashMap<>(baseline));
        return scored;
    }

    private List<String> normalizeChannels(NormalizedEvent event) {
        List<String> channels = new ArrayList<>();
        if (event.getChannels() != null) {
            for (String channel : event.getChannels()) {
                if (Weights.FX_TRANSMISSION_CHANNELS.contains(channel) && !channels.contains(channel)) {
                    channels.add(channel);
                }
            }
        }
        for (String channel : signalChannels(event)) {
            if (Weights.FX_TRANSMISSION_CHANNELS.contains(channel) && !channels.contains(channel)) {
                channels.add(channel);
            }
        }
        return channels;
    }

    private List<String> signalChannels(NormalizedEvent event) {
        List<String> channels = new ArrayList<>();
        if (event.getRiskSignal() != null && !event.getRiskSignal().isBlank()) {
            channels.add(event.getRiskSignal().toLowerCase());
        }
        if ("tightening".equals(event.getRateSignal())) {
            channels.add("rate_tightening");
        }
        if ("easing".equals(event.getRateSignal())) {
            channels.add("rate_easing");
        }
        if ("escalation".equals(event.getGeoSignal())) {
            channels.add("geo_escalation");
        }
        if ("deescalation".equals(event.getGeoSignal())) {
            channels.add("geo_deescalation");
        }
        return channels;
    }

    private double normalizeConfidence(Double value) {
        if (value == null) {
            return 0.6;
        }
        double confidence = value;
        if (Double.isNaN(confidence) || Double.isInfinite(confidence)) {
            return 0.6;
        }
        return Math.max(0.0, Math.min(1.0, confidence));
    }

    private Map<String, String> normalizeRegime(Map<String, String> value) {
        Map<String, String> normalized = new HashMap<>();
        if (value != null) {
            normalized.putAll(value);
        }
        normalized.putIfAbsent("risk_sentiment", "neutral");
        normalized.putIfAbsent("volatility", "elevated");
        normalized.putIfAbsent("liquidity", "neutral");
        return normalized;
    }

    private Map<String, Double> applyEventImpacts(Map<String, Double> sectorDelta,
            Map<String, Integer> impacts, double confidence) {
        if (impacts == null) {
            return sectorDelta;
        }
        for (Map.Entry<String, Integer> entry : impacts.entrySet()) {
            if (entry.getValue() == null) {
                continue;
            }
            sectorDelta.put(entry.getKey(), sectorDelta.getOrDefault(entry.getKey(), 0.0)
                + entry.getValue() * confidence);
        }
        return sectorDelta;
    }

    private String formatFxState(Map<String, Double> bias) {
        return String.format("USD:%+.2f JPY:%+.2f EUR:%+.2f EM:%+.2f",
            bias.getOrDefault("USD", 0.0),
            bias.getOrDefault("JPY", 0.0),
            bias.getOrDefault("EUR", 0.0),
            bias.getOrDefault("EM", 0.0));
    }
}
