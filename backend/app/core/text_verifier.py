from app.live.live_search import fetch_live_evidence, fetch_wikipedia_evidence
from app.llm.evaluator import evaluate_claim_with_llm

def verify_text_claims(claims: list[str], image_context: dict = None) -> list[dict]:
    results = []
    
    for claim in claims:
        live_evidence = fetch_live_evidence(claim)
        wiki_evidence = fetch_wikipedia_evidence(claim)
        
        evidence_text = ""
        sources = []
        
        if live_evidence:
            evidence_text += f"Live Search Result: {live_evidence['text']}\n"
            sources.append("DuckDuckGo")
            print(f"Live Search executed for claim: {claim}")
            
        if wiki_evidence:
            evidence_text += f"Wikipedia Result: {wiki_evidence['text']}\n"
            sources.append("Wikipedia")
        
        llm_result = evaluate_claim_with_llm(claim, evidence_text, image_context)
        
        structured_sources = []
        if live_evidence:
            src_name = live_evidence.get("page", "DuckDuckGo")
            # Extract a relevant snippet for the description (exact resource description)
            snippet = live_evidence.get("text", "")[:300].strip()
            if len(snippet) > 297: snippet = snippet[:297] + "..."
            
            structured_sources.append({
                "name": src_name,
                "type": "RAG: Live Web Audit",
                "description": snippet or f"Audited via {src_name}. Provided real-time context used to evaluate the claim.",
                "url": live_evidence.get("url")
            })
        if wiki_evidence:
            wiki_page = wiki_evidence.get("page", "Wikipedia")
            # Extract a relevant snippet for the description
            snippet = wiki_evidence.get("text", "")[:300].strip()
            if len(snippet) > 297: snippet = snippet[:297] + "..."

            structured_sources.append({
                "name": f"Wikipedia: {wiki_page}",
                "type": "RAG: Consensus Audit",
                "description": snippet or f"Verified against the Wikipedia entry for '{wiki_page}'. Used for established factual and historical consensus.",
                "url": wiki_evidence.get("url")
            })
            
        results.append({
            "claim": claim,
            "status": llm_result["status"],
            "sources": structured_sources,
            "explanation": llm_result["explanation"]
        })

    return results
