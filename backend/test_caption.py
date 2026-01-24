import torch
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration
import os

device = torch.device("cpu")
blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
blip_model.to(device).eval()

image_path = r"C:/Users/jrdhe/.gemini/antigravity/brain/b0d35236-89de-4efb-8ef2-fa78ffbfb849/uploaded_media_1769255608830.jpg"
if os.path.exists(image_path):
    image = Image.open(image_path).convert("RGB")
    inputs = blip_processor(image, return_tensors="pt")
    with torch.no_grad():
        output = blip_model.generate(**inputs, max_new_tokens=30)
    caption = blip_processor.decode(output[0], skip_special_tokens=True).strip()
    print(f"CAPTION RESULT: '{caption}'")
else:
    print("IMAGE NOT FOUND")
