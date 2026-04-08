# LLM 레이어

## 왜 기존 설계가 부족했는가

이전 정규화 경로는 하나의 프롬프트에서 다음 일을 모두 처리하려고 했습니다.

- 이벤트 분류
- 시장 전이 채널 추론
- 시장 영향 설명
- 파싱 가능한 JSON 출력

이 방식에는 구조적인 문제가 세 가지 있었습니다.

1. 분류와 설명이 강하게 결합되어 있었습니다.
2. JSON 파싱이 자유 텍스트 후처리에 의존했습니다.
3. 문서에 있던 LangGraph / structured-output 설계가 실제 런타임에는 연결되지 않았습니다.

이번 업데이트는 실제 런타임 경로를 계층형 구조로 바꿔 이 문제를 정리합니다.

---

## 현재 LLM 아키텍처

이제 LLM 스택은 네 개의 레이어로 나뉩니다.

### 1. 전송 레이어

파일:
- `app/llm/client.py`

역할:
- OpenAI 호환 SDK 클라이언트 초기화
- 일반 chat 요청 전송
- strict JSON schema 요청 전송
- semantic dedupe용 embedding 요청

노출 메서드:
- `chat()`
- `structured_chat()`
- `embedding()`

이 레이어는 API 전송 세부사항을 정규화 로직 밖으로 분리합니다.

---

### 2. 스키마 레이어

파일:
- `app/llm/structured.py`

역할:
- 각 LLM 노드의 출력 계약을 Pydantic으로 정의
- 그 계약을 strict JSON schema로 변환
- 각 노드 응답을 다음 단계로 넘기기 전에 검증

노드 스키마:
- `ClassificationOutput`
- `ChannelOutput`
- `RationaleOutput`

병합 스키마:
- `NormalizationOutput`

중요한 이유:
- 각 노드의 책임이 좁고 명확해짐
- 실패 지점이 국소화됨
- downstream이 loose dict 대신 typed data를 받음

---

### 3. 오케스트레이션 레이어

파일:
- `app/llm/chain.py`

역할:
- LangGraph 워크플로우 정의
- 노드를 안정된 순서로 실행
- state 객체를 명시적으로 유지

그래프:

```text
classify -> channel -> rationale
```

#### classify 노드

입력:
- title
- sector
- published_at
- 기사 세부 텍스트

출력:
- `event_type`
- `policy_domain`
- `risk_signal`
- `confidence`

목적:
- 설명을 쓰기 전에 먼저 이벤트 자체를 결정

#### channel 노드

입력:
- 분류 결과
- 기사 문맥

출력:
- `rate_signal`
- `geo_signal`
- `channels`
- `regime`

목적:
- 이벤트가 FX와 섹터 압력으로 어떻게 전이되는지 결정

#### rationale 노드

입력:
- 이벤트 분류 결과
- 선택된 채널
- 기사 문맥

출력:
- `keywords`
- `rationale`
- `sentiment`
- `sector_impacts`

목적:
- 분류가 안정된 뒤 analyst-style 설명을 생성

---

### 4. 런타임 오케스트레이션 레이어

파일:
- `app/llm/normalize.py`

역할:
- semantic dedupe를 먼저 호출
- LangGraph 체인 실행
- 출력 정규화 및 guardrail 적용
- primary signal에서 implied channel 추가
- rationale 숫자 품질 강제
- embedding 저장
- 평가 telemetry 기록
- 최종 `NormalizedEvent` 반환

이 파일이 실제로 LLM 로직과 worker/API 파이프라인을 연결하는 런타임 브리지입니다.

---

## 전체 런타임 흐름

```text
RawEvent
  -> embedding text 생성
  -> pgvector duplicate check
  -> 중복이고 기존 normalization이 있으면:
       기존 normalization 재사용
     아니면:
       LangGraph classify node 실행
       LangGraph channel node 실행
       LangGraph rationale node 실행
       결과 병합
       필드 정규화 및 검증
  -> embedding 저장
  -> evaluator row 기록
  -> NormalizedEvent 반환
```

---

## 왜 LangGraph가 필요한가

현재 그래프는 선형이지만, 그래도 LangGraph를 쓰는 이유는 오케스트레이션 경계가 실제로 생겼기 때문입니다.

장점:

- 노드 계약이 명시적임
- 각 노드를 독립적으로 테스트 가능
- 추후 재시도 시 전체 프롬프트가 아니라 특정 노드만 다시 실행 가능
- 향후 분기 로직을 쉽게 추가 가능
- 파이프라인이 blob이 아니라 step 구조라 관측성이 좋아짐

즉, 단순히 함수 안에 프롬프트 3개를 넣는 것과는 구조적으로 다릅니다.

---

## 왜 strict structured output이 중요한가

`structured_chat()`은 노드 스키마를 반드시 만족하는 JSON을 요청합니다.

이로 인해 얻는 것:

- 덜 취약한 파싱
- 더 명확한 실패 형태
- malformed free text를 조용히 받아들이지 않음
- Pydantic 검증과 직접 연결 가능

구형 `_safe_json()` 유틸리티는 복원력 차원에서 남아 있지만, 메인 normalization 경로는 이제 strict schema output을 전제로 동작합니다.

---

## Semantic Dedupe

관련 파일:
- `app/store/vector_store.py`
- `app/llm/normalize.py`

동작 방식:

1. 제목과 기사 상세를 합쳐 embedding text를 만듭니다.
2. `text-embedding-3-small`으로 embedding을 생성합니다.
3. pgvector에서 가장 가까운 기존 이벤트를 조회합니다.
4. similarity가 임계값을 넘고 normalized row가 존재하면 기존 결과를 재사용합니다.
5. 그렇지 않으면 새 LangGraph 실행으로 진행합니다.

중요한 이유:

- 여러 카테고리에 반복 노출된 유사 뉴스마다 LLM 비용을 다시 쓰지 않음
- 유사 헤드라인에 대해 시장 내러티브를 더 일관되게 유지 가능

---

## Evaluator Logging

파일:
- `app/llm/evaluator.py`

런타임 연결:
- `app/llm/normalize.py`에서 호출

저장 필드:
- `raw_event_id`
- `event_type`
- `risk_signal`
- expected risk signal
- confidence
- consistency flag
- provider
- model

중요한 이유:

- calibration 없는 confidence만으로는 운영 품질 판단이 약함
- consistency는 drift와 misclassification을 보는 기본 운영 신호가 됨

---

## 사용 패키지

이 프로젝트에서 실제로 사용하는 주요 패키지:

- `openai`
- `langgraph`
- `pydantic`
- `pydantic-settings`
- `psycopg`
- `redis`
- `arq`

각 패키지의 역할:

- `openai`: LLM transport와 embeddings
- `langgraph`: 단계형 LLM 파이프라인 오케스트레이션
- `pydantic`: strict output validation
- `psycopg`: 이벤트 / 평가 데이터 저장
- `redis`, `arq`: multi-step LLM 작업을 HTTP에서 분리하는 비동기 실행 경로

설치 시 주의:

- 이 저장소는 가상환경에서 설치하는 것을 전제로 합니다.
- 전역 Python 환경에 다른 패키지가 설치돼 있으면 `requests` 같은 공용 의존성 충돌 경고가 날 수 있습니다.
- 이 프로젝트는 Snowflake와 무관합니다.

권장 설치:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 아직 남은 것

- 노드 단위 retry는 아직 구현되지 않음
- prompt/version 메타데이터를 노드별로 저장하지 않음
- retrieval-grounded rationale 생성은 아직 없음
- 메인 React UI가 LLM reasoning surface를 아직 충분히 노출하지 않음

이 항목들은 다음 단계 개선 사항이지, 현재 계층형 런타임의 blocker는 아닙니다.
