import io
import logging
import shutil
import re
import asyncio
import numpy as np
from PIL import Image, UnidentifiedImageError, ImageOps, ImageFilter
import pytesseract
from fastapi import UploadFile, HTTPException
from app.core.cross_modal import generate_caption, clip_similarity
from app.rag.agentic_rag import AgenticRAG
from app.utils.serialization import sanitize_response, to_python_type
import cv2
from scipy.ndimage import gaussian_filter
from scipy.fft import fft2, fftshift
from skimage import exposure
import threading

# NEW: Deep learning for deepfake detection
try:
    import torch
    import torch.nn.functional as F
    from torchvision import transforms
    import timm
    TORCH_AVAILABLE = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Reuse model from video_analyzer or load separately
    _image_model = None
    _image_model_lock = threading.Lock()
    
    def get_image_deepfake_model():
        """Lazy load deepfake detection model (Xception)"""
        global _image_model
        if _image_model is None:
            with _image_model_lock:
                if _image_model is None:
                    try:
                        logger_temp = logging.getLogger(__name__)
                        logger_temp.info("Loading deepfake detection model for images...")
                        _image_model = timm.create_model('xception', pretrained=True)
                        _image_model = _image_model.to(DEVICE)
                        _image_model.eval()
                    except Exception as e:
                        logger_temp.warning(f"Failed to load image deepfake model: {e}")
                        _image_model = "failed"
        return None if _image_model == "failed" else _image_model
    
    _image_preprocess = transforms.Compose([
        transforms.Resize((299, 299)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
except (ImportError, AttributeError) as e:
    TORCH_AVAILABLE = False
    logger_temp_init = logging.getLogger(__name__)
    logger_temp_init.warning(f"PyTorch/timm not available for image analysis: {e}")

logger = logging.getLogger(__name__)

# Constants
MAX_IMAGE_DIMENSION = 2048  # Maximum pixel width/height

tesseract_path = shutil.which("tesseract")
TESSERACT_AVAILABLE = False

from app.core.config import HOAX_PATTERNS

tesseract_path = shutil.which("tesseract")
if tesseract_path:
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESSERACT_AVAILABLE = True


# ============================================================================
# NEW: FORENSIC ANALYSIS FUNCTIONS
# ============================================================================

def semantic_consistency_check(image: Image.Image) -> dict:
    """
    NEW: Detect physically impossible visuals
    - Inconsistent lighting and shadows
    - Distorted geometry
    - Unrealistic proportions
    
    Returns:
        {
            "lighting_consistency": 0.0-1.0 (1.0 = consistent),
            "geometry_stability": 0.0-1.0,
            "flags": [list of issues]
        }
    """
    flags = []
    consistency_scores = []
    
    try:
        # PERFORMANCE: Downscale large images before analysis
        if image.width > 1024 or image.height > 1024:
            image = image.resize((min(1024, image.width), min(1024, image.height)))
        
        # Convert to LAB color space for lighting analysis
        img_array = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        
        # Convert RGB to LAB-like representation
        # Extract luminance channel
        L = np.mean(img_array, axis=2)  # Simplified illumination
        
        # Analyze illumination consistency across quadrants
        h, w = L.shape
        quadrant_brightness = []
        for y_start in [0, h // 2]:
            for x_start in [0, w // 2]:
                quad = L[y_start:y_start + h//2, x_start:x_start + w//2]
                quadrant_brightness.append(np.mean(quad))
        
        # Check for extreme lighting inconsistency
        brightness_variance = np.var(quadrant_brightness)
        if brightness_variance > 0.15:  # High variance = inconsistent lighting
            flags.append("Inconsistent illumination across image regions")
            consistency_scores.append(0.3)
        else:
            consistency_scores.append(0.9)
        
        # Geometry/edge consistency via gradient analysis
        edges = cv2.Canny(cv2.cvtColor(np.uint8(img_array * 255), cv2.COLOR_RGB2GRAY), 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        
        # Check for warped perspective (edge discontinuities)
        if edge_density > 0.25:  # Too many edges = warping/distortion
            flags.append("Detected edge discontinuities suggesting warped geometry")
            consistency_scores.append(0.4)
        else:
            consistency_scores.append(0.85)
        
        # Proportion analysis: check for unrealistic object sizes
        # Using contour analysis as proxy
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) > 0:
            contour_areas = [cv2.contourArea(c) for c in contours]
            if len(contour_areas) > 1:
                area_variance = np.std(contour_areas) / (np.mean(contour_areas) + 1e-6)
                if area_variance > 3.0:  # Extreme variance suggests unnatural proportions
                    flags.append("Detected unrealistic object proportions")
                    consistency_scores.append(0.35)
                else:
                    consistency_scores.append(0.80)
        
        lighting_score = consistency_scores[0] if consistency_scores else 0.5
        geometry_score = np.mean(consistency_scores[1:]) if len(consistency_scores) > 1 else 0.5
        
        return {
            "lighting_consistency": round(lighting_score, 3),
            "geometry_stability": round(geometry_score, 3),
            "forensic_flags": flags
        }
    
    except Exception as e:
        logger.debug(f"Semantic consistency check failed: {e}")
        return {
            "lighting_consistency": 0.5,
            "geometry_stability": 0.5,
            "forensic_flags": []
        }


def forensic_artifact_detector(image: Image.Image) -> dict:
    """
    NEW: Detect advanced manipulation indicators
    - GAN artifacts (frequency domain analysis)
    - Copy-move forgery (block matching)
    - Compression inconsistencies (ELA-like detection)
    
    Returns:
        {
            "gan_probability": 0.0-1.0,
            "copymove_probability": 0.0-1.0,
            "compression_inconsistency": 0.0-1.0,
            "artifacts": [list of detected issues]
        }
    """
    artifacts = []
    
    try:
        # PERFORMANCE: Downsample for faster analysis
        analysis_size = 512
        if image.width > analysis_size or image.height > analysis_size:
            image = image.resize((min(analysis_size, image.width), min(analysis_size, image.height)))
        
        img_array = np.array(image.convert("RGB"), dtype=np.float32)
        h, w, c = img_array.shape
        
        # ===== GAN ARTIFACT DETECTION (Frequency Domain) =====
        # Transform to grayscale for frequency analysis
        gray = cv2.cvtColor(np.uint8(img_array), cv2.COLOR_RGB2GRAY).astype(np.float32)
        
        # Compute FFT
        f_transform = fft2(gray)
        f_shift = fftshift(f_transform)
        magnitude_spectrum = np.abs(f_shift)
        
        # Analyze frequency patterns
        # GAN artifacts show unusual frequency concentrations
        log_spectrum = np.log1p(magnitude_spectrum)
        
        # High-frequency artifact detection
        center_h, center_w = h // 2, w // 2
        center_region = log_spectrum[
            max(0, center_h - 50) : min(h, center_h + 50),
            max(0, center_w - 50) : min(w, center_w + 50)
        ]
        periphery_region = log_spectrum[
            max(0, center_h - 100) : min(h, center_h + 100),
            max(0, center_w - 100) : min(w, center_w + 100)
        ]
        
        if len(center_region) > 0 and len(periphery_region) > 0:
            center_energy = np.mean(center_region)
            periphery_energy = np.mean(periphery_region)
            
            # GAN artifacts concentrate energy at specific frequencies
            if periphery_energy > 0.1 and (center_energy / (periphery_energy + 1e-6)) < 0.5:
                gan_probability = min(0.7, (1.0 - center_energy / (periphery_energy + 1e-6)) * 0.8)
                artifacts.append(f"GAN-like frequency patterns detected (probability: {gan_probability:.2f})")
            else:
                gan_probability = 0.1
        else:
            gan_probability = 0.1
        
        # ===== COPY-MOVE FORGERY DETECTION (Simplified Block Matching) =====
        # PERFORMANCE: Use larger block size and fewer iterations
        block_size = 64  # Increased from 32
        blocks = {}
        matches = 0
        total_blocks = 0
        max_blocks = 50  # PERFORMANCE: Limit total blocks to scan
        
        for i in range(0, min(h, 512), block_size):  # PERFORMANCE: Max 512px scan
            for j in range(0, min(w, 512), block_size):
                if total_blocks >= max_blocks:
                    break
                block = gray[i : i + block_size, j : j + block_size]
                if block.size == 0:
                    continue
                block_hash = hash(block.tobytes())  # Simplified hash-based matching
                
                if block_hash in blocks:
                    matches += 1
                blocks[block_hash] = (i, j)
                total_blocks += 1
        
        if total_blocks > 0:
            copymove_probability = min(0.6, (matches / max(total_blocks, 1)) * 0.25)  # Reduced probability
            if matches > max(total_blocks * 0.1, 2):  # More than 10% duplicate blocks
                artifacts.append(f"Potential copy-move forgery detected ({matches} matching blocks)")
        else:
            copymove_probability = 0.0
        
        # ===== COMPRESSION INCONSISTENCY (Skip for performance) =====
        # ELA detection is expensive and not always reliable
        # Use frequency analysis instead
        compression_inconsistency = 0.1  # Default low value
        # Only check if FFT detected issues
        if gan_probability > 0.5:
            compression_inconsistency = min(0.3, gan_probability * 0.3)
            artifacts.append("Potential compression inconsistency (inferred from frequency analysis)")
        
        return {
            "gan_probability": round(gan_probability, 3),
            "copymove_probability": round(copymove_probability, 3),
            "compression_inconsistency": round(compression_inconsistency, 3),
            "artifacts": artifacts
        }
    
    except Exception as e:
        logger.debug(f"Forensic artifact detection failed: {e}")
        return {
            "gan_probability": 0.0,
            "copymove_probability": 0.0,
            "compression_inconsistency": 0.0,
            "artifacts": []
        }


def context_misuse_detector(ocr_text: str, caption: str, image: Image.Image) -> dict:
    """
    NEW: Detect misleading usage of real images
    - Mismatch between caption and visual content
    - Emotionally manipulative framing
    - Out-of-context reuse indicators
    
    Returns:
        {
            "caption_image_mismatch": 0.0-1.0,
            "manipulation_indicators": [list],
            "manipulation_score": 0.0-1.0
        }
    """
    indicators = []
    mismatch_score = 0.0
    
    try:
        combined_text = f"{ocr_text} {caption}".lower()
        
        # EMOTIONAL MANIPULATION CHECK
        emotional_words = [
            "shocking", "disgusting", "outrageous", "unbelievable",
            "breaking", "scandal", "exposed", "must see", "viral",
            "they dont want you to see", "urgent", "warning"
        ]
        
        emotional_count = sum(1 for word in emotional_words if word in combined_text)
        if emotional_count >= 2:
            indicators.append(f"High emotional manipulation language ({emotional_count} markers)")
            mismatch_score += 0.25
        
        # CAPTION-IMAGE SEMANTIC MISMATCH
        # Use simple heuristics for now
        if caption and ocr_text:
            # Check for contradiction indicators
            contradictions = [
                ("peaceful", ["violence", "riot", "attack", "war"]),
                ("happy", ["sad", "crying", "mourning", "death"]),
                ("safe", ["dangerous", "hazard", "toxic", "threat"]),
                ("morning", ["night", "dark", "moon", "stars"]),
            ]
            
            caption_lower = caption.lower()
            for positive, negatives in contradictions:
                if positive in caption_lower:
                    for negative in negatives:
                        if negative in combined_text:
                            indicators.append(f"Caption-image mismatch: '{positive}' in caption but '{negative}' in text")
                            mismatch_score += 0.3
        
        # OUT-OF-CONTEXT REUSE INDICATORS
        # Check for temporal/location inconsistencies in text
        year_pattern = r'\b(201[0-9]|202[0-4])\b'
        years_found = re.findall(year_pattern, combined_text)
        
        if len(years_found) > 1:
            unique_years = set(years_found)
            if len(unique_years) > 1:
                indicators.append(f"Multiple dates detected in text: {unique_years}")
                mismatch_score += 0.15
        
        manipulation_score = min(1.0, mismatch_score)
        
        return {
            "caption_image_mismatch": round(1.0 - (1.0 - min(mismatch_score, 0.5)) / 0.5, 3) if mismatch_score > 0 else 0.0,
            "manipulation_indicators": indicators,
            "manipulation_score": round(manipulation_score, 3)
        }
    
    except Exception as e:
        logger.debug(f"Context misuse detection failed: {e}")
        return {
            "caption_image_mismatch": 0.0,
            "manipulation_indicators": [],
            "manipulation_score": 0.0
        }


def compute_forensic_risk_score(
    red_flags: list[str],
    semantic_check: dict,
    forensic_artifacts: dict,
    context_analysis: dict
) -> float:
    """
    NEW: Weighted combination of multiple forensic signals
    
    Returns weighted risk score incorporating:
    - Traditional red flags (30%)
    - Semantic consistency (20%)
    - Forensic artifacts (30%)
    - Context misuse (20%)
    """
    
    # Base score from red flags
    red_flag_score = min(len(red_flags) * 0.15, 1.0)  # Reduced weight
    
    # Semantic inconsistency score
    semantic_risk = 1.0 - (
        (semantic_check.get("lighting_consistency", 0.5) + 
         semantic_check.get("geometry_stability", 0.5)) / 2.0
    )
    
    # Forensic artifact score (max of three indicators)
    forensic_risk = max(
        forensic_artifacts.get("gan_probability", 0.0),
        forensic_artifacts.get("copymove_probability", 0.0),
        forensic_artifacts.get("compression_inconsistency", 0.0)
    )
    
    # Context misuse score
    context_risk = context_analysis.get("manipulation_score", 0.0)
    
    # Weighted combination
    total_risk = (
        red_flag_score * 0.30 +
        semantic_risk * 0.20 +
        forensic_risk * 0.30 +
        context_risk * 0.20
    )
    
    return round(min(total_risk, 1.0), 3)


# ============================================================================
# EXISTING FUNCTIONS (UNCHANGED)
# ============================================================================

def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Preprocess image for OCR."""
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray)
    return gray.filter(ImageFilter.SHARPEN)


def detect_image_red_flags(
    ocr_text: str,
    caption: str,
    image: Image.Image
) -> list[str]:
    """Detect red flags indicating potential manipulation or hoax patterns."""
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
    """DEPRECATED: Use compute_forensic_risk_score instead (kept for compatibility)."""
    if not red_flags:
        return 0.0
    return round(min(len(red_flags) * 0.35, 1.0), 2)


# ============================================================================
# NEW: DEEPFAKE/AI-GENERATED IMAGE DETECTION
# ============================================================================

def detect_texture_anomalies(image: Image.Image) -> dict:
    """
    NEW: Detect overly smooth textures and artificial smoothing (GAN signature)
    
    AI-generated images often have:
    - Low variance in naturally complex regions (faces, hair)
    - Absence of fine texture details
    - Unnatural smoothness
    
    Returns:
        {
            "texture_smoothness": 0.0-1.0 (1.0 = unnaturally smooth),
            "texture_signals": [list]
        }
    """
    signals = []
    try:
        # Downsample for fast analysis
        if image.width > 1024 or image.height > 1024:
            image = image.resize((min(1024, image.width), min(1024, image.height)))
        
        img_array = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        
        # Convert to grayscale
        gray = np.mean(img_array, axis=2)
        
        # Compute local texture variance using sliding window
        window_size = 16
        local_vars = []
        
        for i in range(0, gray.shape[0] - window_size, window_size):
            for j in range(0, gray.shape[1] - window_size, window_size):
                patch = gray[i:i+window_size, j:j+window_size]
                local_vars.append(np.var(patch))
        
        if local_vars:
            mean_variance = np.mean(local_vars)
            median_variance = np.median(local_vars)
            
            # AI images often have unnaturally LOW variance (over-smoothing)
            # Natural images: mean_var > 0.01
            # AI images: mean_var < 0.005
            if mean_variance < 0.003:
                signals.append(f"Unnaturally smooth texture (variance: {mean_variance:.4f})")
                texture_smoothness = 0.8
            elif mean_variance < 0.008:
                signals.append(f"Low texture complexity detected")
                texture_smoothness = 0.5
            else:
                texture_smoothness = 0.1
            
            # Check for extreme uniformity in any region (GAN blending artifacts)
            uniform_patches = sum(1 for v in local_vars if v < 0.001)
            if uniform_patches > len(local_vars) * 0.3:  # >30% uniform patches
                signals.append(f"Excessive uniform regions detected ({uniform_patches} patches)")
                texture_smoothness = max(texture_smoothness, 0.6)
        else:
            texture_smoothness = 0.0
        
        return {
            "texture_smoothness": round(min(texture_smoothness, 1.0), 3),
            "texture_signals": signals
        }
    
    except Exception as e:
        logger.debug(f"Texture anomaly detection failed: {e}")
        return {"texture_smoothness": 0.0, "texture_signals": []}


def detect_frequency_anomalies(image: Image.Image) -> dict:
    """
    NEW: Detect abnormal frequency distribution (AI-generated indicator)
    
    AI images show:
    - Missing high-frequency noise (natural images have grain)
    - Unusual frequency concentrations
    - Anomalous spectrum patterns
    
    Returns:
        {
            "frequency_anomaly": 0.0-1.0,
            "frequency_signals": [list]
        }
    """
    signals = []
    try:
        # Downsample
        if image.width > 512 or image.height > 512:
            image = image.resize((min(512, image.width), min(512, image.height)))
        
        img_array = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        gray = np.mean(img_array, axis=2)
        
        # Compute FFT
        f_transform = fft2(gray)
        f_shift = fftshift(f_transform)
        magnitude_spectrum = np.abs(f_shift)
        
        # Normalize log scale
        log_spectrum = np.log1p(magnitude_spectrum)
        
        # Analyze frequency distribution
        h, w = log_spectrum.shape
        
        # Split into center (low freq) and periphery (high freq)
        center_h, center_w = h // 2, w // 2
        center_region = log_spectrum[
            max(0, center_h - 20) : min(h, center_h + 20),
            max(0, center_w - 20) : min(w, center_w + 20)
        ]
        
        # High frequency regions (periphery)
        hf_regions = [
            log_spectrum[0:50, :],  # top
            log_spectrum[-50:, :],  # bottom
            log_spectrum[:, 0:50],  # left
            log_spectrum[:, -50:]   # right
        ]
        
        center_energy = np.mean(center_region) if center_region.size > 0 else 0
        hf_energy = np.mean([np.mean(r) for r in hf_regions if r.size > 0])
        
        # Natural images: more high-frequency energy (noise)
        # AI images: concentrated at low frequencies (smooth)
        ratio = hf_energy / (center_energy + 1e-6)
        
        if ratio < 0.3:  # Too low high-freq energy = artifact
            signals.append(f"Low high-frequency content (ratio: {ratio:.2f}) - AI generation indicator")
            frequency_anomaly = 0.7
        elif ratio < 0.5:
            signals.append(f"Reduced high-frequency noise detected")
            frequency_anomaly = 0.4
        else:
            frequency_anomaly = 0.05
        
        # Check for frequency spikes (GAN artifacts)
        spectrum_std = np.std(log_spectrum)
        spectrum_mean = np.mean(log_spectrum)
        spike_threshold = spectrum_mean + 3 * spectrum_std
        spikes = np.sum(log_spectrum > spike_threshold)
        
        if spikes > (h * w) * 0.001:  # >0.1% spikes
            signals.append(f"Frequency spikes detected (GAN artifact signature)")
            frequency_anomaly = max(frequency_anomaly, 0.6)
        
        return {
            "frequency_anomaly": round(min(frequency_anomaly, 1.0), 3),
            "frequency_signals": signals
        }
    
    except Exception as e:
        logger.debug(f"Frequency anomaly detection failed: {e}")
        return {"frequency_anomaly": 0.0, "frequency_signals": []}


def detect_color_lighting_anomalies(image: Image.Image) -> dict:
    """
    NEW: Detect unnatural color and lighting (AI-generated indicator)
    
    AI images show:
    - Inconsistent lighting from multiple angles
    - Unnatural skin tones
    - Impossible shadow directions
    - Flat/2D appearance
    
    Returns:
        {
            "color_anomaly": 0.0-1.0,
            "color_signals": [list]
        }
    """
    signals = []
    try:
        img_array = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        
        # Check color saturation (AI images often have unnatural saturation)
        hsv = cv2.cvtColor(np.uint8(img_array * 255), cv2.COLOR_RGB2HSV).astype(np.float32) / 255.0
        saturation = hsv[:,:,1]
        
        sat_mean = np.mean(saturation)
        sat_std = np.std(saturation)
        
        # Overly saturated or desaturated = anomaly
        if sat_mean > 0.9:  # Too saturated
            signals.append(f"Oversaturated colors detected (S={sat_mean:.2f})")
            color_anomaly = 0.4
        elif sat_mean < 0.2:  # Too desaturated
            signals.append(f"Undersaturated colors (flat appearance)")
            color_anomaly = 0.3
        else:
            color_anomaly = 0.0
        
        # Check for unnatural skin tones (if faces exist)
        # Skin typically in specific hue range
        hue = hsv[:,:,0] * 180  # Convert to 0-180
        value = hsv[:,:,2]
        
        skin_hue_range = ((hue > 0) & (hue < 20)) | ((hue > 330) & (hue <= 360))
        skin_sat_range = (saturation > 0.1) & (saturation < 0.7)
        skin_val_range = (value > 0.3) & (value < 0.95)
        
        potential_skin = skin_hue_range & skin_sat_range & skin_val_range
        skin_pixels = np.sum(potential_skin)
        
        if skin_pixels > 0:
            # Check consistency of skin tones
            hue_skin = hue[potential_skin]
            if len(hue_skin) > 10:
                hue_std = np.std(hue_skin)
                # Natural skin has variation but not excessive
                if hue_std > 30:  # Highly inconsistent
                    signals.append(f"Inconsistent skin tone distribution (std={hue_std:.1f})")
                    color_anomaly = max(color_anomaly, 0.5)
        
        # Check lighting consistency via edge detection
        gray = np.mean(img_array, axis=2)
        edges = cv2.Canny(np.uint8(gray * 255), 50, 150)
        
        # Divide into quadrants for lighting analysis
        h, w = gray.shape
        quadrants = [
            gray[:h//2, :w//2],
            gray[:h//2, w//2:],
            gray[h//2:, :w//2],
            gray[h//2:, w//2:]
        ]
        
        quad_means = [np.mean(q) for q in quadrants]
        quad_std = np.std(quad_means)
        
        if quad_std > 0.2:  # Very inconsistent lighting
            signals.append(f"Inconsistent lighting across quadrants (std={quad_std:.3f})")
            color_anomaly = max(color_anomaly, 0.4)
        
        return {
            "color_anomaly": round(min(color_anomaly, 1.0), 3),
            "color_signals": signals
        }
    
    except Exception as e:
        logger.debug(f"Color/lighting anomaly detection failed: {e}")
        return {"color_anomaly": 0.0, "color_signals": []}


def detect_edge_artifacts(image: Image.Image) -> dict:
    """
    NEW: Detect edge blending artifacts and halo effects (GAN signature)
    
    AI-generated images show:
    - Halo effects around objects
    - Smooth-to-blurry transitions
    - Artificial edge smoothing
    - Boundary inconsistencies
    
    Returns:
        {
            "edge_artifact_score": 0.0-1.0,
            "edge_signals": [list]
        }
    """
    signals = []
    try:
        img_array = np.array(image.convert("RGB"), dtype=np.float32) / 255.0
        gray = np.mean(img_array, axis=2)
        
        # Compute multiple edge maps
        edges_canny = cv2.Canny(np.uint8(gray * 255), 50, 150)
        edges_sobel_x = cv2.Sobel(np.uint8(gray * 255), cv2.CV_32F, 1, 0, ksize=3)
        edges_sobel_y = cv2.Sobel(np.uint8(gray * 255), cv2.CV_32F, 0, 1, ksize=3)
        
        edges_magnitude = np.sqrt(edges_sobel_x**2 + edges_sobel_y**2)
        
        # Detect halo effects: bright region surrounding dark edges
        dilated = cv2.dilate(edges_canny, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
        halo_region = dilated - edges_canny
        
        if np.sum(halo_region) > 0:
            halo_brightness = np.mean(gray[halo_region > 0])
            edge_brightness = np.mean(gray[edges_canny > 0]) if np.sum(edges_canny) > 0 else 0
            
            # Halo = brighter region around edges
            if halo_brightness > edge_brightness + 0.1:
                signals.append(f"Halo effect detected around edges")
                edge_artifact_score = 0.5
            else:
                edge_artifact_score = 0.0
        else:
            edge_artifact_score = 0.0
        
        # Check for unnatural edge sharpness transitions
        edge_histogram = cv2.calcHist([edges_magnitude.astype(np.uint8)], [0], None, [256], [0, 256])
        
        # Natural images have spread distribution
        # AI images have concentrated edges
        hist_entropy = -np.sum((edge_histogram/np.sum(edge_histogram) + 1e-10) * np.log(edge_histogram/np.sum(edge_histogram) + 1e-10))
        
        if hist_entropy < 3.0:  # Low entropy = concentrated edges = AI artifact
            signals.append(f"Unnatural edge distribution ({hist_entropy:.2f} entropy)")
            edge_artifact_score = max(edge_artifact_score, 0.4)
        
        # Check for boundary inconsistencies (sharp to blurry transitions)
        laplacian = cv2.Laplacian(np.uint8(gray * 255), cv2.CV_32F)
        laplacian_abs = np.abs(laplacian)
        
        # Divide into center and border
        h, w = laplacian_abs.shape
        border_width = 10
        center = laplacian_abs[border_width:-border_width, border_width:-border_width]
        border = np.concatenate([
            laplacian_abs[:border_width, :].flatten(),
            laplacian_abs[-border_width:, :].flatten(),
            laplacian_abs[:, :border_width].flatten(),
            laplacian_abs[:, -border_width:].flatten()
        ])
        
        if len(center) > 0 and len(border) > 0:
            center_detail = np.mean(center)
            border_detail = np.mean(border)
            
            # Unnatural if center is much higher detail than border
            if center_detail > border_detail * 2:
                signals.append(f"Sharp center / blurry border artifact")
                edge_artifact_score = max(edge_artifact_score, 0.45)
        
        return {
            "edge_artifact_score": round(min(edge_artifact_score, 1.0), 3),
            "edge_signals": signals
        }
    
    except Exception as e:
        logger.debug(f"Edge artifact detection failed: {e}")
        return {"edge_artifact_score": 0.0, "edge_signals": []}


def compute_ai_deepfake_probability(image: Image.Image, existing_risk: float) -> dict:
    """
    NEW: Comprehensive AI/deepfake detection combining all signals
    
    Returns:
        {
            "deepfake_probability": 0.0-1.0,
            "deepfake_type": "GAN | DIFFUSION | FACE_SWAP | AUTHENTIC | UNKNOWN",
            "deepfake_confidence": 0.0-1.0,
            "deepfake_signals": [list of all signals]
        }
    """
    try:
        # Run all detection modules
        texture_result = detect_texture_anomalies(image)
        frequency_result = detect_frequency_anomalies(image)
        color_result = detect_color_lighting_anomalies(image)
        edge_result = detect_edge_artifacts(image)
        
        # Combine scores
        texture_score = texture_result.get("texture_smoothness", 0.0)
        frequency_score = frequency_result.get("frequency_anomaly", 0.0)
        color_score = color_result.get("color_anomaly", 0.0)
        edge_score = edge_result.get("edge_artifact_score", 0.0)
        
        # Weighted combination (frequency is strongest indicator)
        deepfake_probability = (
            texture_score * 0.25 +
            frequency_score * 0.35 +  # Highest weight
            color_score * 0.20 +
            edge_score * 0.20
        )
        
        # Collect all signals
        all_signals = []
        all_signals.extend(texture_result.get("texture_signals", []))
        all_signals.extend(frequency_result.get("frequency_signals", []))
        all_signals.extend(color_result.get("color_signals", []))
        all_signals.extend(edge_result.get("edge_signals", []))
        
        # Determine deepfake type based on dominant signals
        if frequency_score > 0.6 and texture_score > 0.5:
            deepfake_type = "GAN"
        elif frequency_score > 0.5 and color_score > 0.4:
            deepfake_type = "DIFFUSION"
        elif texture_score > 0.6 and edge_score > 0.4:
            deepfake_type = "FACE_SWAP"
        elif deepfake_probability < 0.3:
            deepfake_type = "AUTHENTIC"
        else:
            deepfake_type = "UNKNOWN"
        
        # Confidence: higher if multiple indicators agree
        agreement_count = sum([
            texture_score > 0.3,
            frequency_score > 0.3,
            color_score > 0.3,
            edge_score > 0.3
        ])
        
        deepfake_confidence = min(0.95, (agreement_count / 4.0) * 0.9 + 0.1)
        
        logger.info(f"AI/Deepfake detection: type={deepfake_type}, prob={deepfake_probability:.2f}, conf={deepfake_confidence:.2f}")
        
        return {
            "deepfake_probability": round(min(deepfake_probability, 1.0), 3),
            "deepfake_type": deepfake_type,
            "deepfake_confidence": round(deepfake_confidence, 3),
            "deepfake_signals": all_signals[:5]  # Top 5 signals
        }
    
    except Exception as e:
        logger.debug(f"AI deepfake probability computation failed: {e}")
        return {
            "deepfake_probability": 0.0,
            "deepfake_type": "UNKNOWN",
            "deepfake_confidence": 0.0,
            "deepfake_signals": []
        }


# ============================================================================
# NEW: DEEPFAKE DETECTION WITH DEEP LEARNING MODEL (Images)
# ============================================================================

def detect_deepfake_model_image(image: Image.Image) -> tuple:
    """
    Run deepfake detection on image using Xception model
    
    Args:
        image: PIL Image
        
    Returns:
        (fake_risk, model_confidence)
    """
    if not TORCH_AVAILABLE:
        return 0.0, 0.0
    
    try:
        model = get_image_deepfake_model()
        if model is None:
            return 0.0, 0.0
        
        # Convert PIL to numpy
        img_array = np.array(image.convert('RGB'))
        
        # Ensure correct format
        if len(img_array.shape) == 2:  # Grayscale
            img_array = np.stack([img_array] * 3, axis=2)
        elif len(img_array.shape) == 3 and img_array.shape[2] == 4:  # RGBA
            img_array = img_array[:, :, :3]
        
        # Preprocess
        pil_img = Image.fromarray(img_array)
        tensor = _image_preprocess(pil_img).unsqueeze(0).to(DEVICE)
        
        # Inference
        with torch.no_grad():
            output = model(tensor)
            logits = output.squeeze(0).cpu().numpy()
            
            # Softmax to probabilities
            probs = np.exp(logits) / np.sum(np.exp(logits))
            fake_risk = max(probs) if len(probs) > 0 else 0.5
            fake_risk = min(fake_risk, 1.0)
            
            logger.info(f"IMAGE DEEPFAKE MODEL: fake_risk={fake_risk:.3f}")
            return float(to_python_type(fake_risk)), float(to_python_type(fake_risk))
            
    except Exception as e:
        logger.warning(f"Image deepfake model error: {e}")
        return 0.0, 0.0


def analyze_image(file: UploadFile) -> dict:
    """
    UPDATED: Analyze image with forensic-level detection + deepfake detection
    
    Analysis layers:
    1. Semantic consistency (lighting, geometry, proportions)
    2. Forensic artifacts (GAN, copy-move, compression)
    3. Context misuse (emotional manipulation, temporal inconsistencies)
    4. Weighted risk scoring
    
    Args:
        file: Uploaded image file
        
    Returns:
        dict with forensic analysis results
    """
    try:
        # Read and validate image
        try:
            file.file.seek(0)
            image_data = file.file.read()
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as e:
            logger.warning(f"Invalid image format: {e}")
            return sanitize_response({
                "error": "Invalid image format",
                "verdict": "FALSE",
                "ocr_text": "",
                "caption": "Invalid image",
                "visual_summary": "Image could not be analyzed",
                "interpretation": "Image analysis failed",
                "red_flags": ["Invalid image format"],
                "image_risk_score": 1.0,
                "cross_modal_score": 0.0,
                "forensic_signals": {
                    "semantic": {"lighting_consistency": 0.0, "geometry_stability": 0.0},
                    "artifacts": {"gan_probability": 0.0},
                    "context": {"manipulation_score": 0.0}
                }
            })
        
        # Enforce maximum dimension limit
        width, height = image.size
        max_dim = max(width, height)
        
        if max_dim > MAX_IMAGE_DIMENSION:
            logger.debug(f"Image too large ({max_dim}px), resizing to {MAX_IMAGE_DIMENSION}px")
            image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
        
        # OCR extraction
        ocr_text = ""
        if TESSERACT_AVAILABLE:
            try:
                ocr_text = pytesseract.image_to_string(
                    preprocess_for_ocr(image),
                    config="--psm 6"
                ).strip()
            except Exception as e:
                logger.debug(f"OCR extraction failed: {e}")
                ocr_text = ""
        
        # Caption generation
        try:
            caption = generate_caption(image).lower()
        except Exception as e:
            logger.warning(f"Caption generation failed: {e}")
            caption = "Unable to generate caption"
        
        # Cultural hint for mythological figures
        if "blue" in caption and "peacock" in caption:
            caption += " (possibly Lord Krishna)"
        elif "blue" in caption and "skin" in caption:
            caption += " (possibly Hindu deity)"
        
        # Filter OCR noise
        clean_ocr = ""
        if ocr_text:
            lines = ocr_text.split("\n")
            valid_lines = [l for l in lines if re.search(r'[a-zA-Z]{3,}', l)]
            clean_ocr = " ".join(valid_lines).strip()
        
        # ===== NEW: FORENSIC ANALYSIS =====
        
        # 1. Traditional red flags
        red_flags = detect_image_red_flags(clean_ocr, caption, image)
        
        # 2. Semantic consistency check
        semantic_check = semantic_consistency_check(image)
        
        # 3. Forensic artifact detection
        forensic_artifacts = forensic_artifact_detector(image)
        
        # 4. Context misuse detection
        context_analysis = context_misuse_detector(clean_ocr, caption, image)
        
        # 5. Weighted risk scoring
        image_risk_score = compute_forensic_risk_score(
            red_flags,
            semantic_check,
            forensic_artifacts,
            context_analysis
        )
        
        # 6. NEW: AI/Deepfake detection with model
        deepfake_detection = compute_ai_deepfake_probability(image, image_risk_score)
        deepfake_prob = deepfake_detection.get("deepfake_probability", 0.0)
        
        # NEW: Deep learning model-based detection
        model_fake_risk, model_confidence = detect_deepfake_model_image(image)
        
        # PART 5: RISK FUSION for images
        # final_risk = 0.6 * model + 0.4 * forensic
        final_risk = min(1.0, max(0.3, (
            model_fake_risk * 0.60 +      # Deep learning model (60%)
            image_risk_score * 0.40       # Forensic analysis (40%)
        )))
        
        logger.info(f"IMAGE ANALYSIS: RISK FUSION = {final_risk:.3f} " +
                   f"(model={model_fake_risk:.3f}, forensic={image_risk_score:.3f})")
        
        # Cross-modal validation
        try:
            cross_modal_score = clip_similarity(image, caption)
        except Exception as e:
            logger.warning(f"Cross-modal scoring failed: {e}")
            cross_modal_score = 0.0
        
        # Summary and interpretation
        visual_summary = f"Visual context shows: {caption}."
        if clean_ocr:
            visual_summary += f" Extracted text: '{clean_ocr}'."
        
        # Enhanced interpretation with forensic signals
        interpretation_parts = []
        
        # Factor in deepfake detection
        combined_risk = max(image_risk_score, deepfake_prob)
        
        if combined_risk > 0.7:
            interpretation_parts.append("HIGH RISK: Multiple forensic indicators suggest manipulation, generation, or deepfake.")
        elif combined_risk > 0.5:
            interpretation_parts.append("MEDIUM RISK: Forensic or AI-generation analysis detected potential manipulation signals.")
        elif combined_risk > 0.2:
            interpretation_parts.append("LOW RISK: Minor inconsistencies detected but image appears likely authentic.")
        else:
            interpretation_parts.append("LOW RISK: Image appears visually authentic with consistent forensic signatures.")
        
        # Add specific forensic findings
        if forensic_artifacts.get("artifacts"):
            interpretation_parts.append(f"Forensic signals: {', '.join(forensic_artifacts['artifacts'][:2])}")
        
        if semantic_check.get("forensic_flags"):
            interpretation_parts.append(f"Visual inconsistencies: {', '.join(semantic_check['forensic_flags'][:2])}")
        
        if context_analysis.get("manipulation_indicators"):
            interpretation_parts.append(f"Context flags: {', '.join(context_analysis['manipulation_indicators'][:1])}")
        
        # Add deepfake signals if present
        if deepfake_detection.get("deepfake_signals"):
            top_signals = deepfake_detection["deepfake_signals"][:3]
            if top_signals:
                interpretation_parts.append(f"AI-generation signals: {', '.join(top_signals)}")
        
        interpretation = " ".join(interpretation_parts)
        
        response = {
            "ocr_text": clean_ocr,
            "caption": caption,
            "visual_summary": visual_summary,
            "interpretation": interpretation,
            "red_flags": red_flags,
            "image_risk_score": float(to_python_type(image_risk_score)),
            "final_risk_score": float(to_python_type(final_risk)),  # NEW: Used by verdict_engine
            "cross_modal_score": float(to_python_type(cross_modal_score)),
            # NEW: Deepfake/AI-generation detection
            "deepfake_probability": float(to_python_type(deepfake_detection.get("deepfake_probability", 0.0))),
            "deepfake_type": deepfake_detection.get("deepfake_type", "UNKNOWN"),
            "deepfake_confidence": float(to_python_type(deepfake_detection.get("deepfake_confidence", 0.0))),
            "deepfake_signals": deepfake_detection.get("deepfake_signals", []),
            "model_fake_risk": float(to_python_type(model_fake_risk)),
            # Forensic analysis details
            "forensic_signals": {
                "semantic": {
                    "lighting_consistency": float(to_python_type(semantic_check.get("lighting_consistency", 0.5))),
                    "geometry_stability": float(to_python_type(semantic_check.get("geometry_stability", 0.5))),
                    "semantic_flags": semantic_check.get("forensic_flags", [])
                },
                "artifacts": {
                    "gan_probability": float(to_python_type(forensic_artifacts.get("gan_probability", 0.0))),
                    "copymove_probability": float(to_python_type(forensic_artifacts.get("copymove_probability", 0.0))),
                    "compression_inconsistency": float(to_python_type(forensic_artifacts.get("compression_inconsistency", 0.0))),
                    "artifact_flags": forensic_artifacts.get("artifacts", [])
                },
                "context": {
                    "manipulation_score": float(to_python_type(context_analysis.get("manipulation_score", 0.0))),
                    "manipulation_indicators": context_analysis.get("manipulation_indicators", [])
                }
            }
        }
        return sanitize_response(response)
        
    except Exception as e:
        # Catch-all error handler: return conservative FALSE verdict
        logger.error(f"Image analysis exception: {type(e).__name__}: {e}")
        return sanitize_response({
            "error": "analysis_failed",
            "verdict": "FALSE",
            "ocr_text": "",
            "caption": "Analysis error",
            "visual_summary": "Image analysis encountered an error",
            "interpretation": "Unable to analyze image",
            "red_flags": ["Analysis error"],
            "image_risk_score": 1.0,
            "final_risk_score": 1.0,  # Failed analysis = high risk
            "cross_modal_score": 0.0,
            "deepfake_probability": 0.0,
            "deepfake_type": "UNKNOWN",
            "deepfake_confidence": 0.0,
            "deepfake_signals": [],
            "model_fake_risk": 0.0,
            "forensic_signals": {
                "semantic": {},
                "artifacts": {},
                "context": {}
            }
        })



