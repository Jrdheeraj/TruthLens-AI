from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from pydantic import BaseModel
import tempfile
import os
import logging
import uuid
import shutil
import aiofiles
from pathlib import Path

# Security and async
import magic  # FIX 4: MIME type validation
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.claim_extractor import extract_claims
from app.core.text_verifier import verify_text_claims
from app.core.image_analyzer import analyze_image, TESSERACT_AVAILABLE
from app.core.verdict_engine import final_verdict
from app.core.video_analyzer import analyze_video
from app.core.audio_analyzer import analyze_audio
from app.live.live_search import fetch_live_evidence, fetch_wikipedia_evidence
from app.llm.evaluator import evaluate_claim_with_llm
from app.rag.agentic_rag import AgenticRAG
from app.utils.serialization import sanitize_response
import cv2
import pytesseract

logger = logging.getLogger(__name__)

# FIX 10: Rate limiting setup
limiter = Limiter(key_func=get_remote_address)

tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

from datetime import datetime

router = APIRouter(tags=["Verification"])


def json_safe_response(response):
    return sanitize_response(response)


def _is_relevant_forensic_source(source) -> bool:
    if not isinstance(source, dict):
        return False
    text = " ".join(
        str(source.get(key, ""))
        for key in ("text", "content", "snippet", "title", "summary", "description")
    ).lower()
    return any(term in text for term in ("deepfake", "ai-generated", "manipulation", "synthetic media", "synthetic"))


def _filter_forensic_sources(sources):
    if not isinstance(sources, list):
        return []
    return [src for src in sources if _is_relevant_forensic_source(src)]

# FIX 4: File validation constants
MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB
MAX_IMAGE_SIZE = 50 * 1024 * 1024   # 50MB
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo"
}
ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif"
}

# FIX 4: File validation helper
async def validate_and_save_upload(
    file: UploadFile,
    allowed_types: set,
    max_size: int
) -> Path:
    """
    Safely validate and save uploaded file with MIME type checking.
    
    Args:
        file: FastAPI UploadFile
        allowed_types: Set of allowed MIME types
        max_size: Maximum file size in bytes
        
    Returns:
        Path to saved temporary file
        
    Raises:
        HTTPException: If file is invalid
    """
    
    # Create secure temp directory
    tmpdir = tempfile.mkdtemp(prefix="truthlens_")
    tmppath = Path(tmpdir)
    
    try:
        # Read and validate file size (reset pointer and read synchronously)
        file.file.seek(0)
        content = file.file.read()
        
        if len(content) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File exceeds {max_size / (1024*1024):.0f}MB limit"
            )
        
        # Validate MIME type using magic
        mime_type = magic.from_buffer(content, mime=True)
        if mime_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {mime_type}. Allowed: {', '.join(allowed_types)}"
            )
        
        # Save to secure unique location
        filename = f"{Path(file.filename or 'file').stem}_{uuid.uuid4()}.tmp"
        safe_path = tmppath / filename
        
        # Write file securely
        with open(safe_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"File uploaded and validated: {mime_type} ({len(content)} bytes)")
        return safe_path
    
    except HTTPException:
        # Clean up on validation error
        shutil.rmtree(tmppath, ignore_errors=True)
        raise
    except Exception as e:
        logger.error(f"File upload error: {e}")
        shutil.rmtree(tmppath, ignore_errors=True)
        raise HTTPException(status_code=400, detail="File processing failed")

@router.get("/version")
def get_version():
    return json_safe_response({"version": "1.7.1", "last_updated": "2026-01-24T17:10:00Z"})

class TextPayload(BaseModel):
    text: str


class StrictFactResponse(BaseModel):
    sub_claims: list[dict]
    final_verdict: str
    confidence: int
    reasoning: str

@router.post("/verify/text")
@limiter.limit("10/minute")
async def verify_text(request: Request, payload: TextPayload):
    """Verify text claims - fully wrapped with error handling"""
    try:
        if not payload.text or not payload.text.strip():
            raise HTTPException(
                status_code=400,
                detail="Text input cannot be empty"
            )

        try:
            claims = extract_claims(payload.text)
        except Exception as e:
            logger.error(f"Claim extraction error: {e}")
            claims = []

        if not claims:
            return json_safe_response(final_verdict(
                text_results=[]
            ))

        try:
            text_results = await verify_text_claims(claims)
        except Exception as e:
            logger.error(f"Text verification error: {e}")
            text_results = []

        # === BUG FIX #3b: Construct RAG result from text_results and pass to verdict_engine ===
        rag_result = None
        if text_results:
            try:
                # Use first result as RAG result (consolidated from all claims)
                first = text_results[0]
                # Calculate average confidence from all results
                avg_confidence = sum(r.get("confidence", 50) for r in text_results) // len(text_results)
                # Combine all sources
                all_sources = []
                for r in text_results:
                    all_sources.extend(r.get("sources", []))
                
                # Determine overall verdict: TRUE if all or most are SUPPORTED
                supported_count = sum(1 for r in text_results if r.get("status") == "SUPPORTED")
                overall_verdict = "TRUE" if supported_count >= len(text_results) / 2 else "FALSE"
                
                rag_result = {
                    "verdict": overall_verdict,
                    "confidence": avg_confidence,
                    "reasoning": first.get("explanation", ""),
                    "sources": all_sources[:8]  # Top 8 sources
                }
            except Exception as e:
                logger.error(f"RAG result construction error: {e}")
                rag_result = None
        
        try:
            return json_safe_response(final_verdict(
                text_results=text_results,
                rag_result=rag_result
            ))
        except Exception as e:
            logger.error(f"Final verdict error: {e}")
            return json_safe_response({
                "verdict": "FALSE",
                "confidence": 0.0,
                "reasoning": ["Unable to generate verdict due to processing error"],
                "sources": []
            })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Text verification endpoint error: {e}")
        return json_safe_response({
            "verdict": "FALSE",
            "confidence": 0.0,
            "reasoning": ["Verification service temporarily unavailable"],
            "sources": []
        })


@router.post("/verify/strict", response_model=StrictFactResponse)
@limiter.limit("10/minute")
async def verify_text_strict(request: Request, payload: TextPayload):
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text input cannot be empty"
        )

    claim = payload.text.strip()
    
    # Use search query generator for precise queries + subject filtering
    from app.utils.search_query_generator import generate_search_query, _extract_subject_name
    precise_query = generate_search_query(claim)
    subject_name = _extract_subject_name(claim)

    # Fetch evidence in parallel (async)
    live_evidence = await fetch_live_evidence(precise_query, subject_name=subject_name)
    wiki_evidence = await fetch_wikipedia_evidence(precise_query, subject_name=subject_name)

    evidence_text = ""
    if live_evidence:
        evidence_text += f"Live Search Result: {live_evidence.get('text', '')}\n"
    if wiki_evidence:
        evidence_text += f"Wikipedia Result: {wiki_evidence.get('text', '')}\n"

    result = evaluate_claim_with_llm(claim, evidence_text)

    sub_claims = result.get("sub_claims", [])
    final_verdict = str(result.get("final_verdict", "FALSE")).upper()
    # Enforce TRUE/FALSE only (no UNCERTAIN, MISLEADING, etc.)
    if final_verdict not in ("TRUE", "FALSE"):
        final_verdict = "FALSE"
    confidence = int(result.get("confidence", 50))
    reasoning = str(result.get("explanation", "Analyzed using fact-checking evidence."))

    return json_safe_response({
        "sub_claims": sub_claims,
        "final_verdict": final_verdict,
        "confidence": max(0, min(confidence, 100)),
        "reasoning": reasoning
    })

@router.post("/verify/image")
@limiter.limit("5/minute")
async def verify_image(request: Request, file: UploadFile = File(...)):
    """Verify image content with file validation - fully wrapped with error handling"""
    tmpdir = None
    try:
        if not file:
            raise HTTPException(
                status_code=400,
                detail="Image file is required"
            )

        try:
            # FIX 4: Validate file upload
            safe_path = await validate_and_save_upload(
                file,
                ALLOWED_IMAGE_TYPES,
                MAX_IMAGE_SIZE
            )
            tmpdir = safe_path.parent
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"File validation error: {e}")
            raise HTTPException(status_code=400, detail="File upload failed")

        try:
            # Reopen the validated file for analysis
            file.file.seek(0)
            image_result = analyze_image(file)
        except Exception as e:
            logger.error(f"Image analysis error: {e}")
            image_result = {
                "error": str(e),
                "verdict": "FALSE",
                "ocr_text": "",
                "caption": "Analysis failed",
                "visual_summary": "Unable to analyze image",
                "interpretation": "Image analysis error",
                "red_flags": [],
                "image_risk_score": 0.5,
                "cross_modal_score": 0.0
            }

        try:
            # FIX: Only fact-check OCR text (real text in image), not the generated caption
            # Captions are visual descriptions, not factual claims
            ocr_text = image_result.get('ocr_text', '').strip()
            image_caption = image_result.get('caption', '').strip()
            
            text_results = []
            rag_result = None
            if ocr_text:
                try:
                    claims = extract_claims(ocr_text)
                    if not claims and len(ocr_text) > 10:
                        claims = [ocr_text]
                        
                    if claims:
                        text_results = await verify_text_claims(claims, image_context=image_result)
                        
                        # === BUG FIX #3b: Construct RAG result from text_results ===
                        if text_results:
                            avg_confidence = sum(r.get("confidence", 50) for r in text_results) // len(text_results)
                            all_sources = []
                            for r in text_results:
                                all_sources.extend(r.get("sources", []))
                            
                            supported_count = sum(1 for r in text_results if r.get("status") == "SUPPORTED")
                            overall_verdict = "TRUE" if supported_count >= len(text_results) / 2 else "FALSE"
                            
                            rag_result = {
                                "verdict": overall_verdict,
                                "confidence": avg_confidence,
                                "reasoning": text_results[0].get("explanation", ""),
                                "sources": all_sources[:8]
                            }
                except Exception as e:
                    logger.error(f"OCR text verification error: {e}")
                    text_results = []
            elif image_caption and len(image_caption) > 10:
                # Enable RAG for image caption-based queries
                try:
                    rag_system = AgenticRAG()
                    query = f"Image analysis: {image_caption}. Is this accurate?"
                    rag_result = await rag_system.run(query, content_type="image")
                    logger.info(f"Image caption RAG query executed")
                except Exception as e:
                    logger.warning(f"Image caption RAG failed: {e}")
                    rag_result = None

            try:
                return json_safe_response(final_verdict(
                    text_results=text_results,
                    image_results=image_result,
                    rag_result=rag_result
                ))
            except Exception as e:
                logger.error(f"Final verdict error in image endpoint: {e}")
                return json_safe_response({
                    "verdict": "FALSE",
                    "confidence": 0.0,
                    "reasoning": ["Image analysis error"],
                    "sources": []
                })
        except Exception as e:
            logger.error(f"Image endpoint processing error: {e}")
            return json_safe_response({
                "verdict": "FALSE",
                "confidence": 0.0,
                "reasoning": ["Unable to process image"],
                "sources": []
            })
    finally:
        # FIX 7: Guarantee cleanup of temp files
        if tmpdir and Path(tmpdir).exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")

@router.post("/verify/multimodal")
@limiter.limit("5/minute")
async def verify_multimodal(
    request: Request,
    text: str = Form(None),
    file: UploadFile = File(None)
):
    """Analyze text and/or image content - fully wrapped with error handling"""
    tmpdir = None
    try:
        if not text and not file:
            raise HTTPException(
                status_code=400,
                detail="At least one of text or image must be provided"
            )

        text_results = []
        image_result = None
        rag_result = None

        try:
            if file:
                try:
                    safe_path = await validate_and_save_upload(
                        file,
                        ALLOWED_IMAGE_TYPES,
                        MAX_IMAGE_SIZE
                    )
                    tmpdir = safe_path.parent
                    file.file.seek(0)
                    image_result = analyze_image(file)
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Image analysis in multimodal failed: {e}")
                    image_result = None

            image_text_content = ""
            if image_result:
                image_text_content = f"{image_result.get('ocr_text', '')} {image_result.get('caption', '')}"

            full_context = f"{text or ''} {image_text_content}".strip()
            
            if full_context:
                try:
                    claims = extract_claims(full_context)
                    # Fallback: if no distinct claims extracted but text exists, verify the text as a whole
                    if not claims and len(full_context) > 10:
                        claims = [full_context]
                    
                    # FIX: If still no claims, create a default one to ensure RAG result with sources
                    if not claims and len(full_context) > 0:
                        logger.warning(f"No claims extracted from context - creating default verification claim")
                        claims = [full_context if len(full_context) > 5 else f"Analyzing provided content"]
                        
                    if claims:
                        try:
                            text_results = await verify_text_claims(claims, image_context=image_result)
                        except Exception as e:
                            logger.error(f"Text verification in multimodal failed: {e}")
                            text_results = []
                        
                        # === BUG FIX #3b: Construct RAG result from text_results ===
                        if text_results:
                            try:
                                avg_confidence = sum(r.get("confidence", 50) for r in text_results) // len(text_results)
                                all_sources = []
                                for r in text_results:
                                    all_sources.extend(r.get("sources", []))
                                
                                supported_count = sum(1 for r in text_results if r.get("status") == "SUPPORTED")
                                overall_verdict = "TRUE" if supported_count >= len(text_results) / 2 else "FALSE"
                                
                                rag_result = {
                                    "verdict": overall_verdict,
                                    "confidence": avg_confidence,
                                    "reasoning": text_results[0].get("explanation", ""),
                                    "sources": all_sources[:8]
                                }
                            except Exception as e:
                                logger.error(f"RAG result construction error: {e}")
                                rag_result = None
                except Exception as e:
                    logger.error(f"Multimodal context processing failed: {e}")
                    text_results = []
                    rag_result = None

            try:
                return json_safe_response(final_verdict(
                    text_results=text_results,
                    image_results=image_result,
                    cross_modal_score=image_result.get("cross_modal_score") if image_result else None,
                    rag_result=rag_result
                ))
            except Exception as e:
                logger.error(f"Final verdict error in multimodal: {e}")
                return json_safe_response({
                    "verdict": "FALSE",
                    "confidence": 0.0,
                    "reasoning": ["Analysis error"],
                    "sources": []
                })
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Multimodal verification error: {e}")
            return json_safe_response({
                "verdict": "FALSE",
                "confidence": 0.0,
                "reasoning": ["Processing error"],
                "sources": []
            })
    finally:
        if tmpdir and Path(tmpdir).exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")

@router.post("/verify/video")
@limiter.limit("5/minute")
async def verify_video(request: Request, file: UploadFile = File(...)):
    """Verify video content with file validation - fully wrapped with error handling"""
    from app.core.cross_modal import generate_caption
    from PIL import Image
    
    tmpdir = None
    try:
        if not file:
            raise HTTPException(status_code=400, detail="Video file is required")

        try:
            # FIX 4: Validate file upload
            safe_path = await validate_and_save_upload(
                file,
                ALLOWED_VIDEO_TYPES,
                MAX_VIDEO_SIZE
            )
            tmpdir = safe_path.parent
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Video file validation error: {e}")
            raise HTTPException(status_code=400, detail="File upload failed")
        
        logger.info(f"Processing video: {file.filename}")
        
        try:
            video_analysis = analyze_video(str(safe_path))
            visual_risk = video_analysis.get('visual_risk_score', 0.0)
            frames = video_analysis.get('frames', [])
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            video_analysis = {'visual_risk_score': 0.5, 'frames': [], 'metadata': {}}
            visual_risk = 0.5
            frames = []
        
        try:
            audio_analysis = analyze_audio(str(safe_path))
            audio_risk = audio_analysis.get('audio_risk_score', 0.0)
            logger.info(f"AUDIO SCORE: {audio_risk}")
        except Exception as e:
            logger.error(f"Audio analysis failed: {e}")
            audio_analysis = {'audio_risk_score': 0.0, 'has_audio': False, 'risk_factors': []}
            audio_risk = 0.0
            logger.info(f"AUDIO SCORE: 0.0 (failed)")
        
        # FIX: Only extract REAL TEXT from video, not captions
        # Captions are visual descriptions, not factual claims to verify
        claims = []
        video_caption = ""
        ocr_texts = []
        
        try:
            if frames:
                for i, frame in enumerate(frames[:3]):
                    try:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(frame_rgb)
                        
                        # Generate caption for metadata (don't fact-check it)
                        if i == 0:
                            try:
                                video_caption = generate_caption(pil_image)
                                logger.info(f"Generated frame caption (descriptive only): '{video_caption}'")
                            except Exception as e:
                                logger.warning(f"Caption generation failed: {e}")
                                video_caption = "Video frame"
                        
                        # ONLY extract real text (OCR) for fact-checking
                        if TESSERACT_AVAILABLE:
                            try:
                                ocr_text = pytesseract.image_to_string(pil_image).strip()
                                if ocr_text and len(ocr_text) > 10:
                                    ocr_texts.append(ocr_text)
                                    logger.info(f"Extracted OCR text from frame {i}: {ocr_text[:50]}")
                            except Exception as e:
                                logger.debug(f"OCR extraction failed for frame {i}: {e}")
                        
                    except Exception as e:
                        logger.warning(f"Frame {i} processing warning: {e}")
                        continue
                
                # Only fact-check actual OCR text, NOT the caption
                if ocr_texts:
                    claims = ocr_texts
                    logger.info(f"Video has {len(claims)} text claims to verify (from OCR)")
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
            claims = []
        
        # If no OCR text found in video, analyze purely for deepfake/manipulation
        # Don't create fake claims to fact-check
        if not claims:
            logger.info("No text content in video - analyzing for deepfake/manipulation only")
        
        video_context = {
            'visual_risk_score': visual_risk,
            'audio_risk_score': audio_risk,
            'has_audio': audio_analysis.get('has_audio', False),
            'video_type': 'video',
            'video_caption': video_caption  # Store caption for reference, not verification
        }
        
        # Only fact-check if we have actual text claims
        text_results = []
        if claims:
            try:
                text_results = await verify_text_claims(claims, image_context=video_context)
            except Exception as e:
                logger.error(f"Text verification from video failed: {e}")
                text_results = []
        
        # === ALWAYS RUN RAG FOR VIDEO (with audio + caption context) ===
        rag_result = None
        audio_transcript = audio_analysis.get('audio_transcript', '')
        audio_context = audio_analysis.get('audio_context', {})
        
        try:
            if text_results:
                # Text-based RAG: Existing logic for OCR text from video
                avg_confidence = sum(r.get("confidence", 50) for r in text_results) // len(text_results)
                all_sources = []
                for r in text_results:
                    all_sources.extend(r.get("sources", []))
                
                supported_count = sum(1 for r in text_results if r.get("status") == "SUPPORTED")
                overall_verdict = "TRUE" if supported_count >= len(text_results) / 2 else "FALSE"
                rag_result = {
                    "verdict": overall_verdict,
                    "confidence": avg_confidence,
                    "reasoning": text_results[0].get("explanation", "") if text_results else "",
                    "sources": _filter_forensic_sources(all_sources)[:8]
                }
                logger.info(f"RAG executed for video text verification: {overall_verdict} ({avg_confidence}%)")
            else:
                # Multimodal RAG: Combine video caption + audio transcript + audio context
                try:
                    rag_system = AgenticRAG()

                    query = f"""
Analyze this video for authenticity:

Description: {video_caption}

Task:
- Detect deepfake or synthetic media
- Find real-world examples of manipulation
- Identify similar AI-generated content patterns

IMPORTANT:
Focus only on:
- deepfake detection
- synthetic media
- AI-generated visuals
""".strip()
                    rag_result = await rag_system.run(query, content_type="video")
                    if isinstance(rag_result, dict):
                        rag_result["sources"] = _filter_forensic_sources(rag_result.get("sources", []))[:8]
                    logger.info(f"RAG executed for multimodal video analysis (caption + audio)")
                except Exception as e:
                    logger.warning(f"Multimodal RAG execution failed: {e}")
                    rag_result = None
        except Exception as e:
            logger.error(f"RAG execution error in video: {e}")
            rag_result = None
        
        try:
            # Ensure complete information passed to verdict engine
            has_meaningful_audio = bool(audio_analysis.get('has_audio')) and bool(str(audio_transcript).strip())
            if not has_meaningful_audio:
                audio_transcript = "No meaningful audio detected"
                final_audio_score = None
            else:
                final_audio_score = audio_analysis.get('audio_risk_score', None)

            # Pass complete video_analysis with audio and context
            video_results = {
                'visual_risk_score': video_analysis.get('visual_risk_score', 0.0),
                'final_risk_score': video_analysis.get('final_risk_score', 0.0),
                'audio_risk_score': audio_analysis.get('audio_risk_score', 0.0),
                'audio_score': final_audio_score,
                'motion_score': video_analysis.get('motion_score', 0.0),
                'has_audio': audio_analysis.get('has_audio', False),
                'video_caption': video_caption,
                'audio_transcript': audio_transcript,
                'audio_context': audio_context,
                'metadata': {**video_analysis.get('metadata', {}), 'filename': file.filename},
                'risk_factors': audio_analysis.get('risk_factors', []),
                'deepfake_analysis': video_analysis.get('deepfake_analysis', {}),
                'temporal_analysis': video_analysis.get('temporal_analysis', {}),
                'model_score': video_analysis.get('deepfake_analysis', {}).get('model_fake_risk', 0.0),
                'sources': rag_result.get('sources', []) if rag_result else []
            }
            logger.info(f"VIDEO PIPELINE: Passing audio_score={final_audio_score}, transcript_len={len(audio_transcript)}, rag_powered={bool(rag_result)}")
            
            return json_safe_response(final_verdict(
                text_results=text_results,
                image_results=video_results,
                cross_modal_score=None,
                rag_result=rag_result,
                motion_score=video_analysis.get('motion_score', 0.0),
                content_type="video",
                audio_score=final_audio_score,
                audio_transcript=audio_transcript,
                audio_context=audio_context
            ))
        except Exception as e:
            logger.error(f"Final verdict error in video endpoint: {e}")
            return json_safe_response({
                "verdict": "FALSE",
                "confidence": 0.0,
                "reasoning": ["Video analysis error"],
                "sources": []
            })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Video verification endpoint error: {e}")
        return json_safe_response({
            "verdict": "FALSE",
            "confidence": 0.0,
            "reasoning": ["Verification service temporarily unavailable"],
            "sources": []
        })
    finally:
        # FIX 7: Guarantee cleanup of temp files
        if tmpdir and Path(tmpdir).exists():
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception as e:
                logger.debug(f"Cleanup error: {e}")
