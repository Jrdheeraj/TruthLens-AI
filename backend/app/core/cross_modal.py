import torch
from PIL import Image
from transformers import (
    BlipProcessor,
    BlipForConditionalGeneration,
    CLIPProcessor,
    CLIPModel
)

device = torch.device("cpu")

blip_processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)
blip_model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)
blip_model.to(device).eval()

clip_processor = CLIPProcessor.from_pretrained(
    "openai/clip-vit-base-patch32"
)
clip_model = CLIPModel.from_pretrained(
    "openai/clip-vit-base-patch32"
)
clip_model.to(device).eval()

def generate_caption(image: Image.Image) -> str:
    if image.mode != "RGB":
        image = image.convert("RGB")

    inputs = blip_processor(image, return_tensors="pt")
    with torch.no_grad():
        output = blip_model.generate(**inputs, max_new_tokens=30)

    caption = blip_processor.decode(
        output[0], skip_special_tokens=True
    ).strip()

    return caption or "A natural photograph"

def clip_similarity(image: Image.Image, text: str) -> float:
    if not text:
        return 0.0

    if image.mode != "RGB":
        image = image.convert("RGB")

    inputs = clip_processor(
        text=[text],
        images=image,
        return_tensors="pt",
        padding=True
    )

    with torch.no_grad():
        outputs = clip_model(**inputs)

    score = outputs.logits_per_image.softmax(dim=1)[0][0].item()
    return round(score, 3)
