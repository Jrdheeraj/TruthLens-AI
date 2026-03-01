from app.utils.explanation_tree import build_explanation_tree

from app.core.config import HOAX_PATTERNS, REFUTATION_KEYWORDS, VISUAL_RISK_THRESHOLD

def detect_hoax_in_claim(claim: str) -> bool:
    claim_lower = claim.lower()
    for pattern in HOAX_PATTERNS:
        if pattern in claim_lower:
            print(f"VERDICT ENGINE DEBUG: Hoax pattern '{pattern}' detected in claim '{claim}'")
            return True
    return False

def final_verdict(text_results=None, image_results=None, cross_modal_score=None):
    print("=" * 80)
    print("VERDICT ENGINE DEBUG: Starting final verdict calculation")
    print(f"Text Results: {text_results}")
    print(f"Image Results: {image_results}")
    print("=" * 80)
    
    score = 0.0
    risk_factors = 0.0
    llm_verdict = None
    has_hoax_signals = False
    claims_with_hoax_patterns = []

    supported_count = 0
    partial_count = 0
    contradicted_count = 0
    hoax_count = 0

    if text_results:
        for r in text_results:
            status = r.get("status")
            explanation = r.get("explanation", "")
            claim = r.get("claim", "")
            
            print(f"VERDICT ENGINE DEBUG: Processing claim='{claim}', status='{status}'")
            
            if detect_hoax_in_claim(claim):
                has_hoax_signals = True
                claims_with_hoax_patterns.append(claim)
            
            hoax_indicators = ["hoax", "alien", "conspiracy", "secret summit", "illuminati", "leaked", "disproven", "fake"]
            if any(indicator in explanation.lower() for indicator in hoax_indicators):
                has_hoax_signals = True
                print(f"VERDICT ENGINE DEBUG: Hoax indicator found in explanation")
            
            if status == "HOAX":
                hoax_count += 1
                has_hoax_signals = True
                print(f"VERDICT ENGINE DEBUG: HOAX status detected")
            elif status == "CONTRADICTED":
                contradicted_count += 1
                has_hoax_signals = True
                print(f"VERDICT ENGINE DEBUG: CONTRADICTED status detected")
            elif status in ["SUPPORTED", "IMPLICITLY_SUPPORTED"]:
                supported_count += 1
            elif status == "PARTIALLY_SUPPORTED":
                partial_count += 1
            elif status == "NO_EVIDENCE":
                if detect_hoax_in_claim(claim):
                    print(f"VERDICT ENGINE DEBUG: NO_EVIDENCE + Hoax Pattern = LIKELY FAKE")
                    has_hoax_signals = True

        if hoax_count > 0 or contradicted_count > 0:
            llm_verdict = "LIKELY FAKE"
        elif partial_count > 0:
            llm_verdict = "MISLEADING"
        elif supported_count > 0:
            llm_verdict = "LIKELY TRUE"
                
    if image_results:
        visual_risk = image_results.get("image_risk_score", image_results.get("visual_risk_score", 0.0))
        audio_risk = image_results.get("audio_risk_score", 0.0)
        
        red_flags = image_results.get("red_flags", [])
        audio_factors = image_results.get("risk_factors", [])
        caption = image_results.get("caption", image_results.get("video_caption", ""))
        metadata_str = str(image_results.get("metadata", {})).lower()
        
        # 1. Restore Hoax Pattern Check for Captions/OCR
        if detect_hoax_in_claim(caption):
            has_hoax_signals = True
        
        if any(detect_hoax_in_claim(f) for f in audio_factors):
            has_hoax_signals = True
            
        # Detect manipulation in metadata
        toxic_metadata = ["manipulated", "synthetic", "ai-generated", "deepfake"]
        if any(word in metadata_str for word in toxic_metadata):
            risk_factors += 0.5
            has_hoax_signals = True
        
        print(f"VERDICT ENGINE DEBUG: Visual risk={visual_risk}, Audio risk={audio_risk}")
        
        # Aggregated risk
        total_media_risk = visual_risk + audio_risk
        if total_media_risk > 0:
            risk_factors += total_media_risk

        # High-Risk Override (Direct Deepfake Signal)
        if visual_risk > 0.5 or audio_risk > 0.5:
            print(f"VERDICT ENGINE DEBUG: High-risk manipulation signal detected (V:{visual_risk} A:{audio_risk})")
            has_hoax_signals = True
            
        for flag in red_flags:
            if any(word in flag.lower() for word in ["alien", "ufo", "suspicious", "hoax", "conspiracy"]):
                has_hoax_signals = True

    # 1.5.0: New Lightweight Cross-Modal Check
    cross_modal_signal = "INSUFFICIENT CROSS-MODAL EVIDENCE"
    if text_results and image_results:
        visual_desc = (image_results.get("caption", "") + " " + image_results.get("ocr_text", "")).lower()
        claims_text = " ".join([r.get("claim", "") for r in text_results]).lower()
        
        # Simple mismatch detector: high visual risk + positive text claim
        visual_risk = image_results.get("image_risk_score", image_results.get("visual_risk_score", 0.0))
        has_positive_claim = any(r.get("status") == "SUPPORTED" for r in text_results)
        
        if visual_risk > 0.6 and has_positive_claim:
             cross_modal_signal = "INCONSISTENT"
             print("VERDICT ENGINE DEBUG: Cross-Modal Inconsistency (Risk vs Claim)")
        elif cross_modal_score and cross_modal_score > 0.7:
             cross_modal_signal = "CONSISTENT"
        elif visual_risk < 0.2 and has_positive_claim:
             cross_modal_signal = "CONSISTENT"

        if cross_modal_signal == "INCONSISTENT":
            risk_factors += 0.4 # Boost risk for mismatch

    print(f"VERDICT ENGINE DEBUG: has_hoax_signals={has_hoax_signals}, risk_factors={risk_factors}, llm_verdict={llm_verdict}")
    
    if has_hoax_signals:
        verdict = "LIKELY FAKE"
        confidence = 0.95
        print(f"VERDICT ENGINE DEBUG: Final verdict=LIKELY FAKE (hoax/contradiction signals)")
    elif risk_factors >= 0.2: # Lowered threshold to catch subtle deepfakes
        verdict = "LIKELY FAKE"
        confidence = 0.85 + min(risk_factors * 0.1, 0.10)
        print(f"VERDICT ENGINE DEBUG: Final verdict=LIKELY FAKE (visual/audio risk factors)")
    elif llm_verdict:
        verdict = llm_verdict
        
        # New: Consensus-based confidence scaling and override
        source_count = 1
        if text_results:
            is_implicit = any(r.get("status") == "IMPLICITLY_SUPPORTED" for r in text_results)
            primary_sources = text_results[0].get("sources", [])
            if isinstance(primary_sources, list):
                source_count = max(1, len([s for s in primary_sources if isinstance(s, dict)]))
        
            # CORE FIX: Truth-Consensus Override
            if is_implicit or (verdict == "LIKELY TRUE" and source_count >= 1):
                print(f"VERDICT ENGINE DEBUG: Applying Truth-Consensus Override")
                verdict = "LIKELY TRUE"
                confidence = max(0.85 if source_count > 1 else 0.75, 0.70)
            else:
                confidence = 0.85 if verdict == "LIKELY TRUE" else 0.82
                if source_count > 1: confidence += 0.08
        else:
            confidence = 0.85 if verdict == "LIKELY TRUE" else 0.82

        print(f"VERDICT ENGINE DEBUG: Final verdict={verdict} (LLM, sources={source_count})")
        if verdict == "MISLEADING":
             confidence = 0.72
    else:
        # 1.6.4: Improved Fallback Guardrail
        if risk_factors > 0.05 or has_hoax_signals:
            verdict = "MISLEADING"
            confidence = 0.70
            print(f"VERDICT ENGINE DEBUG: Final verdict=MISLEADING (Risk > 0 or Hoax Pattern match)")
        else:
            verdict = "UNCERTAIN"
            confidence = 0.35
            print(f"VERDICT ENGINE DEBUG: Final verdict=UNCERTAIN (purely insufficient data)")

    print(f"VERDICT ENGINE DEBUG: Returning verdict={verdict}, confidence={confidence}")
    print("=" * 80)
    
    return build_explanation_tree(
        text_results=text_results,
        image_results=image_results,
        cross_modal={
            "score": cross_modal_score or 0.0,
            "status": cross_modal_signal
        },
        final_confidence=round(min(confidence, 0.99), 2),
        verdict=verdict
    )
