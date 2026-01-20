# 📊 Financial Event–Driven Market Impact System  
### News → FX Transmission → Sector Heatmap

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Postgres](https://img.shields.io/badge/PostgreSQL-Database-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![LLM](https://img.shields.io/badge/LLM-Event%20Interpretation-purple?style=for-the-badge)
![RuleEngine](https://img.shields.io/badge/Rule--Based-Scoring-critical?style=for-the-badge)
![Explainable](https://img.shields.io/badge/Explainable-Design-success?style=for-the-badge)

---

## 1. 프로젝트 개요 (Overview)

본 프로젝트는 **금융 뉴스 이벤트를 구조적으로 해석**하여  
**FX 방향성(FX bias)** 과 **섹터 영향(Sector pressure)** 을  
**룰 기반 점수(rule-based scoring)** 로 계산하고,  
이를 **대시보드(타임라인 + 히트맵)** 로 시각화하는 시스템이다.

이 프로젝트의 목적은 **가격 예측이 아니라** 다음에 있다.

> **“왜 이 뉴스가, 이 통화와 이 섹터에 영향을 줄 수 있는가?”**

### 핵심 설계 원칙

- ❌ LLM에게 가격·수익률·퍼센트 예측을 맡기지 않음
- ❌ 단일 기사 기반의 정량 예측 금지
- ✅ LLM은 **이벤트 해석과 분류만 담당**
- ✅ 실제 결정은 **룰 엔진이 담당**
- ✅ 모든 결과는 **설명 가능(Explainable)** 해야 함

### 핵심 설계 원칙 (detail)
- 역할	담당
- LLM	이벤트 해석 + FX 전파 채널 선택
- FX Bias Rules	통화 방향성 정규화
- FX → Sector Rules	통화 효과를 섹터로 변환
- Risk Sector Rules	시장 리스크 효과 보정
- Market Regime	증폭 / 감쇠
- Baseline + Delta	최종 히트맵

---

## 2. 이 프로젝트가 해결하려는 문제

### 기존 뉴스/시장 분석의 한계

| 기존 접근 | 한계 |
|---|---|
| 뉴스 헤드라인 | 해석이 주관적 |
| 섹터 히트맵 | 결과만 보여주고 원인은 없음 |
| FX 전망 | 왜 그렇게 되는지 설명 불가 |
| LLM 예측 | 근거 없는 수치 생성(hallucination) |

👉 **뉴스 → FX → 섹터 간의 인과 구조(causal structure)**가 연결되지 않는다.

---

## 3. 시스템이 보여주는 두 가지 핵심 결과

### 3.1 FX Forecast (FX Directional Bias)

FX Forecast는 **“이 뉴스 이벤트 이후, 자금이 어느 통화 블록으로 이동할 압력이 있는지”**를 보여준다.

- ❌ 환율 예측
- ❌ 가격 목표
- ❌ 수익률 추정

- ✅ **리스크 자금 이동 방향**
- ✅ **안전자산 vs 위험자산 구조**
- ✅ **FX 전파의 중간 단계**

#### 예시
```
USD +1.40 → 글로벌 안전자산 선호
JPY +1.40 → 리스크 회피 자금 유입
EUR -0.70 → 중립/약세 통화
EM -1.40 → 위험 통화 블록 이탈
```

👉 이는 **“어떤 통화가 오를 것이다”**가 아니라  
👉 **“이 뉴스는 risk-off 성격의 자금 이동을 유발한다”**는 의미다.

---

### 3.2 Sector Heatmap (Sector Directional Pressure)

Sector Heatmap은 **해당 뉴스가 각 산업 섹터에 주는 상대적 방향성 압력**을 시각화한다.

- ❌ 개별 종목 예측
- ❌ 수익률 % 표시

- ✅ 섹터 간 상대 강도
- ✅ 방어/공격 섹터 구분
- ✅ 뉴스 누적 효과 표현

#### 예시 해석
- Defense / Utilities 상승 → 방어적 포지션
- Technology / Consumer 하락 → 리스크 회피

👉 Heatmap은 **의사결정 인터페이스**이며  
👉 **“구조를 한 눈에 보여주는 도구”**다.

---

## 🧠 시스템 접근 방식

이 시스템은 다음과 같은 역할 분리를 따른다.

| 구성 요소 | 역할 |
|---|---|
| 뉴스 수집 | 원문 데이터 확보 |
| LLM | 이벤트 요약 및 신호 정규화 |
| Rule Engine | FX bias / 섹터 점수 결정 |
| DB | 이벤트·스코어 로그 저장 |
| UI | 타임라인 / 히트맵 시각화 |

> **LLM은 “해석”을 담당하고,  
Rule Engine은 “결정”을 담당한다.**

---

## 🧩 전체 파이프라인 개요
```
News Article  
↓  
Raw Event Ingest  
↓  
LLM Event Normalization  
↓  
FX / Risk / Rate / Geo Signals  
↓  
Rule Engine Scoring  
↓  
FX Bias + Sector Scores  
↓  
Timeline & Heatmap Dashboard
```

---

## 📦 구성 요약

- **백엔드 API**: `app/`  
  - FastAPI
  - Postgres 연동
- **정적 UI**: `app/ui/`  
  - FastAPI에서 `/` 경로로 직접 서빙
- **프런트 프로토타입**: `src/`  
  - 현재 실행에는 사용되지 않음 (실험용)

---

## ⚙️ 기술 스택 (Tech Stack)

### Backend
- **Python 3.11+**
- **FastAPI**
- **Uvicorn**
- **PostgreSQL**

### LLM
- OpenAI API (`gpt-4o-mini`)
- OpenAI-compatible Local LLM (Mistral 등)

### Data / Infra
- RapidAPI (뉴스 수집)
- 환경 변수 기반 설정 (`.env`)

### Architecture
- Rule-based Scoring Engine
- Event-driven Pipeline
- Explainable Market Intelligence Design

---

## 📋 요구 사항

- Python **3.11+** (권장)
- PostgreSQL

---

## 🚀 설치 및 실행

### 1️⃣ `.env` 생성
`.env.example` 파일 참고

### 2️⃣ 의존성 설치

```bash
pip install -r requirements.txt

src/               # 프런트 프로토타입
```
