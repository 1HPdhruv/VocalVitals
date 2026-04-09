import os
import numpy as np
from typing import Optional

try:
    import whisper
except Exception:
    whisper = None

_model = None


def _get_model():
    global _model
    if _model is None:
        if whisper is None:
            raise RuntimeError("Local Whisper is unavailable in this environment.")
        model_name = os.getenv("WHISPER_MODEL", "base")
        print(f"Loading Whisper model: {model_name}")
        _model = whisper.load_model(model_name)
    return _model


def transcribe(audio_path: str) -> dict:
    """
    Transcribe audio using local Whisper model.
    Returns: {text, language, word_timestamps: [{word, start, end}]}
    """
    model = _get_model()
    result = model.transcribe(
        audio_path,
        word_timestamps=True,
        language=None,   # auto-detect
        verbose=False,
    )

    # Flatten word timestamps from all segments
    word_timestamps = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            word_timestamps.append({
                "word":  w.get("word", "").strip(),
                "start": round(w.get("start", 0), 3),
                "end":   round(w.get("end", 0), 3),
            })

    return {
        "text":            result.get("text", "").strip(),
        "language":        result.get("language", "en"),
        "word_timestamps": word_timestamps,
    }


def compute_speech_features(transcription: dict, duration: float) -> dict:
    """
    Compute speech rate and pause features from Whisper timestamps.
    Returns: {speech_rate, pause_freq, mean_pause_duration}
    """
    wts = transcription.get("word_timestamps", [])
    text = transcription.get("text", "")
    word_count = len(text.split()) if text else 0

    # Speech rate = words per second
    speech_rate = round(word_count / max(duration, 1), 3)

    # Detect pauses: gaps > 0.4s between consecutive words
    pauses = []
    for i in range(1, len(wts)):
        gap = wts[i]["start"] - wts[i - 1]["end"]
        if gap > 0.4:
            pauses.append(gap)

    pause_freq        = len(pauses)
    mean_pause_dur    = round(float(np.mean(pauses)), 3) if pauses else 0.0
    long_pauses       = [p for p in pauses if p > 2.0]  # > 2s = potential word-finding

    return {
        "speech_rate":         speech_rate,
        "pause_freq":          pause_freq,
        "mean_pause_duration": mean_pause_dur,
        "long_pauses":         len(long_pauses),
    }
