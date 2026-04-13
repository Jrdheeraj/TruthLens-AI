import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

HTTP_TIMEOUT = httpx.Timeout(6.0)
WIKIPEDIA_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
DDG_INSTANT_API = "https://api.duckduckgo.com/"

SPAM_PATTERNS = [
    r"buy now",
    r"click here",
    r"advertisement",
    r"sponsored",
    r"subscribe now",
    r"follow us",
    r"like and share",
    r"porn",
    r"adult",
    r"xxx",
    r"sex cam",
]


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_seconds: float = 60.0

    def __post_init__(self) -> None:
        self._failures = 0
        self._opened_at = 0.0

    def allow_request(self) -> bool:
        if self._opened_at == 0.0:
            return True
        if (time.monotonic() - self._opened_at) >= self.recovery_seconds:
            logger.info("Circuit half-open: %s", self.name)
            self._opened_at = 0.0
            self._failures = 0
            return True
        return False

    def on_success(self) -> None:
        self._failures = 0
        self._opened_at = 0.0

    def on_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()
            logger.warning("Circuit opened: %s", self.name)


_WEB_BREAKER = CircuitBreaker("duckduckgo-web")
_WIKI_BREAKER = CircuitBreaker("wikipedia")
_NEWS_BREAKER = CircuitBreaker("duckduckgo-news")


def _get_query(query_input) -> str:
    if isinstance(query_input, list):
        return query_input[0] if query_input else ""
    if isinstance(query_input, str):
        return query_input
    return ""


def _is_spam(text: str) -> bool:
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in SPAM_PATTERNS)


def _fallback_evidence(source: str, query: str, reason: str, url: str) -> dict:
    logger.warning("Fallback triggered: %s (%s)", source, reason)
    return {
        "source": source,
        "page": "Fallback",
        "url": url,
        "text": f"System fallback due to timeout or retrieval failure for '{query[:120]}': {reason}",
    }


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[dict] = None,
    timeout_seconds: float = 6.0,
) -> dict:
    async def _request() -> dict:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    return await asyncio.wait_for(_request(), timeout=timeout_seconds)


async def fetch_live_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    query = _get_query(query_input).strip()
    if len(query) < 3:
        return None

    logger.info("Start retrieval: web query='%s'", query[:80])
    if not _WEB_BREAKER.allow_request():
        return _fallback_evidence(
            "Live Internet Search",
            query,
            "circuit breaker open",
            "https://duckduckgo.com",
        )

    try:
        from ddgs import DDGS
    except Exception as exc:
        _WEB_BREAKER.on_failure()
        return _fallback_evidence(
            "Live Internet Search",
            query,
            f"ddgs import failed: {type(exc).__name__}",
            "https://duckduckgo.com",
        )

    def _sync_web_search(q: str) -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.text(q, max_results=6))

    try:
        logger.info("Calling external API: DDGS web search")
        raw_results = await asyncio.wait_for(asyncio.to_thread(_sync_web_search, query), timeout=6.0)
        logger.info("Response received: DDGS web search (%s results)", len(raw_results))
    except (asyncio.TimeoutError, Exception) as exc:
        _WEB_BREAKER.on_failure()
        return _fallback_evidence(
            "Live Internet Search",
            query,
            f"web request failed: {type(exc).__name__}",
            "https://duckduckgo.com",
        )

    evidence_chunks = []
    first_title = "DuckDuckGo Results"
    first_url = "https://duckduckgo.com"
    for item in raw_results[:6]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        body = str(item.get("body") or "").strip()
        url = str(item.get("href") or item.get("url") or "").strip()
        if len(body) < 25 or _is_spam(body):
            continue
        if not first_title and title:
            first_title = title
        if first_url == "https://duckduckgo.com" and url:
            first_url = url
        evidence_chunks.append(f"{title}: {body}" if title else body)

    if not evidence_chunks:
        _WEB_BREAKER.on_failure()
        return _fallback_evidence(
            "Live Internet Search",
            query,
            "no useful web snippets",
            "https://duckduckgo.com",
        )

    _WEB_BREAKER.on_success()
    return {
        "source": "Live Internet Search",
        "page": first_title,
        "url": first_url,
        "text": " ".join(evidence_chunks)[:2000],
    }


async def fetch_wikipedia_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    query = _get_query(query_input).strip()
    if len(query) < 3:
        return None

    logger.info("Start retrieval: wiki query='%s'", query[:80])
    if not _WIKI_BREAKER.allow_request():
        return _fallback_evidence(
            "Wikipedia",
            query,
            "circuit breaker open",
            f"https://en.wikipedia.org/w/index.php?search={quote_plus(query)}",
        )

    headers = {"User-Agent": "TruthLensAI/1.7"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
        try:
            logger.info("Calling external API: Wikipedia search")
            search_data = await _get_json(
                client,
                WIKIPEDIA_SEARCH_API,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "utf8": 1,
                    "srlimit": 3,
                },
                timeout_seconds=6.0,
            )
            results = search_data.get("query", {}).get("search", [])
            if not results:
                _WIKI_BREAKER.on_failure()
                return _fallback_evidence(
                    "Wikipedia",
                    query,
                    "no wikipedia results",
                    f"https://en.wikipedia.org/w/index.php?search={quote_plus(query)}",
                )

            best_page = results[0].get("title", "")
            if subject_name:
                lowered = subject_name.lower()
                for result in results:
                    title = str(result.get("title", "")).strip()
                    if lowered and lowered in title.lower():
                        best_page = title
                        break

            logger.info("Calling external API: Wikipedia summary")
            summary_data = await _get_json(
                client,
                f"{WIKIPEDIA_SUMMARY_API}{best_page.replace(' ', '_')}",
                timeout_seconds=6.0,
            )
            extract = str(summary_data.get("extract", "")).strip()
            if len(extract) < 30:
                _WIKI_BREAKER.on_failure()
                return _fallback_evidence(
                    "Wikipedia",
                    query,
                    "summary too short",
                    f"https://en.wikipedia.org/wiki/{best_page.replace(' ', '_')}",
                )

            urls = summary_data.get("content_urls") or {}
            page_url = (
                (urls.get("desktop") or {}).get("page")
                or f"https://en.wikipedia.org/wiki/{best_page.replace(' ', '_')}"
            )

            logger.info("Response received: Wikipedia summary")
            _WIKI_BREAKER.on_success()
            return {
                "source": "Wikipedia",
                "page": best_page,
                "url": page_url,
                "text": extract[:2000],
            }
        except (httpx.HTTPError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
            _WIKI_BREAKER.on_failure()
            return _fallback_evidence(
                "Wikipedia",
                query,
                f"wiki request failed: {type(exc).__name__}",
                f"https://en.wikipedia.org/w/index.php?search={quote_plus(query)}",
            )


async def fetch_news_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    query = _get_query(query_input).strip()
    if len(query) < 3:
        return None

    logger.info("Start retrieval: news query='%s'", query[:80])
    if not _NEWS_BREAKER.allow_request():
        return _fallback_evidence(
            "News",
            query,
            "circuit breaker open",
            "https://duckduckgo.com",
        )

    try:
        from ddgs import DDGS
    except Exception as exc:
        _NEWS_BREAKER.on_failure()
        return _fallback_evidence(
            "News",
            query,
            f"ddgs import failed: {type(exc).__name__}",
            "https://duckduckgo.com",
        )

    def _sync_news_search(q: str) -> list[dict]:
        with DDGS() as ddgs:
            return list(ddgs.news(q, max_results=3))

    try:
        logger.info("Calling external API: DDGS news")
        raw_results = await asyncio.wait_for(asyncio.to_thread(_sync_news_search, query), timeout=6.0)
        logger.info("Response received: DDGS news (%s results)", len(raw_results))
    except (asyncio.TimeoutError, Exception) as exc:
        _NEWS_BREAKER.on_failure()
        return _fallback_evidence(
            "News",
            query,
            f"news request failed: {type(exc).__name__}",
            "https://duckduckgo.com",
        )

    snippets = []
    first_url = "https://duckduckgo.com"
    for item in raw_results[:3]:
        if not isinstance(item, dict):
            continue
        body = str(item.get("body") or "").strip()
        if len(body) < 20 or _is_spam(body):
            continue
        snippets.append(body)
        if first_url == "https://duckduckgo.com":
            first_url = str(item.get("url") or first_url)

    if not snippets:
        _NEWS_BREAKER.on_failure()
        return _fallback_evidence("News", query, "no usable news snippets", "https://duckduckgo.com")

    _NEWS_BREAKER.on_success()
    return {
        "source": "News",
        "page": "News snippets",
        "url": first_url,
        "text": " ".join(snippets)[:2000],
    }
