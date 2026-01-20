package com.finintel.app.config;

import java.net.URI;
import java.net.URISyntaxException;

import javax.sql.DataSource;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.env.Environment;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

@Configuration
public class DataSourceConfig {
    @Bean
    public DataSource dataSource(Environment environment, AppSettings settings) {
        String rawUrl = firstNonEmpty(
            environment.getProperty("DATABASE_URL"),
            settings.getDatabaseUrl(),
            environment.getProperty("spring.datasource.url")
        );

        String username = environment.getProperty("spring.datasource.username");
        String password = environment.getProperty("spring.datasource.password");

        if (rawUrl != null && (rawUrl.startsWith("postgres://") || rawUrl.startsWith("postgresql://"))) {
            ParsedUrl parsed = parseDatabaseUrl(rawUrl);
            rawUrl = parsed.jdbcUrl;
            if (isBlank(username)) {
                username = parsed.username;
            }
            if (isBlank(password)) {
                password = parsed.password;
            }
        }

        DriverManagerDataSource dataSource = new DriverManagerDataSource();
        if (!isBlank(rawUrl)) {
            dataSource.setUrl(rawUrl);
        }
        if (!isBlank(username)) {
            dataSource.setUsername(username);
        }
        if (!isBlank(password)) {
            dataSource.setPassword(password);
        }
        dataSource.setDriverClassName("org.postgresql.Driver");
        return dataSource;
    }

    private static String firstNonEmpty(String... values) {
        if (values == null) {
            return null;
        }
        for (String value : values) {
            if (!isBlank(value)) {
                return value;
            }
        }
        return null;
    }

    private static boolean isBlank(String value) {
        return value == null || value.trim().isEmpty();
    }

    private static ParsedUrl parseDatabaseUrl(String rawUrl) {
        try {
            URI uri = new URI(rawUrl);
            String userInfo = uri.getUserInfo();
            String username = null;
            String password = null;
            if (userInfo != null) {
                String[] parts = userInfo.split(":", 2);
                username = parts.length > 0 ? parts[0] : null;
                password = parts.length > 1 ? parts[1] : null;
            }
            String host = uri.getHost();
            int port = uri.getPort();
            String path = uri.getPath();
            String database = (path != null && path.startsWith("/")) ? path.substring(1) : path;
            String jdbcUrl = "jdbc:postgresql://" + host + (port > 0 ? ":" + port : "") + "/" + database;
            if (uri.getQuery() != null && !uri.getQuery().isBlank()) {
                jdbcUrl = jdbcUrl + "?" + uri.getQuery();
            }
            return new ParsedUrl(jdbcUrl, username, password);
        } catch (URISyntaxException ex) {
            return new ParsedUrl(rawUrl, null, null);
        }
    }

    private static class ParsedUrl {
        private final String jdbcUrl;
        private final String username;
        private final String password;

        private ParsedUrl(String jdbcUrl, String username, String password) {
            this.jdbcUrl = jdbcUrl;
            this.username = username;
            this.password = password;
        }
    }
}
