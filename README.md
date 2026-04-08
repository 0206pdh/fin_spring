# Financial Event-Driven Market Impact System

This project ingests financial news, normalizes each event through a layered LLM pipeline, scores the event with a rule engine, and serves the result through REST and WebSocket APIs.

## Stack

- Python 3.11
- FastAPI
- ARQ
- LangGraph
- OpenAI-compatible LLM API
- PostgreSQL
- TimescaleDB
- pgvector
- Redis
- React + Vite

## Runtime Architecture

1. News is fetched and stored as `raw_events`.
2. ARQ workers normalize events through a LangGraph chain.
3. The rule engine converts the normalized event into FX bias and sector pressure.
4. Results are persisted to `normalized_events`, `scored_events`, `event_embeddings`, and `llm_eval_log`.
5. FastAPI serves timeline, heatmap, graph, and insight APIs.
6. WebSocket clients receive live `event_scored` messages.

## LLM Layer

The LLM path is no longer a single prompt.

It is now a real three-node LangGraph chain:

- `classify`
  - event type
  - policy domain
  - risk signal
  - confidence
- `channel`
  - rate signal
  - geo signal
  - transmission channels
  - regime
- `rationale`
  - keywords
  - rationale
  - sentiment
  - direct sector impacts

Each node returns strict schema-validated JSON through `app/llm/structured.py`.

Detailed documentation:
- [docs/llm-layer.md](docs/llm-layer.md)

## Main Paths

- API entrypoint: `app/main.py`
- Worker: `app/worker.py`
- LLM client: `app/llm/client.py`
- LLM schemas: `app/llm/structured.py`
- LLM graph: `app/llm/chain.py`
- LLM orchestration: `app/llm/normalize.py`
- Rule engine: `app/rules/engine.py`
- Cache: `app/store/cache.py`
- Vector store: `app/store/vector_store.py`

## Local Run

### Python API and worker

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
arq app.worker.WorkerSettings
```

### Full stack with Docker Compose

```bash
docker compose up --build
```

## Tests

```bash
pytest tests/test_rules.py tests/test_normalize.py tests/test_cache.py -v
```

## Current Status

- Phase 1 async pipeline: done
- Phase 2 layered LLM runtime: done
- Phase 3 data layer hardening: partially done
- Phase 4 frontend integration: in progress
- Phase 5 deployment/observability: planned
- Phase 6 grounding/retrieval upgrades: planned
