import logging

from app.utils.explanation_tree import build_explanation_tree
from app.utils.serialization import sanitize_response, to_python_type

logger = logging.getLogger(__name__)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _decide_status(evidence_score: float, ai_score: float) -> tuple[str, float, int]:
    """Deterministic decision engine.

    final_score = evidence_score * 0.6 + ai_score * 0.4
    TRUE when final_score >= 0.6, otherwise FALSE.
    If uncertain, FALSE by design.
    """
    e = _clamp(evidence_score)
    a = _clamp(ai_score)
    final_score = (e * 0.6) + (a * 0.4)

    if final_score >= 0.6:
        verdict = "TRUE"
        confidence = int(round(final_score * 100))
    else:
        verdict = "FALSE"
        confidence = int(round((1.0 - final_score) * 100))

    return verdict, _clamp(final_score), max(0, min(confidence, 100))


def final_verdict(
    text_results=None,
    image_results=None,
    cross_modal_score=None,
    rag_result=None,
    motion_score=None,
    content_type="text",
    audio_score=None,
    audio_transcript=None,
    audio_context=None,
):
    """Strict TRUE/FALSE decision system with deterministic score fusion."""

    if image_results and isinstance(image_results, dict):
        final_risk = float(
            to_python_type(
                image_results.get(
                    "final_risk_score",
                    image_results.get("visual_risk_score", 0.0) or 0.0,
                )
            )
        )
        model_score = float(to_python_type(image_results.get("model_score", 0.0)))
        img_motion_score = float(to_python_type(image_results.get("motion_score", 0.0) or motion_score or 0.0))
        raw_audio_score = image_results.get("audio_score", None)
        if raw_audio_score is None:
            raw_audio_score = audio_score
        img_audio_score = None if raw_audio_score is None else float(to_python_type(raw_audio_score))

        evidence_score = _clamp(1.0 - final_risk)
        ai_score = _clamp(model_score)
        verdict, final_score, confidence = _decide_status(evidence_score, ai_score)
        logger.info(
            "VERDICT: media decision -> %s (%s%%) | evidence=%.2f ai=%.2f final=%.2f",
            verdict,
            confidence,
            evidence_score,
            ai_score,
            final_score,
        )

        determined_content_type = content_type or ("image" if not text_results else "multimodal")
        safe_image_results = dict(image_results)

        response = build_explanation_tree(
            text_results=text_results,
            image_results=safe_image_results,
            cross_modal={"score": cross_modal_score or 0.0, "status": "ANALYZED"},
            final_confidence=confidence / 100.0,
            verdict=verdict,
            sources=safe_image_results.get("sources", []) if safe_image_results else [],
            rag_powered=False,
            evidence_score=evidence_score,
            ai_score=ai_score,
            final_score=final_score,
            model_score=float(model_score),
            visual_risk=float(to_python_type(safe_image_results.get("visual_risk_score", 0.0))),
            motion_score=float(img_motion_score),
            audio_score=img_audio_score,
            audio_transcript=audio_transcript or "",
            audio_context=audio_context or {},
            content_type=determined_content_type,
        )
        return sanitize_response(response)

    if rag_result and isinstance(rag_result, dict):
        rag_verdict = str(rag_result.get("verdict", "")).upper()
        rag_confidence = int(to_python_type(rag_result.get("confidence", 0)))
        rag_sources = rag_result.get("sources", [])

        rag_conf = _clamp(rag_confidence / 100.0)
        evidence_score = rag_conf if rag_verdict == "TRUE" else (1.0 - rag_conf)

        total_claims = len(text_results or [])
        supporting_count = 0
        if text_results:
            for result in text_results:
                if result.get("status") in ["SUPPORTED", "IMPLICITLY_SUPPORTED"]:
                    supporting_count += 1
        ai_score = _clamp((supporting_count / total_claims) if total_claims > 0 else evidence_score)

        verdict, final_score, confidence = _decide_status(evidence_score, ai_score)
        logger.info(
            "VERDICT: text/rag decision -> %s (%s%%) | evidence=%.2f ai=%.2f final=%.2f",
            verdict,
            confidence,
            evidence_score,
            ai_score,
            final_score,
        )

        response = build_explanation_tree(
            text_results=text_results,
            image_results=image_results,
            cross_modal={"score": cross_modal_score or 0.0, "status": "ANALYZED"},
            final_confidence=confidence / 100.0,
            verdict=verdict,
            sources=rag_sources[:8],
            rag_powered=True,
            evidence_score=evidence_score,
            ai_score=ai_score,
            final_score=final_score,
            audio_score=audio_score,
            audio_transcript=audio_transcript or "",
            audio_context=audio_context or {},
            content_type="text",
        )
        return sanitize_response(response)

    supporting_count = 0
    contradicting_count = 0

    if text_results:
        for result in text_results:
            status = result.get("status", "")
            if status in ["SUPPORTED", "IMPLICITLY_SUPPORTED"]:
                supporting_count += 1
            elif status in ["CONTRADICTED", "HOAX"]:
                contradicting_count += 1

    total = max(1, supporting_count + contradicting_count)
    evidence_score = _clamp(supporting_count / total)
    ai_score = _clamp((supporting_count + 0.5) / (total + 1.0))
    verdict, final_score, confidence = _decide_status(evidence_score, ai_score)

    logger.info(
        "VERDICT: fallback text decision -> %s (%s%%) | evidence=%.2f ai=%.2f final=%.2f",
        verdict,
        confidence,
        evidence_score,
        ai_score,
        final_score,
    )

    response = build_explanation_tree(
        text_results=text_results,
        image_results=image_results,
        cross_modal={"score": cross_modal_score or 0.0, "status": "ANALYZED"},
        final_confidence=confidence / 100.0,
        verdict=verdict,
        sources=[],
        rag_powered=False,
        evidence_score=evidence_score,
        ai_score=ai_score,
        final_score=final_score,
        audio_score=audio_score,
        audio_transcript=audio_transcript or "",
        audio_context=audio_context or {},
        content_type="text",
    )
    return sanitize_response(response)
