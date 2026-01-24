def build_explanation_tree(
    text_results=None,
    image_results=None,
    cross_modal=None,
    final_confidence=0.0,
    verdict="UNCERTAIN"
):
    print(">>> EXPLANATION_TREE_V2_ACTIVE")
    explanation = {
        "verdict": verdict,
        "confidence": round(final_confidence, 2),
        "reasoning": [],
        "sources": []
    }

    seen_source_urls = set()

    def add_unique_source(src):
        url = src.get("url", "")
        if url and url in seen_source_urls: return
        if url: seen_source_urls.add(url)
        explanation["sources"].append(src)

    if text_results:
        text_node = {
            "step": "Text Claim Verification",
            "details": []
        }

        for res in text_results:
            if not isinstance(res, dict): continue
            detail = {
                "claim": res.get("claim", "Unknown Claim"),
                "status": res.get("status", "ANALYZED"),
                "similarity_score": round(res.get("similarity_score", 0.0), 3),
                "explanation": res.get("explanation", "Evidence analyzed")
            }

            for src in res.get("sources", []):
                add_unique_source(src)

            text_node["details"].append(detail)

        explanation["reasoning"].append(text_node)

    if image_results and isinstance(image_results, dict):
        image_risk = image_results.get("image_risk_score", image_results.get("visual_risk_score", 0.0)) or 0.0
        status = "AUTHENTIC" if image_risk < 0.2 else "SUSPICIOUS" if image_risk < 0.6 else "MANIPULATED"
        
        audio_factors = image_results.get("risk_factors", [])
        
        # Add Vision/Media Analysis Source
        add_unique_source({
            "name": "TruthLens Vision Engine",
            "type": "Image Analysis",
            "description": "Neural networks used for OCR, aesthetic manipulation detection, and visual context extraction",
            "url": None
        })

        explanation["reasoning"].append({
            "step": "Visual & Audio Analysis",
            "status": status,
            "details": {
                "interpretation": image_results.get("interpretation", "Media analyzed for synthetic or manipulative patterns"),
                "visual_risk": round(image_risk, 2),
                "audio_risk": round(image_results.get("audio_risk_score", 0.0), 2),
                "audio_warnings": ", ".join(audio_factors) if audio_factors else "No significant audio artifacts",
                "extracted_text": image_results.get("ocr_text", image_results.get("video_caption", "")),
                "generated_caption": image_results.get("caption", image_results.get("video_caption", ""))
            }
        })

    if cross_modal:
        score = 0.0
        status = "INSUFFICIENT CROSS-MODAL EVIDENCE"
        if isinstance(cross_modal, dict):
            score = cross_modal.get("score", 0.0)
            status = cross_modal.get("status", status)
            
        # Add Multimodal Analysis Source
        add_unique_source({
            "name": "Cross-Modal Reasoning Engine",
            "type": "Multimodal Verification",
            "description": "Semantic alignment verification between extracted text claims and visual content",
            "url": None
        })

        explanation["reasoning"].append({
            "step": "Cross-Modal Consistency Check",
            "status": status,
            "details": {
                "score": round(score, 2),
                "explanation": (
                    "Text claims and visual content are aligned"
                    if status == "CONSISTENT"
                    else "Text claims mismatch visual context"
                    if status == "INCONSISTENT"
                    else "Insufficient data to determine cross-modal alignment"
                )
            }
        })

    explanation["reasoning"].append({
        "step": "Final Decision",
        "details": {
            "verdict": verdict,
            "confidence": round(final_confidence, 2),
            "summary": (
                "Verified as True. Core Reason: " + (text_results[0].get("explanation") if text_results and text_results[0].get("explanation") else "Matches established factual consensus.")
                if verdict == "LIKELY TRUE"
                else "Identified as Fake. Core Reason: " + (text_results[0].get("explanation") if text_results and text_results[0].get("explanation") else "Contradicts established facts or displays manipulation.")
                if verdict == "LIKELY FAKE"
                else "Misleading Content. Core Reason: " + (text_results[0].get("explanation") if text_results and text_results[0].get("explanation") else "Partial truth or significant cross-modal mismatch.")
                if verdict == "MISLEADING"
                else "Uncertain. Reason: Insufficient external evidence or ambiguous signals found."
            )
        }
    })

    return explanation
