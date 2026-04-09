import os
import json
import tempfile
import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from services.audio_features import extract_features
from services.whisper_client import transcribe, compute_speech_features
from services.claude_client import get_caregiver_summary, get_final_report
from services.pdf_generator import generate_report_pdf
from services.clinic_finder import find_nearby_clinic

router = APIRouter()


class CaregiverAnalyzeRequest(BaseModel):
    audioUrl: str
    patientName: str
    caregiverId: str
    lat: Optional[float] = None
    lon: Optional[float] = None


@router.post("/analyze")
async def caregiver_analyze(req: CaregiverAnalyzeRequest):
    """
    Analyze audio for elder-care cognitive/physical decline indicators.
    """
    # Download audio
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(req.audioUrl)
            resp.raise_for_status()
        suffix = ".wav" if ".wav" in req.audioUrl.lower() else ".webm"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(resp.content)
        tmp.close()
        audio_path = tmp.name
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to download audio: {e}")

    try:
        # Extract features
        try:
            acoustic = extract_features(audio_path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Transcribe
        try:
            transcription = transcribe(audio_path)
            transcript_text = transcription.get("text", "")
            speech_feats    = compute_speech_features(transcription, acoustic.get("duration", 10))
        except Exception:
            transcript_text = ""
            speech_feats = {}

        full_features = {**acoustic, **speech_feats}

        # Get prior submissions from Firestore — placeholder, client handles this
        history = []

        # Claude caregiver analysis
        summary = await get_caregiver_summary(full_features, transcript_text, req.patientName, history)

        # Nearby clinic if severity is high
        clinic = None
        if summary.get("severity") == "high" and req.lat and req.lon:
            clinic = await find_nearby_clinic("general", req.lat, req.lon)

        # Elder-care flag analysis
        flags = {
            "word_finding_pauses": speech_feats.get("long_pauses", 0),
            "jitter_high": acoustic.get("jitter", 0) > 1.04,
            "hnr_low": acoustic.get("hnr", 20) < 10,
            "speech_rate_low": speech_feats.get("speech_rate", 3) < 1.5,
        }

        # Repetition detection (simple: check for duplicate 3-grams)
        words = transcript_text.lower().split()
        ngrams = [" ".join(words[i:i+3]) for i in range(len(words)-2)]
        repetitions = len(ngrams) - len(set(ngrams))
        flags["repetitions_detected"] = repetitions > 2

        return {
            "summary": summary,
            "acoustic_features": full_features,
            "transcript": transcript_text,
            "elder_care_flags": flags,
            "nearby_clinic": clinic,
        }
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass


class CaregiverHistoryRequest(BaseModel):
    caregiverId: str
    patientName: str
