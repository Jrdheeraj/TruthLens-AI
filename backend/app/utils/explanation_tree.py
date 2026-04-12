import logging
import re
from urllib.parse import quote_plus, urlparse

logger = logging.getLogger(__name__)

_VERIFIED_DOMAINS = {
    "reuters.com",
    "apnews.com",
    "bbc.com",
    "nasa.gov",
    "who.int",
    "cdc.gov",
    "snopes.com",
    "politifact.com",
    "factcheck.org",
    "altnews.in",
}


def _is_vague_explanation(text: str) -> bool:
    if not text or len(text) < 25:
        return True
    vague_phrases = [
        "cannot be verified",
        "could not be verified",
        "not enough data",
        "unclear",
        "cannot determine",
        "could not determine",
    ]
    return any(phrase in text.lower() for phrase in vague_phrases)


def _contains_forbidden_patterns(explanation: str) -> bool:
    text_lower = explanation.lower()
    forbidden_patterns = [
        r"\bhypothetical\b",
        r"\bassume\b",
        r"\bi assume\b",
        r"\bi'll assume\b",
        r"scenario",
        r"what if",
        r"imagine",
        r"picture this",
        r"\bmodel score\b",
        r"\bvisual risk\b",
        r"\bmotion score\b",
        r"\bcross-modal\b",
        r"\bocr\b",
    ]
    return any(re.search(pattern, text_lower) for pattern in forbidden_patterns)


def _dedupe_sources(sources):
    seen_urls = set()
    unique_sources = []
    for src in sources or []:
        if not isinstance(src, dict):
            continue
        url = src.get("url", "")
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
        unique_sources.append(src)
    return unique_sources


def _normalize_source(source: dict) -> dict:
    url = str(source.get("url") or source.get("link") or "").strip()
    return {
        "title": str(source.get("title") or source.get("name") or "Source").strip(),
        "description": str(
            source.get("snippet") or source.get("description") or source.get("summary") or source.get("text") or ""
        ).strip(),
        "url": url,
        "link": url,
        "type": str(source.get("type") or source.get("source") or "Web").strip(),
    }


def _is_verified_source(source: dict) -> bool:
    url = str(source.get("url") or "").strip()
    if not url:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if host.startswith("www."):
        host = host[4:]
    return any(host == domain or host.endswith(f".{domain}") for domain in _VERIFIED_DOMAINS)


def _build_fallback_sources(query_text: str) -> list[dict]:
    q = quote_plus((query_text or "fact check").strip()[:180])
    return [
        {
            "title": "Wikipedia Search",
            "description": "Closest encyclopedia reference for the claim context.",
            "url": f"https://en.wikipedia.org/w/index.php?search={q}",
            "link": f"https://en.wikipedia.org/w/index.php?search={q}",
            "type": "Reference",
        },
        {
            "title": "Reuters Search",
            "description": "Closest related reporting query from Reuters.",
            "url": f"https://www.reuters.com/site-search/?query={q}",
            "link": f"https://www.reuters.com/site-search/?query={q}",
            "type": "News",
        },
    ]


def _select_display_sources(sources: list[dict], query_text: str) -> tuple[list[dict], bool]:
    normalized = [_normalize_source(src) for src in sources if isinstance(src, dict)]
    verified = [src for src in normalized if _is_verified_source(src)]
    fallback = [src for src in normalized if src.get("url")]

    selected = (verified if verified else fallback)[:4]
    if len(selected) < 2:
        existing_urls = {src.get("url") for src in selected}
        for extra in _build_fallback_sources(query_text):
            if extra["url"] in existing_urls:
                continue
            selected.append(extra)
            existing_urls.add(extra["url"])
            if len(selected) >= 2:
                break

    has_strong_verified = len(verified) >= 1
    return selected, has_strong_verified


def _derive_status(verdict: str) -> str:
    return "TRUE" if str(verdict).upper() == "TRUE" else "FALSE"


def _build_confidence_justification(
    status: str,
    confidence: int,
    source_count: int,
    has_strong_verified: bool,
    evidence_score: float,
    ai_score: float,
    final_score: float,
) -> str:
    if status == "TRUE":
        return (
            f"Confidence is {confidence}% because the weighted decision score is {final_score:.2f} "
            f"(evidence {evidence_score:.2f} x 0.6 + AI {ai_score:.2f} x 0.4), and {source_count} source(s) support the claim."
        )

    if has_strong_verified:
        return (
            f"Confidence is {confidence}% because the weighted decision score is {final_score:.2f} "
            f"(evidence {evidence_score:.2f} x 0.6 + AI {ai_score:.2f} x 0.4), which falls below the TRUE threshold and defaults to FALSE."
        )

    return (
        f"Confidence is {confidence}% because the weighted decision score is {final_score:.2f} "
        f"(evidence {evidence_score:.2f} x 0.6 + AI {ai_score:.2f} x 0.4), and without credible support the strict system assigns FALSE."
    )


def _build_blended_explanation(
    input_text: str,
    status: str,
    actual_information: str,
    source_count: int,
    model_score=None,
    visual_risk=None,
    motion_score=None,
    audio_score=None,
) -> str:
    technical_bits = []

    if visual_risk is not None:
        try:
            risk = float(visual_risk)
            if risk >= 0.6:
                technical_bits.append("the media shows synthetic-pattern risk indicators such as inconsistent visual structure")
            elif risk <= 0.35:
                technical_bits.append("the visual consistency metrics are closer to authentic-media patterns")
        except Exception:
            pass

    if model_score is not None:
        try:
            score = float(model_score)
            if 0.4 <= score <= 0.6:
                technical_bits.append("the model score falls in an ambiguous range")
            elif score > 0.7:
                technical_bits.append("the model confidence leans clearly toward an authentic classification")
            elif score < 0.3:
                technical_bits.append("the model confidence leans toward manipulation risk")
        except Exception:
            pass

    if motion_score is not None:
        try:
            mscore = float(motion_score)
            if mscore > 0.6:
                technical_bits.append("temporal consistency checks indicate frame-level anomalies")
        except Exception:
            pass

    if audio_score is not None:
        try:
            ascore = float(audio_score)
            if ascore > 0.6:
                technical_bits.append("audio analysis suggests non-natural speech or synthesis artifacts")
        except Exception:
            pass

    if not technical_bits:
        technical_bits.append("cross-checking did not find strong technical anomalies, but evidence strength remains the deciding factor")

    status_text = "TRUE" if status == "TRUE" else "FALSE"

    evidence_phrase = (
        f"{source_count} reference source(s) were available for cross-checking"
        if source_count
        else "the system added closest related reliable references for cross-checking"
    )

    return (
        f"Technical analysis indicates that {technical_bits[0]}, and {evidence_phrase}; this evidence profile leads to a strict {status_text} decision under the deterministic scoring rule. "
        f"In simple terms, this means the claim \"{input_text}\" should be treated as {status_text}, and the interpretation that better matches available evidence is: {actual_information}"
    )


def _extract_input_text(text_results, image_results, content_type: str) -> str:
    if text_results and isinstance(text_results, list):
        for result in text_results:
            if isinstance(result, dict) and result.get("claim"):
                return str(result.get("claim", "")).strip()[:240]

    if isinstance(image_results, dict):
        if content_type == "video":
            caption = image_results.get("video_caption") or image_results.get("caption")
            if caption:
                return str(caption).strip()[:240]
        caption = image_results.get("caption")
        if caption:
            return str(caption).strip()[:240]

    return "The submitted content"


def _line_overlaps_hint(line: str, hint: str) -> bool:
    if not hint or len(hint) < 12:
        return False
    a = re.sub(r"\s+", " ", line).strip().lower()
    b = re.sub(r"\s+", " ", hint).strip().lower()
    if len(a) < 8:
        return False
    return a in b or b in a or (len(a) > 20 and a[:40] == b[:40])


def _build_rag_summary(text_results, sources, exclude_hint: str = "") -> str:
    evidence_lines = []

    if text_results and isinstance(text_results, list):
        for result in text_results[:3]:
            if isinstance(result, dict):
                explanation = str(result.get("explanation", "")).strip()
                corrected = str(result.get("corrected_fact", "")).strip()
                if explanation and not _line_overlaps_hint(explanation, exclude_hint):
                    evidence_lines.append(explanation)
                if corrected and not _line_overlaps_hint(corrected, exclude_hint):
                    evidence_lines.append(f"Correct information: {corrected}")

    for source in sources[:3]:
        text = " ".join(
            str(source.get(key, "")).strip()
            for key in ("title", "snippet", "description", "summary", "text")
            if source.get(key)
        ).strip()
        if text and not _line_overlaps_hint(text, exclude_hint):
            evidence_lines.append(text)

    cleaned = []
    seen = set()
    for line in evidence_lines:
        normalized = re.sub(r"\s+", " ", line).strip()
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            cleaned.append(normalized)

    return "\n".join(f"- {line}" for line in cleaned[:4])


def _extract_actual_information(text_results, sources, verdict: str) -> str:
    if text_results and isinstance(text_results, list):
        for result in text_results:
            if not isinstance(result, dict):
                continue
            corrected = str(result.get("corrected_fact", "")).strip()
            if corrected:
                return corrected
            explanation = str(result.get("explanation", "")).strip()
            if explanation and verdict == "FALSE":
                return explanation[:220]

    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("snippet", "description", "summary", "text"):
            value = str(source.get(key, "")).strip()
            if value:
                return value[:220]

    if verdict == "TRUE":
        return "The available evidence supports the claim."
    return "Trusted evidence does not support the claim."


def _generate_human_explanation(input_text: str, verdict: str, rag_summary: str, actual_information: str) -> str:
    prompt = f"""
You are a careful fact-checker writing for a smart reader who is not a developer.

RULES:
- Write ONE flowing paragraph only (at least 5 sentences). No bullet lists, no markdown, no headings.
- Plain English: you may say "sources," "evidence," or "confidence" briefly, but never stack traces, JSON, internal step names, or jargon like "pipeline" or "embedding."
- Restate the claim in your own words, then say whether the evidence supports it and why that matters to someone deciding what to believe.
- If a "Correct fact" line appears below, weave that idea into your paragraph naturally—do NOT paste it as a duplicate block or repeat it verbatim as its own sentence.
- If evidence is thin, say what was checked and what would change your mind (e.g. stronger official sources).
- Vary your opening; do not start every answer with "This claim is true/false."

CLAIM (may be truncated): {input_text}
VERDICT: {verdict}

EVIDENCE NOTES (may be partial):
{rag_summary or "- (limited structured notes)"}

CORRECT FACT (use for meaning only; do not duplicate verbatim): {actual_information}

Write the paragraph now.
""".strip()

    try:
        from groq import Groq

        client = Groq()
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.35,
            max_tokens=520,
        )
        explanation = response.choices[0].message.content.strip()
        if explanation and not _contains_forbidden_patterns(explanation) and not _is_vague_explanation(explanation):
            return explanation
    except Exception as exc:
        logger.warning(f"Human explanation generation failed: {exc}")

    if verdict == "TRUE":
        return (
            f"We compared what you shared with reputable sources and reporting that we could find at this moment. "
            f"They line up with the idea in your claim: {actual_information} "
            f"That alignment is why we mark this as supported. If major outlets or primary documents later contradict this, you should revisit the conclusion and look for newer evidence."
        )
    return (
        f"We compared what you shared with reputable sources and what we could verify from them. "
        f"They do not support the claim as stated. The picture that fits the evidence better is this: {actual_information} "
        f"That mismatch is why we mark this as not supported. If new authoritative information appears—for example an official statement or widely corroborated reporting—it could change how we read this claim."
    )


def build_explanation_tree(
    text_results=None,
    image_results=None,
    cross_modal=None,
    final_confidence=0.0,
    verdict="FALSE",
    sources=None,
    rag_powered=False,
    model_score=None,
    visual_risk=None,
    motion_score=None,
    content_type="text",
    audio_score=None,
    audio_transcript=None,
    audio_context=None,
    evidence_score=None,
    ai_score=None,
    final_score=None,
):
    unique_sources = _dedupe_sources(sources or [])
    input_text = _extract_input_text(text_results, image_results, content_type)
    selected_sources, has_strong_verified = _select_display_sources(unique_sources, input_text)
    actual_information = _extract_actual_information(text_results, unique_sources, verdict)
    rag_summary = _build_rag_summary(text_results, unique_sources, exclude_hint=actual_information)
    confidence_pct = int(round(final_confidence * 100))
    status = _derive_status(verdict)

    resolved_evidence = float(evidence_score if evidence_score is not None else final_confidence)
    resolved_ai = float(ai_score if ai_score is not None else final_confidence)
    resolved_final = float(final_score if final_score is not None else final_confidence)

    confidence_justification = _build_confidence_justification(
        status,
        confidence_pct,
        len(selected_sources),
        has_strong_verified,
        resolved_evidence,
        resolved_ai,
        resolved_final,
    )
    explanation = _build_blended_explanation(
        input_text=input_text,
        status=status,
        actual_information=actual_information,
        source_count=len(selected_sources),
        model_score=model_score,
        visual_risk=visual_risk,
        motion_score=motion_score,
        audio_score=audio_score,
    )
    
    summary = (
        "TRUE — the claim is supported by the available evidence."
        if status == "TRUE"
        else "FALSE — the claim is contradicted or lacks credible support."
    )

    response = {
        "verdict": verdict,
        "status": status,
        "confidence": confidence_pct,
        "confidence_justification": confidence_justification,
        "summary": summary,
        "explanation": explanation,
        "actual_information": actual_information,
        "what_matches_evidence_better": actual_information,
        "sources": selected_sources,
        "sources_note": "" if selected_sources else "No strong verified sources found",
        "rag_powered": rag_powered,
        "reasoning": [],
        "details": {
            "rag_summary": rag_summary,
            "evidence_score": round(resolved_evidence, 4),
            "ai_score": round(resolved_ai, 4),
            "final_score": round(resolved_final, 4),
        },
    }

    return response
