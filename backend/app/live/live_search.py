import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx
from dotenv import load_dotenv
from tavily import TavilyClient

logger = logging.getLogger(__name__)
ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH)

HTTP_TIMEOUT = httpx.Timeout(5.0)
WIKIPEDIA_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

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


_TAVILY_BREAKER = CircuitBreaker("tavily", failure_threshold=5, recovery_seconds=10.0)
_WIKI_BREAKER = CircuitBreaker("wikipedia", failure_threshold=5, recovery_seconds=10.0)
_TAVILY_CLIENT: Optional[TavilyClient] = None


def _get_tavily_client() -> TavilyClient:
    global _TAVILY_CLIENT
    if _TAVILY_CLIENT is not None:
        return _TAVILY_CLIENT

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY not configured")

    _TAVILY_CLIENT = TavilyClient(api_key=api_key)
    return _TAVILY_CLIENT


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
    timeout_seconds: float = 5.0,
) -> dict:
    async def _request() -> dict:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    return await asyncio.wait_for(_request(), timeout=timeout_seconds)


async def fetch_tavily_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    query = _get_query(query_input).strip()
    if len(query) < 3:
        return None

    logger.info("Start retrieval: tavily query='%s'", query[:80])
    if not _TAVILY_BREAKER.allow_request():
        return None

    try:
        tavily = _get_tavily_client()
    except Exception as exc:
        _TAVILY_BREAKER.on_failure()
        logger.warning("Tavily init failed: %s", type(exc).__name__)
        return None

    def _sync_tavily_search(q: str) -> dict:
        return tavily.search(query=q, max_results=3)

    try:
        logger.info("Calling external API: Tavily search")
        result = await asyncio.wait_for(asyncio.to_thread(_sync_tavily_search, query), timeout=5.0)
        raw_results = result.get("results", []) if isinstance(result, dict) else []
        logger.info("Response received: Tavily search (%s results)", len(raw_results))
    except asyncio.TimeoutError:
        _TAVILY_BREAKER.on_failure()
        return None
    except Exception as exc:
        _TAVILY_BREAKER.on_failure()
        logger.warning("Tavily request failed: %s", type(exc).__name__)
        return None

    evidence_chunks = []
    first_title = "Tavily Results"
    first_url = "https://tavily.com"
    for item in raw_results[:3]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        body = str(item.get("content") or item.get("snippet") or "").strip()
        url = str(item.get("url") or "").strip()
        if len(body) <= 20 or _is_spam(body):
            continue
        if first_title == "Tavily Results" and title:
            first_title = title
        if first_url == "https://tavily.com" and url:
            first_url = url
        evidence_chunks.append(f"{title}: {body}" if title else body)

    if len(raw_results) == 0:
        logger.warning("Tavily returned empty")

    if not evidence_chunks:
        _TAVILY_BREAKER.on_failure()
        return None

    _TAVILY_BREAKER.on_success()
    return {
        "source": "Tavily",
        "page": first_title,
        "url": first_url,
        "text": " ".join(evidence_chunks)[:2000],
    }


async def fetch_live_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    """Compatibility wrapper for legacy callers."""
    return await fetch_tavily_evidence(query_input, subject_name=subject_name)


async def fetch_wikipedia_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    query = _get_query(query_input).strip()
    if len(query) < 3:
        return None

    logger.info("Start retrieval: wiki query='%s'", query[:80])
    if not _WIKI_BREAKER.allow_request():
        return None

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
                    "srlimit": 2,
                },
                timeout_seconds=5.0,
            )
            results = search_data.get("query", {}).get("search", [])
            if not results:
                _WIKI_BREAKER.on_failure()
                return None

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
                timeout_seconds=5.0,
            )
            extract = str(summary_data.get("extract", "")).strip()
            if len(extract) < 30:
                _WIKI_BREAKER.on_failure()
                return None

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
        except asyncio.TimeoutError:
            _WIKI_BREAKER.on_failure()
            return None
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            _WIKI_BREAKER.on_failure()
            return None


async def fetch_news_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    """Compatibility wrapper; news provider now routes through Tavily.

    Keeps call sites stable while removing DDG dependency.
    """
    result = await fetch_tavily_evidence(query_input, subject_name=subject_name)
    if not result:
        return result
    result["source"] = "Tavily"
    return result
