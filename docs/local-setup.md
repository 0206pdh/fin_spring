# 로컬 실행 가이드

## 요구 사항

- Docker Desktop
- Python 3.11+
- (선택) OpenAI API Key 또는 로컬 LLM (Mistral/Ollama)

---

## 1. 환경 설정

```bash
cp .env.example .env
# .env 파일에서 OPENAI_API_KEY 또는 로컬 LLM 설정
```

---

## 2. Docker로 DB + Redis 실행

```bash
docker compose up postgres redis -d

# 준비 확인
docker compose ps
```

---

## 3. Python 의존성 설치

```bash
pip install -r requirements.txt
```

---

## 4. DB 마이그레이션

```bash
# TimescaleDB, pgvector 포함 전체 마이그레이션
alembic upgrade head

# 마이그레이션 이력 확인
alembic history
```

---

## 5. 서버 실행 (터미널 1)

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 6. ARQ 워커 실행 (터미널 2)

```bash
arq app.worker.WorkerSettings
```

---

## 7. 파이프라인 수동 실행 (테스트)

```bash
# 비동기 enqueue (권장)
curl -X POST "http://localhost:8000/pipeline/enqueue?limit_per_category=5"

# 결과 확인
curl http://localhost:8000/heatmap
curl http://localhost:8000/timeline
```

---

## 8. WebSocket 테스트

```bash
# wscat 설치 후
npm install -g wscat
wscat -c ws://localhost:8000/ws/pipeline

# 이벤트 스코어 완료 시 자동 수신:
# {"type": "event_scored", "data": {"raw_event_id": "...", ...}}
```

---

## 전체 스택 한 번에 실행

```bash
# docker compose로 API + 워커까지 포함
docker compose up --build

# 마이그레이션 (첫 실행 시)
docker compose run --rm api alembic upgrade head
```

브라우저: `http://localhost:8000`
API 문서: `http://localhost:8000/docs`
