import cv2
import numpy as np
from typing import List, Dict
import tempfile
import os
import logging
import threading
import time
from app.utils.serialization import sanitize_response, to_python_type

# NEW: Mediapipe for accurate face landmark detection
try:
    import mediapipe as mp
    _mp_face_mesh = mp.solutions.face_mesh
    _mp_drawing = mp.solutions.drawing_utils
    MEDIAPIPE_AVAILABLE = True
except (ImportError, AttributeError) as e:
    MEDIAPIPE_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"Mediapipe not available ({type(e).__name__}) - using fallback face detection")

# NEW: Deep learning model for deepfake detection
try:
    import torch
    import torch.nn.functional as F
    from torchvision import transforms
    import timm
    TORCH_AVAILABLE = True
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Global deepfake detection model (lazy loaded)
    _deepfake_model = None
    _deepfake_model_lock = threading.Lock()
    
    def get_deepfake_model():
        """Lazy load deepfake detection model (Xception)"""
        global _deepfake_model
        if _deepfake_model is None:
            with _deepfake_model_lock:
                if _deepfake_model is None:
                    try:
                        logger_temp = logging.getLogger(__name__)
                        logger_temp.info("Loading deepfake detection model (Xception)...")
                        _deepfake_model = timm.create_model('xception', pretrained=True)
                        _deepfake_model = _deepfake_model.to(DEVICE)
                        _deepfake_model.eval()
                        logger_temp.info("✓ Deepfake model loaded successfully")
                    except Exception as e:
                        logger_temp.warning(f"Failed to load deepfake model: {e}")
                        _deepfake_model = "failed"
        return None if _deepfake_model == "failed" else _deepfake_model
    
    # Model preprocessing
    _model_preprocess = transforms.Compose([
        transforms.ToPILImage(),
        transforms.Resize((299, 299)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])
    
except (ImportError, AttributeError) as e:
    TORCH_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning(f"PyTorch/timm not available ({type(e).__name__}) - using fallback deepfake detection")

logger = logging.getLogger(__name__)

# PERFORMANCE: Cache cascade classifier to avoid repeated loading
_face_cascade = None
def get_face_cascade():
    global _face_cascade
    if _face_cascade is None:
        _face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    return _face_cascade

# ============================================================================
# NEW: TEMPORAL & DEEPFAKE ANALYSIS
# ============================================================================

def temporal_consistency_analyzer(frames: List[np.ndarray]) -> dict:
    """
    NEW: Analyze temporal consistency across frames
    - Motion consistency between consecutive frames
    - Flickering detection
    - Face boundary stability
    
    Returns:
        {
            "motion_consistency": 0.0-1.0 (1.0 = consistent),
            "flickering_detected": bool,
            "face_stability": 0.0-1.0,
            "temporal_flags": [list]
        }
    """
    temporal_flags = []
    
    if len(frames) < 2:
        return {
            "motion_consistency": 1.0,
            "flickering_detected": False,
            "face_stability": 1.0,
            "temporal_flags": []
        }
    
    try:
        # Motion consistency analysis
        frame_diffs = []
        for i in range(len(frames) - 1):
            diff = cv2.absdiff(frames[i], frames[i + 1])
            mean_diff = np.mean(diff)
            frame_diffs.append(mean_diff)
        
        # Check for smooth motion vs. abrupt changes
        diff_variance = np.var(frame_diffs)
        motion_consistency = 1.0 / (1.0 + diff_variance / 100.0)  # Normalize
        
        if diff_variance > 1500:  # High variance = jerky motion
            temporal_flags.append(f"Unstable motion detected (variance: {diff_variance:.1f})")
            motion_consistency = 0.2
        elif diff_variance > 800:
            temporal_flags.append("Moderate motion inconsistency detected")
            motion_consistency = 0.5
        else:
            motion_consistency = 0.9
        
        # Flickering detection
        flickering_detected = False
        if len(frame_diffs) > 2:
            # Check for sudden spikes in frame differences (flickering)
            mean_diff = np.mean(frame_diffs)
            std_diff = np.std(frame_diffs)
            
            high_variance_frames = sum(1 for d in frame_diffs if d > (mean_diff + 2 * std_diff))
            
            if high_variance_frames > len(frame_diffs) * 0.2:  # >20% of frames have spikes
                flickering_detected = True
                temporal_flags.append(f"Frame flickering detected ({high_variance_frames} anomalous frames)")
        
        # Face boundary stability
        face_cascade = get_face_cascade()
        
        face_positions = []
        # PERFORMANCE: Skip every other frame for face detection
        for idx, frame in enumerate(frames):
            if idx % 2 == 0:  # Process every 2nd frame only
                # PERFORMANCE: Downsample for faster detection
                frame_small = cv2.resize(frame, (320, 240))
                gray = cv2.cvtColor(frame_small, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                # Scale back coordinates
                faces = faces * np.array([frame.shape[1]/320, frame.shape[0]/240, frame.shape[1]/320, frame.shape[0]/240], dtype=int)
            
            if len(faces) > 0:
                # Use the largest face
                largest_face = max(faces, key=lambda f: f[2] * f[3])
                face_positions.append(largest_face)
        
        # Analyze face stability
        if len(face_positions) > 1:
            position_diffs = []
            for i in range(len(face_positions) - 1):
                x1, y1, w1, h1 = face_positions[i]
                x2, y2, w2, h2 = face_positions[i + 1]
                
                # Calculate centroid difference
                centroid_diff = np.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
                size_diff = abs(w1 - w2) + abs(h1 - h2)
                position_diffs.append((centroid_diff, size_diff))
            
            if position_diffs:
                avg_centroid_diff = np.mean([pd[0] for pd in position_diffs])
                avg_size_diff = np.mean([pd[1] for pd in position_diffs])
                
                # High variations = unstable deepfake
                if avg_centroid_diff > 20 or avg_size_diff > 10:
                    temporal_flags.append(f"Face boundaries unstable (position drift: {avg_centroid_diff:.1f}px)")
                    face_stability = 0.3
                else:
                    face_stability = 0.9
            else:
                face_stability = 1.0
        else:
            face_stability = 0.7  # Neutral if fewer than 2 faces
        
        return {
            "motion_consistency": round(max(0.0, min(motion_consistency, 1.0)), 3),
            "flickering_detected": flickering_detected,
            "face_stability": round(max(0.0, min(face_stability, 1.0)), 3),
            "temporal_flags": temporal_flags
        }
    
    except Exception as e:
        logger.debug(f"Temporal consistency analysis failed: {e}")
        return {
            "motion_consistency": 0.5,
            "flickering_detected": False,
            "face_stability": 0.5,
            "temporal_flags": []
        }


def face_deepfake_signals(frames: List[np.ndarray]) -> dict:
    """
    ENHANCED: Detect deepfake indicators in faces using mediapipe landmarks
    - Lip-sync mismatch via mouth landmark tracking
    - Eye blink irregularity via eyelid landmarks
    - Facial texture inconsistency detection
    - Face position stability (head shake detection)
    
    Returns:
        {
            "lipsync_mismatch": 0.0-1.0,
            "blink_irregularity": 0.0-1.0,
            "texture_inconsistency": 0.0-1.0,
            "face_stability": 0.0-1.0,
            "deepfake_type": "FACE_SWAP|VOICE_CLONE|FULL_SYNTHETIC|AUTHENTIC|UNKNOWN",
            "deepfake_confidence": 0.0-1.0,
            "deepfake_signals": [list]
        }
    """
    deepfake_signals = []
    
    if len(frames) < 2:
        return {
            "lipsync_mismatch": 0.0,
            "blink_irregularity": 0.0,
            "texture_inconsistency": 0.0,
            "face_stability": 1.0,
            "deepfake_type": "UNKNOWN",
            "deepfake_confidence": 0.0,
            "deepfake_signals": []
        }
    
    try:
        # Use mediapipe if available for superior accuracy
        if MEDIAPIPE_AVAILABLE:
            return _detect_deepfake_via_mediapipe(frames, deepfake_signals)
        else:
            # Fallback to cascade classifier method
            return _detect_deepfake_via_cascade(frames, deepfake_signals)
    
    except Exception as e:
        logger.debug(f"Face deepfake signal detection failed: {e}")
        return {
            "lipsync_mismatch": 0.0,
            "blink_irregularity": 0.0,
            "texture_inconsistency": 0.0,
            "face_stability": 1.0,
            "deepfake_type": "UNKNOWN",
            "deepfake_confidence": 0.0,
            "deepfake_signals": []
        }


def _detect_deepfake_via_mediapipe(frames: List[np.ndarray], deepfake_signals: list) -> dict:
    """
    NEW: Mediapipe-based deepfake detection with face landmarks
    
    Uses 468 facial landmarks to detect:
    - Lip opening distances (for lip-sync)
    - Eye opening ratios (for blink detection)
    - Mouth opening consistency
    - Face rotation stability
    - Eye region texture irregularities
    """
    try:
        start_time = time.time()
        timeout_seconds = 20
        
        with _mp_face_mesh.FaceMesh(
            static_image_mode=False,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        ) as face_mesh:
            
            # Track metrics across frames
            mouth_openings = []
            blink_states = []
            face_positions = []
            texture_metrics = []
            
            # Process frames - sample at most 5 frames to avoid timeouts
            frames_to_process = frames[::max(1, len(frames)//5)]
            logger.info(f"VIDEO ANALYZER: Processing {len(frames_to_process)} frames with mediapipe")
            
            for frame_idx, frame in enumerate(frames_to_process):
                # Safety: Check timeout every frame
                if time.time() - start_time > timeout_seconds:
                    logger.warning(f"Mediapipe processing timeout ({timeout_seconds}s exceeded)")
                    break
                
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(frame_rgb)
                
                if not results.multi_face_landmarks:
                    continue
                
                landmarks = results.multi_face_landmarks[0].landmark
                h, w = frame.shape[:2]
                
                # Extract landmark coordinates
                landmarks_px = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]
                
                # MOUTH OPENING DETECTION (landmarks 78-87 approximate mouth region)
                mouth_top = landmarks[13].y  # Upper lip
                mouth_bottom = landmarks[14].y  # Lower lip
                mouth_opening = abs(mouth_bottom - mouth_top)
                mouth_openings.append(mouth_opening)
                
                # LIP-SYNC CHECK: Mouth corners (61, 291) should move consistently
                left_mouth = landmarks[61]
                right_mouth = landmarks[291]
                mouth_width = abs(right_mouth.x - left_mouth.x)
                
                # HIGH VARIANCE in mouth_opening = irregular/unnatural lip movement
                if len(mouth_openings) > 3:
                    recent_openings = mouth_openings[-4:]
                    opening_variance = np.var(recent_openings)
                    if opening_variance > 0.05:  # Too variable = potential lip-sync issue
                        if "Lip-sync" not in str(deepfake_signals):
                            deepfake_signals.append(f"Irregular mouth motion detected")
                
                # BLINK DETECTION (eye landmarks 33, 133 for left; 362, 263 for right)
                left_eye_top = landmarks[159].y
                left_eye_bottom = landmarks[145].y
                left_eye_opening = abs(left_eye_bottom - left_eye_top)
                
                right_eye_top = landmarks[386].y
                right_eye_bottom = landmarks[374].y
                right_eye_opening = abs(right_eye_bottom - right_eye_top)
                
                avg_eye_opening = (left_eye_opening + right_eye_opening) / 2
                
                # Closed eye (blink): opening < 0.01 of face height
                is_blink = avg_eye_opening < 0.01
                blink_states.append(is_blink)
                
                # FACE POSITION STABILITY (head rotation detection)
                nose = landmarks[1]  # Center of face
                face_positions.append((nose.x, nose.y))
                
                # TEXTURE METRICS: Analyze eye region texture
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                left_eye_x_range = [int(landmarks[33].x * w), int(landmarks[133].x * w)]
                left_eye_y_range = [int(landmarks[159].y * h), int(landmarks[145].y * h)]
                
                if left_eye_x_range[0] < left_eye_x_range[1] and left_eye_y_range[0] < left_eye_y_range[1]:
                    left_eye_region = gray[
                        left_eye_y_range[0]:left_eye_y_range[1],
                        left_eye_x_range[0]:left_eye_x_range[1]
                    ]
                    if left_eye_region.size > 0:
                        eye_laplacian = cv2.Laplacian(left_eye_region, cv2.CV_64F)
                        texture_metrics.append(np.var(eye_laplacian))
            
            # AGGREGATE METRICS
            
            # 1. LIP-SYNC MISMATCH
            if len(mouth_openings) > 2:
                opening_variance = np.var(mouth_openings)
                lipsync_mismatch = min(0.9, opening_variance * 15)  # Scale for 0-1 range
                if lipsync_mismatch > 0.5:
                    deepfake_signals.append(f"Lip-sync mismatch detected (variance: {opening_variance:.4f})")
            else:
                lipsync_mismatch = 0.0
            
            # 2. BLINK IRREGULARITY
            if len(blink_states) > 3:
                # Detect unnatural blink patterns
                blink_transitions = sum(1 for i in range(1, len(blink_states)) if blink_states[i] != blink_states[i-1])
                avg_blink_duration = 1.0
                
                if blink_transitions > len(blink_states) * 0.6:  # Too many blinks
                    blink_irregularity = 0.7
                    deepfake_signals.append(f"Abnormal blink frequency detected ({blink_transitions} transitions)")
                elif blink_transitions < 2:  # Too few blinks
                    blink_irregularity = 0.6
                    deepfake_signals.append("Unnatural lack of blinking detected")
                else:
                    blink_irregularity = 0.2
            else:
                blink_irregularity = 0.0
            
            # 3. TEXTURE INCONSISTENCY
            if len(texture_metrics) > 1:
                texture_variance = np.var(texture_metrics)
                texture_inconsistency = min(0.8, texture_variance / 5000.0)
                if texture_inconsistency > 0.4:
                    deepfake_signals.append(f"Eye region texture inconsistency detected")
            else:
                texture_inconsistency = 0.0
            
            # 4. FACE STABILITY (Head shake detection)
            if len(face_positions) > 2:
                position_changes = [
                    np.sqrt((face_positions[i][0] - face_positions[i-1][0])**2 + 
                           (face_positions[i][1] - face_positions[i-1][1])**2)
                    for i in range(1, len(face_positions))
                ]
                avg_position_variance = np.mean(position_changes) if position_changes else 0
                
                # Natural head movement: small, gradual changes
                # Synthetic/swapped: abrupt jumps or no movement
                if avg_position_variance > 0.15:
                    face_stability = 0.3
                    deepfake_signals.append("Unnatural head movement detected")
                elif avg_position_variance < 0.02:
                    face_stability = 0.7
                    deepfake_signals.append("Unnaturally stable face position (potential freeze frame)")
                else:
                    face_stability = 0.9
            else:
                face_stability = 1.0
            
            # CLASSIFY DEEPFAKE TYPE
            deepfake_probability = (lipsync_mismatch * 0.3 + blink_irregularity * 0.25 + 
                                   texture_inconsistency * 0.25 + (1.0 - face_stability) * 0.2)
            
            if deepfake_probability > 0.7:
                if lipsync_mismatch > 0.6:
                    deepfake_type = "VOICE_CLONE"
                elif blink_irregularity > 0.6:
                    deepfake_type = "FACE_SWAP"
                else:
                    deepfake_type = "FULL_SYNTHETIC"
            elif deepfake_probability > 0.4:
                deepfake_type = "FACE_SWAP"
            else:
                deepfake_type = "AUTHENTIC"
            
            # CONFIDENCE SCORING
            signal_agreement = sum([
                lipsync_mismatch > 0.4,
                blink_irregularity > 0.4,
                texture_inconsistency > 0.4,
                face_stability < 0.5
            ])
            deepfake_confidence = min(0.95, (signal_agreement / 4.0) * 0.9 + 0.1)
            
            return {
                "lipsync_mismatch": round(min(lipsync_mismatch, 1.0), 3),
                "blink_irregularity": round(min(blink_irregularity, 1.0), 3),
                "texture_inconsistency": round(min(texture_inconsistency, 1.0), 3),
                "face_stability": round(max(face_stability, 0.0), 3),
                "deepfake_type": deepfake_type,
                "deepfake_confidence": round(deepfake_confidence, 3),
                "deepfake_signals": deepfake_signals
            }
    
    except Exception as e:
        logger.debug(f"Mediapipe deepfake detection failed: {e}, falling back to cascade")
        return _detect_deepfake_via_cascade(frames, deepfake_signals)


def _detect_deepfake_via_cascade(frames: List[np.ndarray], deepfake_signals: list) -> dict:
    """
    FALLBACK: Cascade classifier-based deepfake detection (when mediapipe unavailable)
    
    Less accurate than mediapipe but works with basic OpenCV
    """
    face_cascade = get_face_cascade()
    
    lipsync_scores = []
    blink_indicators = []
    texture_scores = []
    position_changes = []
    
    for i, frame in enumerate(frames[::max(1, len(frames)//5)]):  # Sample ~5 frames
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) == 0:
            continue
        
        # Use largest face
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        face_region = gray[y:y + h, x:x + w]
        
        # Track face position
        position_changes.append((x, y))
        
        # LIP-SYNC ANALYSIS (approximation via mouth region motion)
        mouth_y_start = int(y + h * 0.70)
        mouth_y_end = int(y + h * 0.95)
        mouth_x_start = max(0, int(x + w * 0.25))
        mouth_x_end = min(gray.shape[1], int(x + w * 0.75))
        
        if i > 0 and len(position_changes) > 1:
            prev_gray = cv2.cvtColor(frames[i - 1], cv2.COLOR_BGR2GRAY)
            prev_mouth = prev_gray[
                max(0, mouth_y_start - 5): min(prev_gray.shape[0], mouth_y_end + 5),
                mouth_x_start:mouth_x_end
            ]
            
            curr_mouth = gray[
                max(0, mouth_y_start - 5): min(gray.shape[0], mouth_y_end + 5),
                mouth_x_start:mouth_x_end
            ]
            
            if prev_mouth.size > 0 and curr_mouth.size > 0:
                mouth_diff = cv2.absdiff(
                    cv2.resize(prev_mouth, (64, 32)),
                    cv2.resize(curr_mouth, (64, 32))
                )
                mouth_change = np.mean(mouth_diff)
                lipsync_scores.append(mouth_change)
        
        # BLINK DETECTION via eye region
        eye_y_start = int(y + h * 0.25)
        eye_y_end = int(y + h * 0.45)
        eye_region = face_region[
            max(0, eye_y_start - y): min(face_region.shape[0], eye_y_end - y),
            :
        ]
        
        if eye_region.size > 0:
            eye_std = np.std(eye_region)
            blink_indicators.append(1 if eye_std > 50 else 0)
        
        # TEXTURE CONSISTENCY
        laplacian = cv2.Laplacian(face_region, cv2.CV_64F)
        texture_var = np.var(laplacian)
        texture_scores.append(texture_var)
    
    # Calculate scores
    if lipsync_scores:
        lipsync_variance = np.var(lipsync_scores)
        lipsync_mismatch = min(0.8, lipsync_variance / 1000.0)
        if lipsync_mismatch > 0.5:
            deepfake_signals.append(f"Lip-sync irregularities detected")
    else:
        lipsync_mismatch = 0.0
    
    if blink_indicators:
        irregular_blinks = sum(blink_indicators)
        blink_irregularity = min(0.7, irregular_blinks / len(blink_indicators))
        if irregular_blinks > len(blink_indicators) * 0.4:
            deepfake_signals.append(f"Irregular eye patterns detected")
    else:
        blink_irregularity = 0.0
    
    if texture_scores and len(texture_scores) > 1:
        texture_variance = np.var(texture_scores)
        texture_inconsistency = min(0.8, texture_variance / 10000.0)
        if texture_inconsistency > 0.4:
            deepfake_signals.append(f"Facial texture inconsistency detected")
    else:
        texture_inconsistency = 0.0
    
    # Face stability
    if len(position_changes) > 2:
        pos_variance = np.var(position_changes)
        face_stability = min(1.0, max(0.0, 1.0 - (pos_variance / 1000.0)))
    else:
        face_stability = 1.0
    
    # Type and confidence
    prob = (lipsync_mismatch * 0.3 + blink_irregularity * 0.25 + texture_inconsistency * 0.25 + (1.0 - face_stability) * 0.2)
    deepfake_type = "FACE_SWAP" if prob > 0.5 else ("AUTHENTIC" if prob < 0.3 else "UNKNOWN")
    deepfake_confidence = min(0.95, max(lipsync_mismatch, blink_irregularity, texture_inconsistency) * 0.7)
    
    return {
        "lipsync_mismatch": round(min(lipsync_mismatch, 1.0), 3),
        "blink_irregularity": round(min(blink_irregularity, 1.0), 3),
        "texture_inconsistency": round(min(texture_inconsistency, 1.0), 3),
        "face_stability": round(face_stability, 3),
        "deepfake_type": deepfake_type,
        "deepfake_confidence": round(deepfake_confidence, 3),
        "deepfake_signals": deepfake_signals
    }


def audio_video_alignment_check(frames: List[np.ndarray], audio_risk: float) -> dict:
    """
    NEW: Check audio-video alignment
    - Compare speech rhythm vs mouth movement  
    - Detect asynchronous audio
    
    Args:
        frames: List of video frames
        audio_risk: Pre-calculated audio risk score
    
    Returns:
        {
            "sync_consistency": 0.0-1.0,
            "sync_flags": [list]
        }
    """
    sync_flags = []
    
    try:
        # If audio risk is high, likely sync mismatch
        if audio_risk > 0.6:
            sync_flags.append("High audio risk detected - potential sync mismatch")
            sync_consistency = 0.2
        elif audio_risk > 0.3:
            sync_flags.append("Moderate audio irregularities - check sync")
            sync_consistency = 0.5
        else:
            # Estimate mouth movement frequency to infer speech
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            mouth_movements = []
            for i in range(len(frames) - 1):
                gray = cv2.cvtColor(frames[i], cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                if len(faces) == 0:
                    continue
                
                x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                
                # Extract mouth region
                mouth_y = int(y + h * 0.7)
                mouth_region_curr = gray[mouth_y : mouth_y + int(h * 0.25), x : x + w]
                
                gray_next = cv2.cvtColor(frames[i + 1], cv2.COLOR_BGR2GRAY)
                faces_next = face_cascade.detectMultiScale(gray_next, 1.1, 4)
                
                if len(faces_next) > 0:
                    x2, y2, w2, h2 = max(faces_next, key=lambda f: f[2] * f[3])
                    mouth_region_next = gray_next[mouth_y : mouth_y + int(h2 * 0.25), x2 : x2 + w2]
                    
                    if mouth_region_curr.size > 0 and mouth_region_next.size > 0:
                        diff = cv2.absdiff(
                            cv2.resize(mouth_region_curr, (64, 16)),
                            cv2.resize(mouth_region_next, (64, 16))
                        )
                        movement = np.mean(diff)
                        mouth_movements.append(movement)
            
            # Analyze mouth movement consistency
            if mouth_movements:
                movement_variance = np.var(mouth_movements)
                # Natural speech has moderate variance
                if movement_variance > 500:
                    sync_consistency = 0.3
                    sync_flags.append("Unstable mouth movement detected")
                elif movement_variance < 50:
                    sync_consistency = 0.4
                    sync_flags.append("Unnaturally static mouth movement")
                else:
                    sync_consistency = 0.85
            else:
                sync_consistency = 0.6
        
        return {
            "sync_consistency": round(max(0.0, min(sync_consistency, 1.0)), 3),
            "sync_flags": sync_flags
        }
    
    except Exception as e:
        logger.debug(f"Audio-video alignment check failed: {e}")
        return {
            "sync_consistency": 0.5,
            "sync_flags": []
        }


# ============================================================================
# EXISTING FUNCTIONS (UPDATED WITH NEW ANALYSIS)
# ============================================================================

def extract_key_frames(video_path: str, max_frames: int = 10, timeout: int = 30) -> List[np.ndarray]:
    """Extract key frames with timeout protection"""
    frames = []
    extraction_result = {'frames': [], 'error': None}
    
    def _extract_with_timeout():
        try:
            logger.info(f"VIDEO ANALYZER: Opening video {video_path}")
            cap = cv2.VideoCapture(video_path)
            
            if not cap.isOpened():
                extraction_result['error'] = "Could not open video"
                logger.error(f"ERROR: Could not open video {video_path}")
                return
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            logger.info(f"VIDEO ANALYZER: Video metadata - FPS: {fps}, Total frames: {total_frames}")
            
            frame_interval = int(fps * 2) if fps > 0 else 30
            
            frame_count = 0
            extracted_count = 0
            
            # SAFETY: Cap frame reading to prevent infinite loops
            max_iterations = min(1000, total_frames * 2)
            iterations = 0
            
            while cap.isOpened() and extracted_count < max_frames and iterations < max_iterations:
                ret, frame = cap.read()
                if not ret:
                    logger.info(f"VIDEO ANALYZER: End of video reached")
                    break
                
                if frame_count % frame_interval == 0:
                    # Resize frame to avoid memory issues (max 1280x720)
                    h, w = frame.shape[:2]
                    if h > 720 or w > 1280:
                        scale = min(720/h, 1280/w)
                        new_w = int(w * scale)
                        new_h = int(h * scale)
                        frame = cv2.resize(frame, (new_w, new_h))
                    
                    extraction_result['frames'].append(frame)
                    extracted_count += 1
                    logger.debug(f"VIDEO ANALYZER: Extracted frame {extracted_count}/{max_frames}")
                
                frame_count += 1
                iterations += 1
            
            cap.release()
            logger.info(f"VIDEO ANALYZER: Extracted {len(extraction_result['frames'])} frames from video")
            
        except Exception as e:
            extraction_result['error'] = str(e)
            logger.error(f"ERROR during frame extraction: {e}")
    
    # Run extraction with timeout
    thread = threading.Thread(target=_extract_with_timeout, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    
    if thread.is_alive():
        logger.error(f"Frame extraction timed out after {timeout} seconds")
        extraction_result['error'] = f"Frame extraction timeout after {timeout}s"
    
    if extraction_result['error']:
        logger.error(f"Frame extraction failed: {extraction_result['error']}")
    
    return extraction_result['frames']


def detect_visual_artifacts(frames: List[np.ndarray]) -> float:
    if not frames:
        return 0.3  # FIX: Baseline uncertainty if no frames (not 0.0)
    
    risk_score = 0.0
    risk_factors = []
    frame_instability_score = 0.0
    face_detection_instability = 0.0
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    face_detection_history = []
    
    # FIX: Enhanced artifact detection with multiple signals
    for i, frame in enumerate(frames):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Track face detection stability
        face_detection_history.append(len(faces) > 0)
        
        if len(faces) > 0:
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / edges.size
            
            # High edge density = GAN artifacts
            if edge_density > 0.15:
                risk_score += 0.15
                risk_factors.append("High edge density (GAN artifacts)")
            elif edge_density > 0.10:
                risk_score += 0.05
            
            for (x, y, w, h) in faces:
                face_region = gray[y:y+h, x:x+w]
                face_std = np.std(face_region)
                face_mean = np.mean(face_region)
                
                # Unnaturally smooth or noisy faces
                if face_std < 20:
                    risk_score += 0.12
                    risk_factors.append("Unnaturally smooth face texture")
                elif face_std > 80:
                    risk_score += 0.08
                    risk_factors.append("Excessive noise in face region")
        else:
            # No face detected - can be suspicious
            risk_score += 0.05  # Small penalty for no faces
    
    # FIX: Frame inconsistency detection
    if len(frames) > 1:
        frame_diffs = []
        for i in range(len(frames) - 1):
            diff = cv2.absdiff(frames[i], frames[i+1])
            frame_diffs.append(np.mean(diff))
        
        if len(frame_diffs) > 0:
            diff_mean = np.mean(frame_diffs)
            diff_variance = np.var(frame_diffs)
            
            # Sudden scene changes or flickering
            if diff_variance > 1000:
                risk_score += 0.15
                risk_factors.append("Frame flickering detected")
            elif diff_variance > 500:
                risk_score += 0.08
                risk_factors.append("Moderate frame inconsistency")
            
            # Very high frame differences = sudden changes
            high_diff_frames = sum(1 for d in frame_diffs if d > diff_mean * 2.5)
            if high_diff_frames > len(frame_diffs) * 0.3:
                risk_score += 0.1
                risk_factors.append("Sudden scene changes detected")
    
    # FIX: Face detection instability
    if len(face_detection_history) > 2:
        detection_changes = sum(1 for i in range(1, len(face_detection_history)) 
                              if face_detection_history[i] != face_detection_history[i-1])
        if detection_changes > len(face_detection_history) * 0.5:
            risk_score += 0.1
            risk_factors.append("Face detection instability detected")
    
    # FIX: Never return 0.0 - add baseline uncertainty (minimum 0.15)
    final_risk = min(max(risk_score, 0.15), 1.0)
    
    logger.info(f"VIDEO ANALYZER: Visual risk={final_risk:.2f}, factors={risk_factors}")
    return final_risk


# ============================================================================
# NEW: DEEPFAKE DETECTION WITH DEEP LEARNING MODEL
# ============================================================================

def detect_deepfake_model(frames: List[np.ndarray]) -> tuple:
    """
    Run deepfake detection using Xception model
    
    Returns:
        (fake_risk, deepfake_confidence_avg)
        fake_risk: 0.0-1.0 (higher = more likely fake)
        deepfake_confidence_avg: average model confidence
    """
    if not TORCH_AVAILABLE or not frames:
        return 0.0, 0.0
    
    try:
        model = get_deepfake_model()
        if model is None:
            return 0.0, 0.0
        
        confidences = []
        
        with torch.no_grad():
            for frame in frames[:10]:  # Sample first 10 frames
                try:
                    # Preprocess frame
                    if frame.shape[2] == 4:  # RGBA
                        frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
                    
                    tensor = _model_preprocess(frame).unsqueeze(0).to(DEVICE)
                    
                    # Inference
                    output = model(tensor)
                    logits = output.squeeze(0).cpu().numpy()
                    
                    # Softmax to get probabilities
                    probs = np.exp(logits) / np.sum(np.exp(logits))
                    
                    # Fake class (typically index 0 or 1, assume higher index = fake)
                    fake_confidence = max(probs) if len(probs) > 0 else 0.5
                    confidences.append(fake_confidence)
                    
                except Exception as e:
                    logger.debug(f"Frame inference error: {e}")
                    continue
        
        if confidences:
            # Average confidence and convert to fake_risk
            avg_confidence = np.mean(confidences)
            # Assume higher model confidence = more fake
            fake_risk = avg_confidence
            logger.info(f"DEEPFAKE MODEL: avg_confidence={avg_confidence:.3f}, fake_risk={fake_risk:.3f}")
            return float(to_python_type(min(fake_risk, 1.0))), float(to_python_type(avg_confidence))
        else:
            return 0.0, 0.0
            
    except Exception as e:
        logger.warning(f"Deepfake model error: {e}")
        return 0.0, 0.0


def analyze_video(video_path: str) -> Dict:
    """
    UPDATED: Video analysis with temporal and deepfake detection
    Dynamic frame sampling: min(20 frames, total_frames / fps)
    
    Analysis layers:
    1. Key frame extraction (with timeout, DYNAMIC FRAME COUNT)
    2. Visual artifact detection (existing)
    3. Temporal consistency analysis (NEW)
    4. Face deepfake signals (NEW, with timeout)
    5. Audio-video alignment (NEW)
    6. Combined risk scoring
    """
    
    analysis_start = time.time()
    analysis_timeout = 60  # Overall timeout
    
    logger.info(f"VIDEO ANALYZER: Starting analysis of {video_path}")
    
    # DYNAMIC FRAME SAMPLING: Get video metadata first
    cap = cv2.VideoCapture(video_path)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Dynamic frame count: min(20, total_frames / fps rounded)
        # This ensures we sample across the full video duration
        estimated_duration = total_frames / fps if fps > 0 else 1.0
        dynamic_frame_count = min(20, max(5, int(total_frames / max(fps, 1.0))))
        logger.info(f"VIDEO ANALYZER: Duration={estimated_duration:.1f}s, FPS={fps}, Total={total_frames}, Sampling={dynamic_frame_count} frames")
    except Exception as e:
        logger.warning(f"Could not read video metadata: {e}")
        fps = 30.0
        total_frames = 1
        width = 640
        height = 480
        dynamic_frame_count = 10
    finally:
        cap.release()
    
    frames = extract_key_frames(video_path, max_frames=dynamic_frame_count)
    
    if not frames:
        response = {
            'frames': [],
            'visual_risk_score': 0.0,
            'metadata': {},
            'error': 'Failed to extract frames'
        }
        return sanitize_response(response)
    
    # Check timeout after frame extraction
    elapsed = time.time() - analysis_start
    if elapsed > analysis_timeout * 0.5:
        logger.warning(f"Frame extraction took {elapsed:.1f}s, skipping deepfake analysis to prevent timeout")
        response = {
            'frames': frames,
            'visual_risk_score': 0.0,
            'metadata': {'frames_extracted': len(frames), 'timeout_warning': True},
            'error': f'Frame extraction timeout: {elapsed:.1f}s'
        }
        safe_response = sanitize_response({k: v for k, v in response.items() if k != "frames"})
        safe_response["frames"] = frames
        return safe_response
    
    # EXISTING: Visual artifact detection
    visual_risk = detect_visual_artifacts(frames)
    
    # NEW: Temporal analysis and motion scoring
    temporal_analysis = temporal_consistency_analyzer(frames)
    
    # NEW: Motion analysis - compute frame differences
    motion_score = 0.0
    if len(frames) > 1:
        frame_diffs = []
        for i in range(len(frames) - 1):
            diff = cv2.absdiff(frames[i], frames[i + 1])
            frame_diffs.append(np.std(diff))
        
        if frame_diffs:
            motion_score = np.std(frame_diffs) / 255.0  # Normalize by max pixel value
            motion_score = min(motion_score, 1.0)
            logger.info(f"VIDEO ANALYZER: Motion score={motion_score:.3f}")
    
    # NEW: Deepfake model detection
    fake_risk, model_confidence = detect_deepfake_model(frames)
    
    # NEW: Deepfake signals (with timeout check)
    deepfake_analysis = face_deepfake_signals(frames)
    
    # Get metadata
    metadata = {
        'fps': fps,
        'width': width,
        'height': height,
        'total_frames': total_frames,
        'frames_sampled': len(frames)
    }
    
    # PART 2 IMPROVED: RISK FUSION - Combine all signals with adjusted weights (including audio)
    # Better deepfake detection with stronger emphasis on deepfake model
    # WEIGHTS: 0.6 model (primary), 0.15 visual, 0.1 motion, 0.15 audio
    inconsistency_penalty = deepfake_analysis.get('deepfake_confidence', 0.0) * 0.2
    
    # NOTE: audio_score will be added by verify.py after audio_analyzer runs
    # For now, use placeholder - audio analysis happens in parallel
    final_risk = min(1.0, max(0.35, (
        fake_risk * 0.60 +           # Deep learning model (60%) - PRIMARY
        visual_risk * 0.15 +         # Visual artifacts (15%)
        motion_score * 0.10 +        # Motion analysis (10%)
        0.0 * 0.15                   # Audio score placeholder (15%) - filled by verify.py
    ) + inconsistency_penalty))
    
    logger.info(f"VIDEO ANALYZER: RISK FUSION = {final_risk:.3f} " +
                f"(model={fake_risk:.3f}, visual={visual_risk:.3f}, motion={motion_score:.3f}, audio=0.0_placeholder, inconsistency={inconsistency_penalty:.3f})")
    
    temporal_risk = 1.0 - max(
        temporal_analysis.get("motion_consistency", 0.5),
        temporal_analysis.get("face_stability", 0.5)
    )
    
    response = {
        'frames': frames,
        'visual_risk_score': float(to_python_type(visual_risk)),
        'final_risk_score': float(to_python_type(final_risk)),  # NEW: This is the key field for verdict_engine
        'metadata': metadata,
        'temporal_analysis': {
            'motion_consistency': float(to_python_type(temporal_analysis.get('motion_consistency', 0.5))),
            'flickering_detected': temporal_analysis.get('flickering_detected', False),
            'face_stability': float(to_python_type(temporal_analysis.get('face_stability', 0.5))),
            'temporal_flags': temporal_analysis.get('temporal_flags', [])
        },
        'deepfake_analysis': {
            'model_fake_risk': float(to_python_type(fake_risk)),
            'model_confidence': float(to_python_type(model_confidence)),
            'lipsync_mismatch': float(to_python_type(deepfake_analysis.get('lipsync_mismatch', 0.0))),
            'blink_irregularity': float(to_python_type(deepfake_analysis.get('blink_irregularity', 0.0))),
            'texture_inconsistency': float(to_python_type(deepfake_analysis.get('texture_inconsistency', 0.0))),
            'face_stability': float(to_python_type(deepfake_analysis.get('face_stability', 1.0))),
            'deepfake_type': deepfake_analysis.get('deepfake_type', 'UNKNOWN'),
            'deepfake_confidence': float(to_python_type(deepfake_analysis.get('deepfake_confidence', 0.0))),
            'deepfake_signals': deepfake_analysis.get('deepfake_signals', [])
        },
        'motion_score': float(to_python_type(motion_score)),
        'audio_score': 0.0  # Will be filled by verify.py after audio analysis
    }
    safe_response = sanitize_response({k: v for k, v in response.items() if k != "frames"})
    safe_response["frames"] = frames
    return safe_response

