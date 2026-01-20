package com.finintel.app.model;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public class NormalizedEvent {
    private String rawEventId;
    private String eventType;
    private String policyDomain;
    private String riskSignal;
    private String rateSignal;
    private String geoSignal;
    private Map<String, Integer> sectorImpacts = new HashMap<>();
    private String sentiment;
    private String rationale;
    private List<String> channels = new ArrayList<>();
    private double confidence = 0.6;
    private Map<String, String> regime = new HashMap<>();
    private Map<String, Double> baseline = new HashMap<>();

    public NormalizedEvent() {
    }

    public String getRawEventId() {
        return rawEventId;
    }

    public void setRawEventId(String rawEventId) {
        this.rawEventId = rawEventId;
    }

    public String getEventType() {
        return eventType;
    }

    public void setEventType(String eventType) {
        this.eventType = eventType;
    }

    public String getPolicyDomain() {
        return policyDomain;
    }

    public void setPolicyDomain(String policyDomain) {
        this.policyDomain = policyDomain;
    }

    public String getRiskSignal() {
        return riskSignal;
    }

    public void setRiskSignal(String riskSignal) {
        this.riskSignal = riskSignal;
    }

    public String getRateSignal() {
        return rateSignal;
    }

    public void setRateSignal(String rateSignal) {
        this.rateSignal = rateSignal;
    }

    public String getGeoSignal() {
        return geoSignal;
    }

    public void setGeoSignal(String geoSignal) {
        this.geoSignal = geoSignal;
    }

    public Map<String, Integer> getSectorImpacts() {
        return sectorImpacts;
    }

    public void setSectorImpacts(Map<String, Integer> sectorImpacts) {
        this.sectorImpacts = sectorImpacts;
    }

    public String getSentiment() {
        return sentiment;
    }

    public void setSentiment(String sentiment) {
        this.sentiment = sentiment;
    }

    public String getRationale() {
        return rationale;
    }

    public void setRationale(String rationale) {
        this.rationale = rationale;
    }

    public List<String> getChannels() {
        return channels;
    }

    public void setChannels(List<String> channels) {
        this.channels = channels;
    }

    public double getConfidence() {
        return confidence;
    }

    public void setConfidence(double confidence) {
        this.confidence = confidence;
    }

    public Map<String, String> getRegime() {
        return regime;
    }

    public void setRegime(Map<String, String> regime) {
        this.regime = regime;
    }

    public Map<String, Double> getBaseline() {
        return baseline;
    }

    public void setBaseline(Map<String, Double> baseline) {
        this.baseline = baseline;
    }
}
