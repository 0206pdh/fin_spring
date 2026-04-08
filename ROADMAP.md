# Financial Event-Driven Market Impact System Roadmap

## Current Position

This repository is now centered on a single Python service stack:

- FastAPI for HTTP and WebSocket APIs
- ARQ for async pipeline execution
- LangGraph for layered LLM normalization
- PostgreSQL + TimescaleDB + pgvector for event storage, time-series queries, and semantic dedupe
- Redis for queueing and cache

The old Spring duplicate backend was removed. The roadmap no longer includes a split Java gateway track.

---

## Phase Summary

| Phase | Goal | Status | Notes |
|---|---|---|---|
| Phase 1 | Async pipeline and live broadcast | Done | ARQ, APScheduler, WebSocket are wired into runtime |
| Phase 2 | Layered LLM normalization | Done | LangGraph chain, strict structured output, evaluator, semantic dedupe connected |
| Phase 3 | Production-ready data layer | In progress | Alembic, cache, Docker Compose exist; startup still keeps compatibility DDL |
| Phase 4 | Frontend integration | In progress | Backend live features exist, main React UI still only exposes part of them |
| Phase 5 | Deployment and observability | Planned | CI/CD, metrics, structured logging, managed deployment |
| Phase 6 | Grounding and analyst-quality reasoning | Planned | EDGAR grounding, better retrieval, richer evaluation |

---

## Phase 1: Async Pipeline and Live Broadcast

### Implemented

- `app/main.py`
  - `/pipeline/enqueue`
  - `/events/enqueue_one`
  - `/ws/pipeline`
- `app/worker.py`
  - `normalize_job`
  - `score_job`
  - `pipeline_batch_job`
  - `seed_replay_job`
- `app/scheduler.py`
  - fixed-interval batch enqueue
- `app/ws_manager.py`
  - connection tracking and event broadcast

### Remaining

- tighten worker retry policy and dead-letter behavior
- add queue depth and job failure metrics

---

## Phase 2: Layered LLM Normalization

### Goal

Move from a single opaque prompt to an explicit multi-layer LLM pipeline that is:

- inspectable
- schema-validated
- reusable across sync and async execution
- observable in production

### Implemented

- `app/llm/client.py`
  - OpenAI SDK wrapper for chat, strict JSON-schema output, and embeddings
- `app/llm/structured.py`
  - node-level Pydantic schemas:
    - `ClassificationOutput`
    - `ChannelOutput`
    - `RationaleOutput`
    - `NormalizationOutput`
- `app/llm/chain.py`
  - real LangGraph execution graph:
    - `classify`
    - `channel`
    - `rationale`
- `app/llm/normalize.py`
  - graph orchestration
  - output validation and normalization
  - rationale numeric guardrail
  - semantic duplicate reuse
  - embedding persistence
  - evaluator logging
- `app/llm/evaluator.py`
  - consistency logging into `llm_eval_log`
- `app/store/vector_store.py`
  - pgvector-backed semantic dedupe

### Definition of Done for Phase 2

- [x] LangGraph chain is used in the actual runtime path
- [x] node outputs are schema-validated
- [x] evaluator is called during normalization
- [x] semantic duplicate detection is called during normalization
- [x] embeddings are persisted for future retrieval and dedupe

---

## Phase 3: Production Data Layer

### Implemented

- Alembic migrations
- TimescaleDB migration for `scored_events`
- pgvector migration for `event_embeddings`
- Redis cache layer for `/heatmap` and `/timeline`
- Docker Compose stack for API, worker, Redis, and Postgres

### Remaining

- remove legacy schema patching from `init_db()`
- move all schema ownership fully to Alembic
- add migration smoke checks to CI

---

## Phase 4: Frontend Integration

### Current State

- main React app renders:
  - FX chart
  - heatmap
- backend already exposes:
  - live WebSocket updates
  - timeline
  - insight endpoint

### Remaining

- integrate `/ws/pipeline` into the main React app
- add timeline and event detail views
- show rationale, FX reasoning, and sector reasoning in the main UI
- remove or fold old prototype UI paths into one frontend

---

## Phase 5: Deployment and Observability

### Planned

- GitHub Actions for lint, test, image build
- container publish and deployment pipeline
- Prometheus/Grafana metrics
- structured logs for API, worker, and LLM calls
- alerting around queue lag and LLM failure rate

---

## Phase 6: Grounding and Analyst-Quality Reasoning

### Planned

- EDGAR-based grounding for rationale quality
- retrieval of similar historical events via `event_embeddings`
- richer evaluation reports beyond consistency rate
- rationale quality scoring and prompt regression tests

---

## Immediate Priority

1. Finish frontend integration against the now-complete Phase 2 backend.
2. Remove remaining legacy schema bootstrap logic from startup.
3. Add deployment automation and production observability.
