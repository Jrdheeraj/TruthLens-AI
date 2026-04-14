import asyncio
import contextlib
import logging
import re
import time
from functools import lru_cache
from typing import Any
from urllib.parse import quote_plus, urlparse

import numpy as np
from sentence_transformers import SentenceTransformer

from app.live.live_search import fetch_tavily_evidence, fetch_wikipedia_evidence
from app.llm.evaluator import GROQ_MODEL, _extract_json_object, get_groq_client
from app.utils.search_query_generator import extract_core_claim

logger = logging.getLogger(__name__)

TRUSTED_SOURCE_DOMAINS = {
    "wikipedia.org",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
}


@lru_cache(maxsize=1)
def _get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer("all-MiniLM-L6-v2")


def preload_embedding_model() -> None:
    """Preload semantic model during app startup to avoid first-request latency spikes."""
    _get_embedding_model()


class AgenticRAG:
    def __init__(self) -> None:
        self.providers = ("wiki", "tavily")
        self.max_queries = 2
        self.max_sources = 3
        self.max_evidence_chars = 2000
        self.call_timeout = 5.0
        self.pipeline_timeout = 14.0
        self.reason_timeout = 8.0
        self.cache_ttl_seconds = 120.0
        self._semaphore = asyncio.Semaphore(6)
        self._query_cache: dict[str, tuple[float, dict[str, Any] | None]] = {}

    def _fallback_response(self, claim: str = "") -> dict[str, Any]:
        logger.warning("Fail-safe fallback triggered")
        fallback_sources = self._curated_reference_sources(claim)
        return {
            "verdict": "FALSE",
            "confidence": 50,
            "reasoning": "No strong real-world evidence found.",
            "explanation": {
                "summary": "No strong real-world evidence found.",
                "points": [
                    "No highly relevant evidence passed semantic filtering.",
                    "System returned conservative FALSE fail-safe.",
                ],
                "technical": "Fail-safe fallback path used after retrieval, ranking, or LLM failure.",
            },
            "technical_details": "Fail-safe fallback path used after retrieval, ranking, or LLM failure.",
            "evidence_points": [
                "No strong real-world evidence found.",
            ],
            "key_evidence": "No strong real-world evidence found.",
            "sources": fallback_sources,
        }

    def plan_queries(self, claim: str, content_type: str = "text") -> list[dict[str, Any]]:
        core_claim = extract_core_claim(claim).strip() or claim.strip()
        if not core_claim:
            return []

        candidates = [
            core_claim,
            f"{core_claim} fact check",
            f"{core_claim} real or fake",
        ]

        seen: set[str] = set()
        planned: list[dict[str, Any]] = []
        for query in candidates:
            q = re.sub(r"\s+", " ", query).strip()
            if not q or q in seen:
                continue
            seen.add(q)
            planned.append({"query": q, "intent": "fact-verification", "priority": len(planned) + 1})
            if len(planned) >= self.max_queries:
                break
        return planned

    def _is_trusted_domain(self, url: str) -> bool:
        if not url:
            return False
        try:
            host = (urlparse(url).hostname or "").lower()
        except Exception:
            return False
        if host.startswith("www."):
            host = host[4:]
        return any(host == d or host.endswith(f".{d}") for d in TRUSTED_SOURCE_DOMAINS)

    def _cache_get(self, key: str) -> dict[str, Any] | None:
        hit = self._query_cache.get(key)
        if not hit:
            return None
        ts, payload = hit
        if (time.monotonic() - ts) > self.cache_ttl_seconds:
            self._query_cache.pop(key, None)
            return None
        return payload

    def _cache_set(self, key: str, payload: dict[str, Any] | None) -> None:
        self._query_cache[key] = (time.monotonic(), payload)

    async def _call_provider(self, provider: str, query: str) -> dict[str, Any]:
        async with self._semaphore:
            cache_key = f"{provider}:{query.lower().strip()}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                return {"provider": provider, "query": query, "payload": cached, "cached": True}

            provider_task: asyncio.Task | None = None
            try:
                if provider == "wiki":
                    provider_task = asyncio.create_task(fetch_wikipedia_evidence(query))
                elif provider == "tavily":
                    provider_task = asyncio.create_task(fetch_tavily_evidence(query))
                else:
                    return {"provider": provider, "query": query, "payload": None, "error": "unsupported-provider"}

                payload = await asyncio.wait_for(provider_task, timeout=self.call_timeout)
                self._cache_set(cache_key, payload if isinstance(payload, dict) else None)
                return {"provider": provider, "query": query, "payload": payload}
            except asyncio.TimeoutError:
                if provider_task and not provider_task.done():
                    provider_task.cancel()
                    await asyncio.gather(provider_task, return_exceptions=True)
                self._cache_set(cache_key, None)
                return {"provider": provider, "query": query, "payload": None, "error": "timeout"}
            except asyncio.CancelledError:
                if provider_task and not provider_task.done():
                    provider_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await provider_task
                raise
            except Exception as exc:
                logger.error("Provider failure: provider=%s error=%s", provider, exc)
                self._cache_set(cache_key, None)
                return {"provider": provider, "query": query, "payload": None, "error": type(exc).__name__}

    async def fetch_all_evidence(self, queries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tasks: list[asyncio.Task] = []
        for query_obj in queries:
            query = str(query_obj.get("query", "")).strip()
            if not query:
                continue
            for provider in self.providers:
                tasks.append(asyncio.create_task(self._call_provider(provider, query)))

        if not tasks:
            return []

        grouped: list[Any] = []
        gather_future = asyncio.gather(*tasks, return_exceptions=True)
        try:
            grouped = await asyncio.wait_for(gather_future, timeout=self.call_timeout + 1.2)
        except asyncio.TimeoutError:
            for task in tasks:
                if task.done():
                    try:
                        grouped.append(task.result())
                    except BaseException as exc:
                        grouped.append(exc)
            for task in tasks:
                if not task.done():
                    task.cancel()
            gather_future.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(asyncio.CancelledError):
                await gather_future
            logger.warning("Retrieval fan-out timeout, using partial provider results")
        except asyncio.CancelledError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            gather_future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks, return_exceptions=True)
                await gather_future
            raise

        evidence: list[dict[str, Any]] = []
        for item in grouped:
            if isinstance(item, Exception):
                continue
            payload = item.get("payload") if isinstance(item, dict) else None
            if isinstance(payload, dict):
                evidence.append(payload)

        return evidence

    def _clean_evidence(self, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned: list[dict[str, Any]] = []
        seen: set[str] = set()
        weak_markers = (
            "search results",
            "no summary available",
            "click here",
            "read more",
            "sponsored",
            "advertisement",
        )
        for item in evidence:
            text = str(item.get("text", "")).strip()
            lowered = text.lower()
            if len(text) < 80:
                continue
            if any(marker in lowered for marker in weak_markers):
                continue
            url = str(item.get("url", "")).strip()
            dedupe_key = f"{url}|{text[:120]}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            cleaned.append(item)
        return cleaned

    def _claim_tokens(self, claim: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", (claim or "").lower()))

    def _compute_similarity_scores(self, claim: str, items: list[dict[str, Any]]) -> list[float]:
        if not items:
            return []
        model = _get_embedding_model()
        texts = [str(item.get("text", "")) for item in items]
        claim_vec = model.encode([claim], normalize_embeddings=True, convert_to_numpy=True)[0]
        evidence_vecs = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        sims = np.dot(evidence_vecs, claim_vec)
        return [float(s) for s in sims]

    async def _semantic_rerank(self, claim: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
        cleaned = self._clean_evidence(evidence)
        if not cleaned:
            return []

        try:
            similarities = await asyncio.wait_for(
                asyncio.to_thread(self._compute_similarity_scores, claim, cleaned),
                timeout=6.0,
            )
        except Exception:
            similarities = [0.0 for _ in cleaned]

        claim_tokens = self._claim_tokens(claim)
        ranked: list[dict[str, Any]] = []
        for item, similarity in zip(cleaned, similarities):
            if similarity <= 0.45:
                continue
            text = str(item.get("text", "")).lower()
            overlap_flag = any(token in text for token in claim_tokens)
            trusted_bonus = 3 if self._is_trusted_domain(str(item.get("url", ""))) else 0
            overlap_bonus = 1 if overlap_flag else 0
            score = (similarity * 5.0) + trusted_bonus + overlap_bonus
            ranked.append({
                **item,
                "similarity_score": round(similarity, 4),
                "score": round(score, 4),
            })

        ranked.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return ranked[: self.max_sources]

    def _curated_reference_sources(self, claim: str) -> list[dict[str, str]]:
        q = quote_plus(claim.strip() or "fact check")
        return [
            {
                "url": f"https://en.wikipedia.org/w/index.php?search={q}",
                "link": f"https://en.wikipedia.org/w/index.php?search={q}",
                "title": "Wikipedia Search",
                "source": "Wikipedia",
                "type": "reference",
                "note": "General encyclopedia reference for the topic.",
            },
            {
                "url": f"https://www.reuters.com/site-search/?query={q}",
                "link": f"https://www.reuters.com/site-search/?query={q}",
                "title": "Reuters Search",
                "source": "Reuters",
                "type": "news",
                "note": "Credible global reporting search results.",
            },
            {
                "url": f"https://www.bbc.co.uk/search?q={q}",
                "link": f"https://www.bbc.co.uk/search?q={q}",
                "title": "BBC Search",
                "source": "BBC",
                "type": "news",
                "note": "Editorial coverage and explainers.",
            },
        ]

    def _build_sources(self, ranked: list[dict[str, Any]]) -> list[dict[str, str]]:
        sources: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in ranked:
            url = str(item.get("url", "")).strip()
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "url": url,
                    "link": url,
                    "title": str(item.get("page") or item.get("title") or item.get("source") or "Source"),
                    "source": str(item.get("source", "web")),
                    "type": "web",
                    "snippet": str(item.get("text", ""))[:180],
                    "note": str(item.get("text", "")).split(".")[0][:140] or "Relevant retrieved evidence.",
                }
            )
            if len(sources) >= self.max_sources:
                break
        return sources

    def _fuse_evidence_text(self, ranked: list[dict[str, Any]]) -> str:
        chunks = []
        used = 0
        for item in ranked:
            sim = item.get("similarity_score", 0.0)
            block = f"[{item.get('source', 'Unknown')} | sim={sim}] {str(item.get('text', ''))[:320]}"
            if used + len(block) > self.max_evidence_chars:
                break
            chunks.append(block)
            used += len(block)
        return "\n".join(chunks)

    async def _llm_semantic_verdict(self, claim: str, evidence_text: str) -> dict[str, Any] | None:
        if not evidence_text.strip():
            return None

        system_prompt = (
            "You are a strict fact-checking verifier. Decide whether the claim is factually correct using ONLY the provided evidence. "
            "Check if the claim contains incorrect attributes (gender, role, time, position, etc). "
            "Even if the entity exists, verify if the statement about it is correct. "
            "Return ONLY valid JSON with keys: verdict, confidence, summary. "
            "verdict must be TRUE or FALSE."
        )
        user_prompt = (
            f"Claim: {claim}\n\n"
            f"Top Evidence:\n{evidence_text[:2200]}\n\n"
            "Check if the claim is factually correct based on the evidence. "
            "Pay attention to incorrect attributes (gender, role, position, time).\n\n"
            "Return ONLY JSON:\n"
            "{\"verdict\":\"TRUE|FALSE\",\"confidence\":0-100,\"summary\":\"short explanation\"}"
        )

        def _run_llm() -> str:
            client = get_groq_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=220,
            )
            return (response.choices[0].message.content or "").strip()

        try:
            raw = await asyncio.wait_for(asyncio.to_thread(_run_llm), timeout=self.reason_timeout)
            parsed = _extract_json_object(raw)
            if not isinstance(parsed, dict):
                upper_raw = raw.upper()
                if "TRUE" in upper_raw or "FALSE" in upper_raw:
                    guess = "TRUE" if "TRUE" in upper_raw and "FALSE" not in upper_raw else "FALSE"
                    return {
                        "verdict": guess,
                        "confidence": 70 if guess == "TRUE" else 60,
                        "summary": raw[:220] or "No strong real-world evidence found.",
                    }
                return None

            verdict = str(parsed.get("verdict", "FALSE")).upper().strip()
            if verdict not in {"TRUE", "FALSE"}:
                verdict = "FALSE"

            confidence_raw = parsed.get("confidence", 50)
            try:
                confidence = int(float(confidence_raw))
            except Exception:
                confidence = 50
            confidence = max(0, min(100, confidence))

            summary = str(
                parsed.get("summary") or parsed.get("reason") or parsed.get("reasoning") or ""
            ).strip() or "No strong real-world evidence found."

            return {
                "verdict": verdict,
                "confidence": confidence,
                "summary": summary,
            }
        except Exception:
            return None

    async def _run_pipeline(self, claim: str, content_type: str) -> dict[str, Any]:
        core_claim = extract_core_claim(claim).strip() or claim.strip()
        queries = self.plan_queries(core_claim, content_type=content_type)
        if not queries:
            return self._fallback_response(claim=core_claim)

        evidence = await self.fetch_all_evidence(queries)
        if not evidence:
            return self._fallback_response(claim=core_claim)

        ranked = await self._semantic_rerank(core_claim, evidence)
        if not ranked:
            return self._fallback_response(claim=core_claim)

        sources = self._build_sources(ranked)
        if not sources:
            return self._fallback_response(claim=core_claim)

        evidence_text = self._fuse_evidence_text(ranked)
        llm_result = await self._llm_semantic_verdict(core_claim, evidence_text)

        if not llm_result:
            fallback = self._fallback_response(claim=core_claim)
            fallback["sources"] = sources if sources else fallback["sources"]
            return fallback

        final_verdict = llm_result["verdict"]
        final_confidence = llm_result["confidence"]
        final_summary = llm_result["summary"]

        return {
            "verdict": final_verdict,
            "confidence": final_confidence,
            "reasoning": final_summary,
            "explanation": {
                "summary": final_summary,
                "points": [
                    f"Providers used: {', '.join(self.providers)}.",
                    "Semantic similarity filtering used threshold > 0.45.",
                    "Re-ranking used similarity + trusted domain + overlap signals.",
                ],
                "technical": "Final verdict is from LLM semantic verification over top ranked evidence.",
            },
            "technical_details": "LLM semantic verdict over Tavily/Wikipedia evidence.",
            "evidence_points": [
                f"Top evidence count: {len(ranked)}",
                "Decision source: LLM JSON output (no rule override).",
            ],
            "key_evidence": evidence_text[:300] if evidence_text else "No strong real-world evidence found.",
            "sources": sources[:3],
        }

    async def run(self, claim: str, timeout: int = 25, content_type: str = "text") -> dict[str, Any]:
        effective_timeout = max(5, min(timeout, int(self.pipeline_timeout)))
        normalized_type = (content_type or "text").lower()
        if normalized_type not in {"text", "image", "video", "multimodal"}:
            normalized_type = "text"

        try:
            return await asyncio.wait_for(
                self._run_pipeline(claim, normalized_type),
                timeout=effective_timeout,
            )
        except Exception:
            return self._fallback_response(claim=claim)
