import re

def extract_claims(text: str) -> list[str]:
    sentences = re.split(r"[.!?]", text)
    return [s.strip() for s in sentences if len(s.strip()) > 5]
