package com.finintel.app.config;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.env.EnvironmentPostProcessor;
import org.springframework.core.Ordered;
import org.springframework.core.env.ConfigurableEnvironment;
import org.springframework.core.env.MapPropertySource;

import io.github.cdimascio.dotenv.Dotenv;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class DotenvLoader implements EnvironmentPostProcessor, Ordered {
    private static final Logger logger = LoggerFactory.getLogger(DotenvLoader.class);

    @Override
    public void postProcessEnvironment(ConfigurableEnvironment environment, SpringApplication application) {
        Path envPath = resolveEnvPath();
        if (envPath == null) {
            logger.info("Dotenv not found; skipping .env load.");
            return;
        }
        Dotenv dotenv = Dotenv.configure()
            .directory(envPath.getParent() != null ? envPath.getParent().toString() : ".")
            .filename(envPath.getFileName().toString())
            .ignoreIfMalformed()
            .ignoreIfMissing()
            .load();
        Map<String, Object> values = dotenv.entries().stream()
            .collect(java.util.stream.Collectors.toMap(
                io.github.cdimascio.dotenv.DotenvEntry::getKey,
                entry -> (Object) entry.getValue()
            ));
        if (!values.isEmpty()) {
            environment.getPropertySources().addFirst(new MapPropertySource("dotenv", values));
            logger.info("Dotenv loaded from {} (keys={})", envPath.toAbsolutePath(), values.size());
        } else {
            logger.warn("Dotenv file {} loaded but had no entries.", envPath.toAbsolutePath());
        }
    }

    @Override
    public int getOrder() {
        return Ordered.HIGHEST_PRECEDENCE;
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
