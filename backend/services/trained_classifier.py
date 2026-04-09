from __future__ import annotations

import os
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import joblib
import librosa
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "models" / "audio_classifier.pkl"

# Get ffmpeg path from imageio-ffmpeg (bundled binary)
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"

# Preload model at startup for faster inference
_PRELOADED_MODEL = None
print("[classifier] Preloading model at startup...")
try:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 100_000:
        _PRELOADED_MODEL = joblib.load(MODEL_PATH)
        print(f"[classifier] Model preloaded successfully")
    else:
        print(f"[classifier] No trained model found, will use heuristics")
except Exception as e:
    print(f"[classifier] Model preload failed: {e}")
    _PRELOADED_MODEL = None


def _convert_webm_to_wav(input_path: str) -> str:
    """Convert WebM/Opus audio to WAV using ffmpeg (bundled via imageio-ffmpeg)."""
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    print(f"[ffmpeg] Converting {input_path} to {output_path}")
    
    try:
        result = subprocess.run(
            [
                FFMPEG_PATH,
                "-y",
                "-i", input_path,
                "-ar", "16000",
                "-ac", "1",
                "-f", "wav",
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=5  # Fast timeout
        )
        
        if result.returncode != 0:
            print(f"[ffmpeg] stderr: {result.stderr}")
            raise Exception(f"ffmpeg conversion failed: {result.stderr[:200]}")
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise Exception("ffmpeg produced empty or invalid output")
        
        print(f"[ffmpeg] Conversion successful, output size: {os.path.getsize(output_path)} bytes")
        return output_path
        
    except subprocess.TimeoutExpired:
        raise Exception("ffmpeg conversion timed out")
    except FileNotFoundError:
        raise Exception(f"ffmpeg not found at {FFMPEG_PATH} - run: pip install imageio-ffmpeg")


@lru_cache(maxsize=1)
def load_trained_classifier():
    """Load trained model (uses preloaded if available)."""
    global _PRELOADED_MODEL
    
    if _PRELOADED_MODEL is not None:
        print("[model] Using preloaded model")
        return _PRELOADED_MODEL
    
    print("[model] Loading from disk...")
    if not MODEL_PATH.exists():
        print(f"[WARNING] Model file not found at {MODEL_PATH}")
        return None
    
    file_size = MODEL_PATH.stat().st_size
    if file_size <= 100_000:
        print(f"[WARNING] Model file too small ({file_size} bytes)")
        return None
    
    payload = joblib.load(MODEL_PATH)
    _PRELOADED_MODEL = payload
    print("[model] Loaded successfully")
    return payload


def _heuristic_classify(features: np.ndarray) -> dict[str, float]:
    """
    Fallback heuristic classifier when trained model isn't available.
    Uses acoustic features to estimate class probabilities.
    """
    # Features: [rms_mean, rms_std, zcr_mean, zcr_std, centroid_mean, centroid_std, 
    #            bandwidth_mean, bandwidth_std, pause_ratio, mfcc_mean(20), mfcc_std(20)]
    
    rms_mean = features[0]
    rms_std = features[1]
    zcr_mean = features[2]
    centroid_mean = features[4]
    pause_ratio = features[8]
    
    # Heuristic rules based on acoustic properties
    speech_score = 0.4
    cough_score = 0.1
    breathing_score = 0.1
    noise_score = 0.4
    
    # High energy with variation suggests speech
    if rms_mean > 0.05 and rms_std > 0.02:
        speech_score += 0.3
        cough_score -= 0.05
    
    # Very high energy burst with high ZCR suggests cough
    if rms_mean > 0.1 and zcr_mean > 0.1:
        cough_score += 0.4
        speech_score -= 0.1
    
    # Low energy with regular pattern suggests breathing
    if rms_mean < 0.03 and pause_ratio > 0.3:
        breathing_score += 0.3
        speech_score -= 0.1
    
    # High spectral centroid with low energy suggests noise
    if centroid_mean > 3000 and rms_mean < 0.02:
        noise_score += 0.3
        speech_score -= 0.1
    
    # Normalize to sum to 1
    total = speech_score + cough_score + breathing_score + noise_score
    return {
        "speech": max(0, speech_score / total),
        "cough": max(0, cough_score / total),
        "breathing": max(0, breathing_score / total),
        "noise": max(0, noise_score / total),
    }


def extract_vector_for_inference(audio_path: str, sample_rate: int = 16000) -> np.ndarray:
    converted_path = None
    
    # Check if input is WebM/Opus and needs conversion
    is_webm = audio_path.lower().endswith(('.webm', '.opus', '.ogg'))
    if is_webm:
        print(f"[extract] Detected WebM/Opus format, converting via ffmpeg...")
        converted_path = _convert_webm_to_wav(audio_path)
        load_path = converted_path
    else:
        load_path = audio_path
    
    try:
        y, sr = librosa.load(load_path, sr=sample_rate, mono=True)
    except Exception as e:
        print("ERROR in audio loading:", e)
        raise Exception(f"Audio loading failed: {str(e)}") from e
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.unlink(converted_path)
            except:
                pass

    print("Audio length:", len(y) if y is not None else 0)
    if y is None or len(y) < 5000:
        raise Exception(f"Audio too short or empty ({len(y) if y else 0} samples, need 5000+)")
    print("Sample rate:", sr)
    if y is None or len(y) == 0:
        raise ValueError("Empty audio signal")

    peak = float(np.max(np.abs(y)))
    if peak <= 1e-8:
        raise ValueError("Near-silent audio signal")
    y = y / peak

    y, _ = librosa.effects.trim(y, top_db=25)
    if len(y) < sample_rate:
        raise ValueError("Audio too short for classification")

    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

    silence_threshold = max(float(np.percentile(rms, 25)), 1e-6)
    pause_ratio = float(np.mean(rms <= silence_threshold))

    feats = [
        float(np.mean(rms)),
        float(np.std(rms)),
        float(np.mean(zcr)),
        float(np.std(zcr)),
        float(np.mean(centroid)),
        float(np.std(centroid)),
        float(np.mean(bandwidth)),
        float(np.std(bandwidth)),
        pause_ratio,
    ]

    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    feats.extend([float(v) for v in mfcc_mean])
    feats.extend([float(v) for v in mfcc_std])

    print("Energy:", float(np.mean(rms)))
    print("ZCR:", float(np.mean(zcr)))
    print("MFCC mean:", [float(v) for v in mfcc_mean])
    print("MFCC std:", [float(v) for v in mfcc_std])
    print("Spectral Centroid:", float(np.mean(centroid)))

    if float(np.mean(rms)) < 1e-6 and float(np.mean(zcr)) < 1e-6 and all(abs(float(v)) < 1e-6 for v in mfcc_mean):
        raise ValueError("Feature extraction failed")

    return np.array(feats, dtype=np.float32)


def predict_audio_proba(audio_path: str) -> dict[str, float] | None:
    print("Loading model...")
    payload = load_trained_classifier()
    
    vector = extract_vector_for_inference(audio_path)
    
    if payload is None:
        print("[WARNING] Using heuristic classifier (model not trained)")
        prob_dict = _heuristic_classify(vector)
        print("Heuristic probabilities:", prob_dict)
        return prob_dict
    
    print("Model loaded successfully")
    model = payload["model"]
    assert model is not None
    classes = list(payload["classes"])

    try:
        probs = model.predict_proba(vector.reshape(1, -1))[0]
        print("Model output:", probs)
    except Exception as e:
        print("ERROR in prediction:", e)
        print("[WARNING] Falling back to heuristic classifier")
        return _heuristic_classify(vector)

    prob_dict = {cls: float(prob) for cls, prob in zip(classes, probs)}
    print("Model probabilities:", prob_dict)

    total = sum(prob_dict.values())
    if not any(v > 0.0 for v in prob_dict.values()):
        raise ValueError("Invalid model output")
    if abs(total - 1.0) > 0.05:
        raise ValueError("Invalid model output")

    return prob_dict
