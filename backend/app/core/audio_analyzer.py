import numpy as np
import tempfile
import os
import logging
import warnings

# Suppress ALL warnings from external libraries
warnings.filterwarnings('ignore')
import sys
if not sys.warnoptions:
    warnings.simplefilter('ignore')

logger = logging.getLogger(__name__)


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio to text using available transcription method
    Falls back gracefully if transcription unavailable
    """
    try:
        try:
            from pydub import AudioSegment
            import speech_recognition as sr
            
            # Try using SpeechRecognition (requires microphone or file support)
            recognizer = sr.Recognizer()
            with sr.AudioFile(audio_path) as source:
                audio_data = recognizer.record(source)
            
            try:
                text = recognizer.recognize_google(audio_data)
                logger.info(f"Audio transcribed: {text[:100]}...")
                return text
            except sr.UnknownValueError:
                logger.debug("Speech recognition could not understand audio")
                return ""
            except sr.RequestError:
                logger.debug("Speech recognition service unavailable")
                return ""
        except (ImportError, Exception) as e:
            logger.debug(f"Transcription unavailable: {e}")
            return ""
    except Exception as e:
        logger.debug(f"Audio transcription failed: {e}")
        return ""


def analyze_audio_semantics(transcript: str, audio_array: np.ndarray = None, sr: int = None) -> dict:
    """
    Analyze semantic meaning of audio content
    - Detect speech presence
    - Detect keywords
    - Categorize audio type (speech/music/noise)
    """
    audio_context = {
        "has_speech": False,
        "has_music": False,
        "has_noise": False,
        "audio_type": "UNKNOWN",
        "keywords": [],
        "semantic_score": 0.0,
        "audio_context_risk": 0.0
    }
    
    try:
        # 1. Speech detection
        if transcript and len(transcript.strip()) > 0:
            audio_context["has_speech"] = True
            audio_context["audio_type"] = "SPEECH"
            logger.info(f"Detected speech in audio: {transcript[:50]}...")
            
            # Extract potential keywords (simplified)
            suspicious_keywords = [
                "deepfake", "fake", "synthetic", "generated", "edited", "manipulated",
                "ai", "model", "algorithm", "filtered", "distorted", "artificial"
            ]
            found_keywords = [kw for kw in suspicious_keywords if kw.lower() in transcript.lower()]
            if found_keywords:
                audio_context["keywords"] = found_keywords
                audio_context["semantic_score"] = 0.7
                logger.info(f"Suspicious keywords detected: {found_keywords}")
        
        # 2. Audio type detection (using signal analysis if available)
        if audio_array is not None and sr is not None:
            try:
                import librosa
                
                # Detect silence
                S = librosa.feature.melspectrogram(y=audio_array, sr=sr)
                S_db = librosa.power_to_db(S, ref=np.max)
                
                # Check for music/noise characteristics
                spectral_centroid = librosa.feature.spectral_centroid(y=audio_array, sr=sr)
                mean_centroid = np.mean(spectral_centroid)
                
                # Music typically has lower spectral centroid than speech
                if mean_centroid < 2000:
                    audio_context["has_music"] = True
                    if not audio_context["has_speech"]:
                        audio_context["audio_type"] = "MUSIC"
                        logger.info("Detected music in audio")
                elif mean_centroid > 4000:
                    audio_context["has_noise"] = True
                    if not audio_context["has_speech"]:
                        audio_context["audio_type"] = "NOISE"
                        logger.info("Detected noise/artifacts in audio")
                
                # Harmonic vs Percussive analysis
                y_harmonic, y_percussive = librosa.effects.hpss(audio_array)
                percussive_ratio = np.sum(np.abs(y_percussive)) / (np.sum(np.abs(y_harmonic)) + np.sum(np.abs(y_percussive)) + 1e-10)
                
                if percussive_ratio > 0.6:
                    audio_context["has_music"] = True
                    logger.info("Detected percussive/musical elements")
                
            except Exception as e:
                logger.debug(f"Audio type detection failed: {e}")
        
        # 3. Overall context risk
        if audio_context["audio_type"] == "NOISE" or (audio_context["has_noise"] and not audio_context["has_speech"]):
            audio_context["audio_context_risk"] = 0.3
        if audio_context["semantic_score"] > 0.5:
            audio_context["audio_context_risk"] = max(audio_context["audio_context_risk"], 0.4)
        
        logger.info(f"Audio context: {audio_context['audio_type']}, risk={audio_context['audio_context_risk']:.2f}")
        
    except Exception as e:
        logger.debug(f"Audio semantic analysis error: {e}")
    
    return audio_context

def detect_audio_deepfake_signals(audio_array: np.ndarray, sr: int) -> dict:
    """
    NEW: Detect audio deepfake indicators
    - Overly smooth waveform (synthetic speech signature)
    - Pitch variance (low = robotic)
    - Frequency stability (unnatural consistency)
    
    Returns:
        {
            "waveform_smoothness": 0.0-1.0,
            "pitch_variance": 0.0-1.0,
            "frequency_consistency": 0.0-1.0,
            "audio_deepfake_signals": [list]
        }
    """
    signals = []
    
    try:
        # 1. WAVEFORM SMOOTHNESS DETECTION
        # Natural speech has irregular waveform; synthetic is smooth
        diff = np.diff(audio_array)
        smoothness = np.mean(np.abs(np.diff(diff)))  # Second derivative
        
        if smoothness < 0.01:
            waveform_smoothness = 0.7
            signals.append("Unnaturally smooth waveform detected (synthetic signature)")
        elif smoothness < 0.05:
            waveform_smoothness = 0.4
        else:
            waveform_smoothness = 0.0
        
        # 2. PITCH VARIANCE DETECTION (via F0 estimation)
        try:
            import librosa
            
            # Extract fundamental frequency
            f0 = librosa.yin(audio_array, fmin=40, fmax=400)  # Human voice range
            
            # Calculate pitch variance
            valid_f0 = f0[f0 > 0]
            if len(valid_f0) > 10:
                pitch_variance_val = np.std(valid_f0) / (np.mean(valid_f0) + 1e-6)
                
                # Synthetic speech: very low pitch variance
                if pitch_variance_val < 0.05:
                    pitch_variance = 0.8
                    signals.append("Robotic pitch consistency detected")
                elif pitch_variance_val < 0.15:
                    pitch_variance = 0.4
                else:
                    pitch_variance = 0.0
            else:
                pitch_variance = 0.0
        except:
            pitch_variance = 0.0
        
        # 3. FREQUENCY STABILITY
        # Analyze STFT for frequency consistency
        try:
            import librosa
            
            D = librosa.stft(audio_array)
            magnitude = np.abs(D)
            
            # Frame-to-frame magnitude changes
            frame_diffs = np.sum(np.abs(np.diff(magnitude, axis=1)), axis=0)
            frame_std = np.std(frame_diffs)
            
            if frame_std < 50:  # Very consistent frequency
                frequency_consistency = 0.7
                signals.append("Unnaturally consistent frequency spectrum")
            elif frame_std < 150:
                frequency_consistency = 0.3
            else:
                frequency_consistency = 0.0
        except:
            frequency_consistency = 0.0
        
        return {
            "waveform_smoothness": round(min(waveform_smoothness, 1.0), 3),
            "pitch_variance": round(min(pitch_variance, 1.0), 3),
            "frequency_consistency": round(min(frequency_consistency, 1.0), 3),
            "audio_deepfake_signals": signals
        }
    
    except Exception as e:
        logger.debug(f"Audio deepfake detection failed: {e}")
        return {
            "waveform_smoothness": 0.0,
            "pitch_variance": 0.0,
            "frequency_consistency": 0.0,
            "audio_deepfake_signals": []
        }


def analyze_audio(video_path: str) -> dict:
    logger.debug(f"Starting audio analysis of {video_path}")
    
    risk_score = 0.0
    risk_factors = []
    has_audio = False
    audio_transcript = ""
    audio_context = {
        "has_speech": False,
        "audio_type": "UNKNOWN",
        "keywords": [],
        "audio_context_risk": 0.0
    }
    audio_deepfake_signals_dict = {
        "waveform_smoothness": 0.0,
        "pitch_variance": 0.0,
        "frequency_consistency": 0.0,
        "audio_deepfake_signals": []
    }
    
    try:
        try:
            from moviepy.editor import VideoFileClip
            
            clip = VideoFileClip(video_path)
            temp_audio_path = None

            try:
                if clip.audio is None:
                    logger.debug("No audio track in video")
                    return {
                        'audio_risk_score': 0.0,
                        'has_audio': False,
                        'audio_transcript': "",
                        'audio_context': audio_context,
                        'risk_factors': [],
                        'deepfake_analysis': audio_deepfake_signals_dict
                    }
                
                has_audio = True
                
                temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
                temp_audio_path = temp_audio.name
                temp_audio.close()
                
                clip.audio.write_audiofile(temp_audio_path, verbose=False, logger=None)
                
                try:
                    import librosa
                    
                    y, sr = librosa.load(temp_audio_path, sr=None)
                    
                    # NEW: Audio transcription
                    audio_transcript = transcribe_audio(temp_audio_path)
                    
                    # NEW: Audio semantic analysis
                    audio_context = analyze_audio_semantics(audio_transcript, y, sr)
                    
                    # NEW: Audio deepfake detection
                    audio_deepfake_signals_dict = detect_audio_deepfake_signals(y, sr)
                    
                    # EXISTING ANALYSIS
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
                    
                    # Add audio deepfake risk
                    audio_deepfake_prob = max(
                        audio_deepfake_signals_dict.get("waveform_smoothness", 0.0),
                        audio_deepfake_signals_dict.get("pitch_variance", 0.0),
                        audio_deepfake_signals_dict.get("frequency_consistency", 0.0)
                    )
                    risk_score = max(risk_score, audio_deepfake_prob)
                    
                    # Add semantic risk
                    risk_score = max(risk_score, audio_context.get("audio_context_risk", 0.0))
                    
                    logger.debug(f"Audio spectral analysis complete, risk={risk_score:.2f}")
                    
                except ImportError:
                    logger.debug("Librosa not available, skipping spectral analysis")
                    risk_score = 0.0
            finally:
                clip.close()
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.remove(temp_audio_path)
                
        except ImportError:
            logger.debug("MoviePy not available, skipping audio analysis")
            return {
                'audio_risk_score': 0.0,
                'has_audio': False,
                'audio_transcript': "",
                'audio_context': audio_context,
                'risk_factors': ['Audio analysis unavailable (missing dependencies)'],
                'deepfake_analysis': {
                    "waveform_smoothness": 0.0,
                    "pitch_variance": 0.0,
                    "frequency_consistency": 0.0,
                    "audio_deepfake_signals": []
                }
            }
    
    except Exception as e:
        logger.debug(f"Audio analysis error: {e}")
        return {
            'audio_risk_score': 0.0,
            'has_audio': False,
            'audio_transcript': "",
            'audio_context': audio_context,
            'risk_factors': [f'Audio analysis failed: {str(e)}'],
            'deepfake_analysis': {
                "waveform_smoothness": 0.0,
                "pitch_variance": 0.0,
                "frequency_consistency": 0.0,
                "audio_deepfake_signals": []
            }
        }
    
    final_risk = min(risk_score, 1.0)
    
    return {
        'audio_risk_score': final_risk,
        'has_audio': has_audio,
        'audio_transcript': audio_transcript,
        'audio_context': audio_context,
        'risk_factors': risk_factors,
        'deepfake_analysis': audio_deepfake_signals_dict
    }
