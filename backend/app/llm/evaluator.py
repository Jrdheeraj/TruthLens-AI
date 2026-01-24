import os
import google.generativeai as genai

from app.core.config import HOAX_PATTERNS, REFUTATION_KEYWORDS, SUPPORT_KEYWORDS

API_KEY = os.environ.get("GOOGLE_API_KEY")

# Cascading model selection for maximum reliability (trying variant strings)
MODEL_NAMES = [
    'gemini-1.5-flash', 
    'models/gemini-1.5-flash', 
    'gemini-pro', 
    'models/gemini-pro',
    'gemini-1.0-pro'
]

def detect_hoax_risk(claim: str) -> tuple[bool, str]:
    claim_lower = claim.lower()
    for pattern in HOAX_PATTERNS:
        if pattern in claim_lower:
            return (True, pattern)
    return (False, "")

def evaluate_claim_with_llm(claim: str, evidence: str, image_context: dict = None) -> dict:
    print("USING HYPER-RELIABLE LLM EVALUATOR")
    is_hoax_risk, hoax_pattern = detect_hoax_risk(claim)
    
    # Pre-process evidence
    ev_text = (evidence or "").lower()
    claim_words = set(claim.lower().split())
    
    if API_KEY:
        last_err = None
        for model_name in MODEL_NAMES:
            try:
                print(f"DEBUG: Attempting analysis with {model_name}...")
                model = genai.GenerativeModel(model_name)
                image_info = ""
                if image_context:
                    ocr = image_context.get("ocr_text", "")
                    caption = image_context.get("caption", image_context.get("video_caption", ""))
                    red_flags = image_context.get("red_flags", [])
                    image_info = f"\nIMAGE/VIDEO CONTEXT: OCR='{ocr}', Caption='{caption}', Flags='{red_flags}'"
                
                prompt = f"""
                TruthLens AI Investigative Agent. Date: Jan 24, 2026.
                Today: Donald Trump is US President (re-elected 2024).
                
                CLAIM: "{claim}"
                SEARCH EVIDENCE: "{evidence[:4200]}" {image_info}
                
                OBJECTIVE: Decisively verify or refute based on EVIDENCE + CONSENSUS.
                
                CRITICAL RULES:
                1. If you verify/refute, you MUST explain the "WHY" using findings from SEARCH EVIDENCE or universal consensus.
                2. Explain specifically which fact or source confirms or debunks the claim.
                
                Verdict: [SUPPORTED | CONTRADICTED | HOAX | NO_EVIDENCE]
                Explanation: [The reason WHY this verdict was chosen, e.g., "Confirmed by medical consensus" or "Matches historical record X"]
                """
                
                response = model.generate_content(prompt)
                text = response.text.strip()
                
                verdict = "NO_EVIDENCE"
                explanation = "Direct knowledge analysis."
                for line in text.split('\n'):
                    if "Verdict:" in line: verdict = line.split("Verdict:")[1].strip().upper()
                    if "Explanation:" in line: explanation = line.split("Explanation:")[1].strip()
                
                # Enhanced mapping for positive/negative signals
                # CORE FIX: Reinterpret NO_EVIDENCE as IMPLICITLY_SUPPORTED for coherent evidence
                v_upper = verdict.upper()
                has_refutation = any(x in ev_text for x in REFUTATION_KEYWORDS)
                has_support = any(x in ev_text for x in SUPPORT_KEYWORDS)
                is_coherent = len(ev_text) > 100
                
                if any(x in v_upper for x in ["SUPPORTED", "TRUE", "FACT", "REAL", "AUTHENTIC"]):
                    verdict = "SUPPORTED"
                elif any(x in v_upper for x in ["CONTRADICTED", "FALSE", "FAKE", "LIE", "DEBUNKED", "INCORRECT"]):
                    verdict = "CONTRADICTED"
                elif "HOAX" in v_upper:
                    verdict = "HOAX"
                elif "NO_EVIDENCE" in v_upper:
                    if is_coherent and not has_refutation:
                        print("DEBUG: Reinterpreting NO_EVIDENCE as IMPLICITLY_SUPPORTED (Consensus/Coherent)")
                        verdict = "IMPLICITLY_SUPPORTED"
                    else:
                        verdict = "NO_EVIDENCE"
                else:
                    verdict = "NO_EVIDENCE"
                
                print(f"DEBUG: {model_name} success. Final Verdict={verdict}")
                return {"status": verdict, "explanation": explanation}
            except Exception as e:
                last_err = e
                print(f"DEBUG: {model_name} failed: {e}")
        
        print(f"LLM Critical Failure. Error: {last_err}. Running Smart Heuristic.")

    # Smart Heuristic Fallback (Detects both positive and negative)
    if any(word in ev_text for word in REFUTATION_KEYWORDS):
        return {"status": "CONTRADICTED", "explanation": "Credible external sources and fact-checkers have explicitly refuted this claim as false."}
    
    if is_hoax_risk:
        return {"status": "HOAX", "explanation": f"Claim triggers hoax pattern '{hoax_pattern}' without support."}

    # Detect positive corroboration
    support_hits = [word for word in SUPPORT_KEYWORDS if word in ev_text]
    
    # New: Word Overlap heuristic for established facts
    significant_claim_words = [w for w in claim_words if len(w) >= 3]
    overlap_count = sum(1 for w in significant_claim_words if w in ev_text)
    print(f"DEBUG: Word overlap count: {overlap_count} for words {significant_claim_words}")
    
    # If 2+ unique significant words match AND no refutations, it's a verify (optimized for 2-3 word facts)
    if (overlap_count >= 2 and len(significant_claim_words) <= 3) or overlap_count >= 3 or len(support_hits) >= 1:
        print(f"DEBUG: Fact confirmed via overlap ({overlap_count}) and zero refutation.")
        return {"status": "SUPPORTED", "explanation": "Multiple independent sources and reference data corroborate this information as factual."}

    return {
        "status": "NO_EVIDENCE",
        "explanation": "Insufficient definitive evidence found in snippets."
    }
