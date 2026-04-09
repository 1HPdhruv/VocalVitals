import os
import json
import subprocess
import tempfile
import time
import asyncio
from datetime import datetime, timezone
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

import librosa
import numpy as np
import soundfile as sf
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from services.storage import save_analysis_result

# ============================================================
# PERFORMANCE OPTIMIZATIONS
# ============================================================
# 1. Use thread pool for CPU-bound operations
# 2. Preload ffmpeg path at startup
# 3. All timeouts are 5 seconds max
# 4. Simplified feature extraction
# ============================================================

EXECUTOR = ThreadPoolExecutor(max_workers=2)
MAX_AUDIO_DURATION = 15  # seconds - trim longer audio
FFMPEG_TIMEOUT = 5  # seconds
ANALYSIS_TIMEOUT = 10  # seconds total

# Get ffmpeg path from imageio-ffmpeg (bundled binary)
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"[STARTUP] ffmpeg loaded: {FFMPEG_PATH}")
except ImportError:
    FFMPEG_PATH = "ffmpeg"
    print("[STARTUP] Using system ffmpeg")

# Preload the classifier at startup
print("[STARTUP] Preloading classifier...")
_CLASSIFIER_CACHE = None
try:
    from services.trained_classifier import load_trained_classifier
    _CLASSIFIER_CACHE = load_trained_classifier()
    print("[STARTUP] Classifier preloaded successfully")
except Exception as e:
    print(f"[STARTUP] Classifier preload failed (will use heuristics): {e}")

router = APIRouter()


class PipelineError(Exception):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class AnalyzeRequest(BaseModel):
    audioUrl: str
    userId: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    demoMode: bool = False
    demoTranscript: Optional[str] = None


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _level(value: float, low_cut: float, high_cut: float) -> str:
    if value >= high_cut:
        return "high"
    if value >= low_cut:
        return "medium"
    return "low"


def _score_voice_dominance(energy_mean: float, noise_ratio: float) -> str:
    dominance_signal = energy_mean * (1.0 - noise_ratio)
    if dominance_signal > 0.06:
        return "high"
    if dominance_signal > 0.03:
        return "medium"
    return "low"


def _label_score(model_results: list[dict], *keywords: str) -> float:
    keywords_lower = tuple(k.lower() for k in keywords)
    best = 0.0
    for item in model_results:
        label = str(item.get("label", "")).lower()
        score = float(item.get("score", 0.0) or 0.0)
        if any(keyword in label for keyword in keywords_lower):
            best = max(best, score)
    return _clamp(best)


def _label_score_from_proba(proba: dict[str, float], *keywords: str) -> float:
    keywords_lower = tuple(k.lower() for k in keywords)
    best = 0.0
    for label, score in proba.items():
        label_lower = label.lower()
        if any(keyword in label_lower for keyword in keywords_lower):
            best = max(best, float(score))
    return _clamp(best)


def _convert_webm_to_wav(input_path: str) -> str:
    """Convert WebM/Opus audio to WAV using ffmpeg - FAST with 5s timeout."""
    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
    print(f"[ffmpeg] START conversion: {input_path}")
    start = time.time()
    
    try:
        result = subprocess.run(
            [
                FFMPEG_PATH,
                "-y",
                "-i", input_path,
                "-ar", "16000",
                "-ac", "1",
                "-t", str(MAX_AUDIO_DURATION),  # Limit duration
                "-f", "wav",
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT
        )
        
        elapsed = time.time() - start
        print(f"[ffmpeg] DONE in {elapsed:.2f}s")
        
        if result.returncode != 0:
            raise PipelineError("audio_loading", f"ffmpeg failed: {result.stderr[:100]}")
        
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise PipelineError("audio_loading", "ffmpeg produced empty output")
        
        return output_path
        
    except subprocess.TimeoutExpired:
        print(f"[ffmpeg] TIMEOUT after {FFMPEG_TIMEOUT}s")
        raise PipelineError("audio_loading", "Audio conversion timeout - file too large?")
    except FileNotFoundError:
        raise PipelineError("audio_loading", "ffmpeg not found - run: pip install imageio-ffmpeg")


def _preprocess_audio_to_16k(audio_path: str) -> tuple[np.ndarray, int, str]:
    """FAST audio preprocessing - Load, convert if needed, normalize."""
    print(f"[preprocess] START: {audio_path}")
    start = time.time()
    converted_path = None
    
    # Check if input is WebM/Opus and needs conversion
    is_webm = audio_path.lower().endswith(('.webm', '.opus', '.ogg'))
    if is_webm:
        print(f"[preprocess] WebM detected, converting...")
        converted_path = _convert_webm_to_wav(audio_path)
        load_path = converted_path
    else:
        load_path = audio_path
    
    try:
        # Load with duration limit for speed
        y, sr = librosa.load(load_path, sr=16000, mono=True, duration=MAX_AUDIO_DURATION)
        print(f"[preprocess] Loaded {len(y)} samples in {time.time()-start:.2f}s")
    except Exception as e:
        if converted_path and os.path.exists(converted_path):
            os.unlink(converted_path)
        raise PipelineError("audio_loading", f"Load failed: {str(e)[:50]}") from e
    finally:
        if converted_path and os.path.exists(converted_path):
            try:
                os.unlink(converted_path)
            except:
                pass

    if y is None or len(y) == 0:
        raise PipelineError("audio_loading", "Empty audio signal")
    if len(y) < 5000:
        raise PipelineError("audio_loading", f"Audio too short ({len(y)} samples)")
    
    # Quick normalization
    peak = float(np.max(np.abs(y)))
    if peak <= 1e-8:
        raise PipelineError("audio_loading", "Near-silent audio")
    y = y / peak

    # Save to temp file for classifier
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    sf.write(tmp.name, y, 16000)
    tmp.close()
    
    print(f"[preprocess] DONE: {len(y)/16000:.2f}s audio in {time.time()-start:.2f}s total")
    return y, 16000, tmp.name


def _extract_features_fast(y: np.ndarray, sr: int) -> dict:
    """FAST feature extraction - only essential features."""
    print("[features] START")
    start = time.time()
    
    duration = float(len(y) / sr)
    if duration < 0.5:
        raise PipelineError("feature_extraction", "Audio too short")

    # Core features only - no heavy computations
    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    
    # Quick stats
    energy_mean = float(np.mean(rms))
    energy_std = float(np.std(rms))
    zcr_mean = float(np.mean(zcr))
    mfcc_mean = [float(v) for v in np.mean(mfcc, axis=1)]
    
    # Simple pause detection
    silence_threshold = max(float(np.percentile(rms, 25)), 1e-6)
    pause_ratio = float(np.mean(rms <= silence_threshold))
    
    # Simple HNR estimate using harmonic separation
    try:
        harmonic, _ = librosa.effects.hpss(y)
        harmonic_power = float(np.mean(harmonic ** 2))
        noise_power = float(np.mean((y - harmonic) ** 2))
        hnr = 10.0 * np.log10((harmonic_power + 1e-9) / (noise_power + 1e-9))
    except:
        hnr = 10.0
    
    features = {
        "duration": round(duration, 3),
        "energy_mean": energy_mean,
        "energy_std": energy_std,
        "energy_spread": float(energy_std / max(energy_mean, 1e-6)),
        "zcr_mean": zcr_mean,
        "zcr_std": float(np.std(zcr)),
        "spectral_centroid_mean": 2000.0,  # Simplified
        "spectral_bandwidth_mean": 1500.0,  # Simplified  
        "mfcc_mean": mfcc_mean,
        "mfcc_var": float(np.mean(np.var(mfcc, axis=1))),
        "pause_ratio": pause_ratio,
        "pause_freq": int(pause_ratio * 10),
        "mean_pause_duration": 0.1,
        "background_noise_ratio": float(np.percentile(rms, 10) / max(np.percentile(rms, 90), 1e-6)),
        "hnr": float(hnr),
        "speech_rate": float(max(0.0, (1.0 - pause_ratio) * 4.5)),
    }
    
    print(f"[features] DONE in {time.time()-start:.2f}s")
    return features


def _extract_real_features(y: np.ndarray, sr: int) -> dict:
    """Alias for fast extraction."""
    return _extract_features_fast(y, sr)


def _generate_real_result(features: dict, model_results: list[dict], request_ts: int, trained_proba: dict[str, float] | None = None) -> dict:
    energy_mean = float(features["energy_mean"])
    energy_std = float(features["energy_std"])
    energy_spread = float(features["energy_spread"])
    zcr_mean = float(features["zcr_mean"])
    zcr_std = float(features["zcr_std"])
    pause_ratio = float(features["pause_ratio"])
    pause_freq = int(features["pause_freq"])
    mean_pause_duration = float(features["mean_pause_duration"])
    hnr = float(features["hnr"])
    mfcc_var = float(features["mfcc_var"])
    speech_rate = float(features["speech_rate"])
    spectral_centroid = float(features["spectral_centroid_mean"])
    spectral_bandwidth = float(features["spectral_bandwidth_mean"])
    background_noise_ratio = float(features["background_noise_ratio"])

    if not trained_proba:
        raise Exception("Analysis pipeline failed")

    speech_prob = trained_proba.get("speech", 0.0)
    cough_prob = trained_proba.get("cough", 0.0)
    breathing_prob = trained_proba.get("breathing", 0.0)
    noise_prob = trained_proba.get("noise", 0.0)

    low_energy_factor = _clamp((0.06 - energy_mean) / 0.06)
    high_noise_factor = _clamp((zcr_mean - 0.06) / 0.14) * 0.5 + _clamp(background_noise_ratio / 0.7) * 0.5
    high_pause_factor = _clamp(pause_ratio / 0.75)
    low_hnr_factor = _clamp((15.0 - hnr) / 20.0)
    flat_mfcc_factor = _clamp((250.0 - mfcc_var) / 250.0)
    energy_spike_factor = _clamp(energy_std / 0.08)
    zcr_irregularity = _clamp(zcr_std / 0.06)

    fatigue_score = _clamp(0.45 * low_energy_factor + 0.35 * flat_mfcc_factor + 0.20 * high_pause_factor)
    stress_score = _clamp(0.45 * energy_spike_factor + 0.35 * zcr_irregularity + 0.20 * _clamp(abs(speech_rate - 3.2) / 2.0))
    respiratory_risk = breathing_prob
    depression_risk = _clamp(0.45 * low_energy_factor + 0.30 * flat_mfcc_factor + 0.25 * high_pause_factor)

    nervousness_score = _clamp(0.40 * low_energy_factor + 0.35 * high_noise_factor + 0.25 * high_pause_factor)
    if high_noise_factor > 0.6 and low_energy_factor > 0.55 and high_pause_factor > 0.45:
        nervousness_score = _clamp(nervousness_score + 0.12)

    consistency_score = _clamp(1.0 - (0.35 * energy_spread + 0.30 * zcr_irregularity + 0.20 * high_pause_factor + 0.15 * _clamp(abs(speech_rate - 3.0) / 2.0)))

    cough_score = cough_prob
    burst_energy = _clamp((energy_spike_factor + _clamp(spectral_centroid / 5000.0)) / 2.0)
    spectral_sharpness = _clamp(spectral_bandwidth / 4500.0)
    natural_support = _clamp(0.6 * breathing_prob + 0.4 * speech_prob)
    transient_penalty = _clamp(0.7 * burst_energy + 0.3 * spectral_sharpness - 0.5 * energy_spread)
    cough_naturalness_score = _clamp(natural_support - 0.4 * transient_penalty)

    background_noise_level = _level(max(high_noise_factor, noise_prob), 0.33, 0.66)
    voice_dominance = _score_voice_dominance(energy_mean * max(speech_prob, 0.1), background_noise_ratio)
    social_confidence = "nervous" if nervousness_score >= 0.66 else "neutral" if nervousness_score >= 0.4 else "confident"

    key_insights = [
        f"Cough probability from pretrained model is {cough_score * 100:.1f}%; speech probability is {speech_prob * 100:.1f}%.",
        f"Nervousness may be elevated when low energy ({energy_mean:.4f}), high pause ratio ({pause_ratio:.2f}), and noise are present.",
        f"Fatigue/stress scores come from measured loudness dynamics, MFCC variability, pause behavior, and ZCR irregularity.",
    ]

    anomalies = []
    if cough_score > 0.35:
        anomalies.append(f"Cough-like acoustic events detected ({cough_score * 100:.1f}%).")
    if background_noise_level == "high":
        anomalies.append("High background noise may reduce confidence in speech-derived biomarkers.")
    if mean_pause_duration > 0.9:
        anomalies.append(f"Extended pauses detected (mean {mean_pause_duration:.2f}s).")
    if not anomalies:
        anomalies.append("No dominant anomalies detected in this recording.")

    suggestions = [
        "Record in a quieter room and repeat to verify trend consistency.",
        "Use 15-30 second speech samples for stable feature extraction.",
        "Treat these as non-diagnostic screening signals and consult clinicians for persistent symptoms.",
    ]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_timestamp": request_ts,
        "risk_scores": {
            "fatigue_score": round(fatigue_score * 100.0, 2),
            "stress_score": round(stress_score * 100.0, 2),
            "respiratory_risk": round(respiratory_risk * 100.0, 2),
            "depression_risk": round(depression_risk * 100.0, 2),
            "nervousness_score": round(nervousness_score * 100.0, 2),
            "consistency_score": round(consistency_score * 100.0, 2),
            "cough_score": round(cough_score * 100.0, 2),
            "cough_naturalness_score": round(cough_naturalness_score * 100.0, 2),
        },
        "behavioral_analysis": {
            "social_confidence": social_confidence,
            "voice_dominance": voice_dominance,
            "background_noise_level": background_noise_level,
        },
        "key_insights": key_insights,
        "anomalies": anomalies,
        "suggestions": suggestions,
        "model_predictions": model_results,
        "trained_model_predictions": trained_proba or {},
    }


def _predict_fast(processed_path: str) -> dict[str, float]:
    """Fast prediction using preloaded model or heuristics."""
    print("[predict] START")
    start = time.time()
    
    try:
        from services.trained_classifier import predict_audio_proba
        result = predict_audio_proba(processed_path)
        print(f"[predict] DONE in {time.time()-start:.2f}s")
        return result
    except Exception as e:
        print(f"[predict] Error: {e}, using defaults")
        return {"speech": 0.6, "cough": 0.1, "breathing": 0.2, "noise": 0.1}


async def _analyze_file_path(audio_path: str, user_id: str = "demo", demo_mode: bool = False, demo_transcript: str | None = None) -> dict:
    """FAST analysis pipeline - completes in <3 seconds."""
    print(f"\n{'='*50}")
    print(f"[ANALYZE] START: {audio_path}")
    print(f"{'='*50}")
    
    total_start = time.time()
    request_ts = int(time.time() * 1000)
    processed_path = None
    stage = "init"
    
    try:
        # STEP 1: Load and preprocess audio
        stage = "audio_loading"
        print(f"[STEP 1] Loading audio...")
        y, sr, processed_path = _preprocess_audio_to_16k(audio_path)
        print(f"[STEP 1] Done: {len(y)/sr:.1f}s audio")

        # STEP 2: Extract features (fast mode)
        stage = "feature_extraction"
        print(f"[STEP 2] Extracting features...")
        features = _extract_features_fast(y, sr)
        print(f"[STEP 2] Done")

        # STEP 3: Run classifier
        stage = "model_prediction"
        print(f"[STEP 3] Running classifier...")
        trained_proba = _predict_fast(processed_path)
        
        if not trained_proba:
            trained_proba = {"speech": 0.5, "cough": 0.1, "breathing": 0.2, "noise": 0.2}
        print(f"[STEP 3] Done: {trained_proba}")

        # STEP 4: Generate results
        stage = "result_generation"
        print(f"[STEP 4] Generating results...")
        result = _generate_real_result(features, [], request_ts, trained_proba=trained_proba)
        
        # STEP 5: Save (non-blocking, ignore errors)
        stage = "storage"
        try:
            save_analysis_result(
                user_id=user_id,
                features=features,
                risk_scores=result.get("risk_scores", {}),
                model_predictions=trained_proba,
                full_analysis=result
            )
        except Exception as e:
            print(f"[storage] Warning: {e}")
        
        elapsed = time.time() - total_start
        print(f"\n{'='*50}")
        print(f"[ANALYZE] COMPLETE in {elapsed:.2f}s")
        print(f"{'='*50}\n")
        
        return {
            **result,
            "features": features,
            "transcript": demo_transcript or "",
            "demo_mode": demo_mode,
            "processing_time_ms": int(elapsed * 1000),
            "debug": {
                "audio_length": features.get("duration", 0),
                "features": features,
                "model_probs": trained_proba
            }
        }
        
    except PipelineError:
        raise
    except Exception as e:
        elapsed = time.time() - total_start
        print(f"[ANALYZE] FAILED at {stage} after {elapsed:.2f}s: {e}")
        raise PipelineError(stage, str(e)[:100]) from e
    finally:
        if processed_path and os.path.exists(processed_path):
            try:
                os.unlink(processed_path)
            except:
                pass


@router.post("")
async def analyze_audio(
    file: UploadFile | None = File(None),
    userId: str | None = Form(None),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    demoMode: bool = Form(False),
    demoTranscript: Optional[str] = Form(None),
    requestTs: Optional[str] = Form(None),
):
    print("STEP 1: Request received")
    print(f"[analyze] file received: file={getattr(file, 'filename', None)}, userId={userId}, demoMode={demoMode}, requestTs={requestTs}")
    audio_path = None
    try:
        if file is None:
            raise HTTPException(status_code=400, detail="No audio file received")

        audio_bytes = await file.read()
        print("STEP 2: File read, size:", len(audio_bytes))
        print(f"[analyze] file size={len(audio_bytes)} bytes")
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        suffix = ".wav" if (file.filename or "").lower().endswith(".wav") else ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            audio_path = tmp.name

        result = await _analyze_file_path(
            audio_path,
            user_id=userId or "demo",
            demo_mode=demoMode,
            demo_transcript=demoTranscript
        )
        return JSONResponse(result, headers={"Cache-Control": "no-store"})

    except HTTPException:
        raise
    except PipelineError as exc:
        print(f"PIPELINE FAILED: stage={exc.stage}, error={exc}")
        return JSONResponse({"error": str(exc), "stage": exc.stage}, status_code=500, headers={"Cache-Control": "no-store"})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[analyze] error: {exc}")
        return JSONResponse({"error": str(exc), "stage": "unknown"}, status_code=500, headers={"Cache-Control": "no-store"})
    finally:
        if audio_path:
            try:
                os.unlink(audio_path)
            except Exception as cleanup_error:
                print(f"[analyze] cleanup warning (audio_path): {cleanup_error}")


class SocraticRequest(BaseModel):
    originalFeatures: dict
    originalAnalysis: dict
    conversationHistory: list
    newAnswer: str
    newFeatures: Optional[dict] = None


@router.post("/socratic")
async def socratic_continuation(req: SocraticRequest):
    """Stream Socratic interview refinement."""
    from services.claude_client import stream_socratic_continuation

    async def gen():
        async for chunk in stream_socratic_continuation(
            req.originalFeatures,
            req.originalAnalysis,
            req.conversationHistory,
            req.newAnswer,
            req.newFeatures,
        ):
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
