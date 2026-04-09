import os
import sys
import json
import tempfile
import httpx
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# Add workers to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from routers import (
    analyze, journal, twilio_router, caregiver, compare, 
    report, insights, patient, diarization_router, baseline_router,
    live_streaming, twilio_live
)

load_dotenv()

app = FastAPI(title="Vocal Vitals API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(journal.router, prefix="/journal", tags=["journal"])
app.include_router(twilio_router.router, prefix="/twilio", tags=["twilio"])
app.include_router(caregiver.router, prefix="/caregiver", tags=["caregiver"])
app.include_router(compare.router, prefix="/compare", tags=["compare"])
app.include_router(report.router, prefix="/report", tags=["report"])
app.include_router(insights.router, prefix="/insights", tags=["insights"])
app.include_router(patient.router, prefix="/patient", tags=["patient"])
app.include_router(diarization_router.router, prefix="/diarization", tags=["diarization"])
app.include_router(baseline_router.router, prefix="/baseline", tags=["baseline"])
app.include_router(live_streaming.router, prefix="/twilio", tags=["live-streaming"])
app.include_router(twilio_live.router, prefix="/twilio", tags=["twilio-live"])


@app.get("/")
async def root():
    return {"status": "Vocal Vitals API running", "version": "1.0.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}
