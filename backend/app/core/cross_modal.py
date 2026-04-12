import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor, CLIPModel, CLIPProcessor
import logging
import json
import re
from typing import Dict, List, Optional
import warnings

# Suppress ALL warnings from external libraries (huggingface, etc)
warnings.filterwarnings('ignore')
warnings.simplefilter('ignore', FutureWarning)
warnings.simplefilter('ignore', UserWarning)

logger = logging.getLogger(__name__)

device = torch.device("cpu")

_blip_processor = None
_blip_model = None
_clip_processor = None
_clip_model = None
_blip_load_failed = False
_clip_load_failed = False


def _load_blip():
    global _blip_processor, _blip_model, _blip_load_failed
    if _blip_load_failed:
        return False
    if _blip_processor is not None and _blip_model is not None:
        return True
    try:
        _blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        _blip_model.to(device).eval()
        return True
    except Exception as e:
        _blip_load_failed = True
        logger.warning(f"BLIP load failed: {e}")
        return False


def _load_clip():
    global _clip_processor, _clip_model, _clip_load_failed
    if _clip_load_failed:
        return False
    if _clip_processor is not None and _clip_model is not None:
        return True
    try:
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        _clip_model.to(device).eval()
        return True
    except Exception as e:
        _clip_load_failed = True
        logger.warning(f"CLIP load failed: {e}")
        return False


def generate_caption(image: Image.Image) -> str:
    """Generate image caption using BLIP (PRESERVED FROM ORIGINAL)"""
    if image.mode != "RGB":
        image = image.convert("RGB")

    if not _load_blip():
        return "A natural photograph"

    inputs = _blip_processor(image, return_tensors="pt")
    with torch.no_grad():
        output = _blip_model.generate(**inputs, max_new_tokens=30)

    caption = _blip_processor.decode(output[0], skip_special_tokens=True).strip()
    logger.info(f"CROSS_MODAL: Generated caption: {caption}")
    return caption or "A natural photograph"


def clip_similarity(image: Image.Image, text: str) -> float:
    """Calculate CLIP similarity (PRESERVED FROM ORIGINAL)"""
    if not text:
        return 0.0

    if image.mode != "RGB":
        image = image.convert("RGB")

    if not _load_clip():
        return 0.5  # Neutral fallback

    image_inputs = _clip_processor(images=image, return_tensors="pt")
    text_inputs = _clip_processor(text=[text], return_tensors="pt", padding=True)

    with torch.no_grad():
        image_features = _clip_model.get_image_features(**image_inputs)
        text_features = _clip_model.get_text_features(**text_inputs)

    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    cosine_score = torch.matmul(image_features, text_features.T)[0][0].item()
    normalized_score = (cosine_score + 1.0) / 2.0
    result = round(max(0.0, min(normalized_score, 1.0)), 3)
    logger.info(f"CROSS_MODAL: CLIP similarity score: {result}")
    return result


# ============================================================================
# NEW: HYBRID LLM REASONING LAYER
# ============================================================================

def initialize_groq_client():
    """Initialize Groq client for LLM-based reasoning"""
    try:
        from groq import Groq
        return Groq()
    except Exception as e:
        logger.warning(f"Failed to initialize Groq client: {e}")
        return None


def llm_contradiction_detector(text: str, caption: str, llm_client=None) -> dict:
    """
    NEW: Use Groq LLM to detect semantic contradictions between text and image caption
    
    Args:
        text: Claimed text/caption from user
        caption: Generated caption from BLIP vision model
        llm_client: Optional pre-initialized Groq client
    
    Returns:
        {
            "contradiction_score": 0.0-1.0,
            "contradiction_type": str (exaggeration|mismatch|context-mispresentation|accurate),
            "confidence": 0.0-1.0,
            "reasoning": str,
            "flags": [list of issues]
        }
    """
    
    contradiction_flags = []
    
    if not text or not caption:
        return {
            "contradiction_score": 0.0,
            "contradiction_type": "insufficient_data",
            "confidence": 0.0,
            "reasoning": "Missing text or caption for analysis",
            "flags": []
        }
    
    try:
        if llm_client is None:
            llm_client = initialize_groq_client()
        
        if llm_client is None:
            # Fallback: simple heuristic analysis
            return _heuristic_contradiction_check(text, caption)
        
        prompt = f"""Analyze the relationship between the claimed text and the image caption. 
Is the text consistent with what the image appears to show?

CLAIMED TEXT: {text[:300]}
IMAGE CAPTION: {caption[:200]}

Provide a JSON response analyzing:
1. "contradiction_type": ONE OF: exaggeration|mismatch|accurate|context-misleading
2. "confidence": 0.0-1.0 (certainty of assessment)
3. "reasoning": Brief explanation (1-2 sentences max)
4. "issues": Array of specific problems found (max 3)

RESPOND ONLY WITH VALID JSON (no markdown, no code blocks):
{{
    "contradiction_type": "...",
    "confidence": 0.0,
    "reasoning": "...",
    "issues": []
}}"""
        
        try:
            response = llm_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a content analyst. Analyze if text matches image content. Respond ONLY with valid JSON."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                timeout=10  # PERFORMANCE: 10-second timeout
            )
        except Exception as timeout_err:
            logger.warning(f"LLM call timeout or error: {timeout_err}, using fallback")
            return _heuristic_contradiction_check(text, caption)
        
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in response_text:
            json_match = re.search(r'```json\n?(.*?)\n?```', response_text, re.DOTALL)
        elif "```" in response_text:
            json_match = re.search(r'```\n?(.*?)\n?```', response_text, re.DOTALL)
        else:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
        
        if json_match:
            try:
                llm_result = json.loads(json_match.group(1) if "```" in response_text else json_match.group())
            except json.JSONDecodeError:
                llm_result = {}
        else:
            llm_result = {}
        
        contradiction_type = llm_result.get("contradiction_type", "unknown")
        confidence = float(llm_result.get("confidence", 0.3))
        reasoning = llm_result.get("reasoning", "Unable to determine")
        issues = llm_result.get("issues", [])
        
        # Map contradiction type to risk score
        if contradiction_type == "exaggeration":
            contradiction_score = 0.55  # Moderate risk
            contradiction_flags.extend(["Text exaggerates image content"] + issues)
        elif contradiction_type == "mismatch":
            contradiction_score = 0.80  # High risk
            contradiction_flags.extend(["Text-image mismatch detected"] + issues)
        elif contradiction_type == "context-misleading":
            contradiction_score = 0.70  # High-moderate risk
            contradiction_flags.extend(["Context misrepresentation"] + issues)
        elif contradiction_type == "accurate":
            contradiction_score = 0.0  # No risk
        else:
            contradiction_score = 0.2
        
        logger.info(f"CROSS_MODAL: LLM contradiction analysis - type={contradiction_type}, score={contradiction_score}")
        
        return {
            "contradiction_score": round(min(1.0, max(0.0, contradiction_score)), 3),
            "contradiction_type": contradiction_type,
            "confidence": round(max(0.0, min(confidence, 1.0)), 3),
            "reasoning": reasoning,
            "flags": contradiction_flags
        }
    
    except Exception as e:
        logger.debug(f"LLM contradiction detection error: {e}, falling back to heuristics")
        return _heuristic_contradiction_check(text, caption)


def _heuristic_contradiction_check(text: str, caption: str) -> dict:
    """
    Fallback: Simple heuristic contradiction detection when LLM is unavailable
    """
    flags = []
    score = 0.0
    
    text_lower = text.lower()
    caption_lower = caption.lower()
    
    # Check for negation mismatch
    negation_words = ["not", "no", "never", "false", "fake", "hoax"]
    has_negative_text = any(word in text_lower for word in negation_words)
    has_negative_caption = any(word in caption_lower for word in negation_words)
    
    if has_negative_text != has_negative_caption:
        flags.append("Negation mismatch between text and caption")
        score += 0.3
    
    # Check for common exaggeration words
    exaggeration_words = ["most", "largest", "biggest", "only", "never", "always", "definitely"]
    has_exaggeration = sum(1 for word in exaggeration_words if word in text_lower.split())
    if has_exaggeration > 2:
        flags.append("Text contains exaggerated language")
        score += 0.2
    
    # Check word overlap
    text_words = set(text_lower.split())
    caption_words = set(caption_lower.split())
    overlap = len(text_words & caption_words)
    
    if overlap < 2 and len(text_words) > 5:
        flags.append("Low vocabulary overlap between text and caption")
        score += 0.25
    
    score = min(1.0, score)
    
    return {
        "contradiction_score": round(score, 3),
        "contradiction_type": "heuristic",
        "confidence": 0.3,
        "reasoning": "Fallback heuristic analysis (LLM unavailable)",
        "flags": flags
    }


def semantic_alignment_analyzer(text: str, caption: str) -> dict:
    """
    NEW: Advanced semantic alignment checking
    - Key entity extraction and matching
    - Negation consistency
    - Confidence scoring
    
    Returns:
        {
            "entity_alignment": 0.0-1.0,
            "alignment_score": 0.0-1.0,
            "mismatches": [list]
        }
    """
    
    mismatches = []
    
    try:
        # Clean and tokenize
        text_lower = text.lower()
        caption_lower = caption.lower()
        
        text_words = set(text_lower.split())
        caption_words = set(caption_lower.split())
        
        # Remove common stop words
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of",
            "is", "are", "was", "were", "be", "by", "with", "from", "as", "that", "this"
        }
        text_words = text_words - stop_words
        caption_words = caption_words - stop_words
        
        # Calculate entity overlap
        if text_words and caption_words:
            overlap = len(text_words & caption_words)
            total = len(text_words | caption_words)
            entity_alignment = overlap / total if total > 0 else 0.3
        else:
            entity_alignment = 0.5
        
        # Check for negation consistency
        negations = ["not", "no", "never", "false", "fake"]
        has_negative_text = any(word in text_lower for word in negations)
        has_negative_caption = any(word in caption_lower for word in negations)
        
        if has_negative_text != has_negative_caption:
            mismatches.append("Negation mismatch between text and caption")
            entity_alignment *= 0.6  # Penalize
        
        # Final alignment score
        alignment_score = entity_alignment
        
        logger.info(f"CROSS_MODAL: Semantic alignment - entity_overlap={entity_alignment:.2f}")
        
        return {
            "entity_alignment": round(max(0.0, min(entity_alignment, 1.0)), 3),
            "alignment_score": round(max(0.0, min(alignment_score, 1.0)), 3),
            "mismatches": mismatches
        }
    
    except Exception as e:
        logger.debug(f"Semantic alignment analysis failed: {e}")
        return {
            "entity_alignment": 0.5,
            "alignment_score": 0.5,
            "mismatches": []
        }


# ============================================================================
# UPDATED: MAIN MULTIMODAL VERIFICATION
# ============================================================================

def analyze_multimodal(text: str, image: Image.Image, llm_client: Optional[object] = None, 
                       deepfake_probability: float = 0.0, image_deepfake_type: str = "UNKNOWN") -> Dict:
    """
    UPDATED: Comprehensive multimodal analysis with deepfake detection integration
    
    Analysis layers:
    1. Caption generation (BLIP) - neural vision model
    2. CLIP-based similarity (feature vectors) - embedding similarity
    3. Deepfake detection (image authenticity) - NEW
    4. LLM-based contradiction detection (semantic reasoning)
    5. Semantic alignment analysis (entity overlap)
    6. Deepfake-aware confidence adjustment and final risk scoring
    
    Args:
        text: Claim text to verify
        image: Image to analyze
        llm_client: Optional LLM client for enhanced reasoning
        deepfake_probability: Probability of AI-generated image (0.0-1.0) from image_analyzer
        image_deepfake_type: Classification (GAN|DIFFUSION|FACE_SWAP|AUTHENTIC|UNKNOWN)
    
    Output layers:
    - CLIP features (35% weight) - statistical similarity
    - Deepfake analysis (30% weight) - AI-generated detection - NEW
    - LLM reasoning (25% weight) - semantic contradiction
    - Alignment metrics (10% weight) - entity overlap
    """
    
    logger.info("CROSS_MODAL: Starting multimodal verification with deepfake analysis")
    
    try:
        # Layer 1: Generate caption from image
        caption = generate_caption(image)
        
        # Layer 2: CLIP similarity (existing feature-based approach)
        clip_sim = clip_similarity(image, text)
        
        # Layer 3: Deepfake detection integration (NEW)
        is_likely_ai_generated = deepfake_probability > 0.6
        is_misleading_ai_content = False
        deepfake_flags = []
        
        if is_likely_ai_generated:
            deepfake_flags.append(f"Image likely AI-generated ({image_deepfake_type})")
            
            # Check if text claims real/authentic while image is AI-generated
            text_claims_authentic = any(phrase in text.lower() for phrase in [
                "real", "authentic", "genuine", "verified", "evidence", "proof",
                "captured", "actual", "filmed", "unedited"
            ])
            
            text_is_sensational = any(phrase in text.lower() for phrase in [
                "shocking", "exclusive", "breaking", "leaked", "never before",
                "revealed", "exposé", "documentary evidence"
            ])
            
            if text_claims_authentic or text_is_sensational:
                is_misleading_ai_content = True
                deepfake_flags.append("Potential misleading content: AI-generated image with authenticity claims")
        
        # Layer 4: LLM-based contradiction detection
        contradiction_analysis = llm_contradiction_detector(text, caption, llm_client)
        
        # Layer 5: Semantic alignment
        alignment_analysis = semantic_alignment_analyzer(text, caption)
        
        # Layer 6: Deepfake-aware confidence adjustment
        # Base score: inverse of clip_similarity (high similarity = low risk)
        base_risk = 1.0 - clip_sim
        
        # Deepfake adjustment (NEW)
        deepfake_risk = deepfake_probability  # 0.0-1.0
        
        # Contradiction adjustment
        contradiction_score = contradiction_analysis.get("contradiction_score", 0.0)
        contradiction_type = contradiction_analysis.get("contradiction_type", "unknown")
        
        if contradiction_type == "exaggeration":
            contradiction_adjustment = contradiction_score * 0.7
        elif contradiction_type == "mismatch":
            contradiction_adjustment = contradiction_score
        else:
            contradiction_adjustment = contradiction_score * 0.5
        
        # Alignment adjustment
        alignment_confidence = alignment_analysis.get("alignment_score", 0.5)
        alignment_risk = 1.0 - alignment_confidence
        
        # FINAL RISK CALCULATION (NEW WEIGHTS with deepfake)
        # Deepfake detection is now heavily weighted (30%) as it's most reliable
        multimodal_risk = min(1.0, (
            base_risk * 0.35 +                    # CLIP similarity (35%)
            deepfake_risk * 0.30 +                # Deepfake detection (30%) - NEW
            contradiction_adjustment * 0.25 +     # LLM reasoning (25%, reduced)
            alignment_risk * 0.10                 # Alignment mismatch (10%, reduced)
        ))
        
        # CONFIDENCE ADJUSTMENT FOR HIGH DEEPFAKE PROBABILITY (NEW)
        # If image is likely AI-generated, reduce confidence by 40-70% depending on agreement
        deepfake_confidence_penalty = 0.0
        if is_likely_ai_generated:
            # Higher penalty if other signals agree
            agreement_score = sum([
                contradiction_score > 0.5,
                alignment_risk > 0.5,
                clip_sim < 0.5
            ])
            deepfake_confidence_penalty = 0.40 + (agreement_score * 0.10)  # 40-70% penalty
        
        # Confidence scoring
        llm_confidence = contradiction_analysis.get("confidence", 0.5)
        alignment_conf = alignment_analysis.get("entity_alignment", 0.5)
        
        base_confidence = min(1.0, (llm_confidence * 0.4 + alignment_conf * 0.3 + clip_sim * 0.3))
        final_confidence = base_confidence * (1.0 - deepfake_confidence_penalty)
        
        # Collect all diagnostic flags
        all_flags = (
            deepfake_flags +
            contradiction_analysis.get("flags", []) +
            alignment_analysis.get("mismatches", [])
        )
        
        # NEW: Deepfake impact warning
        if is_misleading_ai_content:
            all_flags.insert(0, "⚠️  CRITICAL: AI-generated image presented as authentic news")
        
        logger.info(f"CROSS_MODAL: Risk={multimodal_risk:.2f}, confidence={final_confidence:.2f}, deepfake={deepfake_probability:.2f}")
        
        return {
            "caption": caption,
            "clip_similarity": clip_sim,
            "multimodal_risk_score": round(multimodal_risk, 3),
            "final_confidence": round(final_confidence, 3),
            "deepfake_analysis": {
                "probability": deepfake_probability,
                "type": image_deepfake_type,
                "is_likely_ai_generated": is_likely_ai_generated,
                "is_misleading_content": is_misleading_ai_content,
                "confidence_penalty": round(deepfake_confidence_penalty, 3)
            },
            "contradiction_analysis": {
                "score": contradiction_analysis.get("contradiction_score", 0.0),
                "type": contradiction_analysis.get("contradiction_type", "unknown"),
                "confidence": llm_confidence,
                "reasoning": contradiction_analysis.get("reasoning", "")
            },
            "alignment_analysis": {
                "entity_alignment": alignment_analysis.get("entity_alignment", 0.5),
                "alignment_score": alignment_analysis.get("alignment_score", 0.5)
            },
            "multimodal_flags": all_flags,
            "scoring_breakdown": {
                "clip_contribution": round(base_risk * 0.35, 3),
                "deepfake_contribution": round(deepfake_risk * 0.30, 3),
                "llm_contribution": round(contradiction_adjustment * 0.25, 3),
                "alignment_contribution": round(alignment_risk * 0.10, 3)
            },
            "verification_note": "Hybrid CLIP (35%) + Deepfake (30%) + LLM (25%) + Alignment (10%)"
        }
    
    except Exception as e:
        logger.error(f"CROSS_MODAL: Multimodal analysis failed: {e}")
        return {
            "caption": "Error generating caption",
            "clip_similarity": 0.5,
            "multimodal_risk_score": 0.5,
            "final_confidence": 0.0,
            "deepfake_analysis": {
                "probability": deepfake_probability,
                "type": image_deepfake_type,
                "is_likely_ai_generated": deepfake_probability > 0.6,
                "is_misleading_content": False,
                "confidence_penalty": 0.0
            },
            "contradiction_analysis": {
                "score": 0.0,
                "type": "error",
                "confidence": 0.0,
                "reasoning": str(e)[:100]
            },
            "alignment_analysis": {
                "entity_alignment": 0.5,
                "alignment_score": 0.5
            },
            "multimodal_flags": [f"Analysis error: {str(e)[:50]}"],
            "verification_note": "Analysis failed - returning neutral scores with deepfake data"
        }
