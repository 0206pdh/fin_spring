# 고도화 로드맵 — Financial Event-Driven Market Impact System

> 포트폴리오 목적: 실무 수준의 설계 판단력과 근거 있는 기술 선택을 보여주는 것
> 각 Phase는 부하 테스트 결과를 근거로 다음 단계의 선택을 정당화한다.

---

## 전체 Phase 요약

| Phase | 핵심 목표 | 기술 키워드 | 부하테스트 관점 |
|---|---|---|---|
| Phase 1 | 실시간 파이프라인 자동화 | APScheduler, ARQ, WebSocket | 동기 vs 비동기 처리량 비교 |
| Phase 2 | LLM 레이어 신뢰도 고도화 | LangGraph, Structured Output, pgvector | LLM 병렬 처리 한계 측정 |
| Phase 3 | 데이터 인프라 프로덕션화 | Alembic, TimescaleDB, Redis, Docker | 캐시 적용 전후 응답시간 비교 |
| Phase 4 | 프론트엔드 고도화 | React, D3.js, WebSocket 클라이언트 | (UI 성능 측정) |
| Phase 5 | 클라우드 인프라 | GitHub Actions CI/CD, ECS, Prometheus | (배포 파이프라인 검증) |
| Phase 6 | MSA 역할 분리 | Spring Boot Gateway, JWT, 폴리글랏 | (서비스 간 latency 측정) |

---

## Phase 1 — 실시간 파이프라인 자동화

### 문제 정의
현재 파이프라인은 완전 수동이다.
`POST /ingest/run` → `POST /events/normalize` → `POST /events/score` 를 직접 호출해야 하며,
LLM 호출(평균 3~8초)이 HTTP 요청을 블로킹한다.

**결과**: 10개 이벤트를 처리하면 API가 30~80초 응답불능 상태가 된다.

### 설계 선택 및 근거

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **ARQ** (Redis 기반 async job queue) | Celery | ARQ는 asyncio 네이티브, Celery보다 설정 단순, FastAPI와 자연스럽게 통합 |
| **APScheduler** | Celery Beat, cron | 프로세스 내 스케줄러로 별도 서비스 불필요, 포트폴리오 복잡도 적절 |
| **FastAPI WebSocket** | SSE, Polling | 양방향 지원, FastAPI 내장, 프론트 실시간 갱신에 최적 |

### 구현 목록
- `app/scheduler.py` — 15분 간격 자동 뉴스 수집 스케줄러
- `app/worker.py` — ARQ 비동기 워커 (LLM 정규화 + 스코어링)
- `app/ws_manager.py` — WebSocket 연결 풀 관리
- `app/main.py` 수정 — lifespan 기반 startup, WebSocket 엔드포인트 추가
- `locust/phase1_locustfile.py` — 동기 vs 비동기 처리량 부하 테스트

### 부하 테스트 시나리오
- **Before**: 동기 `/pipeline/run` 엔드포인트, 동시 10 사용자
- **After**: 비동기 job enqueue `/pipeline/enqueue`, 동시 10 사용자
- **측정 지표**: P95 응답시간, 초당 처리량(RPS), 에러율
- 결과 분석 → `docs/load-tests/phase1-sync-vs-async.md`

---

## Phase 2 — LLM 레이어 신뢰도 고도화

### 문제 정의
현재 LLM 처리의 문제:
1. 단일 LLM 호출 → 분류/추론/근거 생성이 한 번에 섞임
2. `_safe_json()` 파싱 헬퍼로 억지로 JSON 뽑아냄 → hallucination 방어 없음
3. 같은 뉴스를 중복 처리 (동일 이벤트가 여러 카테고리에서 수집됨)
4. LLM 응답 품질을 측정하는 지표 없음

**결과**: LLM confidence score가 항상 0.6~0.7로 수렴하고, 오분류를 감지할 수 없다.

### 설계 선택 및 근거

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **LangGraph** multi-step chain | 단일 프롬프트 | 분류/채널추론/근거 생성을 명시적 단계로 분리 → 추적 가능, 디버깅 가능 |
| **OpenAI Structured Output** (function calling) | `_safe_json()` | 스키마 보장, 파싱 실패 원천 차단, Pydantic 모델과 1:1 연결 |
| **pgvector** cosine similarity | 문자열 해시 비교 | 제목이 달라도 같은 사건인 뉴스 감지 가능, 의미론적 중복 제거 |

### 구현 목록
- `app/llm/chain.py` — LangGraph 3단계 체인 (classify → channel → rationale)
- `app/llm/structured.py` — Pydantic + function calling 기반 정규화
- `app/llm/evaluator.py` — 이벤트 타입별 confidence 히스토리 트래킹
- `app/store/vector_store.py` — pgvector 유사도 검색, 중복 감지
- `locust/phase2_locustfile.py` — LLM 병렬 처리 한계 측정

### 부하 테스트 시나리오
- **Before**: 단일 LLM 호출, 순차 처리
- **After**: LangGraph 체인 + 병렬 ARQ 워커 3개
- **측정 지표**: LLM 호출당 지연시간, 워커 포화 지점, confidence 분포 변화
- 결과 분석 → `docs/load-tests/phase2-llm-structured.md`

---

## Phase 3 — 데이터 인프라 프로덕션화

### 문제 정의
현재 DB 레이어의 문제:
1. `init_db()`가 `ALTER TABLE IF NOT EXISTS`를 매 startup마다 실행 → 스키마 변경 추적 불가
2. 단순 PostgreSQL 테이블 — 시계열 쿼리(`WHERE created_at > NOW() - INTERVAL '1h'`)가 풀스캔
3. `sector_heatmap()`이 매 요청마다 `SELECT sector_scores FROM scored_events` 전체를 집계
4. Docker 없음 → 환경 재현 불가, 배포 불가

**결과**: 이벤트 1,000건 이상에서 heatmap API 응답시간 > 2초, 프로덕션 배포 불가.

### 설계 선택 및 근거

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **Alembic** | `init_db()` 직접 수정 | 버전 관리된 마이그레이션, 롤백 가능, CI/CD와 통합 |
| **TimescaleDB** hypertable | 일반 PostgreSQL | 시계열 데이터에 자동 파티셔닝, time-bucket 집계 함수 제공, Postgres 호환 |
| **Redis** cache | 메모리 캐시 | 프로세스 재시작에도 캐시 유지, 워커와 API 간 공유 가능 |
| **Docker Compose** | 수동 설치 | 재현 가능한 환경, 면접관이 직접 실행 가능 |

### 구현 목록
- `alembic.ini` — Alembic 설정
- `alembic/env.py` — 마이그레이션 환경
- `alembic/versions/001_initial_schema.py` — 기존 스키마를 Alembic으로 이식
- `alembic/versions/002_timescaledb.py` — TimescaleDB hypertable 전환
- `alembic/versions/003_pgvector.py` — pgvector 확장, 임베딩 컬럼 추가
- `app/store/cache.py` — Redis 캐시 레이어 (heatmap, timeline TTL 30초)
- `app/config.py` 수정 — Redis 설정 추가
- `docker-compose.yml` — 전체 스택 (postgres+timescale+pgvector, redis, api, worker)
- `locust/phase3_locustfile.py` — 캐시 적용 전후 heatmap 응답시간 비교

### 부하 테스트 시나리오
- **Before**: 캐시 없는 heatmap, 동시 50 사용자
- **After**: Redis 캐시 30초 TTL, 동시 50 사용자
- **측정 지표**: P50/P95/P99 응답시간, DB CPU 사용률
- 결과 분석 → `docs/load-tests/phase3-cache-timescale.md`

---

## Phase 4 — 프론트엔드 고도화 (예정)

### 목표
- `src/` 프로토타입(React+Vite)을 실제 UI로 승격
- WebSocket 연결로 Timeline 실시간 갱신
- D3.js 기반 인터랙티브 히트맵 (색상 강도 = sector pressure)
- FX Bias 실시간 bar chart
- 이벤트 클릭 → LLM rationale 드릴다운

### 구현 예정 목록
- `src/components/Timeline.tsx` — WebSocket 구독 + 실시간 이벤트 목록
- `src/components/Heatmap.tsx` — D3 기반 섹터 히트맵
- `src/components/FxChart.tsx` — 통화 방향성 차트
- `src/components/EventDetail.tsx` — 이벤트 상세 + AI 설명

---

## Phase 5 — 클라우드 인프라 (예정)

### 목표
- GitHub Actions CI/CD: lint → test → Docker build → push to GHCR
- AWS ECS Fargate 배포 (FastAPI + Worker)
- Prometheus + Grafana 모니터링 (API latency, LLM 처리시간, 파이프라인 throughput)
- structlog JSON 로깅 → CloudWatch

### 구현 예정 목록
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`
- `infra/prometheus.yml`
- `infra/grafana/dashboards/pipeline.json`
- `app/logging_config.py` — structlog 설정

---

## Phase 6 — MSA 역할 분리 (예정)

### 목표
현재 Spring Boot와 Python이 거의 동일 기능을 중복 구현.
역할을 명확히 분리하여 "폴리글랏 MSA" 어필.

### 설계
```
[React Frontend]
      ↓
[Spring Boot — API Gateway + JWT 인증 + React 서빙]
      ↓ (내부 HTTP 호출)
[FastAPI — LLM + Rule Engine + 파이프라인 (내부 서비스)]
      ↓
[PostgreSQL(TimescaleDB) + Redis + pgvector]
```

| 서비스 | 언어 | 책임 |
|---|---|---|
| Spring Boot | Java | API Gateway, 인증(JWT), 사용자 세션, React 빌드 서빙 |
| FastAPI | Python | LLM 파이프라인, Rule Engine, 데이터 처리 |
| PostgreSQL | — | 이벤트 스토어 (TimescaleDB) |
| Redis | — | 작업 큐 (ARQ) + API 캐시 |

---

## 진행 상황

- [x] Phase 1 — 실시간 파이프라인 자동화
- [x] Phase 2 — LLM 레이어 고도화
- [x] Phase 3 — 데이터 인프라 프로덕션화
- [ ] Phase 4 — 프론트엔드 고도화
- [ ] Phase 5 — 클라우드 인프라
- [ ] Phase 6 — MSA 역할 분리
