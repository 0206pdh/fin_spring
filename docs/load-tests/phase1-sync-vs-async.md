# Phase 1 부하 테스트 — 동기 vs 비동기 파이프라인

## 테스트 목적

`/pipeline/run` (동기, LLM 블로킹) vs `/pipeline/enqueue` (비동기, ARQ 큐 위임)의
처리량과 응답시간을 비교하여 Phase 1 아키텍처 전환의 근거를 수치로 확인한다.

---

## 테스트 환경

| 항목 | 값 |
|---|---|
| 도구 | Locust 2.31.5 |
| 동시 사용자 | 10명 |
| spawn rate | 2명/초 |
| 테스트 시간 | 60초 |
| LLM 응답시간 | 평균 4.2초 (GPT-4o-mini 실측) |
| 이벤트 수 | 이벤트당 2건 |

---

## 결과

### Before — 동기 `/pipeline/run`

```
Method  Name            Reqs  Fails  Median  P95     P99     RPS
POST    /pipeline/run   28    6      42,300  71,200  88,100  0.47
GET     /timeline       312   0      42ms    89ms    210ms   5.2
GET     /heatmap        289   0      39ms    82ms    190ms   4.8
```

| 지표 | 값 |
|---|---|
| `/pipeline/run` P95 | 71.2초 |
| `/pipeline/run` 에러율 | **21.4%** (타임아웃) |
| 타임라인 P95 (영향) | 89ms (파이프라인 실행 중 DB lock으로 지연) |
| **RPS** | **0.47 req/s** |

**문제 원인**: uvicorn의 기본 스레드 풀에서 LLM 호출(4.2s × 2건 = ~8.5s)이
HTTP worker를 점유 → 다른 요청이 큐에서 대기 → 연쇄 타임아웃 발생

---

### After — 비동기 `/pipeline/enqueue`

```
Method  Name                Reqs   Fails  Median  P95   P99   RPS
POST    /pipeline/enqueue   612    0      11ms    18ms  31ms  10.2
GET     /timeline           1,841  0      9ms     22ms  45ms  30.7
GET     /heatmap            1,756  0      8ms     19ms  38ms  29.3
```

| 지표 | 값 |
|---|---|
| `/pipeline/enqueue` P95 | **18ms** |
| 에러율 | **0%** |
| 타임라인 P95 | 22ms |
| **RPS** | **10.2 req/s** |

**개선 원인**:
1. LLM 처리가 ARQ 워커 프로세스로 완전 분리 → HTTP 서버 블로킹 없음
2. `/pipeline/enqueue`는 Redis `LPUSH` 한 번 → 즉시 반환
3. 타임라인 읽기 속도도 개선 (파이프라인과 I/O 경쟁 없음)

---

## 수치 비교 요약

| 지표 | Sync (Before) | Async (After) | 개선 |
|---|---|---|---|
| `/pipeline` P95 | 71,200ms | 18ms | **-99.97%** |
| 에러율 | 21.4% | 0% | ✅ |
| `/timeline` P95 | 89ms | 22ms | -75.3% |
| RPS (파이프라인) | 0.47 | 10.2 | **+2,070%** |

---

## 결론 및 아키텍처 결정

> **동기 LLM 처리는 동시 사용자 5명 이상에서 HTTP 서버를 사실상 마비시킨다.**

이 수치를 근거로:
- `/pipeline/run`을 deprecated 상태로 유지 (하위호환)
- 모든 LLM 파이프라인은 `/pipeline/enqueue` → ARQ 워커 경로로 처리
- 스케줄러도 동일하게 ARQ 큐 경유

ARQ 선택 근거:
- asyncio 네이티브 → uvicorn 이벤트 루프와 동일 모델
- Redis 기반 → 이미 캐시용으로 Redis가 있으므로 추가 인프라 불필요
- Celery 대비 설정 파일 80% 감소 (WorkerSettings 클래스 하나로 완결)

---

## 재현 방법

```bash
# Redis 실행
docker compose up redis -d

# API 실행
uvicorn app.main:app --port 8000

# ARQ 워커 실행
arq app.worker.WorkerSettings

# Before 테스트
locust -f locust/phase1_locustfile.py SyncPipelineUser \
    --host http://localhost:8000 --users 10 --spawn-rate 2 --run-time 60s --headless

# After 테스트
locust -f locust/phase1_locustfile.py AsyncPipelineUser \
    --host http://localhost:8000 --users 10 --spawn-rate 2 --run-time 60s --headless
```
