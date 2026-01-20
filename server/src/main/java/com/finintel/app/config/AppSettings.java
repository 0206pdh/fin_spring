package com.finintel.app.config;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import io.github.cdimascio.dotenv.Dotenv;

@Component
public class AppSettings {
    private static final Logger logger = LoggerFactory.getLogger(AppSettings.class);

    private final Environment environment;
    private final Map<String, String> dotenv;

    public AppSettings(Environment environment) {
        this.environment = environment;
        this.dotenv = loadDotenv();
        if (!dotenv.isEmpty()) {
            logger.info("Dotenv loaded in AppSettings (keys={})", dotenv.size());
        } else {
            logger.info("Dotenv not loaded in AppSettings");
        }
    }

    public String getOpenaiApiKey() {
        return read("OPENAI_API_KEY", "");
    }

    public String getOpenaiModel() {
        return read("OPENAI_MODEL", "gpt-4o-mini");
    }

    public String getOpenaiBaseUrl() {
        return read("OPENAI_BASE_URL", "https://api.openai.com/v1");
    }

    public int getLlmTimeoutSec() {
        String raw = read("LLM_TIMEOUT_SEC", "30");
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException ex) {
            return 30;
        }
    }

    public String getDatabaseUrl() {
        String value = read("DATABASE_URL", "");
        if (!value.isBlank()) {
            return value;
        }
        value = read("FIM_DATABASE_URL", "");
        return value;
    }

    private String read(String key, String fallback) {
        String value = environment.getProperty(key);
        if (value == null || value.isBlank()) {
            value = dotenv.get(key);
        }
        if (value == null || value.isBlank()) {
            return fallback;
        }
        return value;
    }

    private Map<String, String> loadDotenv() {
        Path envPath = resolveEnvPath();
        if (envPath == null) {
            return Map.of();
        }
        Dotenv dotenv = Dotenv.configure()
            .directory(envPath.getParent() != null ? envPath.getParent().toString() : ".")
            .filename(envPath.getFileName().toString())
            .ignoreIfMalformed()
            .ignoreIfMissing()
            .load();
        return dotenv.entries().stream()
            .collect(java.util.stream.Collectors.toMap(
                io.github.cdimascio.dotenv.DotenvEntry::getKey,
                io.github.cdimascio.dotenv.DotenvEntry::getValue
            ));
    }

    private Path resolveEnvPath() {
        Path local = Path.of(".env");
        if (Files.exists(local)) {
            return local;
        }
        Path parent = Path.of("..", ".env");
        if (Files.exists(parent)) {
            return parent;
        }
        return null;
    }
}
