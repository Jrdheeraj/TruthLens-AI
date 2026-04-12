"""
Advanced search query generator for production-quality RAG.
"""

import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in", "is", "it",
    "its", "of", "on", "or", "that", "the", "to", "was", "were", "will", "with", "this", "these", "those",
}

def _extract_subject_name(claim: str) -> str:
    """Extract the main subject (primary entity) from the claim."""
    if not claim:
        return ""
    
    text = claim.strip()
    
    # Pattern: Capitalized word(s) at the beginning (likely the subject)
    match = re.match(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
    if match:
        return match.group(1).strip()
    
    # Fallback: first word if capitalized
    words = text.split()
    if words and words[0] and words[0][0].isupper():
        return words[0]
    
    return ""


def extract_core_claim(claim: str) -> str:
    """Normalize and compress claim into a verification-ready core sentence."""
    if not claim:
        return ""

    text = re.sub(r"\s+", " ", claim).strip()
    text = re.sub(r"^[\"'`\s]+|[\"'`\s]+$", "", text)

    if not text:
        return ""

    # Keep first decisive sentence to avoid broad-topic drift.
    parts = re.split(r"(?<=[.!?])\s+", text)
    first = parts[0].strip() if parts else text
    return first[:220]

def _extract_keywords(claim: str) -> list[str]:
    """Extract important non-stopword keywords from claim."""
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9'-]{2,}\b", (claim or "").lower())
    seen = set()
    keywords = []

    for token in tokens:
        if token in STOPWORDS:
            continue
        if token in seen:
            continue
        seen.add(token)
        keywords.append(token)

    return keywords[:6]

def generate_search_query(claim: str) -> list[str]:
    """
    Generate 2-3 precise, claim-aware fact-check queries.
    """
    if not claim or not isinstance(claim, str):
        return []

    core_claim = extract_core_claim(claim)
    if not core_claim:
        return []

    subject = _extract_subject_name(core_claim)
    keywords = _extract_keywords(core_claim)

    queries = [
        f"{core_claim} fact check",
        f"{core_claim} true or false",
    ]

    if subject:
        queries.append(f"{subject} official statement or record")
    elif keywords:
        queries.append(" ".join(keywords[:4]) + " evidence")

    deduped = []
    seen = set()
    for q in queries:
        clean_q = re.sub(r"\s+", " ", q).strip()
        if not clean_q or clean_q.lower() in seen:
            continue
        seen.add(clean_q.lower())
        deduped.append(clean_q)

    return deduped[:3]

def apply_result_filter(subject_name: str, results: list[dict]) -> list[dict]:
    """Filter results by subject relevance."""
    if not subject_name or not results:
        return results
    
    subject_lower = subject_name.lower()
    filtered = []
    
    for result in results:
        if not isinstance(result, dict):
            continue
        
        text = (result.get('body') or result.get('text') or result.get('summary') or '').lower()
        if subject_lower in text:
            filtered.append(result)
    
    return filtered or results

