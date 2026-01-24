import io
import shutil
import re
from PIL import Image, UnidentifiedImageError, ImageOps, ImageFilter
import pytesseract
from fastapi import UploadFile, HTTPException
from app.core.cross_modal import generate_caption, clip_similarity

tesseract_path = shutil.which("tesseract")
TESSERACT_AVAILABLE = False

from app.core.config import HOAX_PATTERNS

tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    return gray.filter(ImageFilter.SHARPEN)

def detect_image_red_flags(
    ocr_text: str,
    caption: str,
    image: Image.Image
) -> list[str]:
    red_flags = []
    combined_text = f"{ocr_text} {caption}".lower().strip()

    if combined_text:
        found_keywords = [word for word in HOAX_PATTERNS if word in combined_text]
        if found_keywords:
            red_flags.append(f"Contains suspicious vocabulary: {', '.join(found_keywords[:3])}")

        if re.search(r"\b(32|33|34|99)\b", combined_text):
            red_flags.append("Invalid or impossible numeric/date information")

    width, height = image.size
    aspect_ratio = width / height

    if aspect_ratio > 2.2:
        red_flags.append("Banner-like or poster-style composition")

    pixels = list(image.resize((64, 64)).getdata())
    if len(set(pixels)) < 50:
        red_flags.append("Unnaturally low color variation (synthetic image)")

    return list(set(red_flags))

def compute_image_risk_score(red_flags: list[str]) -> float:
    if not red_flags:
        return 0.0
    return round(min(len(red_flags) * 0.35, 1.0), 2)

def analyze_image(file: UploadFile) -> dict:
    try:
        file.file.seek(0)
        image = Image.open(io.BytesIO(file.file.read())).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(422, "Invalid image")

    ocr_text = ""
    if TESSERACT_AVAILABLE:
        try:
            ocr_text = pytesseract.image_to_string(
                preprocess_for_ocr(image),
                config="--psm 6"
            ).strip()
        except Exception:
            pass

    caption = generate_caption(image).lower()
    
    # Cultural Hint: Identify common mythological figures to aid search
    if "blue" in caption and "peacock" in caption:
        caption += " (possibly Lord Krishna)"
    elif "blue" in caption and "skin" in caption:
        caption += " (possibly Hindu deity)"
        
    # Filter OCR noise
    clean_ocr = ""
    if ocr_text:
        # Remove lines that are mostly symbols or numbers without words
        lines = ocr_text.split("\n")
        valid_lines = [l for l in lines if re.search(r'[a-zA-Z]{3,}', l)]
        clean_ocr = " ".join(valid_lines).strip()

    red_flags = detect_image_red_flags(clean_ocr, caption, image)
    image_risk_score = compute_image_risk_score(red_flags)
    cross_modal_score = clip_similarity(image, caption)

    visual_summary = f"Visual context shows: {caption}."
    if clean_ocr:
        visual_summary += f" Extracted text: '{clean_ocr}'."

    # Explain WHY it's real/fake
    if image_risk_score > 0.6:
        interpretation = "Image displays signs of synthetic generation or manipulation (low color variation or composition artifacts)."
    elif red_flags:
        interpretation = f"Image contains suspicious patterns: {', '.join(red_flags)}."
    elif image_risk_score < 0.2:
        interpretation = "Image appears visually authentic with natural color distribution and composition."
    else:
        interpretation = "Image shows no obvious manipulation but contains some minor visual warnings."

    return {
        "ocr_text": clean_ocr,
        "caption": caption,
        "visual_summary": visual_summary,
        "interpretation": interpretation,
        "red_flags": red_flags,
        "image_risk_score": image_risk_score,
        "cross_modal_score": cross_modal_score
    }
