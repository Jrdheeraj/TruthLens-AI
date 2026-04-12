import re
import logging
import html

logger = logging.getLogger(__name__)

MAX_CLAIM_LENGTH = 1000
MAX_TOTAL_LENGTH = 100000
MAX_CLAIMS = 20

def extract_claims(text: str) -> list[str]:
    """
    Extract claims from text with input validation and sanitization.
    
    FIX 5: Input validation, HTML unescaping, character filtering, and length limits.
    
    Args:
        text: User-provided text to extract claims from
        
    Returns:
        List of sanitized claims (at most 20)
        
    Raises:
        ValueError: If input is invalid
    """
    
    # 1. Type validation
    if not isinstance(text, str):
        raise ValueError("Input must be a string")
    
    # 2. Length validation
    if len(text) == 0:
        return []
    
    if len(text) > MAX_TOTAL_LENGTH:
        logger.warning(f"Input truncated from {len(text)} to {MAX_TOTAL_LENGTH}")
        text = text[:MAX_TOTAL_LENGTH]
    
    # 3. Remove control characters and normalize
    text = ''.join(
        ch if ch.isprintable() or ch.isspace() else ''
        for ch in text
    )
    
    # 4. Remove HTML entities
    text = html.unescape(text)
    
    # 5. Split into sentences - better regex handling abbreviations
    sentences = re.split(
        r'(?<=[.!?])\s+(?=[A-Z])',  # Split after punctuation, before capital letter
        text,
        maxsplit=MAX_CLAIMS
    )
    
    # 6. Clean and filter claims
    claims = []
    for sentence in sentences:
        # Remove extra whitespace
        cleaned = ' '.join(sentence.strip().split())
        
        # Check minimum length
        if len(cleaned) < 10:
            continue
        
        # Truncate at word boundary if too long
        if len(cleaned) > MAX_CLAIM_LENGTH:
            # Find last space before limit
            truncated = cleaned[:MAX_CLAIM_LENGTH]
            last_space = truncated.rfind(' ')
            if last_space > 50:  # Ensure we keep at least 50 characters
                cleaned = truncated[:last_space]
            else:
                cleaned = truncated
        
        # Ensure no dangerous control characters
        if '\x00' in cleaned or '\r' in cleaned:
            logger.debug(f"Skipping claim with control characters")
            continue
        
        claims.append(cleaned)
    
    if not claims:
        logger.debug("No valid claims extracted from input")
    
    return claims[:MAX_CLAIMS]
