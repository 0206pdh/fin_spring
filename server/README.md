# Spring Backend

This module replaces the FastAPI service with a Spring Boot API that mirrors the same routes.

## Run

```bash
mvn -f server/pom.xml spring-boot:run
```

## Required configuration

- `DATABASE_URL` (preferred) or `SPRING_DATASOURCE_URL` (JDBC URL)
  - Example: `postgresql://user:pass@localhost:5432/finintel`
  - Or: `jdbc:postgresql://localhost:5432/finintel`

## Optional LLM configuration

- `FIM_LLM_PROVIDER=local|openai`
- `FIM_LLM_BASE_URL=http://localhost:8000/v1`
- `FIM_LLM_MODEL=mistral`
- `FIM_OPENAI_API_KEY=...`
- `FIM_OPENAI_MODEL=gpt-4o-mini`
- `FIM_OPENAI_BASE_URL=https://api.openai.com/v1`
