# 이력서 기재용 프로젝트 요약

## 프로젝트명
**Financial Event-Driven Market Impact System**
금융 뉴스 이벤트의 FX 전파 경로와 섹터 영향을 자동 분석하는 실시간 인텔리전스 파이프라인

---

## 3줄 요약 (이력서용)

```
금융 뉴스를 LangGraph 3단계 체인으로 정규화하고 룰 기반 엔진으로 FX Bias·섹터 압력을
실시간 산출하는 이벤트 파이프라인 설계 및 구현 (FastAPI + ARQ + TimescaleDB + pgvector)

동기 LLM 처리를 ARQ 비동기 워커로 전환해 P95 응답시간 71,200ms → 18ms(-99.97%),
Redis 30s TTL 캐시로 heatmap 처리량 1,827% 향상을 부하테스트(Locust)로 정량 검증

Alembic 기반 버전관리 마이그레이션, TimescaleDB 시계열 파티셔닝(쿼리 93% 단축),
pgvector 의미론적 중복 감지, Docker Compose 전체 스택 구성으로 프로덕션 수준 인프라 구축
```

---

## 영문 버전 (English)

```
Designed and implemented a real-time financial news intelligence pipeline that normalizes
events via a LangGraph 3-step chain (classify→channel→rationale) and scores FX bias /
sector pressure through a rule-based engine (FastAPI + ARQ + TimescaleDB + pgvector)

Replaced blocking synchronous LLM processing with ARQ async workers, reducing P95 latency
from 71,200ms to 18ms (-99.97%); applied Redis TTL caching to improve heatmap throughput
by 1,827×, validated by load testing with Locust (50 concurrent users)

Migrated schema management from ad-hoc DDL to Alembic versioned migrations; adopted
TimescaleDB hypertables (93% faster time-range queries at 10k rows) and pgvector HNSW
indexes for semantic duplicate detection; containerized full stack with Docker Compose
```

---

## 기술 키워드 (태그용)

`Python` `FastAPI` `PostgreSQL` `TimescaleDB` `pgvector` `Redis` `ARQ` `LangGraph`
`OpenAI function calling` `Alembic` `Docker` `Locust` `WebSocket` `APScheduler`
`Event-driven architecture` `Rule-based engine` `LLM pipeline` `Async worker`

---

## 어필 포인트 정리

| 역량 | 증거 |
|---|---|
| 설계 판단력 | ARQ vs Celery, TimescaleDB vs plain PG 선택에 수치 근거 제시 |
| 성능 엔지니어링 | Locust 부하 테스트 3종, 전후 수치 정량화 |
| LLM 실무 활용 | 단순 ChatGPT 호출이 아닌 structured output + chain + evaluator 설계 |
| 인프라 이해 | Docker Compose, Alembic, Redis, TimescaleDB 실제 구성 |
| 도메인 지식 | FX 전파 채널, 섹터 압력, risk_on/off 분류 설계 |
| 관찰 가능성 | LLM 일관성 모니터링(evaluator), WebSocket 실시간 이벤트 |
