from __future__ import annotations

import logging

from app.llm.mistral_client import MistralClient
from app.llm.normalize import extract_details_text
from app.models import NormalizedEvent, RawEvent, ScoredEvent

logger = logging.getLogger("app.llm.insight")

SUMMARY_SYSTEM_PROMPT = (
    "You are a financial news summarizer. "
    "Summarize the provided news in Korean in 2-3 sentences. "
    "Keep proper nouns and numbers. Avoid speculation."
)

SUMMARY_USER_TEMPLATE = """
다음 뉴스 내용을 한국어로 2~3문장으로 요약해줘.
뉴스 내용:
{text}
"""

ANALYSIS_SYSTEM_PROMPT = (
    "You are a financial analyst. "
    "Explain why the analysis result is the way it is in Korean, "
    "using 2-3 concise sentences. Avoid speculation."
)

ANALYSIS_USER_TEMPLATE = """
아래 분석 결과를 근거로 왜 이런 신호/결과가 나왔는지 한국어로 2~3문장으로 설명해줘.
이벤트 분류: {event_type}
정책 도메인: {policy_domain}
리스크 신호: {risk_signal}
금리 신호: {rate_signal}
지정학 신호: {geo_signal}
채널: {channels}
LLM 근거: {rationale}
FX 상태: {fx_state}
총점: {total_score}
"""

HEATMAP_SYSTEM_PROMPT = (
    "You are a market strategist. "
    "Explain the heatmap outcome in Korean in 2-3 sentences, "
    "referencing key sector winners/losers and signals. Avoid speculation."
)

HEATMAP_USER_TEMPLATE = """
아래 heatmap 결과를 근거로 왜 섹터가 그렇게 나왔는지 한국어로 2~3문장으로 설명해줘.
상승 섹터(상위): {top_gainers}
하락 섹터(상위): {top_losers}
채널: {channels}
이벤트 직접 영향: {sector_impacts}
레짐: {regime}
"""

FX_SYSTEM_PROMPT = (
    "You are an FX strategist. "
    "Explain the FX forecast outcome in Korean in 2-3 sentences, "
    "based on the signals and channels. Avoid speculation."
)

FX_USER_TEMPLATE = """
아래 FX 예측 결과를 근거로 왜 이런 방향성이 나왔는지 한국어로 2~3문장으로 설명해줘.
FX 상태: {fx_state}
리스크 신호: {risk_signal}
금리 신호: {rate_signal}
지정학 신호: {geo_signal}
채널: {channels}
레짐: {regime}
"""


def summarize_news_ko(raw_event: RawEvent) -> str:
    text = extract_details_text(raw_event.payload)
    logger.info("Summarize KR: raw_event_id=%s has_details=%s", raw_event.id, bool(text))
    if not text:
        text = raw_event.title or ""
    if not text:
        logger.warning("Summarize KR: no text for raw_event_id=%s", raw_event.id)
        return ""

    client = MistralClient()
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": SUMMARY_USER_TEMPLATE.format(text=text)},
    ]
    try:
        response = client.chat(messages)
    except Exception as exc:
        logger.warning("Korean summary failed: %s", exc)
        return ""

    choices = response.get("choices", [])
    if not choices:
        logger.warning("Summarize KR: no choices for raw_event_id=%s", raw_event.id)
        return ""
    content = choices[0].get("message", {}).get("content", "")
    return str(content or "").strip()


def build_analysis_reason(
    normalized: NormalizedEvent | None,
    scored: ScoredEvent | None,
) -> str:
    logger.info(
        "Build analysis fallback: normalized=%s scored=%s",
        bool(normalized),
        bool(scored),
    )
    if not normalized and not scored:
        return "아직 분석 결과가 없습니다. 파이프라인을 실행해 주세요."

    parts: list[str] = []
    if normalized:
        parts.append(
            (
                "LLM 분류: {event_type} / {policy_domain}. "
                "신호: 리스크 {risk_signal}, 금리 {rate_signal}, 지정학 {geo_signal}."
            ).format(
                event_type=normalized.event_type or "unknown",
                policy_domain=normalized.policy_domain or "unknown",
                risk_signal=normalized.risk_signal or "neutral",
                rate_signal=normalized.rate_signal or "none",
                geo_signal=normalized.geo_signal or "none",
            )
        )
        if normalized.channels:
            parts.append(f"채널: {', '.join(normalized.channels)}.")
        if normalized.rationale:
            parts.append(f"근거: {normalized.rationale}")

    if scored:
        total_score = f"{scored.total_score:.2f}" if scored.total_score is not None else "n/a"
        parts.append(f"FX 결과: {scored.fx_state or 'n/a'}, 총점 {total_score}.")

    return "\n".join(parts).strip()


def generate_analysis_ko(
    normalized: NormalizedEvent | None,
    scored: ScoredEvent | None,
) -> str:
    logger.info(
        "Generate analysis LLM: normalized=%s scored=%s",
        bool(normalized),
        bool(scored),
    )
    if not normalized and not scored:
        logger.warning("Generate analysis LLM: missing inputs")
        return ""
    client = MistralClient()
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": ANALYSIS_USER_TEMPLATE.format(
                event_type=(normalized.event_type if normalized else "") or "unknown",
                policy_domain=(normalized.policy_domain if normalized else "") or "unknown",
                risk_signal=(normalized.risk_signal if normalized else "") or "neutral",
                rate_signal=(normalized.rate_signal if normalized else "") or "none",
                geo_signal=(normalized.geo_signal if normalized else "") or "none",
                channels=", ".join((normalized.channels if normalized else []) or []),
                rationale=(normalized.rationale if normalized else "") or "없음",
                fx_state=(scored.fx_state if scored else "") or "n/a",
                total_score=f"{scored.total_score:.2f}" if scored and scored.total_score is not None else "n/a",
            ),
        },
    ]
    try:
        response = client.chat(messages)
    except Exception as exc:
        logger.warning("Analysis summary failed: %s", exc)
        return ""
    choices = response.get("choices", [])
    if not choices:
        logger.warning("Analysis summary failed: no choices")
        return ""
    return str(choices[0].get("message", {}).get("content", "") or "").strip()


def build_heatmap_reason(
    scored: ScoredEvent | None,
    normalized: NormalizedEvent | None,
) -> str:
    logger.info(
        "Build heatmap fallback: scored=%s has_scores=%s",
        bool(scored),
        bool(scored and scored.sector_scores),
    )
    if not scored or not scored.sector_scores:
        return "아직 heatmap 예측이 없습니다. 파이프라인을 실행해 주세요."

    scores = scored.sector_scores or {}
    entries = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    positives = [(sector, value) for sector, value in entries if value > 0][:3]
    negatives = [(sector, value) for sector, value in reversed(entries) if value < 0][:3]

    lines = [
        "섹터 점수는 FX 바이어스 + 리스크/금리/지정학 채널, 이벤트 직접 영향, 레짐/베이스라인 보정을 합산해 계산합니다.",
    ]
    if normalized and normalized.sector_impacts:
        impacted = sorted(normalized.sector_impacts.items(), key=lambda item: abs(item[1]), reverse=True)[:3]
        impacts_text = ", ".join([f"{sector} {value:+d}" for sector, value in impacted])
        lines.append(f"직접 영향(LLM): {impacts_text}.")
    if positives:
        pos_text = ", ".join([f"{sector} {value:+.2f}" for sector, value in positives])
        lines.append(f"상승 섹터: {pos_text}.")
    if negatives:
        neg_text = ", ".join([f"{sector} {value:+.2f}" for sector, value in negatives])
        lines.append(f"하락 섹터: {neg_text}.")

    return "\n".join(lines).strip()


def generate_heatmap_ko(
    scored: ScoredEvent | None,
    normalized: NormalizedEvent | None,
) -> str:
    logger.info(
        "Generate heatmap LLM: scored=%s has_scores=%s",
        bool(scored),
        bool(scored and scored.sector_scores),
    )
    if not scored or not scored.sector_scores:
        logger.warning("Generate heatmap LLM: missing scores")
        return ""

    scores = scored.sector_scores or {}
    entries = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    positives = [(sector, value) for sector, value in entries if value > 0][:3]
    negatives = [(sector, value) for sector, value in reversed(entries) if value < 0][:3]

    top_gainers = ", ".join([f"{sector} {value:+.2f}" for sector, value in positives]) or "없음"
    top_losers = ", ".join([f"{sector} {value:+.2f}" for sector, value in negatives]) or "없음"

    client = MistralClient()
    messages = [
        {"role": "system", "content": HEATMAP_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": HEATMAP_USER_TEMPLATE.format(
                top_gainers=top_gainers,
                top_losers=top_losers,
                channels=", ".join((normalized.channels if normalized else []) or []),
                sector_impacts=normalized.sector_impacts if normalized else {},
                regime=normalized.regime if normalized else {},
            ),
        },
    ]
    try:
        response = client.chat(messages)
    except Exception as exc:
        logger.warning("Heatmap summary failed: %s", exc)
        return ""
    choices = response.get("choices", [])
    if not choices:
        logger.warning("Heatmap summary failed: no choices")
        return ""
    return str(choices[0].get("message", {}).get("content", "") or "").strip()


def build_fx_reason(
    normalized: NormalizedEvent | None,
    scored: ScoredEvent | None,
) -> str:
    logger.info(
        "Build fx fallback: normalized=%s scored=%s",
        bool(normalized),
        bool(scored),
    )
    if not scored:
        return "아직 FX 예측이 없습니다. 파이프라인을 실행해 주세요."
    signals = []
    if normalized:
        if normalized.risk_signal:
            signals.append(f"리스크 {normalized.risk_signal}")
        if normalized.rate_signal:
            signals.append(f"금리 {normalized.rate_signal}")
        if normalized.geo_signal:
            signals.append(f"지정학 {normalized.geo_signal}")
    signal_text = ", ".join(signals) if signals else "신호 없음"
    return f"FX 상태: {scored.fx_state or 'n/a'}. 기준 신호: {signal_text}."


def generate_fx_ko(
    normalized: NormalizedEvent | None,
    scored: ScoredEvent | None,
) -> str:
    logger.info(
        "Generate fx LLM: normalized=%s scored=%s",
        bool(normalized),
        bool(scored),
    )
    if not scored:
        logger.warning("Generate fx LLM: missing scored")
        return ""
    client = MistralClient()
    messages = [
        {"role": "system", "content": FX_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": FX_USER_TEMPLATE.format(
                fx_state=scored.fx_state or "n/a",
                risk_signal=(normalized.risk_signal if normalized else "") or "neutral",
                rate_signal=(normalized.rate_signal if normalized else "") or "none",
                geo_signal=(normalized.geo_signal if normalized else "") or "none",
                channels=", ".join((normalized.channels if normalized else []) or []),
                regime=normalized.regime if normalized else {},
            ),
        },
    ]
    try:
        response = client.chat(messages)
    except Exception as exc:
        logger.warning("FX summary failed: %s", exc)
        return ""
    choices = response.get("choices", [])
    if not choices:
        logger.warning("FX summary failed: no choices")
        return ""
    return str(choices[0].get("message", {}).get("content", "") or "").strip()
