package com.finintel.app.model;

import java.time.OffsetDateTime;
import java.util.HashMap;
import java.util.Map;

public class RawEvent {
    private String id;
    private String title;
    private String url;
    private OffsetDateTime publishedAt;
    private String sector;
    private String source;
    private Map<String, Object> payload = new HashMap<>();

    public RawEvent() {
    }

    public RawEvent(String id, String title, String url, OffsetDateTime publishedAt, String sector, String source,
            Map<String, Object> payload) {
        this.id = id;
        this.title = title;
        this.url = url;
        this.publishedAt = publishedAt;
        this.sector = sector;
        this.source = source;
        this.payload = payload;
    }

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getUrl() {
        return url;
    }

    public void setUrl(String url) {
        this.url = url;
    }

    public OffsetDateTime getPublishedAt() {
        return publishedAt;
    }

    public void setPublishedAt(OffsetDateTime publishedAt) {
        this.publishedAt = publishedAt;
    }

    public String getSector() {
        return sector;
    }

    public void setSector(String sector) {
        this.sector = sector;
    }

    public String getSource() {
        return source;
    }

    public void setSource(String source) {
        this.source = source;
    }

    public Map<String, Object> getPayload() {
        return payload;
    }

    public void setPayload(Map<String, Object> payload) {
        this.payload = payload;
    }
}
