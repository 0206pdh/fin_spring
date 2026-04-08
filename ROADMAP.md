# 금융 이벤트 기반 시장 영향 분석 시스템 로드맵

## 현재 기준

이 저장소는 이제 단일 Python 서비스 스택 기준으로 정리되어 있습니다.

- FastAPI: HTTP / WebSocket API
- ARQ: 비동기 파이프라인 실행
- LangGraph: 계층형 LLM 정규화
- PostgreSQL + TimescaleDB + pgvector: 이벤트 저장, 시계열 조회, 의미 기반 중복 감지
- Redis: 큐와 캐시

기존 Spring 중복 백엔드는 제거했습니다. 따라서 로드맵에서도 Java 게이트웨이 분리 계획은 제외합니다.

---

## Phase 요약

| Phase | 목표 | 상태 | 비고 |
|---|---|---|---|
| Phase 1 | 비동기 파이프라인과 실시간 브로드캐스트 | 완료 | ARQ, APScheduler, WebSocket이 실제 런타임에 연결됨 |
| Phase 2 | 계층형 LLM 정규화 | 완료 | LangGraph 체인, structured output, evaluator, semantic dedupe 연결 완료 |
| Phase 3 | 프로덕션 지향 데이터 레이어 | 진행 중 | Alembic, 캐시, Docker Compose 존재. startup 호환 DDL은 아직 남아 있음 |
| Phase 4 | 프론트엔드 통합 | 진행 중 | 메인 React UI가 실시간 대시보드로 연결됨. 세부 polish와 정리는 남아 있음 |
| Phase 5 | 배포 및 관측성 | 예정 | CI/CD, 메트릭, 구조화 로그, 배포 자동화 |
| Phase 6 | grounding 및 분석 품질 강화 | 예정 | EDGAR grounding, retrieval, 평가 고도화 |

---

## Phase 1: 비동기 파이프라인과 실시간 브로드캐스트

### 구현 완료

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
  - 고정 주기 배치 enqueue
- `app/ws_manager.py`
  - 연결 관리 및 이벤트 브로드캐스트

### 남은 작업

- 워커 재시도 정책과 dead-letter 처리 정리
- queue depth / job failure 메트릭 추가

---

## Phase 2: 계층형 LLM 정규화

### 목표

단일 불투명 프롬프트에서 벗어나, 다음 조건을 만족하는 명시적 다층 LLM 파이프라인으로 전환합니다.

- 추적 가능
- 스키마 검증 가능
- sync / async 경로에서 재사용 가능
- 운영 중 관측 가능

### 구현 완료

- `app/llm/client.py`
  - OpenAI SDK 기반 chat / strict JSON schema / embedding 래퍼
- `app/llm/structured.py`
  - 노드 단위 Pydantic 스키마
    - `ClassificationOutput`
    - `ChannelOutput`
    - `RationaleOutput`
    - `NormalizationOutput`
- `app/llm/chain.py`
  - 실제 LangGraph 실행 그래프
    - `classify`
    - `channel`
    - `rationale`
- `app/llm/normalize.py`
  - 그래프 실행 오케스트레이션
  - 출력 정규화 및 검증
  - 숫자 근거 guardrail
  - 의미 기반 중복 재사용
  - embedding 저장
  - evaluator 로깅
- `app/llm/evaluator.py`
  - `llm_eval_log` 일관성 로깅
- `app/store/vector_store.py`
  - pgvector 기반 semantic dedupe

### Phase 2 완료 조건

- [x] LangGraph 체인이 실제 런타임 경로에서 사용됨
- [x] 각 노드 출력이 스키마 검증됨
- [x] normalization 시 evaluator가 호출됨
- [x] normalization 시 semantic duplicate detection이 호출됨
- [x] 향후 retrieval / dedupe용 embedding이 저장됨

---

## Phase 3: 프로덕션 지향 데이터 레이어

### 구현 완료

- Alembic 마이그레이션
- `scored_events`용 TimescaleDB 마이그레이션
- `event_embeddings`용 pgvector 마이그레이션
- `/heatmap`, `/timeline`용 Redis 캐시
- API / worker / Redis / Postgres용 Docker Compose

### 남은 작업

- `init_db()`의 레거시 schema patching 제거
- 스키마 소유권을 Alembic으로 완전히 이관
- CI에 migration smoke check 추가

---

## Phase 4: 프론트엔드 통합

### 현재 상태

- 메인 React 앱이 현재 다음을 실제로 사용함
  - FX 차트
  - heatmap
  - timeline
  - category별 뉴스 선택
  - event insight / rationale 패널
  - `/ws/pipeline` 기반 실시간 갱신
- 백엔드 실시간 경로와 메인 프론트가 동일 데이터 경로를 공유함

### 남은 작업

- 프론트 프로토타입 디렉터리와 구형 정적 UI 정리
- timeline 필터링 / 정렬 / 검색 UX 강화
- 실시간 상태와 파이프라인 제어 UX 다듬기
- 메인 UI 기준으로 화면 구성과 스타일 시스템 정리

---

## Phase 5: 배포 및 관측성

### 예정

- GitHub Actions 기반 lint / test / image build
- 컨테이너 publish 및 배포 파이프라인
- Prometheus / Grafana 메트릭
- API / worker / LLM 호출 구조화 로그
- queue lag / LLM failure rate 알림

---

## Phase 6: grounding 및 분석 품질 강화

### 예정

- EDGAR 기반 rationale grounding
- `event_embeddings`를 활용한 유사 이벤트 retrieval
- consistency rate를 넘는 평가 리포트
- rationale 품질 점수화 및 프롬프트 회귀 테스트

---

## 즉시 우선순위

1. 지금 완성된 Phase 2 백엔드를 기준으로 프론트엔드 통합을 마무리합니다.
2. startup의 레거시 schema bootstrap 로직을 제거합니다.
3. 배포 자동화와 운영 관측성을 추가합니다.
