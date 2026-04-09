import os
import io
import subprocess
import tempfile
import numpy as np
import librosa
import soundfile as sf
from typing import Optional

try:
    import parselmouth
    from parselmouth.praat import call
    PARSELMOUTH_AVAILABLE = True
except ImportError:
    PARSELMOUTH_AVAILABLE = False
    print("WARNING: parselmouth not available, jitter/shimmer/HNR will use librosa fallbacks")

# Get ffmpeg path from imageio-ffmpeg (bundled binary)
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"


def _convert_webm_to_wav(input_path: str) -> str:
    """Convert WebM/Opus audio to WAV using ffmpeg (bundled via imageio-ffmpeg)."""
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    print(f"[ffmpeg] Converting {input_path} to {output_path}")
    
    try:
        result = subprocess.run(
            [FFMPEG_PATH, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", "-f", "wav", output_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise ValueError(f"ffmpeg conversion failed: {result.stderr[:200]}")
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise ValueError("ffmpeg produced empty output")
        return output_path
    except subprocess.TimeoutExpired:
        raise ValueError("ffmpeg conversion timed out")
    except FileNotFoundError:
        raise ValueError(f"ffmpeg not found at {FFMPEG_PATH} - run: pip install imageio-ffmpeg")


def extract_features(audio_path: str) -> dict:
    """
    Extract full set of acoustic features from an audio file.
    Returns a dict with all required biomarkers.
    """
    converted_path = None
    
    # Convert WebM/Opus if needed
    if audio_path.lower().endswith(('.webm', '.opus', '.ogg')):
        print(f"[extract_features] Converting WebM/Opus to WAV...")
        converted_path = _convert_webm_to_wav(audio_path)
        load_path = converted_path
    else:
        load_path = audio_path
    
    try:
        y, sr = librosa.load(load_path, sr=None, mono=True)
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.unlink(converted_path)
            except:
                pass
    
    duration = librosa.get_duration(y=y, sr=sr)
    
    print(f"[extract_features] Audio loaded: {len(y)} samples, {sr}Hz, {duration:.2f}s")

    if duration < 3.0:
        raise ValueError("Audio too short (< 3 seconds)")

    # ── MFCC (13 coefficients) ──────────────────────────────────────────────
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_means = [round(float(v), 4) for v in np.mean(mfccs, axis=1)]

    # ── Pitch (YIN algorithm) ───────────────────────────────────────────────
    f0 = librosa.yin(y, fmin=50, fmax=500, sr=sr)
    voiced_f0 = f0[f0 > 0]
    pitch_mean = float(np.mean(voiced_f0)) if len(voiced_f0) > 0 else 0.0
    pitch_std  = float(np.std(voiced_f0))  if len(voiced_f0) > 0 else 0.0

    # ── Energy / amplitude variation ────────────────────────────────────────
    rms = librosa.feature.rms(y=y)[0]
    energy_mean = float(np.mean(rms)) if len(rms) > 0 else 0.0
    energy_std = float(np.std(rms)) if len(rms) > 0 else 0.0
    amplitude_variation = round((energy_std / max(energy_mean, 1e-6)) * 100, 4) if energy_mean > 0 else 0.0

    # ── Spectral / temporal quality features ───────────────────────────────
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    zcr_mean = float(np.mean(zcr)) if len(zcr) > 0 else 0.0

    spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    spectral_centroid_mean = float(np.mean(spectral_centroid)) if len(spectral_centroid) > 0 else 0.0
    spectral_bandwidth_mean = float(np.mean(spectral_bandwidth)) if len(spectral_bandwidth) > 0 else 0.0

    # Background noise estimate from lowest-energy frames.
    # Approximation: lower percentile RMS frames represent room/background floor.
    noise_floor = float(np.percentile(rms, 10)) if len(rms) > 0 else 0.0
    signal_floor = float(np.percentile(rms, 90)) if len(rms) > 0 else 0.0
    background_noise_ratio = round(noise_floor / max(signal_floor, 1e-6), 6)

    # ── Jitter, Shimmer, HNR via parselmouth ────────────────────────────────
    jitter  = 0.0
    shimmer = 0.0
    hnr     = 10.0

    if PARSELMOUTH_AVAILABLE:
        try:
            snd = parselmouth.Sound(audio_path)
            # Pitch object needed for jitter
            pitch_obj = call(snd, "To Pitch", 0.0, 75, 600)
            # PointProcess for jitter/shimmer
            point_process = call([snd, pitch_obj], "To PointProcess (cc)")
            jitter     = call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3)
            jitter      = round(float(jitter) * 100, 4)   # convert to %
            shimmer_obj = call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
            shimmer     = round(float(shimmer_obj) * 100, 4)  # convert to %
            harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
            hnr_val     = call(harmonicity, "Get mean", 0, 0)
            hnr         = round(float(hnr_val), 4) if not np.isnan(hnr_val) else 10.0
        except Exception as e:
            print(f"parselmouth extraction failed: {e}")
            # Fallback: librosa zero-crossing as rough shimmer proxy
            jitter  = round(float(np.mean(np.abs(np.diff(voiced_f0)))) / max(pitch_mean, 1) * 100, 4) if len(voiced_f0) > 1 else 0.0
            shimmer = round(float(np.std(librosa.feature.rms(y=y))), 4)
            hnr     = 10.0
    else:
        # Fallback without parselmouth
        jitter  = round(float(np.mean(np.abs(np.diff(voiced_f0)))) / max(pitch_mean, 1) * 100, 4) if len(voiced_f0) > 1 else 0.0
        shimmer = round(float(np.std(librosa.feature.rms(y=y))), 4)
        hnr     = 10.0

    # ── Breathiness: inverse of HNR normalized 0-1 ──────────────────────────
    # HNR range: -20 to +40 dB; map so low HNR = high breathiness
    hnr_clamped = max(-20.0, min(40.0, hnr))
    breathiness  = round(1.0 - (hnr_clamped + 20.0) / 60.0, 4)

    return {
        "mfcc": mfcc_means,
        "pitch_mean": round(pitch_mean, 4),
        "pitch_std": round(pitch_std, 4),
        "energy_mean": round(energy_mean, 6),
        "energy_std": round(energy_std, 6),
        "amplitude_variation": amplitude_variation,
        "zcr_mean": round(zcr_mean, 6),
        "spectral_centroid_mean": round(spectral_centroid_mean, 4),
        "spectral_bandwidth_mean": round(spectral_bandwidth_mean, 4),
        "background_noise_ratio": background_noise_ratio,
        "jitter": jitter,
        "shimmer": shimmer,
        "hnr": hnr,
        "breathiness": breathiness,
        "duration": round(duration, 2),
    }
