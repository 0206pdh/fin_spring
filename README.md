# 금융 이벤트 기반 시장 영향 분석 시스템

이 프로젝트는 금융 뉴스를 수집한 뒤, 각 이벤트를 계층형 LLM 파이프라인으로 정규화하고, 룰 엔진으로 FX 바이어스와 섹터 압력을 계산한 후 REST API와 WebSocket으로 제공합니다.

## 기술 스택

- Python 3.11
- FastAPI
- ARQ
- LangGraph
- OpenAI 호환 LLM API
- PostgreSQL
- TimescaleDB
- pgvector
- Redis
- React + Vite

## 런타임 구조

1. 뉴스를 수집해 `raw_events`에 저장합니다.
2. ARQ 워커가 LangGraph 체인으로 이벤트를 정규화합니다.
3. 룰 엔진이 정규화 결과를 바탕으로 FX 바이어스와 섹터 압력을 계산합니다.
4. 결과를 `normalized_events`, `scored_events`, `event_embeddings`, `llm_eval_log`에 저장합니다.
5. FastAPI가 timeline, heatmap, graph, insight API를 제공합니다.
6. WebSocket 클라이언트는 실시간 `event_scored` 메시지를 받습니다.

## LLM 레이어

이제 LLM 경로는 단일 프롬프트가 아닙니다.

현재는 실제 LangGraph 3노드 체인으로 동작합니다.

- `classify`
  - 이벤트 유형
  - 정책 도메인
  - 리스크 시그널
  - confidence
- `channel`
  - 금리 시그널
  - 지정학 시그널
  - 전이 채널
  - regime
- `rationale`
  - 키워드
  - 근거 문장
  - sentiment
  - 직접 섹터 영향

각 노드는 `app/llm/structured.py`의 엄격한 스키마 검증을 통과한 JSON만 반환합니다.

상세 설명:
- [docs/llm-layer.md](docs/llm-layer.md)

## 주요 경로

- API 진입점: `app/main.py`
- 워커: `app/worker.py`
- LLM 클라이언트: `app/llm/client.py`
- LLM 스키마: `app/llm/structured.py`
- LLM 그래프: `app/llm/chain.py`
- LLM 오케스트레이션: `app/llm/normalize.py`
- 룰 엔진: `app/rules/engine.py`
- 캐시: `app/store/cache.py`
- 벡터 저장소: `app/store/vector_store.py`

## 로컬 실행

### Python API / Worker

가상환경 사용을 권장합니다.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
arq app.worker.WorkerSettings
```

로컬 실행 시 추가 체크:

- DB 마이그레이션을 먼저 적용해야 합니다.

```bash
alembic upgrade head
```

- Windows 로컬 Redis는 `localhost` 대신 `127.0.0.1`로 두는 편이 안전합니다.

```env
REDIS_URL=redis://127.0.0.1:6379/0
FIM_REDIS_URL=redis://127.0.0.1:6379/0
```

- 로컬 PostgreSQL에 `pgvector` 확장이 없으면 경고가 출력될 수 있습니다. 이 경우 기본 파이프라인 확인은 가능하지만 semantic dedupe는 비활성 상태가 됩니다.

### Docker Compose 전체 실행

```bash
docker compose up --build
```

## 테스트

```bash
pytest tests/test_rules.py tests/test_normalize.py tests/test_cache.py -v
```

## 현재 상태

- Phase 1 비동기 파이프라인: 완료
- Phase 2 계층형 LLM 런타임: 완료
- Phase 3 데이터 레이어 고도화: 일부 완료
- Phase 4 프론트엔드 통합: 진행 중
- Phase 5 배포/관측성: 예정
- Phase 6 grounding / retrieval 고도화: 예정
