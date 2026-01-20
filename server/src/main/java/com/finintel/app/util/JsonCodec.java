package com.finintel.app.util;

import java.io.IOException;
import java.sql.SQLException;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import org.postgresql.util.PGobject;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class JsonCodec {
    private final ObjectMapper mapper;

    public JsonCodec(ObjectMapper mapper) {
        this.mapper = mapper;
    }

    public PGobject toJsonb(Object value) {
        PGobject pg = new PGobject();
        pg.setType("jsonb");
        try {
            pg.setValue(mapper.writeValueAsString(value));
        } catch (IOException | SQLException ex) {
            throw new IllegalStateException("Failed to serialize JSON", ex);
        }
        return pg;
    }

    public Map<String, Object> readMap(Object value) {
        if (value == null) {
            return Collections.emptyMap();
        }
        String json = unwrap(value);
        if (json == null || json.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return mapper.readValue(json, new TypeReference<Map<String, Object>>() {});
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse JSON map", ex);
        }
    }

    public Map<String, Integer> readIntMap(Object value) {
        if (value == null) {
            return Collections.emptyMap();
        }
        String json = unwrap(value);
        if (json == null || json.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return mapper.readValue(json, new TypeReference<Map<String, Integer>>() {});
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse JSON map", ex);
        }
    }

    public Map<String, Double> readDoubleMap(Object value) {
        if (value == null) {
            return Collections.emptyMap();
        }
        String json = unwrap(value);
        if (json == null || json.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return mapper.readValue(json, new TypeReference<Map<String, Double>>() {});
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse JSON map", ex);
        }
    }

    public Map<String, String> readStringMap(Object value) {
        if (value == null) {
            return Collections.emptyMap();
        }
        String json = unwrap(value);
        if (json == null || json.isBlank()) {
            return Collections.emptyMap();
        }
        try {
            return mapper.readValue(json, new TypeReference<Map<String, String>>() {});
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse JSON map", ex);
        }
    }

    public List<String> readStringList(Object value) {
        if (value == null) {
            return Collections.emptyList();
        }
        String json = unwrap(value);
        if (json == null || json.isBlank()) {
            return Collections.emptyList();
        }
        try {
            return mapper.readValue(json, new TypeReference<List<String>>() {});
        } catch (IOException ex) {
            throw new IllegalStateException("Failed to parse JSON list", ex);
        }
    }

    private String unwrap(Object value) {
        if (value instanceof PGobject pg) {
            return pg.getValue();
        }
        return value.toString();
    }
}
