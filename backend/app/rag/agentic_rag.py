import logging
import json
import asyncio
from typing import List, Dict
from functools import lru_cache
import httpx
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Import LLM client
from app.llm.evaluator import get_groq_client, GROQ_MODEL, _extract_json_object
from app.utils.search_query_generator import generate_search_query, extract_core_claim, _extract_subject_name

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
}

# ============================================================================
# AGENTIC RAG SYSTEM
# ============================================================================

class AgenticRAG:
    """
    Production-grade Agentic RAG system for fact verification.
    
    PART 2: Complete rewrite of RAG pipeline with:
    - Query planning (decompose claims into sub-queries)
    - Parallel evidence retrieval (web, Wikipedia, news)
    - Evidence scoring and fusion
    - LLM reasoning with reflection loop
    - TRUE/FALSE only verdicts
    """
    
    def __init__(self):
        self.web_timeout = 3.0  # REDUCED from 6.0s
        self.wiki_timeout = 3.0  # REDUCED from 6.0s
        self.news_timeout = 3.0  # REDUCED from 6.0s
        self.max_evidence_chars = 2000  # REDUCED from 4000
        self.top_results = 5  # REDUCED from 8

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
        return {w for w in re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", (claim or "").lower())}

    def _is_relevant(self, source: Dict, claim: str, subject_name: str = "") -> bool:
        title = str(source.get("title") or "").lower()
        snippet = str(source.get("text") or source.get("snippet") or "").lower()
        haystack = f"{title} {snippet}"

        tokens = self._claim_tokens(claim)
        overlap = sum(1 for token in tokens if token in haystack)

        if subject_name and subject_name.lower() in haystack:
            return True

        # Keep only direct-claim evidence with at least 2 token overlaps.
        return overlap >= 2

    async def _validate_source_title(self, claim: str, source_title: str) -> bool:
        """Optional AI gate: keep only titles that directly help verify the claim."""
        if not source_title:
            return False
        try:
            client = get_groq_client()
            prompt = (
                "Does this source title directly help verify this claim? "
                "Answer only YES or NO.\n"
                f"Claim: {claim}\n"
                f"Source: {source_title}"
            )
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=4,
            )
            answer = (response.choices[0].message.content or "").strip().upper()
            return answer.startswith("YES")
        except Exception:
            # Fail-open to heuristic filtering only.
            return True
        
    # ========================================================================
    # STEP 1: Query Planning
    # ========================================================================
    
    def plan_queries(self, claim: str) -> List[Dict]:
        """
        Decompose claim into 2-4 targeted sub-queries using LLM.
        
        Returns:
            List of queries with intent and priority markers
        """
        core_claim = extract_core_claim(claim)
        query_strings = generate_search_query(core_claim)

        if not query_strings:
            return [{"query": claim, "intent": "factual", "priority": 1}]

        queries = [
            {"query": q, "intent": "fact-check", "priority": idx + 1}
            for idx, q in enumerate(query_strings)
        ]
        logger.info(f"Query planning: {len(queries)} claim-aware queries")
        return queries
    
    # ========================================================================
    # STEP 2: Parallel Evidence Retrieval
    # ========================================================================
    
    async def fetch_web_evidence(self, query: str) -> List[Dict]:
        """Fetch web evidence from DuckDuckGo using asyncio.to_thread()"""
        try:
            import time
            from ddgs import DDGS
            
            def _sync_ddgs_text(q, max_results):
                """Synchronous DDGS search wrapper with exponential backoff"""
                for attempt in range(3):
                    try:
                        with DDGS() as ddgs:
                            results = list(ddgs.text(q, max_results=max_results))
                            return results
                    except Exception as e:
                        err_str = str(e)
                        if "Ratelimit" in err_str or "202" in err_str or "403" in err_str:
                            if attempt < 2:
                                time.sleep(2 ** attempt)  # 1s, 2s backoff
                                continue
                        logger.warning(f"DDGS text error: {e}")
                        return []
                return []
            
            # Run sync function in thread pool
            results = await asyncio.wait_for(
                asyncio.to_thread(_sync_ddgs_text, query, 5),
                timeout=5.0  # PERFORMANCE: Reduced from 8s to 5s
            )
            
            evidence = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                body = (r.get('body') or '').strip()
                url = r.get('href') or r.get('url') or ""
                if len(body) > 20:
                    if url and not self._is_trusted_domain(url):
                        continue
                    evidence.append({
                        "source": r.get('source') or r.get('title', 'DuckDuckGo'),
                        "url": url,
                        "title": r.get('title', 'Search Result'),
                        "text": body,
                        "type": "web"
                    })
            
            logger.debug(f"Web search: {len(evidence)} results for '{query}'")
            return evidence
        
        except asyncio.TimeoutError:
            logger.warning(f"Web search timed out for '{query}'")
            return []
        except Exception as e:
            logger.warning(f"Web search failed for '{query}': {e}")
            return []
    
    async def fetch_wiki_evidence(self, query: str) -> List[Dict]:
        """Fetch Wikipedia evidence using action API"""
        try:
            headers = {
                "User-Agent": "TruthLensAI/1.0 (fact-checking; contact@truthlens.local)"
            }
            
            async with httpx.AsyncClient(timeout=5.0) as client:  # PERFORMANCE: Reduced timeout
                # Step 1: Search for pages
                search_resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": query,
                        "format": "json",
                        "utf8": 1,
                        "srlimit": 3
                    },
                    headers=headers
                )
                search_resp.raise_for_status()
                search_results = search_resp.json().get("query", {}).get("search", [])
                
                if not search_results:
                    return []
                
                evidence = []
                for result in search_results[:3]:
                    page_title = result.get("title", "")
                    snippet = result.get("snippet", "")
                    
                    # Clean HTML tags
                    import re
                    snippet_clean = re.sub(r'<[^>]+>', '', snippet)
                    
                    # Step 2: Get page extract using action API
                    extract_resp = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={
                            "action": "query",
                            "titles": page_title,
                            "prop": "extracts",
                            "exintro": 1,
                            "explaintext": 1,
                            "format": "json",
                            "utf8": 1,
                            "exchars": 800
                        },
                        headers=headers
                    )
                    extract_resp.raise_for_status()
                    pages = extract_resp.json().get("query", {}).get("pages", {})
                    
                    for page_id, page in pages.items():
                        if page_id == "-1":
                            continue
                        extract = page.get("extract", snippet_clean)[:500]
                        if extract:
                            evidence.append({
                                "source": "Wikipedia",
                                "url": f"https://en.wikipedia.org/wiki/{page_title.replace(' ', '_')}",
                                "title": page_title,
                                "text": extract,
                                "type": "wiki"
                            })
                
                logger.debug(f"Wikipedia search: {len(evidence)} results for '{query}'")
                return evidence
        
        except asyncio.TimeoutError:
            logger.warning(f"Wikipedia search timed out for '{query}'")
            return []
        except Exception as e:
            logger.warning(f"Wikipedia search failed for '{query}': {e}")
            return []
    
    async def fetch_news_evidence(self, query: str) -> List[Dict]:
        """Fetch news from credible sources using asyncio.to_thread()"""
        try:
            import time
            from ddgs import DDGS
            from urllib.parse import urlparse
            
            # Credible news domains for filtering
            CREDIBLE_DOMAINS = {
                "reuters.com", "bbc.com", "apnews.com", "bbc.co.uk",
                "theguardian.com", "nytimes.com", "washingtonpost.com",
                "ndtv.com", "thehindu.com", "hindustantimes.com"
            }
            
            def _is_credible_source(url: str) -> bool:
                """Check if URL is from a credible news domain"""
                try:
                    domain = urlparse(url).netloc.replace("www.", "")
                    return any(domain.endswith(d) for d in CREDIBLE_DOMAINS)
                except:
                    return False
            
            def _sync_ddgs_news(q, max_results):
                """Synchronous DDGS news search wrapper with exponential backoff"""
                for attempt in range(2):
                    try:
                        with DDGS() as ddgs:
                            results = list(ddgs.news(q, max_results=max_results))
                            return results
                    except Exception as e:
                        err_str = str(e)
                        if "Ratelimit" in err_str or "202" in err_str or "403" in err_str:
                            if attempt < 1:
                                time.sleep(2 ** attempt)  # 1s backoff
                                continue
                        logger.warning(f"DDGS news error: {e}")
                        return []
                return []
            
            # Use plain query without site: filter (causes rate limiting)
            news_query = query
            
            # Run sync function in thread pool
            results = await asyncio.wait_for(
                asyncio.to_thread(_sync_ddgs_news, news_query, 10),  # Fetch more, filter post-fetch
                timeout=5.0  # PERFORMANCE: Reduced from 8s to 5s
            )
            
            evidence = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                url = r.get('url') or ""
                # Filter to credible sources only
                if url and not _is_credible_source(url):
                    continue
                body = (r.get('body') or '').strip()
                if len(body) > 20:
                    evidence.append({
                        "source": r.get('source') or "News",
                        "url": url,
                        "title": r.get('title', 'News Article'),
                        "text": body,
                        "type": "news",
                        "date": r.get('date', '')
                    })
            
            logger.debug(f"News search: {len(evidence)} results for '{query}' (from credible sources)")
            return evidence
        
        except asyncio.TimeoutError:
            logger.warning(f"News search timed out for '{query}'")
            return []
        except Exception as e:
            logger.warning(f"News search failed for '{query}': {e}")
            return []
    
    async def fetch_all_evidence(self, queries: List[Dict]) -> List[Dict]:
        """
        Run all evidence fetchers in parallel for all queries.
        Properly handles exceptions and filters results.
        
        Returns:
            Combined list of all evidence from all sources
        """
        all_evidence = []
        
        # NORMAL FLOW: Create tasks for all queries and all sources
        tasks = []
        for q in queries:
            query_str = q.get("query", "")
            if query_str:
                # Claim-aware parallel retrieval across wiki/web/news.
                tasks.append(self.fetch_wiki_evidence(query_str))
                tasks.append(self.fetch_web_evidence(query_str))
                tasks.append(self.fetch_news_evidence(query_str))
        
        # Run all in parallel with GLOBAL TIMEOUT
        if tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=8.0  # REDUCED from 15s
                )
                
                for result in results:
                    if isinstance(result, Exception):
                        logger.debug(f"Evidence fetch exception: {result}")
                        continue
                    if isinstance(result, list):
                        all_evidence.extend(result)
            except asyncio.TimeoutError:
                logger.warning("Evidence gathering timed out after 8s - using partial results")
        
        logger.info(f"Total evidence gathered: {len(all_evidence)} snippets from {len(queries)} queries")
        return all_evidence
    
    # ========================================================================
    # STEP 3: Evidence Scoring and Fusion
    # ========================================================================
    
    def fuse_evidence(self, raw_results: List[Dict], claim: str) -> str:
        """
        Score, deduplicate, and fuse evidence into structured string.
        
        Returns:
            Formatted evidence string with source labels and scoring
        """
        import re
        from urllib.parse import urlparse
        
        # Credible news domains
        CREDIBLE_DOMAINS = {
            "reuters.com", "bbc.com", "apnews.com", "bbc.co.uk",
            "theguardian.com", "nytimes.com", "washingtonpost.com",
            "ndtv.com", "thehindu.com", "hindustantimes.com"
        }
        
        # Deduplicate by URL
        seen = {}
        for item in raw_results:
            url = item.get("url", "")
            if url and url not in seen:
                seen[url] = item
            elif not url:
                # Items without URL get included (web snippets sometimes lack URL)
                seen[id(item)] = item
        
        deduped = list(seen.values())
        
        # Score each piece of evidence
        claim_lower = claim.lower()
        claim_words = set(re.findall(r'\b\w{4,}\b', claim_lower))  # words 4+ chars
        
        scored = []
        
        for evidence in deduped:
            score = 0.0
            text_lower = evidence.get("text", "").lower()
            url = evidence.get("url", "")
            ev_type = evidence.get("type", "")
            title = evidence.get("title", "").lower()
            
            # Source credibility score
            domain = ""
            try:
                domain = urlparse(url).netloc.replace("www.", "") if url else ""
            except:
                pass
            
            if any(domain.endswith(d) for d in CREDIBLE_DOMAINS):
                score += 3
            elif ev_type == "wiki":
                score += 2
            else:
                score += 1
            
            # PAGE TYPE BONUS: Prioritize current/biographical pages over elections
            # For current-role claims, boost biography and role-specific pages
            if "chief minister" in title or "chief minister" in text_lower[:200]:
                score += 5  # Strong boost for role-specific pages
            elif "biography" in title or "biography" in text_lower[:100]:
                score += 3  # Boost biography pages
            elif "election" in title and "2024" not in claim_lower:
                score -= 2  # Downweight old elections if not specifically asked about them
            elif "election" in title and "2024" in claim_lower and "won" in claim_lower:
                score += 2  # Boost election pages if specifically asking about election wins
            
            # Keyword relevance score
            matched_words = sum(1 for w in claim_words if w in text_lower)
            score += min(matched_words, 4)  # cap at 4 to avoid over-weighting
            
            # Recency bonus (if date available)
            date = evidence.get("date", "")
            if date and any(year in date for year in ["2024", "2025", "2026"]):
                score += 1
            
            # INCUMBENT BONUS: Look for incumbent/current keywords
            if re.search(r'\b(incumbent|current|serving as|now|currently)\b', text_lower):
                score += 3  # Strong indicator of current position
            
            scored.append({
                **evidence,
                "score": score
            })
        
        # Sort by score descending
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Take top results
        top_results = scored[:self.top_results]
        
        # Format as structured string
        formatted_parts = []
        total_chars = 0
        
        for evidence in top_results:
            source = evidence.get("source", "Unknown")
            text = evidence.get("text", "")[:300]  # Truncate snippet
            
            part = f"[SOURCE: {source}]\n{text}\n"
            
            if total_chars + len(part) < self.max_evidence_chars:
                formatted_parts.append(part)
                total_chars += len(part)
            else:
                break
        
        result = "\n".join(formatted_parts)
        if not result:
            result = "No evidence available"
        
        logger.info(f"Evidence fusion: {len(formatted_parts)} sources, {len(result)} chars")
        return result
    
    # ========================================================================
    # STEP 4: LLM Reasoning with Reflection
    # ========================================================================
    
    async def reason(self, claim: str, evidence: str) -> Dict:
        """
        LLM reasoning with reflection loop for improving verdict confidence.
        
        Returns:
            {"verdict": "TRUE"|"FALSE", "confidence": 0-100, "reasoning": str, "key_evidence": str}
        """
        
        try:
            client = get_groq_client()
        except ValueError as e:
            logger.error(f"LLM client init failed: {e}")
            return {
                "verdict": "FALSE",
                "confidence": 0,
                "reasoning": "LLM service unavailable",
                "key_evidence": ""
            }
        
        # System message with strict constraints (unbiased)
        system_message = """You are a strict, unbiased fact-checking AI. Your ONLY job is to determine if a claim is TRUE or FALSE based on the evidence provided.

CRITICAL RULES:
1. You MUST respond with ONLY valid JSON — no other text, no markdown, no code blocks
2. verdict MUST be exactly "TRUE" or "FALSE" — no other values allowed
3. Evaluate ONLY what the evidence says — do not use your training knowledge alone
4. If the evidence SUPPORTS the claim → verdict is "TRUE"
5. If the evidence CONTRADICTS the claim → verdict is "FALSE"
6. If evidence is mixed but leans toward supporting → "TRUE" with lower confidence
7. If evidence is mixed but leans toward contradicting → "FALSE" with lower confidence
8. Do NOT default to FALSE just because evidence is incomplete
9. Do NOT be confused by historical context — focus on what the evidence states as current fact
10. Wikipedia "incumbent" means currently holding the position — treat this as strong evidence of TRUE

BIAS CHECK: Before finalizing, ask yourself:
- Does the evidence explicitly say the claim is wrong? → FALSE
- Does the evidence explicitly confirm the claim? → TRUE
- Is the claim a common known fact supported by evidence? → TRUE"""

        user_message = f"""Evaluate this claim strictly based on the evidence below.

CLAIM TO VERIFY:
"{claim}"

EVIDENCE FROM MULTIPLE SOURCES:
{evidence}

EVALUATION STEPS:
1. Identify what the claim is asserting (who, what role/fact, where)
2. Find evidence that directly addresses each assertion
3. Determine if the evidence supports or contradicts the claim
4. Assign verdict: TRUE if supported, FALSE if contradicted

IMPORTANT: The word "incumbent" in evidence means the person currently holds that position.
If evidence says "X is the incumbent Y of Z" and the claim says "X is Y of Z" → this is TRUE.

Respond with ONLY this JSON (no other text):
{{
    "verdict": "TRUE" or "FALSE",
    "confidence": <integer 50-100>,
    "reasoning": "<one clear sentence explaining why TRUE or FALSE>",
    "key_evidence": "<exact quote from evidence that determined the verdict>"
}}"""

        try:
            # First reasoning pass
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=512,
            )
            
            text = (response.choices[0].message.content or "").strip()
            parsed = _extract_json_object(text)
            
            if not parsed:
                logger.warning("Failed to parse LLM reasoning response")
                return {
                    "verdict": "FALSE",
                    "confidence": 0,
                    "reasoning": "Unable to parse result",
                    "key_evidence": ""
                }
            
            verdict = str(parsed.get("verdict", "FALSE")).upper().strip()
            confidence = parsed.get("confidence", 0)
            
            try:
                confidence = int(float(confidence))
            except (ValueError, TypeError):
                confidence = 0
            confidence = max(0, min(confidence, 100))
            
            reasoning = str(parsed.get("reasoning", ""))[:500]
            key_evidence = str(parsed.get("key_evidence", ""))[:300]
            
            # REFLECTION LOOP: Low confidence → reconsider (only if < 55 and seems inconsistent)
            if confidence < 55:
                logger.info(f"Low confidence ({confidence}%) - triggering reflection")
                
                reflection_system = """You are re-evaluating a fact-check. Be VERY decisive and clear.
Look for keywords: "incumbent", "current", "is", "serves as", "is the".
These indicate CURRENT status, not history. They support TRUE verdict.
Respond ONLY with valid JSON."""
                
                reflection_user = f"""Re-examine VERY carefully:

CLAIM: "{claim}"

EVIDENCE: {evidence}

PREVIOUS VERDICT: {verdict} ({confidence}%)

SPECIAL INSTRUCTIONS FOR RE-EVALUATION:
1. Search for keywords: "incumbent" (= currently holding), "current", "is", "serves as"
2. If person's NAME appears with the ROLE in evidence → usually TRUE
3. If evidence is about past elections but doesn't say they LOST → likely TRUE (they won)
4. Only say FALSE if evidence explicitly says someone ELSE holds the role or they LOST

Example: If evidence says "N. Chandrababu Naidu is Chief Minister" OR "Incumbent: N. Chandrababu Naidu" 
and claim is "N. Chandrababu Naidu is Chief Minister" → this is clearly TRUE.

Return ONLY JSON:
{{"verdict": "TRUE" or "FALSE", "confidence": <60-95>, "reasoning": "<clear reason>", "key_evidence": "<quote>"}}"""

                reflect_response = client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": reflection_system},
                        {"role": "user", "content": reflection_user},
                    ],
                    temperature=0.1,
                    max_tokens=512,
                )
                
                reflect_text = (reflect_response.choices[0].message.content or "").strip()
                reflect_parsed = _extract_json_object(reflect_text)
                
                if reflect_parsed:
                    reflect_verdict = str(reflect_parsed.get("verdict", "FALSE")).upper().strip()
                    reflect_conf = reflect_parsed.get("confidence", confidence)
                    try:
                        reflect_conf = int(float(reflect_conf))
                    except:
                        reflect_conf = confidence
                    reflect_conf = max(0, min(reflect_conf, 100))
                    
                    # Use reflection result if it has higher confidence
                    if reflect_conf > confidence and reflect_verdict in ("TRUE", "FALSE"):
                        verdict = reflect_verdict
                        confidence = reflect_conf
                        reasoning = str(reflect_parsed.get("reasoning", reasoning))[:500]
                        key_evidence = str(reflect_parsed.get("key_evidence", key_evidence))[:300]
                        logger.info(f"Reflection update: verdict={verdict}, confidence={confidence}%")
            
            # FINAL SAFETY: Enforce TRUE/FALSE constraint with fallback extraction
            if verdict not in {"TRUE", "FALSE"}:
                reasoning_upper = reasoning.upper()
                if "TRUE" in reasoning_upper and "FALSE" not in reasoning_upper:
                    verdict = "TRUE"
                else:
                    verdict = "FALSE"
                logger.warning(f"Invalid verdict converted to {verdict}")
            
            result = {
                "verdict": verdict,
                "confidence": confidence,
                "reasoning": reasoning,
                "key_evidence": key_evidence
            }
            
            logger.info(f"Reasoning result: {verdict} ({confidence}%)")
            return result
        
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return {
                "verdict": "FALSE",
                "confidence": 0,
                "reasoning": "Reasoning failed",
                "key_evidence": ""
            }
    
    # ========================================================================
    # STEP 5: Integration - Main Entry Point
    # ========================================================================
    
    async def run(self, claim: str, timeout: int = 20) -> Dict:  # REDUCED from 30s
        """
        Main async entry point: orchestrate all RAG steps with timeout protection.
        
        Returns:
            {
                "verdict": "TRUE"|"FALSE",
                "confidence": 0-100,
                "reasoning": str,
                "key_evidence": str,
                "sources": list[dict] with url, title, source, type
            }
        """
        
        logger.info(f"RAG pipeline started for claim: {claim[:100]}")
        
        try:
            # Run entire pipeline with timeout
            result = await asyncio.wait_for(
                self._run_rag_steps(claim),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.error(f"RAG pipeline timeout after {timeout}s")
            return {
                "verdict": "FALSE",
                "confidence": 0,
                "reasoning": f"Verification timed out after {timeout}s",
                "key_evidence": "",
                "sources": []
            }
        except Exception as e:
            logger.error(f"RAG pipeline error: {e}")
            return {
                "verdict": "FALSE",
                "confidence": 0,
                "reasoning": f"Verification failed: {str(e)[:100]}",
                "key_evidence": "",
                "sources": []
            }
    
    async def _run_rag_steps(self, claim: str) -> Dict:
        """
        Internal async helper that runs all RAG steps.
        """
        # Step 1: Plan claim-aware queries
        core_claim = extract_core_claim(claim)
        queries = self.plan_queries(core_claim)
        logger.info(f"Planned {len(queries)} sub-queries")
        
        # Step 2: Fetch evidence in parallel (already has 15s timeout)
        all_evidence = await self.fetch_all_evidence(queries)
        
        # Step 3: Build sources list before fusion (top 8 unique sources)
        seen_urls = set()
        unique_evidence = []
        subject_name = _extract_subject_name(core_claim)
        for e in all_evidence:
            url = e.get("url", "")
            if url and not self._is_trusted_domain(url):
                continue
            if not self._is_relevant(e, core_claim, subject_name):
                continue
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_evidence.append(e)
            elif not url:
                unique_evidence.append(e)
        
        # Score and get top results for sources
        scored = []
        claim_lower = claim.lower()
        for evidence in unique_evidence:
            score = 0.0
            source = evidence.get("source", "Unknown")
            text = evidence.get("text", "")
            ev_type = evidence.get("type", "")
            
            if any(s in source.lower() for s in ["reuters", "bbc", "ap news", "apnews", "guardian", "wikipedia"]):
                score += 2.0
            elif "news" in ev_type.lower():
                score += 1.5
            elif "wiki" in ev_type.lower():
                score += 2.0
            else:
                score += 1.0
            
            date = evidence.get("date", "")
            if date and any(year in date for year in ["2024", "2025", "2026"]):
                score += 1.0
            
            if any(kw in text.lower() for kw in claim_lower.split()[:3]):
                score += 1.0
            
            scored.append({"score": score, **evidence})
        
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)
        top_evidence = scored[:6]

        # Optional AI validation on top titles to eliminate random matches.
        validated = []
        for ev in top_evidence:
            title = ev.get("title", "")
            if await self._validate_source_title(core_claim, title):
                validated.append(ev)

        top_evidence = validated[:4] if validated else top_evidence[:4]
        
        # Build sources list with deduplication by URL
        seen_urls = set()
        sources_list = []
        for e in top_evidence:
            url = e.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                sources_list.append({
                    "url": url,
                    "link": url,
                    "title": e.get("title", ""),
                    "source": e.get("source", ""),
                    "type": e.get("type", "web"),
                    "snippet": e.get("text", "")[:150]  # First 150 chars of text
                })
        
        # Step 4: Fuse evidence into string
        fused_evidence = self.fuse_evidence(all_evidence, claim)
        
        # Step 5: LLM reasoning
        result = await self.reason(claim, fused_evidence)
        
        # Add sources to result
        result["sources"] = sources_list
        
        logger.info(f"RAG pipeline complete. Verdict: {result['verdict']} ({result['confidence']}%) with {len(sources_list)} sources")
        
        return result
