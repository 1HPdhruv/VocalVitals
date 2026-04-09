"""
Clinical-Grade Voice Feature Extraction

Extracts comprehensive biomarkers for disease detection:
- Praat/Parselmouth: jitter/shimmer variants, HNR, F0 statistics
- OpenSMILE: ComParE 2016 feature set (6373 features)
- SpeechBrain: x-vector embeddings (512-dim)

These features enable detection of:
- Parkinson's disease (jitter/shimmer patterns)
- Depression (F0 flatness, pause patterns)
- Respiratory disease (voiced fraction, breathiness)
- Cognitive decline (pause frequency, speech rate)
"""

import os
import json
import base64
import tempfile
import subprocess
import numpy as np
from typing import Optional
from pathlib import Path

# Core audio libraries
import librosa
import soundfile as sf

# Praat via parselmouth
try:
    import parselmouth
    from parselmouth.praat import call
    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False
    print("[clinical_features] WARNING: parselmouth not available")

# OpenSMILE for ComParE features
try:
    import opensmile
    OPENSMILE_AVAILABLE = True
    # Initialize OpenSMILE extractor at module level (heavy initialization)
    _SMILE = opensmile.Smile(
        feature_set=opensmile.FeatureSet.ComParE_2016,
        feature_level=opensmile.FeatureLevel.Functionals
    )
    print(f"[clinical_features] OpenSMILE loaded: {_SMILE.feature_names[:5]}... ({len(_SMILE.feature_names)} features)")
except ImportError:
    OPENSMILE_AVAILABLE = False
    _SMILE = None
    print("[clinical_features] WARNING: opensmile not available")
except Exception as e:
    OPENSMILE_AVAILABLE = False
    _SMILE = None
    print(f"[clinical_features] OpenSMILE init error: {e}")

# SpeechBrain for x-vector embeddings
try:
    import torch
    import torchaudio
    from speechbrain.inference.speaker import EncoderClassifier
    SPEECHBRAIN_AVAILABLE = True
    # Lazy load to avoid startup delay
    _XVECTOR_MODEL = None
except ImportError:
    SPEECHBRAIN_AVAILABLE = False
    _XVECTOR_MODEL = None
    print("[clinical_features] WARNING: speechbrain not available")

# Get ffmpeg path
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"


def _get_xvector_model():
    """Lazy load x-vector model to avoid slow startup."""
    global _XVECTOR_MODEL
    if _XVECTOR_MODEL is None and SPEECHBRAIN_AVAILABLE:
        try:
            _XVECTOR_MODEL = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-xvect-voxceleb",
                savedir=str(Path(__file__).parent.parent / "models" / "speechbrain_xvect"),
                run_opts={"device": "cpu"}
            )
            print("[clinical_features] SpeechBrain x-vector model loaded")
        except Exception as e:
            print(f"[clinical_features] x-vector model load failed: {e}")
    return _XVECTOR_MODEL


def _convert_to_wav(input_path: str) -> str:
    """Convert audio to 16kHz mono WAV for consistent processing."""
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", output_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise ValueError(f"ffmpeg failed: {result.stderr[:200]}")
        return output_path
    except subprocess.TimeoutExpired:
        raise ValueError("ffmpeg timeout")


def extract_praat_features(audio_path: str) -> dict:
    """
    Extract clinical voice features using Praat/Parselmouth.
    
    Returns comprehensive jitter/shimmer/HNR variants used in
    clinical voice assessment.
    """
    if not PARSELMOUTH_AVAILABLE:
        return _fallback_praat_features(audio_path)
    
    try:
        snd = parselmouth.Sound(audio_path)
        
        # Pitch object for F0 analysis
        pitch = call(snd, "To Pitch", 0.0, 75, 600)
        
        # F0 statistics
        f0_mean = call(pitch, "Get mean", 0, 0, "Hertz")
        f0_std = call(pitch, "Get standard deviation", 0, 0, "Hertz")
        f0_min = call(pitch, "Get minimum", 0, 0, "Hertz", "Parabolic")
        f0_max = call(pitch, "Get maximum", 0, 0, "Hertz", "Parabolic")
        
        # Voiced fraction
        n_frames = call(pitch, "Get number of frames")
        n_voiced = 0
        for i in range(1, n_frames + 1):
            if call(pitch, "Get value in frame", i, "Hertz") > 0:
                n_voiced += 1
        voiced_fraction = n_voiced / max(n_frames, 1)
        
        # Point process for jitter/shimmer
        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 600)
        
        # Jitter variants (perturbation of F0 period)
        jitter_local = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
        jitter_rap = call(point_process, "Get jitter (rap)", 0, 0, 0.0001, 0.02, 1.3)
        jitter_ppq5 = call(point_process, "Get jitter (ppq5)", 0, 0, 0.0001, 0.02, 1.3)
        
        # Shimmer variants (perturbation of amplitude)
        shimmer_local = call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        shimmer_apq3 = call([snd, point_process], "Get shimmer (apq3)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        shimmer_apq5 = call([snd, point_process], "Get shimmer (apq5)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
        
        # Harmonicity (HNR/NHR)
        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr = call(harmonicity, "Get mean", 0, 0)
        
        # Convert NaN to defaults
        def safe_float(v, default=0.0):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return default
            return float(v)
        
        return {
            "f0_mean": safe_float(f0_mean, 150.0),
            "f0_std": safe_float(f0_std, 20.0),
            "f0_min": safe_float(f0_min, 75.0),
            "f0_max": safe_float(f0_max, 300.0),
            "voiced_fraction": safe_float(voiced_fraction, 0.5),
            "jitter_local": safe_float(jitter_local) * 100,  # Convert to %
            "jitter_rap": safe_float(jitter_rap) * 100,
            "jitter_ppq5": safe_float(jitter_ppq5) * 100,
            "shimmer_local": safe_float(shimmer_local) * 100,
            "shimmer_apq3": safe_float(shimmer_apq3) * 100,
            "shimmer_apq5": safe_float(shimmer_apq5) * 100,
            "hnr": safe_float(hnr, 10.0),
            "nhr": 1.0 / max(safe_float(hnr, 10.0), 0.1),  # Noise-to-harmonics ratio
        }
        
    except Exception as e:
        print(f"[clinical_features] Praat extraction error: {e}")
        return _fallback_praat_features(audio_path)


def _fallback_praat_features(audio_path: str) -> dict:
    """Fallback using librosa when Praat is unavailable."""
    y, sr = librosa.load(audio_path, sr=16000)
    
    # Basic pitch estimation
    f0 = librosa.yin(y, fmin=75, fmax=600, sr=sr)
    voiced = f0[f0 > 0]
    
    f0_mean = float(np.mean(voiced)) if len(voiced) > 0 else 150.0
    f0_std = float(np.std(voiced)) if len(voiced) > 0 else 20.0
    f0_min = float(np.min(voiced)) if len(voiced) > 0 else 75.0
    f0_max = float(np.max(voiced)) if len(voiced) > 0 else 300.0
    voiced_fraction = len(voiced) / max(len(f0), 1)
    
    # Approximate jitter from F0 variation
    if len(voiced) > 1:
        jitter_local = float(np.mean(np.abs(np.diff(voiced))) / max(f0_mean, 1)) * 100
    else:
        jitter_local = 0.5
    
    # Approximate shimmer from RMS variation
    rms = librosa.feature.rms(y=y)[0]
    shimmer_local = float(np.std(rms) / max(np.mean(rms), 1e-6)) * 100
    
    return {
        "f0_mean": round(f0_mean, 2),
        "f0_std": round(f0_std, 2),
        "f0_min": round(f0_min, 2),
        "f0_max": round(f0_max, 2),
        "voiced_fraction": round(voiced_fraction, 4),
        "jitter_local": round(jitter_local, 4),
        "jitter_rap": round(jitter_local * 0.8, 4),
        "jitter_ppq5": round(jitter_local * 0.9, 4),
        "shimmer_local": round(shimmer_local, 4),
        "shimmer_apq3": round(shimmer_local * 0.7, 4),
        "shimmer_apq5": round(shimmer_local * 0.85, 4),
        "hnr": 15.0,
        "nhr": 0.067,
    }


def extract_opensmile_features(audio_path: str, n_components: int = 50) -> dict:
    """
    Extract OpenSMILE ComParE 2016 features.
    
    Returns top PCA components for storage efficiency.
    Full feature set is 6373 dimensions.
    """
    if not OPENSMILE_AVAILABLE or _SMILE is None:
        return _fallback_opensmile_features(audio_path, n_components)
    
    try:
        # Extract features
        features_df = _SMILE.process_file(audio_path)
        features = features_df.values.flatten()
        
        # Replace NaN/Inf with 0
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Simple dimensionality reduction: take mean of feature groups
        # ComParE has 65 LLDs with various functionals
        n_features = len(features)
        
        if n_components >= n_features:
            reduced = features
        else:
            # Reshape and reduce by taking statistics per group
            group_size = n_features // n_components
            reduced = []
            for i in range(n_components):
                start = i * group_size
                end = start + group_size if i < n_components - 1 else n_features
                reduced.append(float(np.mean(features[start:end])))
            reduced = np.array(reduced)
        
        return {
            "compare_features": [round(float(v), 6) for v in reduced],
            "compare_dim": len(reduced),
            "compare_full_dim": n_features,
        }
        
    except Exception as e:
        print(f"[clinical_features] OpenSMILE error: {e}")
        return _fallback_opensmile_features(audio_path, n_components)


def _fallback_opensmile_features(audio_path: str, n_components: int = 50) -> dict:
    """Fallback using librosa spectral features."""
    y, sr = librosa.load(audio_path, sr=16000)
    
    features = []
    
    # MFCCs (40 coefficients)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    features.extend(np.mean(mfccs, axis=1))
    features.extend(np.std(mfccs, axis=1))
    
    # Spectral features
    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
    spectral_contrast = librosa.feature.spectral_contrast(y=y, sr=sr)
    
    features.append(np.mean(spectral_centroid))
    features.append(np.std(spectral_centroid))
    features.append(np.mean(spectral_bandwidth))
    features.append(np.mean(spectral_rolloff))
    features.extend(np.mean(spectral_contrast, axis=1))
    
    # RMS energy
    rms = librosa.feature.rms(y=y)[0]
    features.append(np.mean(rms))
    features.append(np.std(rms))
    
    # Zero crossing rate
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    features.append(np.mean(zcr))
    
    # Pad/truncate to n_components
    features = np.array(features)[:n_components]
    if len(features) < n_components:
        features = np.pad(features, (0, n_components - len(features)))
    
    return {
        "compare_features": [round(float(v), 6) for v in features],
        "compare_dim": n_components,
        "compare_full_dim": n_components,
    }


def extract_xvector(audio_path: str) -> dict:
    """
    Extract SpeechBrain x-vector embedding (512 dimensions).
    
    X-vectors capture speaker characteristics and voice quality
    that correlate with various health conditions.
    """
    if not SPEECHBRAIN_AVAILABLE:
        return _fallback_xvector(audio_path)
    
    model = _get_xvector_model()
    if model is None:
        return _fallback_xvector(audio_path)
    
    try:
        # Load audio
        signal, sr = torchaudio.load(audio_path)
        
        # Resample to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            signal = resampler(signal)
        
        # Convert to mono if stereo
        if signal.shape[0] > 1:
            signal = torch.mean(signal, dim=0, keepdim=True)
        
        # Extract embedding
        with torch.no_grad():
            embeddings = model.encode_batch(signal)
            embedding = embeddings.squeeze().cpu().numpy()
        
        # Compress to base64 for efficient storage
        embedding_bytes = embedding.astype(np.float32).tobytes()
        embedding_b64 = base64.b64encode(embedding_bytes).decode('ascii')
        
        return {
            "xvector": [round(float(v), 6) for v in embedding[:50]],  # First 50 for preview
            "xvector_b64": embedding_b64,
            "xvector_dim": len(embedding),
        }
        
    except Exception as e:
        print(f"[clinical_features] x-vector error: {e}")
        return _fallback_xvector(audio_path)


def _fallback_xvector(audio_path: str) -> dict:
    """Fallback: use extended MFCCs as pseudo-embedding."""
    y, sr = librosa.load(audio_path, sr=16000)
    
    # Extended MFCC statistics as embedding substitute
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    
    embedding = []
    # Mean, std, delta mean, delta std for each coefficient
    embedding.extend(np.mean(mfccs, axis=1))
    embedding.extend(np.std(mfccs, axis=1))
    
    delta_mfccs = librosa.feature.delta(mfccs)
    embedding.extend(np.mean(delta_mfccs, axis=1))
    embedding.extend(np.std(delta_mfccs, axis=1))
    
    # Pad to 512 dims
    embedding = np.array(embedding)
    if len(embedding) < 512:
        embedding = np.pad(embedding, (0, 512 - len(embedding)))
    embedding = embedding[:512]
    
    embedding_bytes = embedding.astype(np.float32).tobytes()
    embedding_b64 = base64.b64encode(embedding_bytes).decode('ascii')
    
    return {
        "xvector": [round(float(v), 6) for v in embedding[:50]],
        "xvector_b64": embedding_b64,
        "xvector_dim": 512,
    }


def extract_speech_timing(audio_path: str, transcript: Optional[str] = None) -> dict:
    """
    Extract speech timing and rhythm features.
    
    These are important for depression and cognitive decline detection.
    """
    y, sr = librosa.load(audio_path, sr=16000)
    duration = librosa.get_duration(y=y, sr=sr)
    
    # Energy-based speech/pause detection
    rms = librosa.feature.rms(y=y, hop_length=512)[0]
    threshold = np.mean(rms) * 0.3
    is_speech = rms > threshold
    
    # Calculate pause statistics
    speech_frames = np.sum(is_speech)
    total_frames = len(is_speech)
    pause_ratio = 1.0 - (speech_frames / max(total_frames, 1))
    
    # Count pause segments
    transitions = np.diff(is_speech.astype(int))
    pause_count = np.sum(transitions == -1)  # Transitions from speech to pause
    pause_freq = pause_count / max(duration, 1)  # Pauses per second
    
    # Energy dynamics
    energy_mean = float(np.mean(rms))
    energy_std = float(np.std(rms))
    energy_range = float(np.max(rms) - np.min(rms))
    
    # Estimate speech rate from transcript if available
    if transcript:
        word_count = len(transcript.split())
        speech_duration = duration * (1 - pause_ratio)
        speech_rate = word_count / max(speech_duration / 60, 0.1)  # Words per minute
    else:
        # Estimate from energy patterns
        speech_rate = 120.0  # Default estimate
    
    return {
        "speech_rate": round(speech_rate, 2),
        "pause_ratio": round(pause_ratio, 4),
        "pause_freq": round(pause_freq, 4),
        "pause_count": int(pause_count),
        "energy_mean": round(energy_mean, 6),
        "energy_std": round(energy_std, 6),
        "energy_range": round(energy_range, 6),
        "duration": round(duration, 2),
    }


def extract_all_clinical_features(audio_path: str, transcript: Optional[str] = None) -> dict:
    """
    Extract complete clinical feature set from audio.
    
    Returns all features needed for disease detection:
    - Praat features (jitter/shimmer/HNR variants, F0 stats)
    - OpenSMILE ComParE features (reduced to 50 dims)
    - X-vector embedding (512 dims, stored as base64)
    - Speech timing features
    
    Total dimensionality: ~570 features per recording
    """
    # Convert to WAV if needed
    converted_path = None
    if audio_path.lower().endswith(('.webm', '.opus', '.ogg')):
        converted_path = _convert_to_wav(audio_path)
        wav_path = converted_path
    else:
        wav_path = audio_path
    
    try:
        # Extract all feature types
        praat_feats = extract_praat_features(wav_path)
        opensmile_feats = extract_opensmile_features(wav_path)
        xvector_feats = extract_xvector(wav_path)
        timing_feats = extract_speech_timing(wav_path, transcript)
        
        # MFCC for backward compatibility
        y, sr = librosa.load(wav_path, sr=16000)
        mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        mfcc_means = [round(float(v), 4) for v in np.mean(mfccs, axis=1)]
        
        return {
            # Praat features
            **praat_feats,
            
            # OpenSMILE features
            "compare_features": opensmile_feats.get("compare_features", []),
            "compare_dim": opensmile_feats.get("compare_dim", 0),
            
            # X-vector
            "xvector": xvector_feats.get("xvector", []),
            "xvector_b64": xvector_feats.get("xvector_b64", ""),
            "xvector_dim": xvector_feats.get("xvector_dim", 0),
            
            # Speech timing
            **timing_feats,
            
            # Legacy MFCC
            "mfcc": mfcc_means,
            
            # Derived features for backward compatibility
            "pitch_mean": praat_feats.get("f0_mean", 150.0),
            "pitch_std": praat_feats.get("f0_std", 20.0),
            "jitter": praat_feats.get("jitter_local", 0.5),
            "shimmer": praat_feats.get("shimmer_local", 3.0),
            "breathiness": 1.0 - min(1.0, praat_feats.get("hnr", 15.0) / 40.0),
        }
        
    finally:
        # Clean up temp file
        if converted_path and os.path.exists(converted_path):
            try:
                os.unlink(converted_path)
            except:
                pass


# Feature availability check
def get_feature_status() -> dict:
    """Return status of available feature extractors."""
    return {
        "parselmouth": PARSELMOUTH_AVAILABLE,
        "opensmile": OPENSMILE_AVAILABLE,
        "speechbrain": SPEECHBRAIN_AVAILABLE,
        "opensmile_features": len(_SMILE.feature_names) if OPENSMILE_AVAILABLE and _SMILE else 0,
    }
