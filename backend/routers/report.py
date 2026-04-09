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
from services.claude_client import get_final_report
from services.pdf_generator import generate_report_pdf

router = APIRouter()


class FinalReportRequest(BaseModel):
    audioUrl: str
    userId: str
    userName: Optional[str] = "Patient"
    interviewRounds: Optional[list] = []
    originalFeatures: Optional[dict] = None
    originalTranscript: Optional[str] = None


class GetReportRequest(BaseModel):
    analysisId: str
    userId: str


@router.post("/generate")
async def generate_report(req: FinalReportRequest):
    """
    Generate final pre-consultation report and PDF.
    """
    # If we have cached features, use them; otherwise extract fresh
    if req.originalFeatures:
        acoustic = req.originalFeatures
        transcript_text = req.originalTranscript or ""
    else:
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
            raise HTTPException(status_code=400, detail=f"Audio download failed: {e}")

        try:
            acoustic = extract_features(audio_path)
            transcription = transcribe(audio_path)
            transcript_text = transcription.get("text", "")
            speech_feats = compute_speech_features(transcription, acoustic.get("duration", 10))
            acoustic = {**acoustic, **speech_feats}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        finally:
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    # Generate final Claude report
    report_data = await get_final_report(acoustic, transcript_text, req.interviewRounds)

    # Generate PDF
    pdf_bytes = generate_report_pdf(report_data, acoustic, req.userName)

    return {
        "report": report_data,
        "acoustic_features": acoustic,
        "transcript": transcript_text,
        "pdf_base64": __import__("base64").b64encode(pdf_bytes).decode(),
    }


@router.get("/pdf/{analysis_id}")
async def download_pdf(analysis_id: str):
    """
    Return a PDF directly for download — data fetched from Firestore by client.
    In practice, the frontend downloads the PDF from Firebase Storage.
    """
    raise HTTPException(status_code=501, detail="Use Firebase Storage URL for PDF download")
