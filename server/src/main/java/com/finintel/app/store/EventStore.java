package com.finintel.app.store;

import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import com.finintel.app.model.NormalizedEvent;
import com.finintel.app.model.RawEvent;
import com.finintel.app.model.ScoredEvent;
import com.finintel.app.rules.Weights;
import com.finintel.app.util.JsonCodec;

@Repository
public class EventStore {
    private final JdbcTemplate jdbcTemplate;
    private final JsonCodec json;

    public EventStore(JdbcTemplate jdbcTemplate, JsonCodec json) {
        this.jdbcTemplate = jdbcTemplate;
        this.json = json;
    }

    public void resetScoredData() {
        jdbcTemplate.execute("TRUNCATE scored_events");
        jdbcTemplate.execute("TRUNCATE normalized_events");
    }

    public int saveRawEvents(Iterable<RawEvent> events) {
        int count = 0;
        for (RawEvent event : events) {
            int updated = jdbcTemplate.update(connection -> {
                PreparedStatement ps = connection.prepareStatement(
                    "INSERT INTO raw_events (id, title, url, published_at, sector, source, payload) " +
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING"
                );
                ps.setString(1, event.getId());
                ps.setString(2, event.getTitle());
                ps.setString(3, event.getUrl());
                ps.setObject(4, event.getPublishedAt());
                ps.setString(5, event.getSector());
                ps.setString(6, event.getSource());
                ps.setObject(7, json.toJsonb(event.getPayload()));
                return ps;
            });
            if (updated > 0) {
                count += 1;
            }
        }
        return count;
    }

    public List<RawEvent> fetchUnprocessedRawEvents(int limit) {
        return jdbcTemplate.query(
            "SELECT r.* FROM raw_events r LEFT JOIN normalized_events n ON n.raw_event_id::text = r.id " +
            "WHERE n.raw_event_id IS NULL ORDER BY r.published_at DESC LIMIT ?",
            rawEventMapper(),
            limit
        );
    }

    public RawEvent fetchRawEvent(String rawEventId) {
        List<RawEvent> rows = jdbcTemplate.query(
            "SELECT * FROM raw_events WHERE id = ?",
            rawEventMapper(),
            rawEventId
        );
        return rows.isEmpty() ? null : rows.get(0);
    }

    public void saveNormalized(NormalizedEvent event) {
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO normalized_events " +
                "(raw_event_id, event_type, policy_domain, risk_signal, rate_signal, geo_signal, sector_impacts, " +
                "sentiment, rationale, channels, confidence, regime, baseline) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
                "ON CONFLICT (raw_event_id) DO UPDATE SET " +
                "event_type = EXCLUDED.event_type, policy_domain = EXCLUDED.policy_domain, " +
                "risk_signal = EXCLUDED.risk_signal, rate_signal = EXCLUDED.rate_signal, geo_signal = EXCLUDED.geo_signal, " +
                "sector_impacts = EXCLUDED.sector_impacts, sentiment = EXCLUDED.sentiment, rationale = EXCLUDED.rationale, " +
                "channels = EXCLUDED.channels, confidence = EXCLUDED.confidence, regime = EXCLUDED.regime, " +
                "baseline = EXCLUDED.baseline"
            );
            ps.setString(1, event.getRawEventId());
            ps.setString(2, event.getEventType());
            ps.setString(3, event.getPolicyDomain());
            ps.setString(4, event.getRiskSignal());
            ps.setString(5, event.getRateSignal());
            ps.setString(6, event.getGeoSignal());
            ps.setObject(7, json.toJsonb(event.getSectorImpacts()));
            ps.setString(8, event.getSentiment());
            ps.setString(9, event.getRationale());
            ps.setObject(10, json.toJsonb(event.getChannels()));
            ps.setDouble(11, event.getConfidence());
            ps.setObject(12, json.toJsonb(event.getRegime()));
            ps.setObject(13, json.toJsonb(event.getBaseline()));
            return ps;
        });
    }

    public List<NormalizedEvent> fetchUnscoredEvents(int limit) {
        return jdbcTemplate.query(
            "SELECT n.* FROM normalized_events n LEFT JOIN scored_events s ON s.raw_event_id::text = n.raw_event_id::text " +
            "WHERE s.raw_event_id IS NULL ORDER BY n.raw_event_id DESC LIMIT ?",
            normalizedMapper(),
            limit
        );
    }

    public NormalizedEvent fetchNormalizedEvent(String rawEventId) {
        List<NormalizedEvent> rows = jdbcTemplate.query(
            "SELECT * FROM normalized_events WHERE raw_event_id = ?",
            normalizedMapper(),
            rawEventId
        );
        return rows.isEmpty() ? null : rows.get(0);
    }

    public void saveScored(ScoredEvent event) {
        jdbcTemplate.update(connection -> {
            PreparedStatement ps = connection.prepareStatement(
                "INSERT INTO scored_events " +
                "(raw_event_id, event_type, policy_domain, risk_signal, rate_signal, geo_signal, sector_impacts, " +
                "sentiment, rationale, fx_state, sector_scores, total_score, created_at, channels, confidence, regime, baseline) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) " +
                "ON CONFLICT (raw_event_id) DO UPDATE SET " +
                "event_type = EXCLUDED.event_type, policy_domain = EXCLUDED.policy_domain, " +
                "risk_signal = EXCLUDED.risk_signal, rate_signal = EXCLUDED.rate_signal, geo_signal = EXCLUDED.geo_signal, " +
                "sector_impacts = EXCLUDED.sector_impacts, sentiment = EXCLUDED.sentiment, rationale = EXCLUDED.rationale, " +
                "fx_state = EXCLUDED.fx_state, sector_scores = EXCLUDED.sector_scores, total_score = EXCLUDED.total_score, " +
                "created_at = EXCLUDED.created_at, channels = EXCLUDED.channels, confidence = EXCLUDED.confidence, " +
                "regime = EXCLUDED.regime, baseline = EXCLUDED.baseline"
            );
            ps.setString(1, event.getRawEventId());
            ps.setString(2, event.getEventType());
            ps.setString(3, event.getPolicyDomain());
            ps.setString(4, event.getRiskSignal());
            ps.setString(5, event.getRateSignal());
            ps.setString(6, event.getGeoSignal());
            ps.setObject(7, json.toJsonb(event.getSectorImpacts()));
            ps.setString(8, event.getSentiment());
            ps.setString(9, event.getRationale());
            ps.setString(10, event.getFxState());
            ps.setObject(11, json.toJsonb(event.getSectorScores()));
            ps.setDouble(12, event.getTotalScore());
            ps.setObject(13, event.getCreatedAt());
            ps.setObject(14, json.toJsonb(event.getChannels()));
            ps.setDouble(15, event.getConfidence());
            ps.setObject(16, json.toJsonb(event.getRegime()));
            ps.setObject(17, json.toJsonb(event.getBaseline()));
            return ps;
        });
    }

    public ScoredEvent fetchScoredEvent(String rawEventId) {
        List<ScoredEvent> rows = jdbcTemplate.query(
            "SELECT * FROM scored_events WHERE raw_event_id = ?",
            scoredMapper(),
            rawEventId
        );
        return rows.isEmpty() ? null : rows.get(0);
    }

    public List<Map<String, Object>> listTimeline(int limit) {
        return jdbcTemplate.query(
            "SELECT r.title, r.url, r.published_at, r.sector, s.risk_signal, s.rate_signal, s.geo_signal, s.fx_state, " +
            "s.sentiment, s.total_score FROM raw_events r JOIN scored_events s ON s.raw_event_id::text = r.id " +
            "ORDER BY r.published_at DESC LIMIT ?",
            (rs, rowNum) -> {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("title", rs.getString("title"));
                row.put("url", rs.getString("url"));
                OffsetDateTime published = rs.getObject("published_at", OffsetDateTime.class);
                row.put("published_at", published != null ? published.toString() : null);
                row.put("sector", rs.getString("sector"));
                row.put("risk_signal", rs.getString("risk_signal"));
                row.put("rate_signal", rs.getString("rate_signal"));
                row.put("geo_signal", rs.getString("geo_signal"));
                row.put("fx_state", rs.getString("fx_state"));
                row.put("sentiment", rs.getString("sentiment"));
                row.put("total_score", rs.getDouble("total_score"));
                return row;
            },
            limit
        );
    }

    public Map<String, Double> sectorHeatmap() {
        List<Map<String, Double>> scores = jdbcTemplate.query(
            "SELECT sector_scores FROM scored_events",
            (rs, rowNum) -> json.readDoubleMap(rs.getObject("sector_scores"))
        );

        Map<String, Double> totals = new LinkedHashMap<>();
        for (Map<String, Double> scoreMap : scores) {
            for (Map.Entry<String, Double> entry : scoreMap.entrySet()) {
                totals.put(entry.getKey(), totals.getOrDefault(entry.getKey(), 0.0) + entry.getValue());
            }
        }
        for (String sector : Weights.ALL_SECTORS) {
            totals.putIfAbsent(sector, 0.0);
        }
        Map<String, Double> rounded = new LinkedHashMap<>();
        for (Map.Entry<String, Double> entry : totals.entrySet()) {
            rounded.put(entry.getKey(), Math.round(entry.getValue() * 1000.0) / 1000.0);
        }
        return rounded;
    }

    public List<Map<String, Object>> graphEdges(int limit) {
        List<Map<String, Object>> rows = jdbcTemplate.query(
            "SELECT r.title, s.fx_state, s.risk_signal, s.rate_signal, s.geo_signal, s.sector_scores " +
            "FROM raw_events r JOIN scored_events s ON s.raw_event_id::text = r.id " +
            "ORDER BY r.published_at DESC LIMIT ?",
            (rs, rowNum) -> {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("title", rs.getString("title"));
                row.put("fx_state", rs.getString("fx_state"));
                row.put("risk_signal", rs.getString("risk_signal"));
                row.put("rate_signal", rs.getString("rate_signal"));
                row.put("geo_signal", rs.getString("geo_signal"));
                row.put("sector_scores", json.readDoubleMap(rs.getObject("sector_scores")));
                return row;
            },
            limit
        );

        List<Map<String, Object>> edges = new ArrayList<>();
        for (Map<String, Object> row : rows) {
            @SuppressWarnings("unchecked")
            Map<String, Double> sectorScores = (Map<String, Double>) row.get("sector_scores");
            for (Map.Entry<String, Double> entry : sectorScores.entrySet()) {
                Map<String, Object> edge = new LinkedHashMap<>();
                edge.put("event", row.get("title"));
                edge.put("fx", row.get("fx_state"));
                edge.put("risk_signal", row.get("risk_signal"));
                edge.put("rate_signal", row.get("rate_signal"));
                edge.put("geo_signal", row.get("geo_signal"));
                edge.put("sector", entry.getKey());
                edge.put("weight", entry.getValue());
                edge.put("fx_theme", row.get("fx_state"));
                edges.add(edge);
            }
        }

        if (edges.isEmpty()) {
            Map<String, Object> fallback = new LinkedHashMap<>();
            fallback.put("event", "Sample event (default)");
            fallback.put("fx", "USD:+0 JPY:+0 EUR:+0 EM:+0");
            fallback.put("risk_signal", "neutral");
            fallback.put("rate_signal", "none");
            fallback.put("geo_signal", "none");
            fallback.put("sector", "Energy");
            fallback.put("weight", 1);
            fallback.put("fx_theme", "neutral");
            edges.add(fallback);
        }

        return edges;
    }

    private RowMapper<RawEvent> rawEventMapper() {
        return (rs, rowNum) -> {
            RawEvent event = new RawEvent();
            event.setId(rs.getString("id"));
            event.setTitle(rs.getString("title"));
            event.setUrl(rs.getString("url"));
            event.setPublishedAt(rs.getObject("published_at", OffsetDateTime.class));
            event.setSector(rs.getString("sector"));
            event.setSource(rs.getString("source"));
            event.setPayload(json.readMap(rs.getObject("payload")));
            return event;
        };
    }

    private RowMapper<NormalizedEvent> normalizedMapper() {
        return (rs, rowNum) -> {
            NormalizedEvent event = new NormalizedEvent();
            event.setRawEventId(rs.getString("raw_event_id"));
            event.setEventType(rs.getString("event_type"));
            event.setPolicyDomain(rs.getString("policy_domain"));
            event.setRiskSignal(rs.getString("risk_signal"));
            event.setRateSignal(rs.getString("rate_signal"));
            event.setGeoSignal(rs.getString("geo_signal"));
            event.setSectorImpacts(json.readIntMap(rs.getObject("sector_impacts")));
            event.setSentiment(rs.getString("sentiment"));
            event.setRationale(rs.getString("rationale"));
            event.setChannels(new ArrayList<>(json.readStringList(rs.getObject("channels"))));
            event.setConfidence(rs.getDouble("confidence"));
            event.setRegime(json.readStringMap(rs.getObject("regime")));
            event.setBaseline(json.readDoubleMap(rs.getObject("baseline")));
            return event;
        };
    }

    private RowMapper<ScoredEvent> scoredMapper() {
        return (rs, rowNum) -> {
            ScoredEvent event = new ScoredEvent();
            event.setRawEventId(rs.getString("raw_event_id"));
            event.setEventType(rs.getString("event_type"));
            event.setPolicyDomain(rs.getString("policy_domain"));
            event.setRiskSignal(rs.getString("risk_signal"));
            event.setRateSignal(rs.getString("rate_signal"));
            event.setGeoSignal(rs.getString("geo_signal"));
            event.setSectorImpacts(json.readIntMap(rs.getObject("sector_impacts")));
            event.setSentiment(rs.getString("sentiment"));
            event.setRationale(rs.getString("rationale"));
            event.setFxState(rs.getString("fx_state"));
            event.setSectorScores(json.readDoubleMap(rs.getObject("sector_scores")));
            event.setTotalScore(rs.getDouble("total_score"));
            event.setCreatedAt(rs.getObject("created_at", OffsetDateTime.class));
            event.setChannels(new ArrayList<>(json.readStringList(rs.getObject("channels"))));
            event.setConfidence(rs.getDouble("confidence"));
            event.setRegime(json.readStringMap(rs.getObject("regime")));
            event.setBaseline(json.readDoubleMap(rs.getObject("baseline")));
            return event;
        };
    }
}
