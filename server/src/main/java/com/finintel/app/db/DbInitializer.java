package com.finintel.app.db;

import jakarta.annotation.PostConstruct;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class DbInitializer {
    private final JdbcTemplate jdbcTemplate;

    public DbInitializer(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    @PostConstruct
    public void init() {
        jdbcTemplate.execute(
            "CREATE TABLE IF NOT EXISTS raw_events (" +
            "id TEXT PRIMARY KEY," +
            "title TEXT NOT NULL," +
            "url TEXT NOT NULL," +
            "published_at TIMESTAMPTZ NOT NULL," +
            "sector TEXT NOT NULL," +
            "source TEXT NOT NULL," +
            "payload JSONB NOT NULL" +
            ")"
        );

        jdbcTemplate.execute(
            "CREATE TABLE IF NOT EXISTS normalized_events (" +
            "raw_event_id TEXT PRIMARY KEY," +
            "event_type TEXT NOT NULL," +
            "policy_domain TEXT NOT NULL," +
            "risk_signal TEXT NOT NULL," +
            "rate_signal TEXT NOT NULL," +
            "geo_signal TEXT NOT NULL," +
            "sector_impacts JSONB NOT NULL," +
            "sentiment TEXT NOT NULL," +
            "rationale TEXT NOT NULL," +
            "channels JSONB NOT NULL," +
            "confidence DOUBLE PRECISION NOT NULL," +
            "regime JSONB NOT NULL," +
            "baseline JSONB NOT NULL" +
            ")"
        );

        jdbcTemplate.execute(
            "CREATE TABLE IF NOT EXISTS scored_events (" +
            "raw_event_id TEXT PRIMARY KEY," +
            "event_type TEXT NOT NULL," +
            "policy_domain TEXT NOT NULL," +
            "risk_signal TEXT NOT NULL," +
            "rate_signal TEXT NOT NULL," +
            "geo_signal TEXT NOT NULL," +
            "sector_impacts JSONB NOT NULL," +
            "sentiment TEXT NOT NULL," +
            "rationale TEXT NOT NULL," +
            "fx_state TEXT NOT NULL," +
            "sector_scores JSONB NOT NULL," +
            "total_score DOUBLE PRECISION NOT NULL," +
            "created_at TIMESTAMPTZ NOT NULL," +
            "channels JSONB NOT NULL," +
            "confidence DOUBLE PRECISION NOT NULL," +
            "regime JSONB NOT NULL," +
            "baseline JSONB NOT NULL" +
            ")"
        );

        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS policy_domain TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS risk_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS rate_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS geo_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS channels JSONB NOT NULL DEFAULT '[]'");
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6");
        jdbcTemplate.execute(
            "ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS regime JSONB NOT NULL DEFAULT '{\"risk_sentiment\":\"neutral\",\"volatility\":\"elevated\",\"liquidity\":\"neutral\"}'"
        );
        jdbcTemplate.execute("ALTER TABLE normalized_events ADD COLUMN IF NOT EXISTS baseline JSONB NOT NULL DEFAULT '{}' ");

        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS policy_domain TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS risk_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS rate_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS geo_signal TEXT NOT NULL DEFAULT ''");
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS channels JSONB NOT NULL DEFAULT '[]'");
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0.6");
        jdbcTemplate.execute(
            "ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS regime JSONB NOT NULL DEFAULT '{\"risk_sentiment\":\"neutral\",\"volatility\":\"elevated\",\"liquidity\":\"neutral\"}'"
        );
        jdbcTemplate.execute("ALTER TABLE scored_events ADD COLUMN IF NOT EXISTS baseline JSONB NOT NULL DEFAULT '{}' ");

        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE scored_events ALTER COLUMN total_score TYPE DOUBLE PRECISION USING total_score::double precision;" +
            "EXCEPTION WHEN undefined_column THEN NULL; WHEN datatype_mismatch THEN NULL; END $$;"
        );

        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE normalized_events ALTER COLUMN region DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE normalized_events ALTER COLUMN country DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE normalized_events ALTER COLUMN fx_theme DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE scored_events ALTER COLUMN region DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE scored_events ALTER COLUMN country DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
        jdbcTemplate.execute(
            "DO $$ BEGIN " +
            "ALTER TABLE scored_events ALTER COLUMN fx_theme DROP NOT NULL;" +
            "EXCEPTION WHEN undefined_column THEN NULL; END $$;"
        );
    }
}
