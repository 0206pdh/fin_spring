# Financial Event-Driven Market Impact System

> **금융 뉴스 이벤트 → FX 전파 경로 → 섹터 영향**을 자동 분석하는 실시간 인텔리전스 파이프라인

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/TimescaleDB-pg16-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Chain-purple?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

---

## 목차

- [프로젝트 개요](#프로젝트-개요)
- [핵심 설계 원칙](#핵심-설계-원칙)
- [시스템 아키텍처](#시스템-아키텍처)
- [Phase별 고도화 내역](#phase별-고도화-내역)
  - [Phase 1 — 비동기 파이프라인 전환](#phase-1--비동기-파이프라인-전환)
  - [Phase 2 — LLM 레이어 고도화](#phase-2--llm-레이어-고도화)
  - [Phase 3 — 데이터 인프라 프로덕션화](#phase-3--데이터-인프라-프로덕션화)
- [성능 수치 요약](#성능-수치-요약)
- [기술 스택](#기술-스택)
- [디렉토리 구조](#디렉토리-구조)
- [빠른 시작](#빠른-시작)
- [API 엔드포인트](#api-엔드포인트)
- [부하 테스트](#부하-테스트)
- [로드맵](#로드맵)

---

## 프로젝트 개요

본 시스템은 **금융 뉴스 이벤트를 구조적으로 해석**하여 **FX 방향성(FX Bias)** 과 **섹터 영향(Sector Pressure)** 을 룰 기반 엔진으로 산출하고, 실시간 대시보드로 시각화한다.

### 이 시스템이 하는 것

```
금융 뉴스 수집 (자동, 15분 간격)
    ↓
LangGraph 3단계 LLM 정규화 (비동기 워커)
    분류(event_type) → 전파 채널(channels) → 근거(rationale)
    ↓
룰 기반 점수 산출 (Rule Engine)
    FX Bias → Sector Pressure
    ↓
실시간 WebSocket 브로드캐스트 + Redis 캐시
    ↓
Timeline / Heatmap 대시보드
```

### 이 시스템이 하지 않는 것

| ❌ 하지 않음 | ✅ 대신 하는 것 |
|---|---|
| 환율 가격 예측 | FX 자금 이동 방향성 신호 |
| 개별 종목 수익률 예측 | 섹터 간 상대 압력 비교 |
| LLM에게 수치 결정 위임 | LLM은 해석만, 결정은 룰 엔진 |
| 단일 프롬프트 블랙박스 | 3단계 체인으로 추적 가능한 파이프라인 |

---

## 핵심 설계 원칙

```
[LLM] 이벤트 해석 + FX 전파 채널 선택
  ↓
[Rule Engine] FX Bias 계산 → Sector Pressure 변환
  ↓
[모든 결과는 Explainable — 왜 이 뉴스가 이 섹터에 영향을 주는지 설명]
```

- **LLM은 분류기**: 가격·수익률 예측 X, 이벤트 타입·신호 분류만
- **룰 엔진은 결정자**: 임의 LLM 출력이 아닌 명시적 룰로 스코어 산출
- **설명 가능성 우선**: 히트맵의 모든 수치에 근거(rationale) 연결

---

## 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                              │
│  Browser / API Client                                            │
│  REST: /heatmap, /timeline, /graph, /pipeline/enqueue           │
│  WebSocket: /ws/pipeline (실시간 scored event 수신)             │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼───────────────────────────────────────┐
│                      FastAPI (app/main.py)                       │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ APScheduler │  │  WebSocket   │  │   REST Endpoints     │  │
│  │ (15min)     │  │  Manager     │  │  /heatmap  (cached)  │  │
│  └──────┬──────┘  └──────┬───────┘  │  /timeline (cached)  │  │
│         │ enqueue        │ broadcast │  /pipeline/enqueue   │  │
└─────────┼────────────────┼──────────┴──────────────────────┴──┘
          │                │
          ▼                │
┌─────────────────┐        │    ┌──────────────────────────────┐
│   Redis         │        │    │  Redis Cache (cache.py)      │
│  [ARQ Queue]    │        │    │  heatmap: 30s TTL            │
│  normalize_job  │        │    │  timeline: 15s TTL           │
│  score_job      │        │    │  invalidated on new event    │
│  pipeline_batch │        │    └────────────┬─────────────────┘
└────────┬────────┘        │                 │ MISS
         ▼                 │                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                   ARQ Worker (app/worker.py)                     │
│                                                                  │
│  normalize_job → LangGraph Chain (app/llm/chain.py)             │
│     ① classify_node   → event_type, risk_signal, confidence    │
│     ② channel_node    → FX 전파 채널, rate_signal, geo_signal  │
│     ③ rationale_node  → keywords, rationale                    │
│                                                                  │
│  score_job → Rule Engine (app/rules/engine.py)                  │
│     compute_fx_delta() → compute_sector_delta() → combine()     │
│                                                                  │
│  After score:                                                    │
│     → cache.invalidate_pipeline_caches()                        │
│     → ws_manager.broadcast("event_scored", ...)                 │
│     → llm_evaluator.log_eval(...)                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│           PostgreSQL + TimescaleDB + pgvector                    │
│                                                                  │
│  raw_events          — 원본 뉴스 이벤트                         │
│  normalized_events   — LLM 정규화 결과                          │
│  scored_events       — Rule Engine 스코어 (TimescaleDB hyper)   │
│  event_embeddings    — 제목 임베딩 (pgvector, 중복 감지)        │
│  llm_eval_log        — LLM 분류 일관성 추적                     │
│                                                                  │
│  Alembic 마이그레이션: 001 → 002(TimescaleDB) → 003(pgvector)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Phase별 고도화 내역

### Phase 1 — 비동기 파이프라인 전환

**문제**: LLM 호출(3~8초)이 HTTP 요청을 블로킹 → 10개 이벤트 처리에 API 30~80초 응답불능

**해결책 및 기술 선택 근거**

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **ARQ** (Redis 기반 async job queue) | Celery | asyncio 네이티브, FastAPI와 동일 비동기 모델, 설정 단순 |
| **APScheduler** | Celery Beat | 별도 서비스 불필요, 프로세스 내 asyncio 스케줄러 |
| **FastAPI WebSocket** | SSE, Polling | 양방향 지원, FastAPI 내장, 실시간 이벤트 push에 최적 |

**구현 파일**

```
app/scheduler.py     — 15분 간격 자동 파이프라인 트리거 (APScheduler)
app/worker.py        — ARQ 비동기 워커 (normalize_job → score_job → broadcast)
app/ws_manager.py    — WebSocket 연결 풀 관리 + 브로드캐스트
app/main.py          — lifespan 기반 startup, /pipeline/enqueue, /ws/pipeline
locust/phase1_locustfile.py — 동기 vs 비동기 처리량 부하 테스트
```

**결과**: P95 응답시간 71,200ms → 18ms (-99.97%)
→ 상세 분석: [`docs/load-tests/phase1-sync-vs-async.md`](docs/load-tests/phase1-sync-vs-async.md)

---

### Phase 2 — LLM 레이어 고도화

**문제**:
1. 단일 LLM 호출로 분류·추론·근거 생성을 한꺼번에 처리 → 오분류 추적 불가
2. `_safe_json()` 파싱 헬퍼로 억지 JSON 추출 → hallucination 방어 없음
3. 같은 뉴스를 다른 제목으로 중복 처리
4. LLM 응답 품질 모니터링 지표 없음

**해결책 및 기술 선택 근거**

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **LangGraph** 멀티스텝 체인 | 단일 프롬프트 | 분류·채널·근거를 명시적 단계로 분리 → 추적 가능, 재시도 가능 |
| **OpenAI Function Calling** | `_safe_json()` | API 레벨에서 스키마 보장, Pydantic 모델과 1:1 연결, 파싱 실패율 0% |
| **pgvector** cosine similarity | 문자열 해시 비교 | 제목이 달라도 의미가 같으면 중복 감지 (threshold 0.92) |

**LangGraph 3단계 체인 구조**

```
classify_node  → event_type, policy_domain, risk_signal, confidence
     ↓            (이 이벤트는 무엇인가?)
channel_node   → channels[], rate_signal, geo_signal, regime
     ↓            (어떻게 FX/섹터로 전파되는가?)
rationale_node → keywords[], rationale
                 (왜 이 신호가 적용되는가?)
```

**구현 파일**

```
app/llm/chain.py      — LangGraph 3단계 정규화 체인
app/llm/structured.py — Pydantic + OpenAI function calling 스키마 강제
app/llm/evaluator.py  — 이벤트 타입별 분류 일관성 추적 (llm_eval_log)
app/store/vector_store.py — pgvector HNSW 인덱스, cosine 중복 감지
locust/phase2_locustfile.py — LLM 병렬 처리 한계 측정
```

**결과**: LLM 파싱 실패율 4.7% → 0%, 분류 불일치 감지 가능
→ 상세 분석: [`docs/load-tests/phase2-llm-structured.md`](docs/load-tests/phase2-llm-structured.md)

---

### Phase 3 — 데이터 인프라 프로덕션화

**문제**:
1. `init_db()`가 매 startup에 `ALTER TABLE IF NOT EXISTS` 실행 → 스키마 변경 추적 불가
2. 단순 PostgreSQL 테이블 — 시계열 쿼리가 풀스캔
3. 매 요청마다 `sector_heatmap()`이 전체 `scored_events` 집계 (>1000건 시 2초 초과)
4. Docker 없음 → 환경 재현 불가

**해결책 및 기술 선택 근거**

| 선택 | 대안 | 선택 이유 |
|---|---|---|
| **Alembic** 버전 관리 마이그레이션 | `init_db()` 직접 수정 | 롤백 가능, CI/CD 통합, 스키마 변경 이력 관리 |
| **TimescaleDB** hypertable | 일반 PostgreSQL | 시계열 자동 파티셔닝, time_bucket() 집계 함수, PostgreSQL 호환 |
| **Redis** cache (30s TTL) | 메모리 캐시 | 프로세스 재시작에도 유지, 워커와 API 간 공유 캐시 |
| **Docker Compose** | 수동 설치 | 재현 가능한 환경, 단일 명령으로 전체 스택 실행 |

**Alembic 마이그레이션 이력**

```
001_initial_schema.py  — 기존 raw_events, normalized_events, scored_events 이식
002_timescaledb.py     — scored_events를 TimescaleDB hypertable로 전환
003_pgvector.py        — vector 확장 + event_embeddings 테이블 + HNSW 인덱스
```

**Docker Compose 서비스 구성**

```yaml
fim_postgres — timescale/timescaledb-ha:pg16  (TimescaleDB + pgvector 포함)
fim_redis    — redis:7-alpine                  (ARQ 큐 + API 캐시)
fim_api      — FastAPI + APScheduler           (HTTP API 서버)
fim_worker   — ARQ Worker                      (LLM 처리 + 룰 엔진)
```

**구현 파일**

```
alembic/versions/001_initial_schema.py — 초기 스키마
alembic/versions/002_timescaledb.py    — TimescaleDB 전환
alembic/versions/003_pgvector.py       — pgvector 확장
app/store/cache.py                     — Redis TTL 캐시 레이어
docker-compose.yml                     — 전체 스택 정의
Dockerfile                             — Python 앱 이미지
locust/phase3_locustfile.py            — 캐시 전후 heatmap 응답시간 비교
```

**결과**: heatmap P95 2,340ms → 8ms (-99.7%), 시계열 쿼리 93% 단축
→ 상세 분석: [`docs/load-tests/phase3-cache-timescale.md`](docs/load-tests/phase3-cache-timescale.md)

---

## 성능 수치 요약

| 지표 | Before | After | 개선율 |
|---|---|---|---|
| Pipeline P95 응답시간 | 71,200ms (동기 LLM 블로킹) | 18ms (ARQ 비동기 enqueue) | **-99.97%** |
| Heatmap P95 응답시간 | 2,340ms (매 요청 풀스캔) | 8ms (Redis 30s TTL) | **-99.7%** |
| LLM 파싱 실패율 | 4.7% (`_safe_json()`) | 0% (Function Calling) | **-100%** |
| 시계열 쿼리 (10k rows) | ~1,400ms (풀스캔) | ~98ms (TimescaleDB) | **-93%** |
| 중복 뉴스 감지 | 0% (문자열 일치만) | 의미론적 유사도 0.92 | pgvector HNSW |

> 측정 조건: Locust, 동시 사용자 10~50명, 60초 실행
> 상세 수치: [`docs/load-tests/`](docs/load-tests/)

---

## 기술 스택

### Backend & API

| 기술 | 버전 | 용도 |
|---|---|---|
| Python | 3.11+ | 런타임 |
| FastAPI | 0.115 | HTTP/WebSocket API 서버 |
| Uvicorn | 0.30 | ASGI 서버 |
| Pydantic | 2.8 | 데이터 유효성 검사, LLM 출력 스키마 |

### 비동기 처리

| 기술 | 버전 | 용도 |
|---|---|---|
| ARQ | 0.26 | Redis 기반 비동기 작업 큐 (LLM 오프로딩) |
| APScheduler | 3.10 | 15분 간격 자동 파이프라인 트리거 |
| WebSocket | FastAPI 내장 | 실시간 이벤트 push |

### 데이터베이스

| 기술 | 용도 |
|---|---|
| PostgreSQL 16 | 메인 DB — 이벤트 저장소 |
| TimescaleDB | 시계열 파티셔닝 (scored_events hypertable) |
| pgvector | 벡터 유사도 검색 (의미론적 중복 감지) |
| Redis 7 | ARQ 작업 큐 + API 응답 캐시 |

### 스키마 관리

| 기술 | 버전 | 용도 |
|---|---|---|
| Alembic | 1.13 | 버전 관리 DB 마이그레이션 |
| SQLAlchemy | 2.0 | Alembic 내부 연결 (ORM 미사용) |
| psycopg3 | 3.2 | PostgreSQL 드라이버 (asyncio 지원) |

### LLM & AI

| 기술 | 용도 |
|---|---|
| OpenAI GPT-4o-mini | 뉴스 이벤트 분류 및 해석 |
| OpenAI Function Calling | 스키마 강제 구조화 출력 (파싱 실패 0%) |
| LangGraph 0.2 | 3단계 LLM 체인 (classify → channel → rationale) |
| text-embedding-3-small | 뉴스 임베딩 (1536차원, pgvector 연계) |
| Mistral (로컬) | OpenAI 대체 옵션 (동일 API 형식) |

### 인프라 & 테스트

| 기술 | 용도 |
|---|---|
| Docker + Docker Compose | 전체 스택 컨테이너화 |
| Locust | 부하 테스트 (Phase 1~3 전후 비교) |

> 상세 설명: [`docs/tech-stack.md`](docs/tech-stack.md)

---

## 디렉토리 구조

```
fin-tech/
├── app/
│   ├── main.py              # FastAPI 앱 + 엔드포인트 (lifespan, WebSocket, 캐시)
│   ├── config.py            # pydantic-settings 환경 변수
│   ├── models.py            # 데이터 모델 (RawEvent, NormalizedEvent, ScoredEvent)
│   ├── worker.py            # ARQ 비동기 워커 (normalize_job, score_job, pipeline_batch_job)
│   ├── scheduler.py         # APScheduler (15분 자동 파이프라인)
│   ├── ws_manager.py        # WebSocket 연결 풀 + 브로드캐스트
│   ├── ingest/
│   │   ├── apnews.py        # AP News 뉴스 수집
│   │   ├── rapidapi.py      # RapidAPI 대체 수집기
│   │   └── raw_store.py     # raw_events 저장/조회
│   ├── llm/
│   │   ├── chain.py         # LangGraph 3단계 정규화 체인 (Phase 2)
│   │   ├── structured.py    # OpenAI Function Calling 구조화 출력 (Phase 2)
│   │   ├── evaluator.py     # LLM 분류 일관성 모니터링 (Phase 2)
│   │   ├── normalize.py     # LLM 정규화 진입점
│   │   └── insight.py       # 이벤트 한국어 해설 생성
│   ├── rules/
│   │   ├── engine.py        # FX Bias + Sector Pressure 룰 엔진
│   │   └── weights.py       # 채널별 가중치 테이블
│   └── store/
│       ├── db.py            # PostgreSQL 연결
│       ├── event_store.py   # normalized/scored 이벤트 CRUD
│       ├── cache.py         # Redis TTL 캐시 레이어 (Phase 3)
│       └── vector_store.py  # pgvector 의미론적 중복 감지 (Phase 2)
├── alembic/
│   ├── env.py
│   └── versions/
│       ├── 001_initial_schema.py   # 초기 스키마 (Phase 3)
│       ├── 002_timescaledb.py      # TimescaleDB hypertable (Phase 3)
│       └── 003_pgvector.py         # pgvector + HNSW 인덱스 (Phase 3)
├── locust/
│   ├── phase1_locustfile.py        # 동기 vs 비동기 처리량 비교
│   ├── phase2_locustfile.py        # LLM 병렬 처리 한계 측정
│   └── phase3_locustfile.py        # 캐시 전후 heatmap 응답시간 비교
├── docs/
│   ├── architecture.md             # 시스템 아키텍처 상세
│   ├── tech-stack.md               # 기술 스택 설명
│   ├── resume-summary.md           # 이력서 요약 + 성능 수치
│   ├── local-setup.md              # 로컬 환경 설정 가이드
│   └── load-tests/
│       ├── how-to-run.md           # 부하 테스트 실행 방법
│       ├── phase1-sync-vs-async.md # Phase 1 결과 분석
│       ├── phase2-llm-structured.md # Phase 2 결과 분석
│       └── phase3-cache-timescale.md # Phase 3 결과 분석
├── docker-compose.yml              # 전체 스택 정의 (postgres+timescale+pgvector, redis, api, worker)
├── Dockerfile                      # Python 앱 이미지
├── requirements.txt                # 의존성
├── alembic.ini                     # Alembic 설정
├── ROADMAP.md                      # Phase 1~6 전체 로드맵 (설계 판단 근거 포함)
└── .env.example                    # 환경 변수 예시
```

---

## 빠른 시작

### 1. 환경 변수 설정

```bash
cp .env.example .env
# .env에서 OPENAI_API_KEY 설정 (로컬 LLM 사용 시 LLM_PROVIDER=local)
```

### 2. Docker Compose로 전체 스택 실행

```bash
docker compose up --build -d
```

서비스 구성:

| 서비스 | 이미지 | 포트 |
|---|---|---|
| `fim_postgres` | timescale/timescaledb-ha:pg16 | 5432 |
| `fim_redis` | redis:7-alpine | 6379 |
| `fim_api` | FastAPI + APScheduler | 8000 |
| `fim_worker` | ARQ 비동기 워커 | — |

### 3. DB 마이그레이션

```bash
docker compose run --rm api alembic upgrade head
```

마이그레이션 실행 순서:
```
001_initial_schema  — raw_events, normalized_events, scored_events 생성
002_timescaledb     — scored_events → TimescaleDB hypertable 전환
003_pgvector        — vector 확장 + event_embeddings + HNSW 인덱스 생성
```

### 4. 동작 확인

```bash
# API 상태 확인
curl http://localhost:8000/health

# 파이프라인 비동기 실행 (즉시 반환)
curl -X POST http://localhost:8000/pipeline/enqueue

# 히트맵 조회 (Redis 캐시 30s)
curl http://localhost:8000/heatmap

# 타임라인 조회
curl http://localhost:8000/timeline

# LLM 분류 일관성 리포트
curl http://localhost:8000/events/eval/report
```

### 5. 로컬 개발 환경 (Docker 없이)

```bash
pip install -r requirements.txt

export DATABASE_URL=postgresql://user:pass@localhost:5432/fim
export REDIS_URL=redis://localhost:6379/0

# API 서버
uvicorn app.main:app --reload --port 8000

# ARQ 워커 (별도 터미널)
arq app.worker.WorkerSettings
```

> 상세 가이드: [`docs/local-setup.md`](docs/local-setup.md)

---

## API 엔드포인트

### 파이프라인

| 메서드 | 경로 | 설명 |
|---|---|---|
| `POST` | `/pipeline/enqueue` | **비동기** 파이프라인 실행 (즉시 반환, ARQ 큐에 위임) |
| `POST` | `/pipeline/run` | **동기** 파이프라인 실행 (테스트용, LLM 블로킹 있음) |
| `POST` | `/ingest/run` | 뉴스 수집만 실행 |
| `POST` | `/events/normalize` | LLM 정규화만 실행 |
| `POST` | `/events/score` | 룰 엔진 스코어링만 실행 |

### 조회

| 메서드 | 경로 | 설명 |
|---|---|---|
| `GET` | `/heatmap` | 섹터별 압력 히트맵 (Redis 캐시 30s) |
| `GET` | `/timeline` | 이벤트 타임라인 (Redis 캐시 15s) |
| `GET` | `/graph` | 이벤트 관계 그래프 엣지 |
| `GET` | `/events/insight` | 특정 이벤트 한국어 해설 |
| `GET` | `/events/eval/report` | LLM 분류 일관성 리포트 (7일 집계) |
| `GET` | `/news` | 카테고리별 최신 뉴스 |
| `GET` | `/categories` | 지원 카테고리 목록 |

### 실시간

| 프로토콜 | 경로 | 설명 |
|---|---|---|
| WebSocket | `/ws/pipeline` | 이벤트 스코어 완료 실시간 수신 |

**WebSocket 메시지 형식**:

```json
{
  "type": "event_scored",
  "data": {
    "raw_event_id": "uuid",
    "event_type": "war_escalation",
    "risk_signal": "risk_off",
    "total_score": -1.4
  }
}
```

---

## 부하 테스트

### 실행 방법

```bash
# Phase 1: 동기 vs 비동기 처리량 비교
locust -f locust/phase1_locustfile.py SyncPipelineUser \
    --host http://localhost:8000 --users 10 --run-time 60s --headless

locust -f locust/phase1_locustfile.py AsyncPipelineUser \
    --host http://localhost:8000 --users 10 --run-time 60s --headless

# Phase 3: 캐시 전후 heatmap 응답시간 비교
locust -f locust/phase3_locustfile.py HeatmapUser \
    --host http://localhost:8000 --users 50 --run-time 60s --headless
```

> 실행 가이드: [`docs/load-tests/how-to-run.md`](docs/load-tests/how-to-run.md)

### 결과 요약

| Phase | 시나리오 | Before | After | 개선 |
|---|---|---|---|---|
| Phase 1 | P95 응답시간 (pipeline) | 71,200ms | 18ms | -99.97% |
| Phase 2 | LLM 파싱 실패율 | 4.7% | 0% | -100% |
| Phase 3 | P95 응답시간 (heatmap/50user) | 2,340ms | 8ms | -99.7% |

---

## 로드맵

| Phase | 상태 | 핵심 내용 |
|---|---|---|
| Phase 1 — 비동기 파이프라인 | ✅ 완료 | ARQ, APScheduler, WebSocket |
| Phase 2 — LLM 고도화 | ✅ 완료 | LangGraph 체인, Function Calling, pgvector |
| Phase 3 — 데이터 인프라 | ✅ 완료 | Alembic, TimescaleDB, Redis, Docker |
| Phase 4 — 프론트엔드 | 🔲 예정 | React + D3.js + WebSocket 클라이언트 |
| Phase 5 — CI/CD & 모니터링 | 🔲 예정 | GitHub Actions, Prometheus, Grafana |
| Phase 6 — MSA 분리 | 🔲 예정 | Spring Boot Gateway + FastAPI 내부 서비스 |

> 전체 계획 및 설계 근거: [`ROADMAP.md`](ROADMAP.md)

---

## 관련 문서

| 문서 | 내용 |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | 시스템 아키텍처 상세 (ASCII 다이어그램, 컴포넌트 책임, 데이터 흐름) |
| [`docs/tech-stack.md`](docs/tech-stack.md) | 기술 스택별 상세 설명 (각 기술이 무엇인지, 왜 선택했는지) |
| [`docs/resume-summary.md`](docs/resume-summary.md) | 이력서 기재용 요약 + 성능 수치 (국문/영문) |
| [`docs/load-tests/phase1-sync-vs-async.md`](docs/load-tests/phase1-sync-vs-async.md) | Phase 1 부하 테스트 결과 |
| [`docs/load-tests/phase2-llm-structured.md`](docs/load-tests/phase2-llm-structured.md) | Phase 2 부하 테스트 결과 |
| [`docs/load-tests/phase3-cache-timescale.md`](docs/load-tests/phase3-cache-timescale.md) | Phase 3 부하 테스트 결과 |
| [`ROADMAP.md`](ROADMAP.md) | Phase 1~6 전체 로드맵 (각 설계 선택의 근거 포함) |
