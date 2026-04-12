import asyncio
import json
import logging
import re
from typing import Optional, List
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ============================================================================
# Validation Models (Pydantic)
# ============================================================================

class DDGSearchResult(BaseModel):
    """DuckDuckGo search result validation model."""
    body: Optional[str] = None
    title: Optional[str] = None
    href: Optional[str] = None


class DDGResponse(BaseModel):
    """DuckDuckGo API response validation."""
    results: List[DDGSearchResult] = Field(default_factory=list)


class WikipediaSearchResult(BaseModel):
    """Wikipedia search result validation."""
    title: str
    pageid: int


class WikipediaSearchResponse(BaseModel):
    """Wikipedia search API response."""
    query: Optional[dict] = None


class WikipediaSummaryResponse(BaseModel):
    """Wikipedia summary API response."""
    extract: Optional[str] = None
    content_urls: Optional[dict] = Field(default_factory=dict)


# ============================================================================
# Constants
# ============================================================================

SPAM_PATTERNS = [
    r"buy now", r"click here", r"advertisement", r"sponsored",
    r"subscribe now", r"follow us", r"like and share",
    r"porn", r"adult", r"xxx", r"sex cam"
]

DDGS_SEARCH_URL = "https://api.duckduckgo.com/"
WIKIPEDIA_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_SUMMARY_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"

HTTP_TIMEOUT = httpx.Timeout(6.0)


# ============================================================================
# Helper Functions
# ============================================================================

def _is_spam(text: str) -> bool:
    """Check if text contains spam indicators."""
    text_lower = text.lower()
    return any(re.search(pattern, text_lower) for pattern in SPAM_PATTERNS)


def _get_query(query_input) -> str:
    """Convert query input (string or list) to string."""
    if isinstance(query_input, list):
        return query_input[0] if query_input else ""
    elif isinstance(query_input, str):
        return query_input
    else:
        return ""


# ============================================================================
# Live Search (DuckDuckGo)
# ============================================================================

async def fetch_live_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    """
    Fetch evidence from DuckDuckGo using async httpx.
    
    Args:
        query_input: Query string or list of strings
        subject_name: Optional subject name for filtering
        
    Returns:
        dict with keys: source, page, url, text
    """
    try:
        query = _get_query(query_input)
        
        if not query or len(query.strip()) < 3:
            logger.debug(f"Query too short: '{query}'")
            return None
        
        logger.debug(f"Fetching DuckDuckGo evidence for query: {query}")
        
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            try:
                # Primary search attempt
                params = {
                    "q": query,
                    "format": "json",
                    "no_html": 1,
                    "max_results": 5
                }
                response = await client.get(DDGS_SEARCH_URL, params=params)
                response.raise_for_status()
                data = response.json()
                results = data.get("Results", [])
                
                logger.debug(f"DuckDuckGo returned {len(results)} results")
                
            except (httpx.RequestError, json.JSONDecodeError) as e:
                logger.warning(f"DuckDuckGo search failed: {e}")
                # Retry with simpler query if multiple words
                if len(query.split()) > 1:
                    simple_query = query.split()[0]
                    logger.debug(f"Retrying with simpler query: {simple_query}")
                    try:
                        params = {
                            "q": simple_query,
                            "format": "json",
                            "no_html": 1,
                            "max_results": 5
                        }
                        response = await client.get(DDGS_SEARCH_URL, params=params)
                        response.raise_for_status()
                        data = response.json()
                        results = data.get("Results", [])
                    except (httpx.RequestError, json.JSONDecodeError) as retry_e:
                        logger.warning(f"Retry search failed: {retry_e}")
                        return None
                else:
                    return None
        
        if not results:
            logger.debug("No DuckDuckGo results found")
            return None
        
        # Extract valid evidence
        evidence_parts = []
        seen_text = set()
        
        for result in results[:5]:
            try:
                # Validate result structure
                result_obj = DDGSearchResult(**result)
                body = (result_obj.body or "").strip()
                
                if len(body) < 20:
                    continue
                
                if _is_spam(body):
                    logger.debug(f"Skipping spam result: {body[:50]}")
                    continue
                
                if body not in seen_text:
                    evidence_parts.append(body)
                    seen_text.add(body)
                    
            except Exception as e:
                logger.warning(f"Invalid result structure: {e}")
                continue
        
        if not evidence_parts:
            logger.debug("No valid evidence after filtering")
            return None
        
        combined_evidence = " ".join(evidence_parts)[:3000]
        
        if len(combined_evidence.strip()) < 20:
            logger.debug("Combined evidence too short")
            return None
        
        first_result = results[0]
        return {
            "source": "Live Internet Search",
            "page": first_result.get("Title", "Web Results"),
            "url": first_result.get("FirstURL", "https://duckduckgo.com"),
            "text": combined_evidence
        }
        
    except Exception as e:
        logger.error(f"Live search exception: {type(e).__name__}: {e}")
        return None


# ============================================================================
# Wikipedia Search
# ============================================================================

async def fetch_wikipedia_evidence(query_input, subject_name: str = None) -> Optional[dict]:
    """
    Fetch evidence from Wikipedia using async httpx.
    
    Args:
        query_input: Query string or list of strings
        subject_name: Optional subject name for filtering
        
    Returns:
        dict with keys: source, page, url, text
    """
    try:
        query = _get_query(query_input)
        
        if not query or len(query.strip()) < 3:
            logger.debug(f"Wikipedia query too short: '{query}'")
            return None
        
        logger.debug(f"Fetching Wikipedia evidence for query: {query}")
        
        headers = {"User-Agent": "TruthLensAI/1.7"}
        
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            
            # Step 1: Search for pages
            try:
                search_params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "utf8": 1,
                    "srlimit": 5
                }
                search_response = await client.get(WIKIPEDIA_SEARCH_API, params=search_params)
                search_response.raise_for_status()
                search_data = search_response.json()
                
                search_obj = WikipediaSearchResponse(**search_data)
                results = search_obj.query.get("search", []) if search_obj.query else []
                
            except (httpx.RequestError, json.JSONDecodeError, Exception) as e:
                logger.warning(f"Wikipedia search failed: {e}")
                return None
            
            if not results:
                logger.debug("No Wikipedia results found")
                return None
            
            # Step 2: Find best matching page
            best_page = None
            if subject_name:
                subject_lower = subject_name.lower()
                for result in results:
                    if subject_lower in result.get("title", "").lower():
                        best_page = result.get("title")
                        break
            
            if not best_page:
                best_page = results[0].get("title")
            
            # Step 3: Fetch page summary
            try:
                summary_url = f"{WIKIPEDIA_SUMMARY_API}{best_page.replace(' ', '_')}"
                summary_response = await client.get(summary_url)
                summary_response.raise_for_status()
                summary_data = summary_response.json()
                
                summary_obj = WikipediaSummaryResponse(**summary_data)
                extract = summary_obj.extract
                content_urls = summary_obj.content_urls or {}
                
            except (httpx.RequestError, json.JSONDecodeError, Exception) as e:
                logger.warning(f"Wikipedia summary fetch failed: {e}")
                return None
            
            if not extract or len(extract) < 30:
                logger.debug("Wikipedia extract too short")
                return None
            
            page_url = extract_url = None
            if content_urls.get("desktop"):
                page_url = content_urls["desktop"].get("page")
            
            if not page_url:
                page_url = f"https://en.wikipedia.org/wiki/{best_page.replace(' ', '_')}"
            
            return {
                "source": "Wikipedia",
                "page": best_page,
                "url": page_url,
                "text": extract[:2000]
            }
            
    except Exception as e:
        logger.error(f"Wikipedia fetch exception: {type(e).__name__}: {e}")
        return None

