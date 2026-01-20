package com.finintel.app.llm;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.finintel.app.config.AppSettings;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Component
public class LlmClient {
    private static final Logger logger = LoggerFactory.getLogger(LlmClient.class);
    private final AppSettings settings;
    private final ObjectMapper mapper;
    private final HttpClient httpClient;

    public LlmClient(AppSettings settings, ObjectMapper mapper) {
        this.settings = settings;
        this.mapper = mapper;
        this.httpClient = HttpClient.newBuilder()
            .connectTimeout(Duration.ofSeconds(settings.getLlmTimeoutSec()))
            .build();
        String keyStatus = (settings.getOpenaiApiKey() != null && !settings.getOpenaiApiKey().isBlank()) ? "present" : "missing";
        logger.info("LLM config loaded base_url={} model={} api_key={}", settings.getOpenaiBaseUrl(), settings.getOpenaiModel(), keyStatus);
    }

    public Map<String, Object> chat(List<Map<String, String>> messages) {
        String baseUrl = settings.getOpenaiBaseUrl();
        String model = settings.getOpenaiModel();
        String apiKey = settings.getOpenaiApiKey();

        Map<String, Object> payload = new HashMap<>();
        payload.put("model", model);
        payload.put("messages", messages);
        payload.put("temperature", 0.2);

        try {
            String body = mapper.writeValueAsString(payload);
            HttpRequest.Builder builder = HttpRequest.newBuilder()
                .uri(URI.create(baseUrl.replaceAll("/+$", "") + "/chat/completions"))
                .timeout(Duration.ofSeconds(settings.getLlmTimeoutSec()))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body));

        if (apiKey != null && !apiKey.isBlank()) {
            builder.header("Authorization", "Bearer " + apiKey);
        }

            HttpResponse<String> response = httpClient.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("LLM request failed with status " + response.statusCode());
            }
            return mapper.readValue(response.body(), new TypeReference<Map<String, Object>>() {});
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("LLM request interrupted", ex);
        } catch (IOException ex) {
            throw new IllegalStateException("LLM request failed", ex);
        }
    }

    public Map<String, Object> extractJson(List<Map<String, String>> messages) {
        Map<String, Object> response = chat(messages);
        Object choices = response.get("choices");
        if (!(choices instanceof List<?> list) || list.isEmpty()) {
            throw new IllegalStateException("No choices returned from LLM");
        }
        Object choice0 = list.get(0);
        if (!(choice0 instanceof Map<?, ?> choiceMap)) {
            throw new IllegalStateException("Invalid LLM response format");
        }
        Object message = choiceMap.get("message");
        if (!(message instanceof Map<?, ?> msgMap)) {
            throw new IllegalStateException("Invalid LLM response format");
        }
        Object content = msgMap.get("content");
        String text = content != null ? content.toString() : "";
        return safeJson(text);
    }

    public Map<String, Object> safeJson(String text) {
        try {
            return mapper.readValue(text, new TypeReference<Map<String, Object>>() {});
        } catch (IOException ex) {
            int start = text.indexOf('{');
            int end = text.lastIndexOf('}');
            if (start < 0 || end < 0 || end <= start) {
                throw new IllegalStateException("No JSON content found", ex);
            }
            String trimmed = text.substring(start, end + 1);
            try {
                return mapper.readValue(trimmed, new TypeReference<Map<String, Object>>() {});
            } catch (IOException nested) {
                throw new IllegalStateException("Failed to parse JSON content", nested);
            }
        }
    }

}
