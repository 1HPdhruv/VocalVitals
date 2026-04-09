import os
import json
import tempfile
import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from services.audio_features import extract_features
from services.whisper_client import transcribe, compute_speech_features
from services.claude_client import get_weekly_journal_summary
from services.storage import get_user_history, get_all_history

# Import clinical features if available
try:
    from services.clinical_features import extract_all_clinical_features
    from services.clinical_storage import save_checkin, get_user_checkins
    CLINICAL_FEATURES_AVAILABLE = True
except ImportError:
    CLINICAL_FEATURES_AVAILABLE = False
    print("[journal] Clinical features not available, using basic extraction")

router = APIRouter()


@router.get("")
async def get_journal(
    userId: Optional[str] = Query(None, description="User ID to filter by"),
    limit: int = Query(60, ge=1, le=200, description="Maximum entries to return"),
    clinical: bool = Query(False, description="Use clinical storage if available")
):
    """
    Get historical analysis results for graphing.
    Returns chronological list of voice metrics.
    """
    try:
        # Try clinical storage first if requested
        if clinical and CLINICAL_FEATURES_AVAILABLE and userId:
            entries = get_user_checkins(userId, days=60, limit=limit)
            if entries:
                print(f"[journal] returning {len(entries)} clinical entries for userId={userId}")
                return entries
        
        # Fall back to regular storage
        if userId:
            entries = get_user_history(userId, limit=limit)
        else:
            entries = get_all_history(limit=limit)
        
        print(f"[journal] returning {len(entries)} entries for userId={userId}")
        return entries
    except Exception as e:
        print(f"[journal] error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class JournalCheckinRequest(BaseModel):
    audioUrl: str
    userId: str
    useClinical: bool = True  # Use clinical feature extraction


class WeeklySummaryRequest(BaseModel):
    userId: str
    entries: list  # Last 7 journal entries from Firestore


@router.post("/checkin")
async def journal_checkin(req: JournalCheckinRequest):
    """
    Process a daily journal check-in: extract acoustic features.
    Returns features to be saved and stores in clinical database.
    """
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
        # Use clinical features if available and requested
        if req.useClinical and CLINICAL_FEATURES_AVAILABLE:
            try:
                clinical_features = extract_all_clinical_features(audio_path)
                acoustic = clinical_features
                print(f"[journal] Clinical features extracted: {len(clinical_features)} fields")
            except Exception as e:
                print(f"[journal] Clinical extraction failed, falling back: {e}")
                acoustic = extract_features(audio_path)
        else:
            try:
                acoustic = extract_features(audio_path)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        # Get transcript
        try:
            transcription = transcribe(audio_path)
            transcript_text = transcription.get("text", "")
            speech_feats = compute_speech_features(transcription, acoustic.get("duration", 10))
        except Exception:
            transcript_text = ""
            speech_feats = {}

        full_features = {**acoustic, **speech_feats}
        
        # Save to clinical storage if available
        checkin_id = None
        if CLINICAL_FEATURES_AVAILABLE:
            try:
                checkin_id = save_checkin(
                    user_id=req.userId,
                    features=full_features,
                    transcript=transcript_text
                )
                print(f"[journal] Saved clinical checkin id={checkin_id}")
            except Exception as e:
                print(f"[journal] Failed to save clinical checkin: {e}")

        return {
            "acousticFeatures": full_features,
            "transcript": transcript_text,
            "userId": req.userId,
            "checkinId": checkin_id,
        }
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass


@router.post("/weekly-summary")
async def weekly_summary(req: WeeklySummaryRequest):
    """
    Generate weekly Claude summary from 7 journal entries.
    """
    if not req.entries:
        raise HTTPException(status_code=400, detail="No entries provided")

    summary = await get_weekly_journal_summary(req.entries)
    return {"summary": summary}
