# 아키텍처

## 현재 서비스 구조

현재 시스템은 단일 Python 서비스 스택으로 동작합니다. 기존 Spring 중복 백엔드는 제거됐습니다.

```text
브라우저 / React UI
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

## 핵심 컴포넌트

| 컴포넌트 | 파일 | 역할 |
|---|---|---|
| API | `app/main.py` | REST / WebSocket 엔드포인트 |
| Scheduler | `app/scheduler.py` | 주기적 배치 enqueue |
| Worker | `app/worker.py` | 비동기 normalize / score 작업 |
| LLM client | `app/llm/client.py` | chat, strict schema output, embeddings |
| Structured schemas | `app/llm/structured.py` | 노드 단위 출력 계약 |
| LangGraph chain | `app/llm/chain.py` | classify -> channel -> rationale |
| Normalization orchestration | `app/llm/normalize.py` | dedupe, graph 실행, validation, eval logging |
| Rule engine | `app/rules/engine.py` | FX / sector score 계산 |
| Cache | `app/store/cache.py` | heatmap / timeline 캐시 |
| Vector store | `app/store/vector_store.py` | semantic duplicate detection / embeddings |

## LLM 흐름

```text
raw_event
  -> pgvector duplicate check
  -> LangGraph classify node
  -> LangGraph channel node
  -> LangGraph rationale node
  -> 검증된 NormalizedEvent
  -> llm_eval_log 기록
  -> event_embeddings 기록
```

## 저장소 구조

- `raw_events`: 수집된 원본 뉴스
- `normalized_events`: 계층형 LLM 출력
- `scored_events`: 룰 엔진 출력
- `event_embeddings`: dedupe / 향후 retrieval용 pgvector row
- `llm_eval_log`: 일관성과 confidence 추적

## 프론트엔드 공백

백엔드는 이미 다음을 지원합니다.

- 실시간 WebSocket 업데이트
- timeline 데이터
- insight / rationale API

하지만 메인 React 앱은 아직 이 기능들을 직접 소비하지 않고 있습니다.
