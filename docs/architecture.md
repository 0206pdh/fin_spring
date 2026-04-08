# Architecture

## Current Service Shape

The system now runs as a single Python service stack. The duplicate Spring backend was removed.

```text
Browser / React UI
    -> REST / WebSocket
FastAPI
    -> Redis cache
    -> ARQ enqueue
ARQ Worker
    -> LangGraph normalization chain
    -> Rule engine scoring
    -> WebSocket broadcast
PostgreSQL + TimescaleDB + pgvector
Redis
```

## Core Components

| Component | File | Responsibility |
|---|---|---|
| API | `app/main.py` | REST and WebSocket endpoints |
| Scheduler | `app/scheduler.py` | periodic batch enqueue |
| Worker | `app/worker.py` | async normalize and score jobs |
| LLM client | `app/llm/client.py` | chat, strict schema output, embeddings |
| Structured schemas | `app/llm/structured.py` | node-level output contracts |
| LangGraph chain | `app/llm/chain.py` | classify -> channel -> rationale |
| Normalization orchestration | `app/llm/normalize.py` | dedupe, graph execution, validation, eval logging |
| Rule engine | `app/rules/engine.py` | FX and sector score calculation |
| Cache | `app/store/cache.py` | heatmap and timeline caching |
| Vector store | `app/store/vector_store.py` | semantic duplicate detection and embeddings |

## LLM Flow

```text
raw_event
  -> duplicate check via pgvector
  -> LangGraph classify node
  -> LangGraph channel node
  -> LangGraph rationale node
  -> validated NormalizedEvent
  -> llm_eval_log write
  -> event_embeddings write
```

## Storage

- `raw_events`: ingested news items
- `normalized_events`: layered LLM output
- `scored_events`: rule-engine output
- `event_embeddings`: pgvector rows for dedupe and future retrieval
- `llm_eval_log`: consistency and confidence tracking

## Frontend Gap

The backend now supports:

- live WebSocket updates
- timeline data
- insight/rationale APIs

The main React app still needs to consume these features directly.
