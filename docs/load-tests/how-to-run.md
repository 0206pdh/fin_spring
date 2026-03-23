# 부하 테스트 실행 가이드

## 사전 조건

```bash
pip install locust==2.31.5
docker compose up -d  # postgres + redis 실행
alembic upgrade head  # 마이그레이션
uvicorn app.main:app --port 8000  # API 서버
arq app.worker.WorkerSettings     # ARQ 워커 (별도 터미널)
```

---

## Phase 1 — 동기 vs 비동기

### Step 1: Before (동기 블로킹)
```bash
locust -f locust/phase1_locustfile.py SyncPipelineUser \
    --host http://localhost:8000 \
    --users 10 --spawn-rate 2 --run-time 60s \
    --headless --csv=results/phase1_before
```

### Step 2: After (ARQ 비동기)
```bash
locust -f locust/phase1_locustfile.py AsyncPipelineUser \
    --host http://localhost:8000 \
    --users 10 --spawn-rate 2 --run-time 60s \
    --headless --csv=results/phase1_after
```

### 결과 확인
```bash
# P95 응답시간 비교
cat results/phase1_before_stats.csv
cat results/phase1_after_stats.csv
```

---

## Phase 2 — LLM 처리량 한계

```bash
# LLM insight 부하 (concurrent ceiling 측정)
locust -f locust/phase2_locustfile.py InsightHeavyUser \
    --host http://localhost:8000 \
    --users 5 --spawn-rate 1 --run-time 120s \
    --headless --csv=results/phase2_insight

# 혼합 트래픽 (현실적 시나리오)
locust -f locust/phase2_locustfile.py MixedPipelineUser \
    --host http://localhost:8000 \
    --users 20 --spawn-rate 2 --run-time 60s \
    --headless --csv=results/phase2_mixed
```

---

## Phase 3 — 캐시 전후 비교

### Step 1: Before (캐시 없음 — Redis 중지)
```bash
docker compose stop redis

locust -f locust/phase3_locustfile.py NoCacheUser \
    --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 60s \
    --headless --csv=results/phase3_before
```

### Step 2: After (Redis 캐시 활성화)
```bash
docker compose start redis

locust -f locust/phase3_locustfile.py WithCacheUser \
    --host http://localhost:8000 \
    --users 50 --spawn-rate 5 --run-time 60s \
    --headless --csv=results/phase3_after
```

---

## Web UI로 실시간 모니터링

```bash
# --headless 제거하면 http://localhost:8089 에서 UI 확인 가능
locust -f locust/phase3_locustfile.py WithCacheUser \
    --host http://localhost:8000
```

---

## 결과 업데이트

테스트 후 실측값으로 docs 업데이트:
```
docs/load-tests/phase1-sync-vs-async.md  ← P95 수치 교체
docs/load-tests/phase2-llm-structured.md ← throughput 수치 교체
docs/load-tests/phase3-cache-timescale.md ← cache 비교 수치 교체
```

결과 CSV는 `results/` 폴더에 보관 (gitignore 제외 권장).
