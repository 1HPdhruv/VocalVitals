"""
VocalVitals - Complete Twilio Live Call Processing

This is a standalone, production-ready module that handles:
1. Twilio webhook for incoming calls
2. WebSocket for Twilio Media Streams
3. WebSocket for frontend real-time updates
4. Audio processing and AI insights

Run with: uvicorn main:app --reload
Test with: curl http://localhost:8000/twilio/test
"""

import os
import io
import json
import base64
import wave
import asyncio
from datetime import datetime, timezone
from typing import Set, Dict, List, Any
from dataclasses import dataclass, field, asdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request, Query
from fastapi.responses import Response, JSONResponse

# Audio processing - handle Python 3.13+ deprecation
try:
    import audioop
except ImportError:
    import audioop_lts as audioop

import numpy as np

router = APIRouter()

# ============================================================
# CONFIGURATION
# ============================================================

# Set this environment variable to your ngrok URL (without protocol)
# Example: NGROK_URL=abc123.ngrok-free.app
NGROK_URL = os.getenv("NGROK_URL", "")

# ============================================================
# IN-MEMORY STATE (production would use Redis)
# ============================================================

@dataclass
class CallState:
    call_sid: str
    from_number: str
    to_number: str
    status: str = "ringing"
    started_at: str = ""
    ended_at: str = ""
    duration_sec: float = 0.0
    chunks_processed: int = 0
    # AI Insights (simulated)
    stress_level: float = 0.0
    anomaly_score: float = 0.0
    speech_clarity: float = 100.0
    voice_energy: float = 0.0
    insights: List[str] = field(default_factory=list)

# Active calls
_calls: Dict[str, CallState] = {}

# Completed calls (last 50)
_call_history: List[dict] = []

# Connected frontend WebSocket clients
_frontend_clients: Set[WebSocket] = set()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_stream_url(request: Request) -> str:
    """Get the WebSocket URL for Twilio Media Streams."""
    if NGROK_URL:
        return f"wss://{NGROK_URL}/twilio/media-stream"
    
    # Fallback: construct from request headers
    host = request.headers.get("host", "localhost:8000")
    # Twilio requires wss:// for production
    if "ngrok" in host or "localhost" not in host:
        return f"wss://{host}/twilio/media-stream"
    return f"ws://{host}/twilio/media-stream"


async def broadcast(event: dict):
    """Send event to all connected frontend clients."""
    if not _frontend_clients:
        return
    
    message = json.dumps(event)
    dead = set()
    
    for client in _frontend_clients:
        try:
            await client.send_text(message)
        except Exception:
            dead.add(client)
    
    _frontend_clients.difference_update(dead)


def analyze_audio_chunk(pcm_bytes: bytes) -> dict:
    """
    Analyze audio chunk and return AI insights.
    This is a simplified analysis - replace with real ML models.
    """
    if len(pcm_bytes) < 100:
        return {"energy": 0, "zcr": 0}
    
    try:
        # Convert to numpy array
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0  # Normalize to [-1, 1]
        
        # Basic features
        energy = float(np.sqrt(np.mean(audio ** 2)))  # RMS energy
        zcr = float(np.mean(np.abs(np.diff(np.sign(audio)))))  # Zero crossing rate
        peak = float(np.max(np.abs(audio)))
        
        # Simulated AI insights based on audio features
        # In production, these would come from ML models
        stress_level = min(100, max(0, (zcr * 500 + energy * 200)))
        anomaly_score = min(100, max(0, abs(energy - 0.1) * 300))
        speech_clarity = min(100, max(0, 100 - zcr * 200))
        
        return {
            "energy": energy,
            "zcr": zcr,
            "peak": peak,
            "stress_level": stress_level,
            "anomaly_score": anomaly_score,
            "speech_clarity": speech_clarity,
        }
    except Exception as e:
        print(f"[analyze] Error: {e}")
        return {"energy": 0, "zcr": 0, "error": str(e)}


# ============================================================
# TWILIO WEBHOOK - POST /twilio/incoming
# ============================================================

@router.post("/incoming")
async def twilio_incoming(request: Request):
    """
    Twilio webhook for incoming calls.
    
    Configure in Twilio Console:
    1. Go to Phone Numbers → Your Number
    2. Voice & Fax → A Call Comes In
    3. Webhook: https://YOUR_NGROK_URL/twilio/incoming
    4. Method: HTTP POST
    """
    try:
        form = await request.form()
    except Exception:
        form = {}
    
    call_sid = form.get("CallSid", f"test_{datetime.now().timestamp()}")
    from_number = form.get("From", "Unknown")
    to_number = form.get("To", "Unknown")
    
    print(f"\n{'='*60}")
    print(f"[INCOMING CALL]")
    print(f"  CallSid: {call_sid}")
    print(f"  From: {from_number}")
    print(f"  To: {to_number}")
    print(f"{'='*60}\n")
    
    # Create call state
    call = CallState(
        call_sid=call_sid,
        from_number=from_number,
        to_number=to_number,
        status="ringing",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _calls[call_sid] = call
    
    # Notify frontend
    await broadcast({
        "type": "call_started",
        "call": asdict(call),
    })
    
    # Build TwiML response
    stream_url = get_stream_url(request)
    print(f"[TwiML] Stream URL: {stream_url}")
    
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Welcome to Vocal Vitals. Your voice is being analyzed for health insights.
        Please speak naturally and describe how you are feeling today.
    </Say>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="CallSid" value="{call_sid}"/>
        </Stream>
    </Connect>
    <Say voice="Polly.Joanna">
        Thank you for using Vocal Vitals. Your analysis is complete. Goodbye.
    </Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


# ============================================================
# TWILIO MEDIA STREAM - WebSocket /twilio/media-stream
# ============================================================

@router.websocket("/media-stream")
async def twilio_media_stream(ws: WebSocket):
    """
    WebSocket endpoint for Twilio Media Streams.
    
    Twilio sends:
    - connected: Stream connected
    - start: Stream started with metadata
    - media: Base64 encoded audio (μ-law 8kHz)
    - stop: Stream ended
    """
    await ws.accept()
    
    call_sid = None
    audio_buffer = bytearray()
    chunk_count = 0
    
    print(f"\n[STREAM] Twilio Media Stream connected")
    
    try:
        while True:
            message = await ws.receive_text()
            data = json.loads(message)
            event = data.get("event")
            
            if event == "connected":
                print(f"[STREAM] Protocol: {data.get('protocol', 'unknown')}")
                
            elif event == "start":
                start = data.get("start", {})
                call_sid = start.get("callSid") or start.get("customParameters", {}).get("CallSid")
                stream_sid = start.get("streamSid", "unknown")
                
                print(f"[STREAM] Started - CallSid: {call_sid}, StreamSid: {stream_sid}")
                
                # Update call status
                if call_sid and call_sid in _calls:
                    _calls[call_sid].status = "active"
                    await broadcast({
                        "type": "call_active",
                        "call_sid": call_sid,
                    })
                
            elif event == "media":
                media = data.get("media", {})
                payload = media.get("payload", "")
                
                if not payload:
                    continue
                
                # Decode base64 μ-law audio
                try:
                    ulaw_bytes = base64.b64decode(payload)
                    # Convert μ-law to PCM16
                    pcm_bytes = audioop.ulaw2lin(ulaw_bytes, 2)
                    audio_buffer.extend(pcm_bytes)
                except Exception as e:
                    print(f"[STREAM] Decode error: {e}")
                    continue
                
                # Process every ~2 seconds (32000 bytes at 8kHz 16-bit)
                if len(audio_buffer) >= 32000:
                    chunk_count += 1
                    chunk_data = bytes(audio_buffer[:32000])
                    audio_buffer = audio_buffer[32000:]
                    
                    # Analyze audio
                    insights = analyze_audio_chunk(chunk_data)
                    
                    print(f"[STREAM] Chunk #{chunk_count}: energy={insights.get('energy', 0):.4f}, "
                          f"stress={insights.get('stress_level', 0):.1f}%")
                    
                    # Update call state
                    if call_sid and call_sid in _calls:
                        call = _calls[call_sid]
                        call.chunks_processed = chunk_count
                        call.duration_sec = chunk_count * 2.0
                        call.stress_level = insights.get("stress_level", 0)
                        call.anomaly_score = insights.get("anomaly_score", 0)
                        call.speech_clarity = insights.get("speech_clarity", 100)
                        call.voice_energy = insights.get("energy", 0) * 100
                        
                        # Generate insight messages
                        if insights.get("stress_level", 0) > 60:
                            if "Elevated stress detected" not in call.insights:
                                call.insights.append("Elevated stress detected")
                        if insights.get("anomaly_score", 0) > 50:
                            if "Voice anomaly detected" not in call.insights:
                                call.insights.append("Voice anomaly detected")
                    
                    # Broadcast to frontend
                    await broadcast({
                        "type": "analysis_update",
                        "call_sid": call_sid,
                        "chunk": chunk_count,
                        "duration_sec": chunk_count * 2.0,
                        "insights": insights,
                        "call": asdict(_calls[call_sid]) if call_sid and call_sid in _calls else None,
                    })
                
            elif event == "stop":
                print(f"[STREAM] Stopped - CallSid: {call_sid}")
                
                # Process remaining audio
                if len(audio_buffer) > 1600:  # At least 0.1 sec
                    insights = analyze_audio_chunk(bytes(audio_buffer))
                    chunk_count += 1
                
                # Finalize call
                if call_sid and call_sid in _calls:
                    call = _calls[call_sid]
                    call.status = "ended"
                    call.ended_at = datetime.now(timezone.utc).isoformat()
                    call.duration_sec = chunk_count * 2.0
                    
                    # Add to history
                    _call_history.insert(0, asdict(call))
                    if len(_call_history) > 50:
                        _call_history.pop()
                    
                    # Broadcast
                    await broadcast({
                        "type": "call_ended",
                        "call": asdict(call),
                    })
                    
                    # Remove from active
                    del _calls[call_sid]
                
                break
                
    except WebSocketDisconnect:
        print(f"[STREAM] Disconnected - CallSid: {call_sid}")
    except Exception as e:
        print(f"[STREAM] Error: {e}")
    finally:
        # Cleanup
        if call_sid and call_sid in _calls:
            call = _calls[call_sid]
            call.status = "ended"
            call.ended_at = datetime.now(timezone.utc).isoformat()
            _call_history.insert(0, asdict(call))
            await broadcast({"type": "call_ended", "call": asdict(call)})
            del _calls[call_sid]


# ============================================================
# FRONTEND WEBSOCKET - /twilio/ws/dashboard
# ============================================================

@router.websocket("/ws/dashboard")
async def frontend_dashboard_ws(ws: WebSocket):
    """
    WebSocket for frontend to receive real-time call updates.
    
    Connect: ws://localhost:8000/twilio/ws/dashboard
    
    Events sent:
    - init: Current state (active calls, history)
    - call_started: New incoming call
    - call_active: Call connected
    - analysis_update: AI insights update
    - call_ended: Call completed
    """
    await ws.accept()
    _frontend_clients.add(ws)
    
    print(f"[DASHBOARD] Frontend connected. Total: {len(_frontend_clients)}")
    
    # Send current state
    await ws.send_json({
        "type": "init",
        "active_calls": [asdict(c) for c in _calls.values()],
        "history": _call_history[:20],
    })
    
    try:
        while True:
            # Keep alive - also allows frontend to send commands
            msg = await ws.receive_text()
            # Handle ping/pong
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[DASHBOARD] Error: {e}")
    finally:
        _frontend_clients.discard(ws)
        print(f"[DASHBOARD] Frontend disconnected. Total: {len(_frontend_clients)}")


# ============================================================
# REST API ENDPOINTS
# ============================================================

@router.get("/calls/active")
async def get_active_calls():
    """Get all currently active calls."""
    return {
        "count": len(_calls),
        "calls": [asdict(c) for c in _calls.values()],
    }


@router.get("/calls/history")
async def get_call_history(limit: int = Query(20, ge=1, le=100)):
    """Get recent call history."""
    return {
        "count": len(_call_history),
        "calls": _call_history[:limit],
    }


@router.get("/calls/{call_sid}")
async def get_call(call_sid: str):
    """Get specific call by SID."""
    if call_sid in _calls:
        return {"status": "active", "call": asdict(_calls[call_sid])}
    
    for call in _call_history:
        if call.get("call_sid") == call_sid:
            return {"status": "completed", "call": call}
    
    return JSONResponse({"error": "Call not found"}, status_code=404)


@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify the system is working."""
    return {
        "status": "ok",
        "message": "VocalVitals Twilio integration is running",
        "endpoints": {
            "webhook": "POST /twilio/incoming",
            "media_stream": "WebSocket /twilio/media-stream",
            "dashboard": "WebSocket /twilio/ws/dashboard",
            "active_calls": "GET /twilio/calls/active",
            "call_history": "GET /twilio/calls/history",
        },
        "ngrok_url": NGROK_URL or "Not set - will use request host",
        "active_calls": len(_calls),
        "frontend_clients": len(_frontend_clients),
    }


@router.post("/test/simulate-call")
async def simulate_call():
    """Simulate an incoming call for testing without Twilio."""
    call_sid = f"SIM_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    call = CallState(
        call_sid=call_sid,
        from_number="+1555123TEST",
        to_number="+17625722165",
        status="active",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    _calls[call_sid] = call
    
    await broadcast({"type": "call_started", "call": asdict(call)})
    
    # Simulate 5 analysis updates
    for i in range(5):
        await asyncio.sleep(1)
        call.chunks_processed = i + 1
        call.duration_sec = (i + 1) * 2.0
        call.stress_level = 20 + i * 10
        call.anomaly_score = 10 + i * 5
        call.speech_clarity = 95 - i * 3
        call.voice_energy = 30 + i * 8
        
        if i == 3:
            call.insights.append("Elevated stress detected")
        
        await broadcast({
            "type": "analysis_update",
            "call_sid": call_sid,
            "chunk": i + 1,
            "duration_sec": call.duration_sec,
            "call": asdict(call),
        })
    
    # End call
    call.status = "ended"
    call.ended_at = datetime.now(timezone.utc).isoformat()
    _call_history.insert(0, asdict(call))
    del _calls[call_sid]
    
    await broadcast({"type": "call_ended", "call": asdict(call)})
    
    return {"status": "ok", "call_sid": call_sid, "message": "Simulated call completed"}
