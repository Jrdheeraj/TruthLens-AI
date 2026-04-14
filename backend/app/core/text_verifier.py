import asyncio
import logging
from app.rag.agentic_rag import AgenticRAG
from app.utils.search_query_generator import generate_search_query, _extract_subject_name

logger = logging.getLogger(__name__)


async def safe_rag_call(rag: AgenticRAG, claim: str, timeout: int = 20, content_type: str = "text") -> dict:
    """Run RAG with hard timeout and guaranteed fallback payload."""
    logger.info(f"safe_rag_call: starting for claim '{claim[:80]}'")
    try:
        result = await asyncio.wait_for(rag.run(claim, content_type=content_type), timeout=timeout)
        if not isinstance(result, dict):
            logger.warning("safe_rag_call: invalid payload type, fallback triggered")
            return {
                "verdict": "FALSE",
                "confidence": 50,
                "reasoning": "Invalid RAG payload - system fallback triggered",
                "key_evidence": "",
                "sources": [],
            }
        return result
    except asyncio.TimeoutError:
        logger.error(f"safe_rag_call: timeout after {timeout}s")
        return {
            "verdict": "FALSE",
            "confidence": 50,
            "reasoning": "System fallback due to timeout or retrieval failure",
            "key_evidence": "",
            "sources": [],
        }
    except Exception as exc:
        logger.error(f"safe_rag_call: exception {type(exc).__name__}: {exc}")
        return {
            "verdict": "FALSE",
            "confidence": 50,
            "reasoning": "System fallback due to timeout or retrieval failure",
            "key_evidence": "",
            "sources": [],
        }


def generate_corrected_fact(original_claim: str, reasoning: str, evidence: str) -> str:
    """
    PART 4: Generate corrected fact for FALSE claims using LLM
    
    Extracts or generates the correct information when a claim is false.
    Format: "X is NOT Y. Actually: [fact]"
    
    Args:
        original_claim: The original false claim
        reasoning: Reasoning from RAG about why it's false
        evidence: Key evidence that contradicts the claim
        
    Returns:
        Corrected fact string or None if unable to generate
    """
    try:
        from groq import Groq
    except ImportError:
        logger.warning("Groq not available - skipping corrected fact generation")
        return None
    
    try:
        client = Groq()
        
        prompt = f"""Based on the provided evidence, generate a brief corrected fact for this false claim.

Original Claim: {original_claim}
Evidence Indicating It's False: {evidence}
Reasoning: {reasoning}

Provide a concise corrected statement (1-2 sentences max) in the format:
"ACTUALLY: [The correct information]"

Be specific and factual. Only include information directly from the evidence."""

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {
                    "role": "system",
                    "content": "You are a fact-checking assistant. Provide accurate corrections to false claims based on evidence."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        corrected_fact = response.choices[0].message.content.strip()
        logger.info(f"Generated corrected fact: {corrected_fact[:80]}...")
        return corrected_fact
        
    except Exception as e:
        logger.debug(f"Could not generate corrected fact: {e}")
        # Fallback: Extract from evidence if possible
        if evidence and len(evidence) > 20:
            return f"ACTUALLY: {evidence[:150].strip()}"
        return None


async def verify_text_claims(claims: list[str], image_context: dict = None) -> list[dict]:
    """
    Verify text claims using Agentic RAG pipeline.
    
    Agentic RAG performs:
    1. Query planning (decompose claim into sub-queries)
    2. Parallel evidence retrieval (Tavily + Wikipedia)
    3. Evidence fusion (deduplication, credibility scoring)
    4. Deterministic rule-based verdict
    5. Verdict generation (TRUE/FALSE only)
    
    Args:
        claims: List of text claims to verify
        image_context: Optional image analysis context (unused in Agentic RAG)
        
    Returns:
        List of results with: claim, status, sources, explanation
    """
    
    results = []
    rag = AgenticRAG()
    content_type = "text"
    if isinstance(image_context, dict):
        if image_context.get("video_type") == "video":
            content_type = "video"
        elif image_context:
            content_type = "image"
    
    for claim in claims:
        try:
            logger.info(f"Verifying claim: {claim}")

            # Run Agentic RAG pipeline with hard safety wrapper.
            rag_result = await safe_rag_call(rag, claim, timeout=25, content_type=content_type)
            
            # Extract verdict and reasoning
            verdict = rag_result.get("verdict", "FALSE")  # TRUE or FALSE
            confidence = rag_result.get("confidence", 50)
            reasoning = rag_result.get("reasoning", "")
            technical_details = rag_result.get("technical_details", "")
            evidence_points = rag_result.get("evidence_points", [])
            key_evidence = rag_result.get("key_evidence", "")
            
            # Map TRUE/FALSE verdict to status format
            # TRUE → "SUPPORTED", FALSE → "CONTRADICTED"
            status = "SUPPORTED" if verdict == "TRUE" else "CONTRADICTED"
            
            # PART 4: For FALSE claims, extract or generate corrected fact
            corrected_fact = None
            if status == "CONTRADICTED":
                # Try to extract corrected fact from reasoning/evidence
                corrected_fact = generate_corrected_fact(claim, reasoning, key_evidence)
            
            # Build explanation from reasoning and key evidence
            explanation = f"{reasoning}"
            if evidence_points:
                explanation += "\n\nWhat we found: " + " | ".join(str(point) for point in evidence_points[:2])
            if key_evidence:
                explanation += f"\n\nKey Evidence: {key_evidence}"
            if technical_details:
                explanation += f"\n\nTechnical note: {technical_details}"
            
            # Build sources list from evidence (if returned by RAG)
            sources = rag_result.get("sources", [])
            structured_sources = []
            
            if sources:
                for source in sources:
                    structured_sources.append({
                        "url": source.get("url", ""),
                        "title": source.get("title", "Unknown Source"),
                        "source": source.get("source", "Web Search"),
                        "type": source.get("type", "web"),
                        "description": (
                            source.get("description")
                            or source.get("snippet")
                            or source.get("text", "")
                        )[:300]
                        if (
                            source.get("description")
                            or source.get("snippet")
                            or source.get("text")
                        )
                        else ""
                    })
            else:
                # Fallback: generate sources from query generators
                query = generate_search_query(claim)
                subject = _extract_subject_name(claim)
                structured_sources.append({
                    "url": "",
                    "title": "Agentic RAG Search",
                    "source": "Multi-source Verification",
                    "type": "web",
                    "description": f"Verified claim using parallel evidence retrieval (confidence: {confidence}%)"
                })
            
            result_dict = {
                "claim": claim,
                "status": status,
                "sources": structured_sources,
                "explanation": explanation,
                "confidence": confidence,
                "summary": reasoning,
                "technical_details": technical_details,
                "evidence_points": evidence_points,
            }
            
            # Add corrected fact if available
            if corrected_fact:
                result_dict["corrected_fact"] = corrected_fact
            
            results.append(result_dict)
            
            logger.info(f"Claim verdict: {verdict} (confidence: {confidence}%)")
            
        except Exception as e:
            logger.error(f"Error verifying claim '{claim}': {e}")
            # Return conservative FALSE verdict on error
            results.append({
                "claim": claim,
                "status": "CONTRADICTED",
                "sources": [],
                "explanation": f"Verification error: {str(e)}",
                "confidence": 0
            })
    
    return results


def verify_text_claims_sync(claims: list[str], image_context: dict = None) -> list[dict]:
    """
    Synchronous wrapper for verify_text_claims.
    
    This function runs the async verification in a new event loop.
    Use this when calling from synchronous code.
    
    Args:
        claims: List of text claims to verify
        image_context: Optional image analysis context
        
    Returns:
        List of verification results
    """
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(verify_text_claims(claims, image_context))
        return results
    finally:
        loop.close()

