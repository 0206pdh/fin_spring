package com.finintel.app.rules;

import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

public final class Weights {
    public static final Set<String> FX_TRANSMISSION_CHANNELS = Set.of(
        "risk_off",
        "risk_on",
        "rate_tightening",
        "rate_easing",
        "geo_escalation",
        "geo_deescalation"
    );

    public static final Map<String, Map<String, Integer>> FX_BIAS_RULES = Map.of(
        "risk_off", Map.of("USD", 2, "JPY", 2, "EUR", -1, "EM", -2),
        "risk_on", Map.of("USD", -2, "JPY", -2, "EUR", 1, "EM", 2),
        "rate_tightening", Map.of("USD", 2, "JPY", 0, "EUR", 0, "EM", -1),
        "rate_easing", Map.of("USD", -2, "JPY", 0, "EUR", 0, "EM", 1),
        "geo_escalation", Map.of("USD", 1, "JPY", 1, "EUR", 0, "EM", -1),
        "geo_deescalation", Map.of("USD", -1, "JPY", -1, "EUR", 0, "EM", 1)
    );

    public static final Map<String, Map<String, Integer>> FX_SECTOR_RULES = Map.of(
        "USD_up", Map.of(
            "Energy", 1,
            "Defense", 1,
            "Financials", 1,
            "Technology", -1,
            "Consumer Discretionary", -1
        ),
        "USD_down", Map.of(
            "Technology", 1,
            "Consumer Discretionary", 1,
            "Growth", 1,
            "Financials", -1
        ),
        "JPY_up", Map.of(
            "Defense", 1,
            "Autos", -1
        ),
        "EUR_up", Map.of(
            "Industrials", 1,
            "Energy", -1
        ),
        "EM_up", Map.of(
            "Materials", 1,
            "Industrials", 1,
            "Utilities", -1
        )
    );

    public static final Map<String, Map<String, Integer>> RISK_SECTOR_RULES = Map.of(
        "risk_off", Map.of(
            "Defense", 2,
            "Energy", 2,
            "Utilities", 2,
            "Technology", -2,
            "Consumer Discretionary", -2
        ),
        "risk_on", Map.of(
            "Technology", 2,
            "Consumer Discretionary", 2,
            "Industrials", 2,
            "Defense", -2
        )
    );

    public static final List<String> ALL_SECTORS;

    static {
        List<String> sectors = new ArrayList<>(
            FX_SECTOR_RULES.values().stream()
                .flatMap(map -> map.keySet().stream())
                .collect(Collectors.toCollection(HashSet::new))
        );
        Collections.sort(sectors);
        ALL_SECTORS = Collections.unmodifiableList(sectors);
    }

    private Weights() {
    }

    public static double regimeMultiplier(Map<String, String> regime) {
        double multiplier = 1.0;
        if ("risk_off".equals(regime.get("risk_sentiment"))) {
            multiplier *= 1.1;
        } else if ("risk_on".equals(regime.get("risk_sentiment"))) {
            multiplier *= 0.9;
        }

        if ("high".equals(regime.get("volatility"))) {
            multiplier *= 1.2;
        } else if ("low".equals(regime.get("volatility"))) {
            multiplier *= 0.9;
        }

        if ("tight".equals(regime.get("liquidity"))) {
            multiplier *= 1.1;
        } else if ("loose".equals(regime.get("liquidity"))) {
            multiplier *= 0.9;
        }

        return multiplier;
    }

    public static Map<String, Double> computeFxDelta(List<String> channels, double confidence) {
        Map<String, Double> delta = new HashMap<>();
        for (String channel : channels) {
            Map<String, Integer> rule = FX_BIAS_RULES.get(channel);
            if (rule == null) {
                continue;
            }
            for (Map.Entry<String, Integer> entry : rule.entrySet()) {
                delta.put(entry.getKey(), delta.getOrDefault(entry.getKey(), 0.0) + entry.getValue() * confidence);
            }
        }
        return delta;
    }

    public static Map<String, Double> computeSectorDeltaFromFx(Map<String, Double> fxDelta) {
        Map<String, Double> delta = new HashMap<>();
        for (Map.Entry<String, Double> entry : fxDelta.entrySet()) {
            if (entry.getValue() == 0.0) {
                continue;
            }
            String direction = entry.getValue() > 0 ? "up" : "down";
            String ruleKey = entry.getKey() + "_" + direction;
            Map<String, Integer> rule = FX_SECTOR_RULES.get(ruleKey);
            if (rule == null) {
                continue;
            }
            for (Map.Entry<String, Integer> sector : rule.entrySet()) {
                delta.put(sector.getKey(), delta.getOrDefault(sector.getKey(), 0.0)
                    + sector.getValue() * Math.abs(entry.getValue()));
            }
        }
        return delta;
    }

    public static Map<String, Double> applyRiskSectorRules(Map<String, Double> sectorDelta,
            List<String> channels, double confidence) {
        for (String channel : channels) {
            Map<String, Integer> rule = RISK_SECTOR_RULES.get(channel);
            if (rule == null) {
                continue;
            }
            for (Map.Entry<String, Integer> entry : rule.entrySet()) {
                sectorDelta.put(entry.getKey(), sectorDelta.getOrDefault(entry.getKey(), 0.0)
                    + entry.getValue() * confidence);
            }
        }
        return sectorDelta;
    }

    public static double clamp(double value, double minValue, double maxValue) {
        return Math.max(minValue, Math.min(maxValue, value));
    }

    public static Map<String, Double> combineBaselineDelta(Map<String, Double> baseline,
            Map<String, Double> sectorDelta, Map<String, String> regime) {
        double multiplier = regimeMultiplier(regime);
        Map<String, Double> result = new HashMap<>();
        Set<String> all = new HashSet<>(baseline.keySet());
        all.addAll(sectorDelta.keySet());
        for (String sector : all) {
            double base = baseline.getOrDefault(sector, 0.0);
            double delta = sectorDelta.getOrDefault(sector, 0.0) * multiplier;
            result.put(sector, clamp(base + delta, -5.0, 5.0));
        }
        return result;
    }
}
