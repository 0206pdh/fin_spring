# 시스템 아키텍처

## 전체 구조 (Phase 1~3 완료 기준)

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  Browser / API Client                                            │
│  - REST: /heatmap, /timeline, /graph, /pipeline/enqueue         │
│  - WebSocket: /ws/pipeline (실시간 scored event 수신)            │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────▼─────────────────────────────────────┐
│                      FastAPI (app/)                              │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ APScheduler │  │  WebSocket   │  │   REST Endpoints     │   │
│  │ (15min tick)│  │  Manager     │  │  /heatmap (cached)   │   │
│  └──────┬──────┘  └──────┬───────┘  │  /timeline (cached)  │   │
│         │                │          │  /pipeline/enqueue   │   │
│         │ enqueue        │ broadcast│  /events/eval/report │   │
└─────────┼────────────────┼──────────┴──────────────────────┴───┘
          │                │
          ▼                │
┌─────────────────┐        │         ┌──────────────────────────┐
│   Redis         │        │         │  Redis Cache Layer       │
│                 │        │         │  (app/store/cache.py)    │
│  [ARQ Queue]    │        │         │  heatmap: 30s TTL        │
│  normalize_job  │        │         │  timeline: 15s TTL       │
│  score_job      │        │         │  invalidated on score    │
│  batch_job      │        │         └────────────┬─────────────┘
└────────┬────────┘        │                      │
         │                 │                      │ MISS
         ▼                 │                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ARQ Worker (app/worker.py)                  │
│                                                                  │
│  normalize_job ──► LangGraph Chain (app/llm/chain.py)           │
│      ├─ classify_node   (event_type, risk_signal)               │
│      ├─ channel_node    (FX transmission channels)              │
│      └─ rationale_node  (keywords, rationale)                   │
│                                                                  │
│  score_job ──► Rule Engine (app/rules/engine.py)                │
│      ├─ compute_fx_delta()                                      │
│      ├─ compute_sector_delta_from_fx()                          │
│      ├─ apply_risk_sector_rules()                               │
│      └─ combine_baseline_delta()                                │
│                                                                  │
│  After score: ──► cache.invalidate_pipeline_caches()            │
│               ──► ws_manager.broadcast("event_scored", ...)     │
│               ──► llm_evaluator.log_eval(...)                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL + TimescaleDB + pgvector                 │
│                                                                  │
│  raw_events          — 원본 뉴스 이벤트                          │
│  normalized_events   — LLM 정규화 결과                          │
│  scored_events       — Rule Engine 스코어 (TimescaleDB hyper)   │
│  event_embeddings    — 제목 임베딩 (pgvector, 중복 감지)         │
│  llm_eval_log        — LLM 분류 일관성 추적                     │
│                                                                  │
│  Alembic 버전: 001 → 002(TimescaleDB) → 003(pgvector)          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 컴포넌트별 책임

| 컴포넌트 | 파일 | 책임 |
|---|---|---|
| APScheduler | `app/scheduler.py` | 15분 간격 자동 ingest 트리거 |
| ARQ Worker | `app/worker.py` | LLM + Rule Engine 비동기 처리 |
| WebSocket Manager | `app/ws_manager.py` | 실시간 이벤트 push |
| LangGraph Chain | `app/llm/chain.py` | 3단계 LLM 정규화 (분류→채널→근거) |
| Structured Output | `app/llm/structured.py` | OpenAI function calling 스키마 보장 |
| LLM Evaluator | `app/llm/evaluator.py` | 분류 일관성 모니터링 |
| Vector Store | `app/store/vector_store.py` | pgvector 기반 의미론적 중복 감지 |
| Cache | `app/store/cache.py` | Redis TTL 캐시 (heatmap, timeline) |
| Alembic | `alembic/` | 버전 관리 DB 마이그레이션 |

---

## 데이터 흐름

```
[News Source]
    │
    ▼ (APScheduler 15min)
[Ingest: apnews.py]
    │ fetch_raw_events()
    ▼
[raw_events table]
    │
    ▼ (ARQ: normalize_job)
[LangGraph Chain]
  classify → channel → rationale
    │
    ├─► [pgvector] 중복 체크 (cosine > 0.92 → skip)
    │
    ▼
[normalized_events table]
    │
    ▼ (ARQ: score_job)
[Rule Engine]
  fx_delta → sector_delta → combine_baseline
    │
    ├─► [llm_eval_log] 분류 일관성 기록
    ├─► [Redis] 캐시 무효화
    ├─► [WebSocket] 클라이언트에 실시간 push
    │
    ▼
[scored_events table (TimescaleDB hypertable)]
    │
    ▼ (API 요청 시)
[Redis Cache] → hit: 즉시 반환
               miss: DB 조회 → 캐시 저장 → 반환
```

---

## 인프라 (Docker Compose)

```
fim_postgres  ← timescale/timescaledb-ha:pg16 (TimescaleDB + pgvector 포함)
fim_redis     ← redis:7-alpine
fim_api       ← Python 3.11 FastAPI + APScheduler
fim_worker    ← Python 3.11 ARQ Worker
```

---

## Phase 4~6 예정 추가 컴포넌트

```
fim_frontend  ← React + Vite (WebSocket 실시간 UI)
fim_gateway   ← Spring Boot (API Gateway + JWT 인증)
Prometheus    ← 메트릭 수집
Grafana       ← 대시보드
GitHub Actions ← CI/CD
```
