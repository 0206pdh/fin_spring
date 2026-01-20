package com.finintel.app.ingest;

import java.io.IOException;
import java.io.StringReader;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import javax.xml.parsers.DocumentBuilderFactory;

import org.springframework.stereotype.Service;
import org.w3c.dom.Document;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;
import org.xml.sax.InputSource;

import com.finintel.app.model.RawEvent;

@Service
public class ApNewsIngestService {
    private static final Map<String, String> AP_HUBS = Map.of(
        "top_stories", "https://feeds.bbci.co.uk/news/rss.xml",
        "business", "https://feeds.bbci.co.uk/news/business/rss.xml",
        "technology", "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "world", "https://feeds.bbci.co.uk/news/world/rss.xml",
        "uk", "https://feeds.bbci.co.uk/news/uk/rss.xml",
        "politics", "https://feeds.bbci.co.uk/news/politics/rss.xml",
        "health", "https://feeds.bbci.co.uk/news/health/rss.xml",
        "science_environment", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
    );

    private static final Map<String, String> SECTOR_MAP = Map.of(
        "top_stories", "macro",
        "business", "corporate",
        "technology", "technology",
        "world", "geopolitics",
        "uk", "policy",
        "politics", "policy",
        "health", "healthcare",
        "science_environment", "industrials"
    );

    private final HttpClient httpClient = HttpClient.newBuilder()
        .followRedirects(HttpClient.Redirect.NORMAL)
        .build();
    private static final org.slf4j.Logger logger = org.slf4j.LoggerFactory.getLogger(ApNewsIngestService.class);

    public List<Map<String, String>> getCategories() {
        List<Map<String, String>> categories = new ArrayList<>();
        for (Map.Entry<String, String> entry : AP_HUBS.entrySet()) {
            Map<String, String> row = new LinkedHashMap<>();
            row.put("sector", entry.getKey());
            row.put("url", entry.getValue());
            categories.add(row);
        }
        return categories;
    }

    public List<RawEvent> fetchRawEvents(String category, int limitPerCategory) {
        Map<String, String> hubs = filteredHubs(category);
        List<RawEvent> events = new ArrayList<>();
        for (Map.Entry<String, String> hub : hubs.entrySet()) {
            String key = hub.getKey();
            String hubUrl = hub.getValue();
            String rssXml = fetchText(hubUrl);
            if (rssXml == null || rssXml.isBlank()) {
                logger.warn("RSS fetch returned empty body for {}", hubUrl);
                continue;
            }
            List<Map<String, String>> items = parseRssItems(rssXml);
            int limit = Math.min(limitPerCategory, items.size());
            for (int i = 0; i < limit; i++) {
                Map<String, String> item = items.get(i);
                String url = item.getOrDefault("url", "");
                if (url.isBlank()) {
                    continue;
                }
                String title = item.getOrDefault("title", "");
                String publishedAt = item.getOrDefault("published_at", "");
                String summary = item.getOrDefault("summary", "");
                OffsetDateTime published = parseDateTime(publishedAt);
                if (published == null) {
                    published = OffsetDateTime.now(ZoneOffset.UTC);
                }
                String eventId = stableId(title, url, published);

                Map<String, Object> rawPayload = new LinkedHashMap<>();
                rawPayload.put("category_url", hubUrl);
                Map<String, Object> itemPayload = new LinkedHashMap<>();
                itemPayload.put("title", title);
                itemPayload.put("url", url);
                itemPayload.put("published_at", publishedAt);
                rawPayload.put("item", itemPayload);
                Map<String, Object> detailsPayload = new LinkedHashMap<>();
                detailsPayload.put("title", title);
                detailsPayload.put("summary", summary);
                detailsPayload.put("text", "");
                rawPayload.put("details", detailsPayload);

                RawEvent event = new RawEvent();
                event.setId(eventId);
                event.setTitle(!title.isBlank() ? title.trim() : titleFromUrl(url));
                event.setUrl(url);
                event.setPublishedAt(published);
                event.setSector(SECTOR_MAP.getOrDefault(key, key));
                event.setSource("apnews");
                event.setPayload(rawPayload);
                events.add(event);
            }
        }
        return events;
    }

    public Map<String, String> fetchArticleDetails(String url) {
        String html = fetchText(url);
        String title = extractMeta(html, "property", "og:title");
        if (title.isBlank()) {
            title = extractTitle(html);
        }
        String summary = extractMeta(html, "property", "og:description");
        String publishedAt = extractMeta(html, "property", "article:published_time");
        if (publishedAt.isBlank()) {
            publishedAt = extractMeta(html, "name", "pubdate");
        }
        String body = extractParagraphs(html);
        if (body.isBlank()) {
            body = summary;
        }

        Map<String, String> result = new LinkedHashMap<>();
        result.put("title", title);
        result.put("published_at", publishedAt);
        result.put("summary", summary);
        result.put("text", body);
        return result;
    }

    private Map<String, String> filteredHubs(String category) {
        if (category == null || category.isBlank()) {
            return AP_HUBS;
        }
        String needle = normalizeToken(category);
        for (Map.Entry<String, String> entry : AP_HUBS.entrySet()) {
            if (normalizeToken(entry.getKey()).equals(needle)) {
                return Map.of(entry.getKey(), entry.getValue());
            }
        }
        return Map.of();
    }

    private String fetchText(String url) {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .header("User-Agent", "Mozilla/5.0")
                .GET()
                .build();
            HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() >= 400) {
                throw new IllegalStateException("Request failed with status " + response.statusCode());
            }
            String body = response.body();
            if (body == null || body.isBlank()) {
                logger.warn("Empty response body from {}", url);
            }
            return body;
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Request interrupted", ex);
        } catch (IOException ex) {
            throw new IllegalStateException("Request failed", ex);
        }
    }

    private List<Map<String, String>> parseRssItems(String xmlText) {
        List<Map<String, String>> items = new ArrayList<>();
        if (xmlText == null || xmlText.isBlank()) {
            return items;
        }
        try {
            Document document = DocumentBuilderFactory.newInstance().newDocumentBuilder()
                .parse(new InputSource(new StringReader(xmlText)));
            NodeList nodes = document.getElementsByTagName("item");
            for (int i = 0; i < nodes.getLength(); i++) {
                Node item = nodes.item(i);
                String title = textContent(item, "title");
                String link = textContent(item, "link");
                String pubDate = textContent(item, "pubDate");
                String description = textContent(item, "description");
                String summary = stripHtml(description);
                if (!link.isBlank()) {
                    Map<String, String> entry = new LinkedHashMap<>();
                    entry.put("title", title);
                    entry.put("url", link);
                    entry.put("published_at", pubDate);
                    entry.put("summary", summary);
                    items.add(entry);
                }
            }
        } catch (Exception ex) {
            return items;
        }
        return items;
    }

    private String textContent(Node parent, String tag) {
        if (parent == null || parent.getChildNodes() == null) {
            return "";
        }
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (node.getNodeName().equalsIgnoreCase(tag)) {
                return node.getTextContent() != null ? node.getTextContent().trim() : "";
            }
        }
        return "";
    }

    private OffsetDateTime parseDateTime(String value) {
        if (value == null || value.isBlank()) {
            return null;
        }
        try {
            return OffsetDateTime.parse(value, DateTimeFormatter.RFC_1123_DATE_TIME);
        } catch (DateTimeParseException ex) {
            try {
                return OffsetDateTime.parse(value);
            } catch (DateTimeParseException ignored) {
                return null;
            }
        }
    }

    private String stableId(String title, String url, OffsetDateTime published) {
        String raw = title + "|" + url + "|" + published.toString();
        return UUID.nameUUIDFromBytes(raw.getBytes()).toString();
    }

    private String normalizeToken(String value) {
        return value == null ? "" : value.trim().toLowerCase().replaceAll("[^a-z0-9]+", "");
    }

    private String titleFromUrl(String url) {
        if (url == null || url.isBlank()) {
            return "";
        }
        String slug = url.replaceAll("/+$", "");
        int idx = slug.lastIndexOf('/');
        if (idx >= 0) {
            slug = slug.substring(idx + 1);
        }
        slug = slug.replaceAll("-\\d{4}-\\d{2}-\\d{2}$", "");
        String title = slug.replace("-", " ").trim();
        if (title.isBlank()) {
            return "";
        }
        return Character.toUpperCase(title.charAt(0)) + title.substring(1);
    }

    private String extractMeta(String html, String attr, String value) {
        String pattern = "<meta[^>]+" + Pattern.quote(attr) + "=\"" + Pattern.quote(value) +
            "\"[^>]+content=\"([^\"]+)\"";
        Matcher matcher = Pattern.compile(pattern, Pattern.CASE_INSENSITIVE).matcher(html);
        return matcher.find() ? unescape(matcher.group(1)).trim() : "";
    }

    private String extractTitle(String html) {
        Matcher matcher = Pattern.compile("<title>([^<]+)</title>", Pattern.CASE_INSENSITIVE).matcher(html);
        return matcher.find() ? unescape(matcher.group(1)).trim() : "";
    }

    private String extractParagraphs(String html) {
        Matcher matcher = Pattern.compile("<p[^>]*>(.*?)</p>", Pattern.CASE_INSENSITIVE | Pattern.DOTALL).matcher(html);
        List<String> texts = new ArrayList<>();
        while (matcher.find()) {
            String cleaned = stripHtml(matcher.group(1));
            if (!cleaned.isBlank()) {
                texts.add(cleaned);
            }
        }
        String joined = String.join(" ", texts);
        if (joined.length() > 4000) {
            return joined.substring(0, 4000);
        }
        return joined;
    }

    private String stripHtml(String text) {
        if (text == null) {
            return "";
        }
        String cleaned = text.replaceAll("<script[^>]*>.*?</script>", " ")
            .replaceAll("<style[^>]*>.*?</style>", " ")
            .replaceAll("<[^>]+>", " ")
            .replaceAll("\\s+", " ")
            .trim();
        return unescape(cleaned);
    }

    private String unescape(String text) {
        if (text == null) {
            return "";
        }
        return text.replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&#39;", "'");
    }
}
