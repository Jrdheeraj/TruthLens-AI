import cv2
import numpy as np
from typing import List, Dict
import tempfile
import os

def extract_key_frames(video_path: str, max_frames: int = 10) -> List[np.ndarray]:
    frames = []
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"ERROR: Could not open video {video_path}")
        return frames
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    frame_interval = int(fps * 2) if fps > 0 else 30
    
    frame_count = 0
    extracted_count = 0
    
    while cap.isOpened() and extracted_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        if frame_count % frame_interval == 0:
            frames.append(frame)
            extracted_count += 1
        
        frame_count += 1
    
    cap.release()
    print(f"VIDEO ANALYZER: Extracted {len(frames)} frames from video")
    return frames

def detect_visual_artifacts(frames: List[np.ndarray]) -> float:
    if not frames:
        return 0.0
    
    risk_score = 0.0
    risk_factors = []
    
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    for i, frame in enumerate(frames):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        if len(faces) > 0:
            edges = cv2.Canny(gray, 100, 200)
            edge_density = np.sum(edges > 0) / edges.size
            
            if edge_density > 0.15:
                risk_score += 0.2
                risk_factors.append("High edge density (GAN artifacts)")
            
            for (x, y, w, h) in faces:
                face_region = gray[y:y+h, x:x+w]
                face_std = np.std(face_region)
                
                if face_std < 20:
                    risk_score += 0.15
                    risk_factors.append("Unnaturally smooth face texture")
                elif face_std > 80:
                    risk_score += 0.1
                    risk_factors.append("Excessive noise in face region")
    
    if len(frames) > 1:
        frame_diffs = []
        for i in range(len(frames) - 1):
            diff = cv2.absdiff(frames[i], frames[i+1])
            frame_diffs.append(np.mean(diff))
        
        if len(frame_diffs) > 0:
            diff_variance = np.var(frame_diffs)
            if diff_variance > 1000:
                risk_score += 0.2
                risk_factors.append("Frame flickering detected")
    
    final_risk = min(risk_score, 1.0)
    
    print(f"VIDEO ANALYZER: Visual risk={final_risk:.2f}, factors={risk_factors}")
    return final_risk

def analyze_video(video_path: str) -> Dict:
    print(f"VIDEO ANALYZER: Starting analysis of {video_path}")
    
    frames = extract_key_frames(video_path, max_frames=10)
    
    if not frames:
        return {
            'frames': [],
            'visual_risk_score': 0.0,
            'metadata': {},
            'error': 'Failed to extract frames'
        }
    
    visual_risk = detect_visual_artifacts(frames)
    
    cap = cv2.VideoCapture(video_path)
    metadata = {
        'fps': cap.get(cv2.CAP_PROP_FPS),
        'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    }
    cap.release()
    
    return {
        'frames': frames,
        'visual_risk_score': visual_risk,
        'metadata': metadata
    }
