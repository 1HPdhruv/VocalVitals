"""
Real-Time Twilio Media Streams Handler

Simplified, direct real-time audio processing for live calls.
Pushes results to frontend via WebSocket without Celery.

Key features:
- Direct WebSocket streaming from Twilio
- Real-time audio chunk processing
- Live push to frontend dashboard
- No external dependencies (no Celery, no S3)
"""

import os
import io
import json
import base64
import wave
import tempfile
import asyncio
from datetime import datetime, timezone
from typing import Set, Dict, Any, Optional
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response

# Audio processing
try:
    import audioop
except ImportError:
    import audioop_lts as audioop

import numpy as np

router = APIRouter()

# Environment variables
STREAM_WEBSOCKET_URL = os.getenv("STREAM_WEBSOCKET_URL", "wss://localhost:8000/twilio/stream-live")

# ============================================================
# Global State for Real-Time Dashboard
# ============================================================

# Connected frontend clients (for live push)
_frontend_clients: Set[WebSocket] = set()

# Active call data
_active_calls: Dict[str, dict] = {}

# Analysis results history (in-memory, for dashboard)
_call_results: list = []


async def broadcast_to_frontend(message: dict):
    """Send update to all connected frontend clients."""
    if not _frontend_clients:
        return
    
    dead_clients = set()
    for client in _frontend_clients:
        try:
            await client.send_json(message)
        except Exception:
            dead_clients.add(client)
    
    # Remove disconnected clients
    _frontend_clients.difference_update(dead_clients)


# ============================================================
# Frontend WebSocket - /ws/live
# ============================================================

@router.websocket("/ws/live")
async def frontend_websocket(ws: WebSocket):
    """
    WebSocket endpoint for frontend to receive live updates.
    
    Connect from frontend:
        const ws = new WebSocket("ws://localhost:8000/twilio/ws/live")
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data)
            updateDashboard(data)
        }
    """
    await ws.accept()
    _frontend_clients.add(ws)
    
    print(f"[live] Frontend connected. Total clients: {len(_frontend_clients)}")
    
    # Send current state on connect
    await ws.send_json({
        "type": "init",
        "active_calls": list(_active_calls.keys()),
        "recent_results": _call_results[-20:],  # Last 20 results
    })
    
    try:
        while True:
            # Keep connection alive, handle any incoming messages
            data = await ws.receive_text()
            # Could handle commands from frontend here
            
    except WebSocketDisconnect:
        _frontend_clients.discard(ws)
        print(f"[live] Frontend disconnected. Total clients: {len(_frontend_clients)}")
    except Exception as e:
        _frontend_clients.discard(ws)
        print(f"[live] Frontend error: {e}")


# ============================================================
# Twilio TwiML Endpoint - /twilio/incoming
# ============================================================

@router.post("/incoming")
async def twilio_incoming(request: Request):
    """
    Twilio webhook for incoming calls.
    Returns TwiML that starts a Media Stream.
    
    Configure in Twilio Console:
        Voice & Fax → A Call Comes In → Webhook
        URL: https://YOUR_NGROK_URL/twilio/incoming
        Method: POST
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    from_number = form.get("From", "anonymous")
    
    print(f"[twilio] Incoming call: {call_sid} from {from_number}")
    
    # Get ngrok URL from environment or request
    host = request.headers.get("host", "localhost:8000")
    protocol = "wss" if request.url.scheme == "https" else "ws"
    
    # Use environment variable if set, otherwise construct from request
    stream_url = os.getenv("STREAM_WEBSOCKET_URL")
    if not stream_url or "yourdomain" in stream_url:
        stream_url = f"{protocol}://{host}/twilio/stream-live"
    
    # TwiML response with Media Stream
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Welcome to Vocal Vitals. Your voice is being analyzed for health screening.
        Please describe how you are feeling today.
    </Say>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="callSid" value="{call_sid}" />
            <Parameter name="callerNumber" value="{from_number}" />
        </Stream>
    </Connect>
    <Say voice="Polly.Joanna">
        Thank you. Your analysis is complete. Goodbye.
    </Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


# ============================================================
# Audio Processing Functions
# ============================================================

def ulaw_to_pcm16(ulaw_bytes: bytes) -> bytes:
    """Convert μ-law to PCM16."""
    return audioop.ulaw2lin(ulaw_bytes, 2)


def resample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """Resample from 8kHz to 16kHz."""
    return audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)[0]


def pcm_to_wav_bytes(pcm_bytes: bytes, sample_rate: int = 16000) -> bytes:
    """Convert PCM bytes to WAV format in memory."""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buffer.getvalue()


def compute_audio_energy(pcm_bytes: bytes) -> float:
    """Compute RMS energy of audio."""
    if len(pcm_bytes) < 2:
        return 0.0
    try:
        return audioop.rms(pcm_bytes, 2)
    except:
        return 0.0


async def analyze_audio_chunk(pcm_bytes: bytes, call_sid: str, chunk_index: int) -> dict:
    """
    Analyze a chunk of audio and return risk scores.
    
    This is the core analysis function that:
    1. Extracts basic features
    2. Runs ML model (if available)
    3. Returns risk scores
    """
    # Convert to 16kHz for analysis
    try:
        pcm_16k = resample_8k_to_16k(pcm_bytes)
    except Exception as e:
        print(f"[analyze] Resample error: {e}")
        pcm_16k = pcm_bytes
    
    # Basic audio metrics
    energy = compute_audio_energy(pcm_16k)
    duration = len(pcm_16k) / (16000 * 2)  # seconds
    
    # Convert to numpy for analysis
    audio_array = np.frombuffer(pcm_16k, dtype=np.int16).astype(np.float32) / 32768.0
    
    # Basic feature extraction
    features = {
        "energy": energy,
        "duration": duration,
        "max_amplitude": float(np.abs(audio_array).max()) if len(audio_array) > 0 else 0,
        "zero_crossings": int(np.sum(np.abs(np.diff(np.sign(audio_array))))) if len(audio_array) > 100 else 0,
    }
    
    # Try to use the trained model for predictions
    risk_scores = await _run_model_prediction(pcm_16k, features)
    
    result = {
        "call_sid": call_sid,
        "chunk_index": chunk_index,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration": duration,
        "features": features,
        **risk_scores,
    }
    
    print(f"[analyze] Chunk {chunk_index}: energy={energy:.0f}, cough={risk_scores.get('cough_score', 0):.1f}%")
    
    return result


async def _run_model_prediction(pcm_bytes: bytes, basic_features: dict) -> dict:
    """
    Run ML model prediction on audio chunk.
    
    Returns risk scores (0-100) for each category.
    Falls back to heuristic scoring if model unavailable.
    """
    try:
        # Try to use the trained classifier
        from services.trained_classifier import predict_audio_class
        
        # Save to temp file for classifier
        wav_bytes = pcm_to_wav_bytes(pcm_bytes, 16000)
        
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        
        try:
            probs = predict_audio_class(tmp_path)
            
            return {
                "cough_score": probs.get("cough", 0) * 100,
                "respiratory_risk": probs.get("breathing", 0) * 100,
                "speech_score": probs.get("speech", 0) * 100,
                "noise_level": probs.get("noise", 0) * 100,
                "model_used": "trained_classifier",
            }
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
                
    except Exception as e:
        print(f"[analyze] Model prediction error: {e}")
    
    # Fallback: heuristic scoring based on audio features
    energy = basic_features.get("energy", 0)
    max_amp = basic_features.get("max_amplitude", 0)
    zcr = basic_features.get("zero_crossings", 0)
    
    # Simple heuristics (replace with real model in production)
    cough_score = min(100, max(0, (energy - 500) / 50)) if energy > 500 else 0
    respiratory_risk = min(100, max(0, (zcr - 1000) / 100)) if zcr > 1000 else 5
    speech_score = min(100, max(0, 50 + (energy - 200) / 20)) if 200 < energy < 2000 else 20
    
    return {
        "cough_score": cough_score,
        "respiratory_risk": respiratory_risk,
        "speech_score": speech_score,
        "noise_level": 100 - speech_score,
        "model_used": "heuristic_fallback",
    }


# ============================================================
# Twilio Media Stream WebSocket - /twilio/stream-live
# ============================================================

@router.websocket("/stream-live")
async def twilio_stream_live(ws: WebSocket):
    """
    Twilio Media Stream WebSocket endpoint.
    
    Receives base64 μ-law audio from Twilio, processes in real-time,
    and pushes results to frontend dashboard.
    """
    await ws.accept()
    
    call_sid = None
    caller_number = "unknown"
    audio_buffer = bytearray()
    chunk_index = 0
    total_duration = 0.0
    cumulative_scores = {"cough": [], "respiratory": [], "speech": []}
    
    print("[stream] Twilio Media Stream connected")
    
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            event = data.get("event")
            
            if event == "connected":
                print("[stream] Twilio stream connected")
                
            elif event == "start":
                # Stream started - extract metadata
                start_data = data.get("start", {})
                stream_sid = start_data.get("streamSid", "unknown")
                call_sid = start_data.get("callSid", "unknown")
                
                # Get custom parameters
                custom_params = start_data.get("customParameters", {})
                call_sid = custom_params.get("callSid", call_sid)
                caller_number = custom_params.get("callerNumber", "unknown")
                
                # Track active call
                _active_calls[call_sid] = {
                    "call_sid": call_sid,
                    "caller_number": caller_number,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                    "status": "active",
                }
                
                print(f"[stream] Call started: {call_sid} from {caller_number}")
                
                # Notify frontend
                await broadcast_to_frontend({
                    "type": "call_started",
                    "call_sid": call_sid,
                    "caller_number": caller_number,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                
            elif event == "media":
                if not call_sid:
                    continue
                
                # Decode base64 μ-law audio
                media_data = data.get("media", {})
                payload = media_data.get("payload", "")
                
                if not payload:
                    continue
                
                try:
                    ulaw_bytes = base64.b64decode(payload)
                    pcm_bytes = ulaw_to_pcm16(ulaw_bytes)
                    audio_buffer.extend(pcm_bytes)
                except Exception as e:
                    print(f"[stream] Audio decode error: {e}")
                    continue
                
                # Process every ~3 seconds of audio (48000 bytes at 8kHz 16-bit)
                # 8000 samples/sec * 2 bytes/sample * 3 sec = 48000 bytes
                if len(audio_buffer) >= 48000:
                    chunk_bytes = bytes(audio_buffer[:48000])
                    audio_buffer = audio_buffer[48000:]
                    
                    # Analyze chunk
                    result = await analyze_audio_chunk(chunk_bytes, call_sid, chunk_index)
                    
                    # Track scores
                    cumulative_scores["cough"].append(result.get("cough_score", 0))
                    cumulative_scores["respiratory"].append(result.get("respiratory_risk", 0))
                    cumulative_scores["speech"].append(result.get("speech_score", 0))
                    
                    total_duration += result.get("duration", 0)
                    chunk_index += 1
                    
                    # Add to results
                    result["caller_number"] = caller_number
                    result["total_duration"] = total_duration
                    
                    # Calculate running averages
                    result["avg_cough_score"] = sum(cumulative_scores["cough"]) / len(cumulative_scores["cough"])
                    result["avg_respiratory_risk"] = sum(cumulative_scores["respiratory"]) / len(cumulative_scores["respiratory"])
                    result["avg_speech_score"] = sum(cumulative_scores["speech"]) / len(cumulative_scores["speech"])
                    
                    # Determine severity
                    max_cough = max(cumulative_scores["cough"])
                    if max_cough > 60:
                        result["severity"] = "high"
                    elif max_cough > 30:
                        result["severity"] = "medium"
                    else:
                        result["severity"] = "low"
                    
                    # Push to frontend immediately
                    await broadcast_to_frontend({
                        "type": "analysis",
                        **result,
                    })
                    
            elif event == "stop":
                print(f"[stream] Call ended: {call_sid}")
                
                # Process any remaining audio
                if len(audio_buffer) > 8000:  # At least 0.5 seconds
                    result = await analyze_audio_chunk(bytes(audio_buffer), call_sid, chunk_index)
                    cumulative_scores["cough"].append(result.get("cough_score", 0))
                    cumulative_scores["respiratory"].append(result.get("respiratory_risk", 0))
                    
                    result["caller_number"] = caller_number
                    await broadcast_to_frontend({
                        "type": "analysis",
                        **result,
                    })
                
                # Generate final summary
                if cumulative_scores["cough"]:
                    final_result = {
                        "type": "call_ended",
                        "call_sid": call_sid,
                        "caller_number": caller_number,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "total_duration": total_duration,
                        "chunks_analyzed": chunk_index,
                        "final_cough_score": sum(cumulative_scores["cough"]) / len(cumulative_scores["cough"]),
                        "max_cough_score": max(cumulative_scores["cough"]),
                        "final_respiratory_risk": sum(cumulative_scores["respiratory"]) / len(cumulative_scores["respiratory"]),
                        "severity": "high" if max(cumulative_scores["cough"]) > 60 else ("medium" if max(cumulative_scores["cough"]) > 30 else "low"),
                    }
                    
                    # Store result
                    _call_results.append(final_result)
                    if len(_call_results) > 100:
                        _call_results.pop(0)
                    
                    # Notify frontend
                    await broadcast_to_frontend(final_result)
                
                # Remove from active calls
                if call_sid in _active_calls:
                    del _active_calls[call_sid]
                
                break
                
    except WebSocketDisconnect:
        print(f"[stream] WebSocket disconnected: {call_sid}")
    except Exception as e:
        print(f"[stream] Error: {e}")
    finally:
        if call_sid and call_sid in _active_calls:
            del _active_calls[call_sid]
        
        # Notify frontend of disconnection
        if call_sid:
            await broadcast_to_frontend({
                "type": "call_disconnected",
                "call_sid": call_sid,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })


# ============================================================
# API Endpoints for Dashboard
# ============================================================

@router.get("/active-calls")
async def get_active_calls():
    """Get list of currently active calls."""
    return {
        "active_calls": list(_active_calls.values()),
        "count": len(_active_calls),
    }


@router.get("/recent-results")
async def get_recent_results(limit: int = 20):
    """Get recent call analysis results."""
    return {
        "results": _call_results[-limit:],
        "total": len(_call_results),
    }


@router.get("/stats")
async def get_call_stats():
    """Get aggregate call statistics."""
    if not _call_results:
        return {
            "total_calls": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
            "avg_cough_score": 0,
        }
    
    return {
        "total_calls": len(_call_results),
        "high_risk": sum(1 for r in _call_results if r.get("severity") == "high"),
        "medium_risk": sum(1 for r in _call_results if r.get("severity") == "medium"),
        "low_risk": sum(1 for r in _call_results if r.get("severity") == "low"),
        "avg_cough_score": sum(r.get("final_cough_score", 0) for r in _call_results) / len(_call_results),
    }
