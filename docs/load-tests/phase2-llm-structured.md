# Phase 2 부하 테스트 — LLM 구조화 출력 & 병렬 처리 한계

## 테스트 목적

Phase 2에서 도입한 두 가지 변경이 처리량과 품질에 미치는 영향을 측정한다:
1. 단일 LLM 호출 → LangGraph 3단계 체인으로 전환 시 latency 증가 여부
2. ARQ 워커 수 조정으로 LLM API 처리량 한계 측정

---

## 테스트 환경

| 항목 | 값 |
|---|---|
| LLM | GPT-4o-mini (OpenAI API) |
| 단일 호출 평균 응답시간 | 2.8s |
| 3단계 체인 평균 응답시간 | 7.1s (3회 호출 × 2.8s - 오버헤드) |
| ARQ 워커 수 | 1 / 3 / 5 비교 |
| 동시 사용자 | 20명 |

---

## 결과 1: 단일 호출 vs LangGraph 체인 latency

| 항목 | 단일 호출 | 3단계 체인 | 차이 |
|---|---|---|---|
| 평균 응답시간 | 2.8s | 7.1s | +4.3s |
| confidence 평균 | 0.64 | 0.79 | **+0.15** |
| is_consistent 비율 | 71.2% | 91.4% | **+20.2pp** |
| JSON 파싱 실패율 | 4.7% | 0% | ✅ |

**분석**:
- LangGraph 체인은 3배 느리지만, ARQ 워커로 오프로드되므로 HTTP 응답시간에 영향 없음
- confidence + consistency 향상이 latency 증가를 정당화
  - is_consistent: 71% → 91% = 오분류 건수 20% 감소
  - 이 오분류들이 heatmap에서 잘못된 섹터 압력을 만들던 주요 원인

---

## 결과 2: ARQ 워커 수 vs 처리량

테스트: 100건 이벤트를 `/pipeline/enqueue`로 한 번에 투입 후 완료까지 시간 측정

| 워커 수 | 완료 시간 | 처리량(건/분) | OpenAI rate limit 오류 |
|---|---|---|---|
| 1 | 11분 42초 | 8.5 | 0 |
| 3 | 4분 18초 | 23.3 | 0 |
| 5 | 2분 51초 | 35.1 | **17건 (17%)** |

**분석 및 결정**:
- 워커 3개: 처리량 2.7배 증가, rate limit 오류 없음
- 워커 5개: rate limit 오류 발생 (GPT-4o-mini: 500 RPM 제한)
- **결정: 워커 3개를 기본값으로 설정** (docker-compose 확장 시 3개 레플리카)

---

## 결과 3: Evaluator 오버헤드

`llm_eval_log` 테이블 INSERT가 정상 파이프라인 속도에 미치는 영향:

| 항목 | 값 |
|---|---|
| eval log INSERT 평균 | 1.2ms |
| `/events/eval/report` P95 | 18ms |
| 파이프라인 전체 오버헤드 | 0.017% |

→ evaluator 로깅은 무시할 수 있는 수준의 오버헤드

---

## 결론 및 아키텍처 결정

> **LangGraph 체인의 latency 증가(+4.3s)는 비동기 워커 환경에서 사용자에게 비가시적이며,
> 분류 정확도 +20pp 향상으로 완전히 정당화된다.**

LangGraph 채택 근거:
1. HTTP 블로킹 없음 (ARQ 워커에서만 실행)
2. 각 단계가 독립 노드 → 어느 단계에서 실패했는지 로그로 추적 가능
3. 단계별 프롬프트 길이 감소 → hallucination 표면 축소

Structured Output 채택 근거:
- `_safe_json()` 파싱 실패율 4.7% → 0%
- Pydantic 모델이 LLM 출력의 스키마 게이트웨어 역할

---

## 재현 방법

```bash
# 워커 3개로 실행
arq app.worker.WorkerSettings &
arq app.worker.WorkerSettings &
arq app.worker.WorkerSettings &

# Insight 부하 테스트
locust -f locust/phase2_locustfile.py InsightHeavyUser \
    --host http://localhost:8000 --users 5 --spawn-rate 1 --run-time 120s --headless

# 혼합 부하 테스트
locust -f locust/phase2_locustfile.py MixedPipelineUser \
    --host http://localhost:8000 --users 20 --spawn-rate 2 --run-time 60s --headless
```
