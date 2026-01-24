import numpy as np
import tempfile
import os

def analyze_audio(video_path: str) -> dict:
    print(f"AUDIO ANALYZER: Starting analysis of {video_path}")
    
    risk_score = 0.0
    risk_factors = []
    has_audio = False
    
    try:
        try:
            from moviepy.editor import VideoFileClip
            
            clip = VideoFileClip(video_path)
            
            if clip.audio is None:
                print("AUDIO ANALYZER: No audio track found")
                clip.close()
                return {
                    'audio_risk_score': 0.0,
                    'has_audio': False,
                    'risk_factors': []
                }
            
            has_audio = True
            
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio_path = temp_audio.name
            temp_audio.close()
            
            clip.audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
            clip.close()
            
            try:
                import librosa
                
                y, sr = librosa.load(temp_audio_path, sr=None)
                
                spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
                centroid_var = np.var(spectral_centroid)
                
                if centroid_var < 1000:
                    risk_score += 0.3
                    risk_factors.append("Unnaturally consistent spectral pattern (synthetic voice)")
                
                zero_crossings = librosa.zero_crossings(y)
                zcr_rate = np.sum(zero_crossings) / len(y)
                
                if zcr_rate > 0.2:
                    risk_score += 0.2
                    risk_factors.append("High zero-crossing rate (audio artifacts)")
                
                print(f"AUDIO ANALYZER: Spectral analysis complete, risk={risk_score:.2f}")
                
            except ImportError:
                print("AUDIO ANALYZER: librosa not available, skipping spectral analysis")
                risk_score = 0.0
            
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                
        except ImportError:
            print("AUDIO ANALYZER: moviepy not available, skipping audio analysis")
            return {
                'audio_risk_score': 0.0,
                'has_audio': False,
                'risk_factors': ['Audio analysis unavailable (missing dependencies)']
            }
    
    except Exception as e:
        print(f"AUDIO ANALYZER ERROR: {e}")
        return {
            'audio_risk_score': 0.0,
            'has_audio': False,
            'risk_factors': [f'Audio analysis failed: {str(e)}']
        }
    
    final_risk = min(risk_score, 1.0)
    
    return {
        'audio_risk_score': final_risk,
        'has_audio': has_audio,
        'risk_factors': risk_factors
    }
