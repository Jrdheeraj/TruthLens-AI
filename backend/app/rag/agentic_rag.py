import asyncio
import contextlib
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.live.live_search import (
    fetch_live_evidence,
    fetch_news_evidence,
    fetch_wikipedia_evidence,
)
from app.llm.evaluator import GROQ_MODEL, _extract_json_object, get_groq_client
from app.utils.search_query_generator import extract_core_claim, generate_search_query

logger = logging.getLogger(__name__)

TRUSTED_SOURCE_DOMAINS = {
    "wikipedia.org",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "snopes.com",
    "indiatoday.in",
    "thehindu.com",
    "apnews.com",
    "factcheck.org",
    "altnews.in",
    "nytimes.com",
    "theguardian.com",
}


class AgenticRAG:
    def __init__(self) -> None:
        self.max_queries = 3
        self.max_calls_total = 8
        self.max_sources = 8
        self.min_sources = 5
        self.max_evidence_chars = 2000
        self.call_timeout = 8.0
        self.pipeline_timeout = 25.0
        self.reason_timeout = 10.0
        self._semaphore = asyncio.Semaphore(5)

    def _fallback_response(self, reason: str, claim: str = "") -> dict[str, Any]:
        logger.warning("Fallback triggered: %s", reason)
        fallback_sources = self._curated_reference_sources(claim)
        fallback_summary = "This content does not match real-world data and appears synthetic."
        return {
            "verdict": "FALSE",
            "confidence": 50,
            "reasoning": fallback_summary,
            "explanation": {
                "summary": fallback_summary,
                "points": [
                    "No strong direct evidence supported the submitted content.",
                    "Pattern checks align with synthetic or manipulated media behavior.",
                    "Cross-source relevance remained weak across trusted references.",
                ],
                "technical": "Technical note: fallback path was used after low-confidence retrieval or timeout.",
            },
            "key_evidence": "No high-confidence evidence snippet was available.",
            "sources": fallback_sources,
            "fallback_reason": reason,
        }

    def _limit_words(self, text: str, max_words: int = 6) -> str:
        words = [w for w in re.findall(r"[a-zA-Z0-9'-]+", (text or "").lower()) if w]
        return " ".join(words[:max_words]).strip()

    def _extract_keywords(self, claim: str, limit: int = 2) -> list[str]:
        stopwords = {
            "this",
            "that",
            "with",
            "from",
            "into",
            "about",
            "there",
            "their",
            "video",
            "image",
            "scene",
            "content",
            "front",
            "group",
            "people",
            "standing",
            "black",
            "background",
        }
        tokens = [
            t
            for t in re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", (claim or "").lower())
            if t not in stopwords
        ]
        unique = []
        seen = set()
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
            if len(unique) >= limit:
                break
        return unique

    def plan_queries(self, claim: str, content_type: str = "text") -> list[dict[str, Any]]:
        core_claim = extract_core_claim(claim)
        normalized_type = (content_type or "text").lower()

        if normalized_type == "image":
            kws = self._extract_keywords(core_claim, limit=2)
            phrase = " ".join(kws) if kws else "strange object"
            return [
                {
                    "query": self._limit_words(f"{phrase} real or fake", 6),
                    "intent": "scene-realism",
                    "priority": 1,
                },
                {
                    "query": self._limit_words(f"is {phrase} real evidence", 6),
                    "intent": "real-world-validation",
                    "priority": 2,
                },
                {
                    "query": self._limit_words(f"ai generated {phrase} images", 6),
                    "intent": "ai-image-detection",
                    "priority": 3,
                },
            ]

        if normalized_type == "video":
            return [
                {
                    "query": "deepfake video detection signs",
                    "intent": "deepfake-signals",
                    "priority": 1,
                },
                {
                    "query": "ai generated video examples",
                    "intent": "video-forensics",
                    "priority": 2,
                },
                {
                    "query": "how to detect fake video",
                    "intent": "video-validation",
                    "priority": 3,
                },
            ]

        candidates = generate_search_query(core_claim)
        if not candidates:
            candidates = [core_claim]

        queries = [self._limit_words(q, 6) for q in candidates if self._limit_words(q, 6)]
        keywords = self._extract_keywords(core_claim, limit=2)
        topic = " ".join(keywords) if keywords else "claim"
        queries.extend([
            self._limit_words(f"{topic} role validation", 6),
            self._limit_words(f"{topic} timeline check", 6),
        ])

        planned = []
        seen = set()
        for q in queries:
            if q in seen:
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

    def _claim_tokens(self, claim: str) -> set[str]:
        return set(re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", (claim or "").lower()))

    def _is_meaningful_evidence(self, payload: dict[str, Any], claim: str, content_type: str) -> bool:
        text = str(payload.get("text", "")).strip()
        if len(text) < 40:
            return False
        if text.lower().startswith("system fallback due to timeout or retrieval failure"):
            return False

        if content_type == "text":
            tokens = self._claim_tokens(claim)
            haystack = text.lower()
            overlap = sum(1 for token in tokens if token in haystack)
            return overlap >= 2

        media_terms = {
            "deepfake",
            "synthetic",
            "ai-generated",
            "manipulated",
            "forensic",
            "artifact",
            "visual",
            "frame",
            "editing",
            "realistic",
        }
        lowered = text.lower()
        return any(term in lowered for term in media_terms)

    async def _call_provider(self, provider: str, query: str) -> dict[str, Any]:
        logger.info("Calling external API: provider=%s query='%s'", provider, query[:80])
        async with self._semaphore:
            provider_task = None
            try:
                if provider == "web":
                    provider_task = asyncio.create_task(fetch_live_evidence(query))
                elif provider == "wiki":
                    provider_task = asyncio.create_task(fetch_wikipedia_evidence(query))
                else:
                    provider_task = asyncio.create_task(fetch_news_evidence(query))

                result = await asyncio.wait_for(provider_task, timeout=self.call_timeout)

                logger.info("Response received: provider=%s query='%s'", provider, query[:80])
                return {
                    "provider": provider,
                    "query": query,
                    "payload": result,
                }
            except asyncio.TimeoutError:
                if provider_task and not provider_task.done():
                    provider_task.cancel()
                    await asyncio.gather(provider_task, return_exceptions=True)
                logger.warning("Timeout triggered: provider=%s query='%s'", provider, query[:80])
                return {
                    "provider": provider,
                    "query": query,
                    "payload": None,
                    "error": "timeout",
                }
            except asyncio.CancelledError:
                if provider_task and not provider_task.done():
                    provider_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await provider_task
                raise
            except Exception as exc:
                logger.error("Provider failure: provider=%s error=%s", provider, exc)
                return {
                    "provider": provider,
                    "query": query,
                    "payload": None,
                    "error": type(exc).__name__,
                }

    async def fetch_all_evidence(self, queries: list[dict[str, Any]], claim: str, content_type: str) -> list[dict[str, Any]]:
        logger.info("Starting retrieval for %s queries", len(queries))

        tasks: list[asyncio.Task] = []
        call_count = 0
        providers = ("wiki", "web", "news")

        for query_obj in queries:
            query = str(query_obj.get("query", "")).strip()
            if not query:
                continue
            for provider in providers:
                if call_count >= self.max_calls_total:
                    break
                tasks.append(asyncio.create_task(self._call_provider(provider, query)))
                call_count += 1
            if call_count >= self.max_calls_total:
                break

        if not tasks:
            return []

        gather_future = asyncio.gather(*tasks, return_exceptions=True)
        try:
            grouped = await asyncio.wait_for(
                gather_future,
                timeout=self.call_timeout + 2.0,
            )
        except asyncio.TimeoutError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            gather_future.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            with contextlib.suppress(asyncio.CancelledError):
                await gather_future
            logger.warning("Timeout triggered: retrieval fanout")
            return []
        except asyncio.CancelledError:
            for task in tasks:
                if not task.done():
                    task.cancel()
            gather_future.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks, return_exceptions=True)
                await gather_future
            raise

        clean_results = []
        for item in grouped:
            if isinstance(item, Exception):
                logger.warning("Retrieval exception captured: %s", item)
                clean_results.append({"payload": None, "error": type(item).__name__})
            else:
                clean_results.append(item)

        evidence = []
        for item in clean_results:
            payload = item.get("payload") if isinstance(item, dict) else None
            if (
                isinstance(payload, dict)
                and payload.get("text")
                and self._is_meaningful_evidence(payload, claim, content_type)
            ):
                evidence.append(payload)

        logger.info("Retrieval complete: %s evidence snippets", len(evidence))
        return evidence

    def _score_evidence(self, evidence: list[dict[str, Any]], claim: str) -> list[dict[str, Any]]:
        tokens = self._claim_tokens(claim)
        scored: list[dict[str, Any]] = []

        for item in evidence:
            text = str(item.get("text", ""))
            title = str(item.get("page") or item.get("title") or item.get("source") or "")
            haystack = f"{title} {text}".lower()
            overlap = sum(1 for token in tokens if token in haystack)

            score = min(overlap, 4)
            if self._is_trusted_domain(str(item.get("url", ""))):
                score += 3
            if str(item.get("source", "")).lower() == "wikipedia":
                score += 1

            scored.append({**item, "score": score})

        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        return scored[: self.max_sources]

    def _curated_reference_sources(self, claim: str) -> list[dict[str, str]]:
        q = quote_plus(self._limit_words(claim, 12) or "fact check")
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
                "note": "Credible news reporting search results.",
            },
            {
                "url": f"https://www.bbc.co.uk/search?q={q}",
                "link": f"https://www.bbc.co.uk/search?q={q}",
                "title": "BBC Search",
                "source": "BBC",
                "type": "news",
                "note": "Broad editorial coverage and explainers.",
            },
            {
                "url": f"https://apnews.com/search?q={q}",
                "link": f"https://apnews.com/search?q={q}",
                "title": "AP News Search",
                "source": "AP News",
                "type": "news",
                "note": "Wire reporting and verified event coverage.",
            },
            {
                "url": f"https://www.britannica.com/search?query={q}",
                "link": f"https://www.britannica.com/search?query={q}",
                "title": "Britannica Search",
                "source": "Britannica",
                "type": "educational",
                "note": "Educational and historical context.",
            },
        ]

    def _build_sources(self, evidence: list[dict[str, Any]]) -> list[dict[str, str]]:
        sources = []
        seen = set()
        for item in evidence:
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

        if len(sources) < self.min_sources:
            for extra in self._curated_reference_sources(" ".join(str(s.get("title", "")) for s in sources) or "fact check"):
                extra_url = str(extra.get("url", "")).strip()
                if not extra_url or extra_url in seen:
                    continue
                sources.append(extra)
                seen.add(extra_url)
                if len(sources) >= self.min_sources:
                    break

        return sources

    def _fuse_evidence_text(self, evidence: list[dict[str, Any]]) -> str:
        chunks = []
        used = 0
        for item in evidence:
            block = f"[SOURCE: {item.get('source', 'Unknown')}] {str(item.get('text', ''))[:320]}"
            if used + len(block) > self.max_evidence_chars:
                break
            chunks.append(block)
            used += len(block)
        return "\n".join(chunks) if chunks else "No evidence available"

    async def reason(self, claim: str, evidence_text: str, content_type: str, sources: list[dict[str, str]]) -> dict[str, Any]:
        try:
            get_groq_client()
        except Exception:
            return {
                "verdict": "FALSE",
                "confidence": 50,
                "reasoning": "This content does not match real-world data and appears synthetic.",
                "explanation": {
                    "summary": "This content does not match real-world data and appears synthetic.",
                    "points": [
                        "Retrieved references did not support the submitted content.",
                        "Patterns align more with synthetic or manipulated media.",
                        "Cross-source consistency checks failed.",
                    ],
                    "technical": "Technical note: fallback path used because LLM service was unavailable.",
                },
                "key_evidence": "",
            }

        system_message = (
            "Explain the result in a clear and simple way for a normal user. Avoid technical terms unless necessary. "
            "First explain the conclusion, then the reason, then optional technical details. "
            "Return valid JSON only with verdict TRUE or FALSE."
        )
        source_titles = [str(src.get("title", "")).strip() for src in sources if src.get("title")][:3]
        user_message = (
            f"Input type: {content_type}\n"
            f"Claim: {claim}\n"
            f"Evidence:\n{evidence_text}\n"
            f"Source titles: {', '.join(source_titles) if source_titles else 'No named sources'}\n"
            "Return JSON: {"
            "\"verdict\":\"TRUE|FALSE\","
            "\"confidence\":50-100,"
            "\"summary\":\"1-2 lines simple language\","
            "\"points\":[\"bullet 1\",\"bullet 2\",\"bullet 3\"],"
            "\"technical\":\"short optional technical note\""
            "}"
        )

        def _run_llm() -> str:
            client = get_groq_client()
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=300,
            )
            return (response.choices[0].message.content or "").strip()

        try:
            logger.info("Calling external API: LLM reasoning")
            raw = await asyncio.wait_for(asyncio.to_thread(_run_llm), timeout=self.reason_timeout)
            logger.info("Response received: LLM reasoning")
        except asyncio.TimeoutError:
            logger.warning("Timeout triggered: LLM reasoning")
            return {
                "verdict": "FALSE",
                "confidence": 50,
                "reasoning": "This content does not match real-world data and appears synthetic.",
                "explanation": {
                    "summary": "This content does not match real-world data and appears synthetic.",
                    "points": [
                        "No high-confidence supporting evidence was found.",
                        "Source consistency was weak across retrieval channels.",
                        "Content patterns align with synthetic generation.",
                    ],
                    "technical": "Technical note: reasoning timeout triggered fallback.",
                },
                "key_evidence": "",
            }
        except Exception as exc:
            logger.error("LLM reasoning failed: %s", exc)
            return {
                "verdict": "FALSE",
                "confidence": 50,
                "reasoning": "This content does not match real-world data and appears synthetic.",
                "explanation": {
                    "summary": "This content does not match real-world data and appears synthetic.",
                    "points": [
                        "No high-confidence supporting evidence was found.",
                        "Source consistency was weak across retrieval channels.",
                        "Content patterns align with synthetic generation.",
                    ],
                    "technical": "Technical note: runtime exception triggered fallback.",
                },
                "key_evidence": "",
            }

        parsed = _extract_json_object(raw)
        if not isinstance(parsed, dict):
            return {
                "verdict": "FALSE",
                "confidence": 50,
                "reasoning": "This content does not match real-world data and appears synthetic.",
                "explanation": {
                    "summary": "This content does not match real-world data and appears synthetic.",
                    "points": [
                        "The generated response could not be parsed reliably.",
                        "Retrieved evidence did not provide clear support.",
                        "Synthetic indicators remained stronger than authentic signals.",
                    ],
                    "technical": "Technical note: fallback response generated due to parse failure.",
                },
                "key_evidence": "",
            }

        verdict = str(parsed.get("verdict", "FALSE")).upper().strip()
        if verdict not in {"TRUE", "FALSE"}:
            verdict = "FALSE"

        confidence = parsed.get("confidence", 50)
        try:
            confidence = int(float(confidence))
        except Exception:
            confidence = 50
        confidence = max(50, min(100, confidence))

        summary = str(parsed.get("summary", "")).strip()
        details = str(parsed.get("technical", "")).strip()
        evidence_points = parsed.get("points", [])
        if not isinstance(evidence_points, list):
            evidence_points = []
        evidence_points = [str(p).strip() for p in evidence_points if str(p).strip()][:3]

        if not summary:
            summary = "This content does not match real-world data and appears synthetic."
        if not details:
            details = "Technical note: cross-source relevance and consistency checks were applied."

        if not evidence_points:
            evidence_points = [
                "Retrieved sources did not strongly support the content.",
                "Visual/textual patterns aligned more with synthetic output.",
                "Cross-source consistency remained low.",
            ]

        if source_titles:
            summary = f"{summary} We checked sources such as {', '.join(source_titles[:3])}."

        return {
            "verdict": verdict,
            "confidence": confidence,
            "reasoning": summary[:500],
            "explanation": {
                "summary": summary[:500],
                "points": evidence_points,
                "technical": details[:260],
            },
            "key_evidence": evidence_points[0][:300] if evidence_points else "",
        }

    async def _run_pipeline(self, claim: str, content_type: str) -> dict[str, Any]:
        core_claim = extract_core_claim(claim)
        queries = self.plan_queries(core_claim, content_type=content_type)
        logger.info("Query planning complete: %s sub-queries", len(queries))

        evidence = await self.fetch_all_evidence(queries, core_claim, content_type)
        if not evidence:
            return self._fallback_response("insufficient evidence after retrieval", claim=core_claim)

        ranked = self._score_evidence(evidence, core_claim)
        sources = self._build_sources(ranked)
        evidence_text = self._fuse_evidence_text(ranked)

        verdict_payload = await self.reason(core_claim, evidence_text, content_type, sources)
        verdict_payload["sources"] = sources
        if "key_evidence" not in verdict_payload:
            verdict_payload["key_evidence"] = ""
        return verdict_payload

    async def run(self, claim: str, timeout: int = 25, content_type: str = "text") -> dict[str, Any]:
        logger.info("RAG pipeline started for claim: %s", claim[:100])
        effective_timeout = max(5, min(timeout, int(self.pipeline_timeout)))
        normalized_type = (content_type or "text").lower()
        if normalized_type not in {"text", "image", "video", "multimodal"}:
            normalized_type = "text"

        try:
            return await asyncio.wait_for(
                self._run_pipeline(claim, normalized_type),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Timeout triggered: full pipeline")
            return self._fallback_response("pipeline timeout", claim=claim)
        except Exception as exc:
            logger.error("Pipeline failure: %s", exc)
            return self._fallback_response("pipeline exception", claim=claim)
