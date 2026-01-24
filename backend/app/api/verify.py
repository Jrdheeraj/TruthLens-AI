from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
import tempfile
import os

from app.core.claim_extractor import extract_claims
from app.core.text_verifier import verify_text_claims
from app.core.image_analyzer import analyze_image, TESSERACT_AVAILABLE
from app.core.verdict_engine import final_verdict
from app.core.video_analyzer import analyze_video
from app.core.audio_analyzer import analyze_audio
import cv2
import pytesseract
import shutil

tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

from datetime import datetime

router = APIRouter(tags=["Verification"])

@router.get("/version")
def get_version():
    return {"version": "1.7.1", "last_updated": "2026-01-24T17:10:00Z"}

class TextPayload(BaseModel):
    text: str

@router.post("/verify/text")
async def verify_text(payload: TextPayload):
    if not payload.text or not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail="Text input cannot be empty"
        )

    claims = extract_claims(payload.text)

    if not claims:
        return final_verdict(
            text_results=[]
        )

    text_results = verify_text_claims(claims)

    return final_verdict(
        text_results=text_results
    )

@router.post("/verify/image")
async def verify_image(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(
            status_code=400,
            detail="Image file is required"
        )

    image_result = analyze_image(file)

    combined_text = f"{image_result.get('ocr_text', '')} {image_result.get('caption', '')}".strip()
    
    text_results = []
    if combined_text:
        claims = extract_claims(combined_text)
        # Fallback: if no distinct claims extracted but text exists, verify the text as a whole
        if not claims and len(combined_text) > 10:
            claims = [combined_text]
            
        if claims:
            text_results = verify_text_claims(claims, image_context=image_result)

    return final_verdict(
        text_results=text_results,
        image_results=image_result
    )

@router.post("/verify/multimodal")
async def verify_multimodal(
    text: str = Form(None),
    file: UploadFile = File(None)
):
    if not text and not file:
        raise HTTPException(
            status_code=400,
            detail="At least one of text or image must be provided"
        )

    text_results = []
    image_result = None

    image_text_content = ""
    if file:
        image_result = analyze_image(file)
        image_text_content = f"{image_result.get('ocr_text', '')} {image_result.get('caption', '')}"

    full_context = f"{text or ''} {image_text_content}".strip()
    
    if full_context:
        claims = extract_claims(full_context)
        # Fallback: if no distinct claims extracted but text exists, verify the text as a whole
        if not claims and len(full_context) > 10:
            claims = [full_context]
            
        if claims:
            text_results = verify_text_claims(claims, image_context=image_result)

    return final_verdict(
        text_results=text_results,
        image_results=image_result,
        cross_modal_score=image_result.get("cross_modal_score") if image_result else None
    )

@router.post("/verify/video")
async def verify_video(file: UploadFile = File(...)):
    from app.core.cross_modal import generate_caption
    from PIL import Image
    
    print(f"VIDEO ENDPOINT: Started processing file {file.filename}")
    if not file:
        raise HTTPException(status_code=400, detail="Video file is required")
    
    temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
    temp_video_path = temp_video.name
    
    try:
        content = await file.read()
        temp_video.write(content)
        temp_video.close()
        
        print(f"VIDEO ENDPOINT: Processing video {file.filename}")
        
        video_analysis = analyze_video(temp_video_path)
        visual_risk = video_analysis.get('visual_risk_score', 0.0)
        frames = video_analysis.get('frames', [])
        
        audio_analysis = analyze_audio(temp_video_path)
        audio_risk = audio_analysis.get('audio_risk_score', 0.0)
        
        claims = []
        video_caption = ""
        
        if frames:
            for i, frame in enumerate(frames[:3]):
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)
                    
                    if i == 0:
                        video_caption = generate_caption(pil_image)
                        print(f"VIDEO ENDPOINT: Generated frame caption: '{video_caption}'")
                        if video_caption and video_caption != "A natural photograph":
                            claims.append(video_caption)
                    
                    if TESSERACT_AVAILABLE:
                        ocr_text = pytesseract.image_to_string(pil_image).strip()
                        if ocr_text and len(ocr_text) > 10:
                            claims.append(ocr_text)
                    
                except Exception as e:
                    print(f"VIDEO ENDPOINT: Frame {i} processing warning: {e}")
            
            if not claims and video_caption:
                claims.append(video_caption)
            if not claims:
                claims.append(f"Analyzing video content for suspicious patterns (File: {file.filename})")
        
            # Add filename as a claim to catch context in file naming
            if file.filename:
                claims.append(file.filename.replace("_", " ").replace("-", " "))
            
            video_context = {
                'visual_risk_score': visual_risk,
                'audio_risk_score': audio_risk,
                'has_audio': audio_analysis.get('has_audio', False),
                'video_type': 'video'
            }
            text_results = verify_text_claims(claims, image_context=video_context)
        else:
            text_results = []
        
        video_results = {
            'visual_risk_score': visual_risk,
            'audio_risk_score': audio_risk,
            'has_audio': audio_analysis.get('has_audio', False),
            'video_caption': video_caption,
            'metadata': {**video_analysis.get('metadata', {}), 'filename': file.filename},
            'risk_factors': audio_analysis.get('risk_factors', [])
        }
        
        return final_verdict(
            text_results=text_results,
            image_results=video_results,
            cross_modal_score=None
        )
        
    finally:
        if os.path.exists(temp_video_path):
            os.remove(temp_video_path)
