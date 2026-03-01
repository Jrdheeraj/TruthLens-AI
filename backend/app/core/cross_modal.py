import torch
from PIL import Image
from transformers import BlipForConditionalGeneration, BlipProcessor, CLIPModel, CLIPProcessor

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
        print(f"BLIP load failed: {e}")
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
        print(f"CLIP load failed: {e}")
        return False


def generate_caption(image: Image.Image) -> str:
    if image.mode != "RGB":
        image = image.convert("RGB")

    if not _load_blip():
        return "A natural photograph"

    inputs = _blip_processor(image, return_tensors="pt")
    with torch.no_grad():
        output = _blip_model.generate(**inputs, max_new_tokens=30)

    caption = _blip_processor.decode(output[0], skip_special_tokens=True).strip()
    return caption or "A natural photograph"


def clip_similarity(image: Image.Image, text: str) -> float:
    if not text:
        return 0.0

    if image.mode != "RGB":
        image = image.convert("RGB")

    if not _load_clip():
        return 0.0

    image_inputs = _clip_processor(images=image, return_tensors="pt")
    text_inputs = _clip_processor(text=[text], return_tensors="pt", padding=True)

    with torch.no_grad():
        image_features = _clip_model.get_image_features(**image_inputs)
        text_features = _clip_model.get_text_features(**text_inputs)

    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
    text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    cosine_score = torch.matmul(image_features, text_features.T)[0][0].item()
    normalized_score = (cosine_score + 1.0) / 2.0
    return round(max(0.0, min(normalized_score, 1.0)), 3)
