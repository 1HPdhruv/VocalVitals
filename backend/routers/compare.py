import os
import json
import tempfile
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.audio_features import extract_features
from services.whisper_client import transcribe, compute_speech_features
from services.claude_client import get_second_opinion

router = APIRouter()


class CompareRequest(BaseModel):
    audioUrlA: str
    audioUrlB: str
    userId: str


async def _download(url: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    suffix = ".wav" if ".wav" in url.lower() else ".webm"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(resp.content)
    tmp.close()
    return tmp.name


@router.post("")
async def compare_recordings(req: CompareRequest):
    path_a = await _download(req.audioUrlA)
    path_b = await _download(req.audioUrlB)

    try:
        try:
            features_a = extract_features(path_a)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Recording A error: {e}")

        try:
            features_b = extract_features(path_b)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Recording B error: {e}")

        trans_a = ""
        trans_b = ""
        try:
            trans_a = transcribe(path_a).get("text", "")
        except Exception:
            pass
        try:
            trans_b = transcribe(path_b).get("text", "")
        except Exception:
            pass

        result = await get_second_opinion(features_a, features_b, trans_a, trans_b)

        return {
            "features_a": features_a,
            "features_b": features_b,
            "transcript_a": trans_a,
            "transcript_b": trans_b,
            "comparison": result,
        }
    finally:
        for p in [path_a, path_b]:
            try:
                os.unlink(p)
            except Exception:
                pass
