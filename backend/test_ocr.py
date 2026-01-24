import pytesseract
from PIL import Image, ImageOps, ImageFilter
import shutil
import os

tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    return gray.filter(ImageFilter.SHARPEN)

image_path = r"C:/Users/jrdhe/.gemini/antigravity/brain/b0d35236-89de-4efb-8ef2-fa78ffbfb849/uploaded_media_1769255608830.jpg"
if os.path.exists(image_path):
    image = Image.open(image_path).convert("RGB")
    processed = preprocess_for_ocr(image)
    ocr_text = pytesseract.image_to_string(processed, config="--psm 6").strip()
    print(f"OCR RESULT: '{ocr_text}'")
else:
    print("IMAGE NOT FOUND")
