# 기술 스택 상세 설명

> 이 프로젝트에서 실제로 사용된 기술들을 분류별로 정리한다.

---

## 웹 프레임워크

### FastAPI
- Python용 웹 프레임워크. Flask보다 빠르고 자동으로 API 문서(`/docs`)를 만들어줌
- `@app.get("/heatmap")` 같이 데코레이터로 엔드포인트 정의
- asyncio 기반 → 비동기 처리에 최적화
- **이 프로젝트**: API 서버 전체, WebSocket 엔드포인트 (`app/main.py`)

### Uvicorn
- FastAPI를 실제로 실행시켜주는 서버 (ASGI 서버)
- FastAPI 자체는 "앱 설계도"고, Uvicorn이 "실제로 포트 열고 요청 받는 것"
- `uvicorn app.main:app --port 8000`

### Pydantic
- Python 데이터 유효성 검사 라이브러리
- `class NormalizedEvent(BaseModel)` 처럼 타입을 정의하면 자동으로 검증해줌
- **이 프로젝트**: LLM 출력을 스키마에 맞게 강제할 때 핵심 역할 (`app/models.py`, `app/llm/structured.py`)

### pydantic-settings
- `.env` 파일을 읽어서 `settings.database_url` 처럼 Python 객체로 쓸 수 있게 해줌
- **이 프로젝트**: `app/config.py`의 `Settings` 클래스

---

## 데이터베이스

### PostgreSQL
- 이 프로젝트의 메인 DB. 뉴스 이벤트, 분석 결과 전부 여기 저장
- **이 프로젝트**: `raw_events`, `normalized_events`, `scored_events` 테이블

### psycopg3 (`psycopg[binary]`)
- Python에서 PostgreSQL에 연결하는 드라이버 (라이브러리)
- psycopg2가 구버전, psycopg3이 최신 (asyncio 지원)
- **이 프로젝트**: `app/store/db.py`에서 `psycopg.connect(url)`로 SQL 직접 실행

### TimescaleDB
- PostgreSQL 확장(Extension). 시계열 데이터에 특화
- `scored_events` 테이블을 "hypertable"로 전환 → 날짜 기준으로 자동 파티셔닝
- `WHERE created_at > NOW() - INTERVAL '24h'` 같은 쿼리가 일반 PostgreSQL 대비 최대 93% 빠름
- **이 프로젝트**: `docker-compose.yml`의 `timescaledb-ha` 이미지로 별도 설치 없이 사용, `alembic/versions/002_timescaledb.py`

### pgvector
- PostgreSQL 확장. 벡터(숫자 배열) 저장 + 유사도 검색 기능 추가
- "이 뉴스랑 비슷한 뉴스 찾아줘"가 가능해짐 (cosine similarity)
- **이 프로젝트**: 중복 뉴스 감지 — 제목이 달라도 의미가 같으면 재처리 방지 (`app/store/vector_store.py`)

### SQLAlchemy
- Python ORM(Object-Relational Mapping)의 대표 라이브러리
- **이 프로젝트**: Alembic이 DB에 연결할 때 내부적으로만 사용. 직접 쿼리 작성엔 미사용

### Alembic
- DB 스키마 버전 관리 도구. git이 코드를 버전 관리하듯, DB 구조 변경을 버전 관리
- `upgrade()` (적용) + `downgrade()` (롤백) 함수로 언제든 이전 상태로 되돌릴 수 있음
- **이 프로젝트**: `init_db()`의 17줄짜리 ALTER TABLE 패치를 3개의 버전 파일로 대체

```bash
alembic upgrade head   # 최신 스키마로
alembic downgrade -1   # 직전 버전으로 롤백
alembic history        # 전체 변경 이력 확인
alembic current        # 현재 DB 버전 확인
```

---

## 비동기 처리 & 메시지 큐

### Redis
- 인메모리(RAM) 데이터 저장소. 디스크 기반 DB보다 수십 배 빠름
- **이 프로젝트에서 두 가지 역할**:
  1. **ARQ 작업 큐**: LLM 처리 요청을 리스트로 쌓아두고 워커가 꺼내감
  2. **API 캐시**: heatmap 결과를 30초간 저장 → 매 요청마다 DB 안 뒤져도 됨 (처리량 +1,827%)

### ARQ
- Redis 기반 비동기 작업 큐 라이브러리
- `await redis.enqueue_job("normalize_job", event_id)` → 워커에게 일 위임하고 즉시 반환
- Celery보다 가볍고 asyncio 네이티브 (FastAPI와 동일한 비동기 모델)
- **이 프로젝트**: LLM 처리를 HTTP 서버에서 분리 (`app/worker.py`)

```
HTTP 요청 → /pipeline/enqueue → Redis에 job 추가 → 즉시 응답 (12ms)
                                        ↓
                                   ARQ 워커가 꺼내서 처리 (LLM 호출 ~7s)
```

### APScheduler
- Python 스케줄러 라이브러리. 정해진 시간마다 함수를 자동 실행
- **이 프로젝트**: 15분마다 뉴스 수집 자동 트리거 (`app/scheduler.py`)

```python
scheduler.add_job(fn, IntervalTrigger(minutes=15))
```

### WebSocket
- 서버↔클라이언트 간 지속 연결 프로토콜
- HTTP는 "요청 → 응답 → 연결 끊김"이지만 WebSocket은 연결을 유지하며 양방향 통신
- **이 프로젝트**: `/ws/pipeline` 연결하면 새 이벤트 스코어 완료 시 서버가 자동 push (`app/ws_manager.py`)

---

## LLM & AI

### OpenAI API (gpt-4o-mini)
- 뉴스를 분석해서 event_type, risk_signal, channels 등 구조화된 정보 추출
- **이 프로젝트**: `app/llm/normalize.py`, `app/llm/insight.py`

### OpenAI Function Calling (Structured Output)
- LLM한테 "이 JSON 형식으로만 대답해"를 API 레벨에서 강제하는 기능
- 기존 방식: LLM이 자유 텍스트로 답 → `_safe_json()`으로 억지 파싱 → 실패율 4.7%
- 신규 방식: OpenAI가 스키마를 보장하여 반환 → 파싱 실패율 0%
- **이 프로젝트**: `app/llm/structured.py`

### LangGraph
- LLM 호출을 여러 단계(노드)로 구성하는 프레임워크
- 단일 프롬프트 대신 역할을 분리해 각 단계를 독립적으로 처리
- **이 프로젝트**: classify → channel → rationale 3단계 체인 (`app/llm/chain.py`)

```
단일 호출:  [분류 + 채널 + 근거 한꺼번에] → 혼재, 디버깅 어려움
LangGraph:  classify → channel → rationale → 단계별 추적 가능
```

### text-embedding-3-small (OpenAI)
- 텍스트를 1536차원 숫자 배열(벡터)로 변환하는 임베딩 모델
- 의미가 비슷한 문장은 벡터도 비슷 → cosine similarity로 유사도 계산 가능
- **이 프로젝트**: pgvector와 연계해 의미론적 중복 뉴스 감지 (`app/store/vector_store.py`)

```
"Fed raises rates 25bp"          → [0.02, -0.15, 0.88, ...] (1536개 숫자)
"Federal Reserve hikes benchmark" → [0.03, -0.14, 0.87, ...] → 유사도 0.97 → 중복
```

### Mistral (로컬 LLM)
- OpenAI API 없이 로컬에서 실행하는 LLM 옵션
- OpenAI 호환 API 형식으로 호출 → 코드 변경 없이 provider만 교체 가능
- **이 프로젝트**: `app/llm/mistral_client.py`

---

## 인프라

### Docker
- 앱을 컨테이너로 패키징. "내 PC에서만 되는 문제" 없앰
- **이 프로젝트**: `Dockerfile` — Python 앱 이미지 빌드 설명서

### Docker Compose
- 여러 컨테이너를 한 번에 정의하고 관리
- **이 프로젝트**: `docker-compose.yml` — postgres + redis + api + worker 한 번에 실행

```bash
docker compose up -d          # 전체 스택 백그라운드 실행
docker compose stop redis     # Redis만 중지
docker compose logs worker    # 워커 로그 확인
```

---

## 테스트 & 품질

### Locust
- Python으로 부하 테스트 시나리오를 코드로 작성하는 도구
- 가상 사용자(User) 클래스를 정의해 실제 사용자 행동을 시뮬레이션
- P50/P95/P99 응답시간, RPS(초당 요청수), 에러율 자동 측정
- **이 프로젝트**: `locust/phase1,2,3_locustfile.py` — 각 Phase 전후 성능 비교

```bash
locust -f locust/phase1_locustfile.py SyncPipelineUser \
    --host http://localhost:8000 --users 10 --run-time 60s --headless
```

---

## 요약 테이블

| 분류 | 기술 | 역할 | 관련 파일 |
|---|---|---|---|
| 웹 서버 | FastAPI + Uvicorn | HTTP/WebSocket API 서버 | `app/main.py` |
| 데이터 검증 | Pydantic | LLM 출력 스키마 강제 | `app/models.py` |
| 환경 설정 | pydantic-settings | .env → Python 객체 | `app/config.py` |
| DB | PostgreSQL | 이벤트 저장소 | `app/store/` |
| DB 드라이버 | psycopg3 | Python → PostgreSQL 연결 | `app/store/db.py` |
| 시계열 DB | TimescaleDB | 날짜 기반 파티셔닝 | `alembic/versions/002` |
| 벡터 검색 | pgvector | 의미 유사도 검색 | `app/store/vector_store.py` |
| 스키마 관리 | Alembic | DB 버전 관리 | `alembic/` |
| 캐시 | Redis | API 응답 캐시 (TTL) | `app/store/cache.py` |
| 작업 큐 | ARQ | LLM 처리 비동기 오프로드 | `app/worker.py` |
| 스케줄러 | APScheduler | 15분 자동 실행 | `app/scheduler.py` |
| 실시간 통신 | WebSocket | 이벤트 실시간 push | `app/ws_manager.py` |
| LLM | OpenAI GPT-4o-mini | 뉴스 해석/분류 | `app/llm/normalize.py` |
| 구조화 출력 | Function Calling | LLM 스키마 보장 | `app/llm/structured.py` |
| LLM 체인 | LangGraph | 멀티스텝 파이프라인 | `app/llm/chain.py` |
| 임베딩 | text-embedding-3-small | 텍스트 → 벡터 변환 | `app/store/vector_store.py` |
| 로컬 LLM | Mistral | OpenAI 대체 옵션 | `app/llm/mistral_client.py` |
| 컨테이너 | Docker + Compose | 환경 패키징 | `Dockerfile`, `docker-compose.yml` |
| 부하 테스트 | Locust | 성능 측정 | `locust/` |
