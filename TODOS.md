# 기술 부채와 다음 작업

## 이번 업데이트에서 완료한 것

- Spring 중복 백엔드 제거
- 단일 프롬프트 정규화 경로를 실제 LangGraph 체인으로 교체
- `app/llm/structured.py` 기반 엄격한 스키마 검증 적용
- evaluator 로깅을 실제 normalization 경로에 연결
- pgvector semantic dedupe와 embedding 저장을 실제 normalization 경로에 연결

## 현재 기술 부채

### `app/store/db.py`의 레거시 startup DDL

`init_db()`는 아직 프로세스 시작 시 테이블 생성과 컬럼 patching을 수행합니다. 빠른 실험 단계에서는 유용했지만, 이제 스키마 소유권은 Alembic으로 완전히 넘어가야 합니다.

언제 처리할지:
- Phase 5 CI/CD 고도화 전

해야 할 것:
- `init_db()`를 연결 확인 / bootstrap 수준으로 축소
- 마이그레이션이 누락되면 런타임 patch 대신 즉시 실패하도록 변경

---

### 메인 프론트엔드가 아직 Phase 2 백엔드를 충분히 사용하지 않음

이 항목은 일부 해소됐습니다. 메인 React 앱이 이제 다음을 사용합니다.

- WebSocket 기반 실시간 갱신
- timeline 데이터
- event insight / rationale API
- category 기반 뉴스 선택과 단건 파이프라인 실행

하지만 아직 남은 정리가 있습니다.

언제 처리할지:
- Phase 4

해야 할 것:
- 중복 프로토타입 프론트엔드와 `app/ui` 정리
- timeline 검색 / 필터 / 정렬 추가
- insight 패널과 파이프라인 제어 UX 다듬기

---

## 향후 작업

### Phase 6: EDGAR Grounding

실제 SEC filing을 이용해 analyst rationale을 grounding합니다.

기대 효과:

- 기업별 rationale 품질 향상
- 근거 없는 서술 감소
- 시장 영향 설명의 감사 가능성 강화

선행 조건:

- 프론트엔드 통합과 배포 고도화가 먼저 필요
