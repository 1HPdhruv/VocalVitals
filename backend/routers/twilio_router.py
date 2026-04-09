"""
Twilio Media Streams WebSocket Bridge

Handles real-time audio streaming from phone calls:
- POST /twilio/voice - TwiML response with consent and media stream
- WebSocket /twilio/stream - Real-time audio processing with VAD
"""

import os
import io
import json
import base64
import wave
import tempfile
import asyncio
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

import httpx
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient
from twilio.twiml.voice_response import VoiceResponse, Dial, Stream, Say, Gather

# Audio processing
try:
    import audioop
except ImportError:
    import audioop_lts as audioop

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    print("[twilio] WARNING: webrtcvad not available, using energy-based VAD")

# AWS S3
try:
    import boto3
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    print("[twilio] WARNING: boto3 not available, S3 upload disabled")

from services.audio_features import extract_features
from services.whisper_client import transcribe, compute_speech_features

router = APIRouter()

# Environment variables (loaded from .env)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "vocalvitals-audio")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_WEBSOCKET_URL = os.getenv("STREAM_WEBSOCKET_URL", "wss://yourdomain.com/twilio/stream")

# Twilio client singleton
_twilio_client: TwilioClient | None = None

# In-memory call buffers (keyed by call_sid)
_call_buffers: dict[str, dict] = defaultdict(lambda: {
    "audio_buffer": bytearray(),
    "speech_buffer": bytearray(),
    "chunk_index": 0,
    "user_id": None,
    "target_number": None,
    "sample_rate": 8000,
    "vad": None,
    "speech_frames": 0,
    "silence_frames": 0,
    "do_not_monitor": False,
})


def get_twilio_client() -> TwilioClient:
    """Get or create Twilio client."""
    global _twilio_client
    if _twilio_client is None:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            raise HTTPException(status_code=500, detail="Twilio credentials not configured")
        _twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    return _twilio_client


def get_s3_client():
    """Get boto3 S3 client."""
    if not S3_AVAILABLE:
        return None
    return boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def ulaw_to_pcm16(ulaw_bytes: bytes) -> bytes:
    """Convert µ-law to PCM16."""
    return audioop.ulaw2lin(ulaw_bytes, 2)


def pcm16_to_wav(pcm_bytes: bytes, sample_rate: int = 8000, channels: int = 1) -> bytes:
    """Convert PCM16 bytes to WAV format."""
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return buffer.getvalue()


def resample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """Resample from 8kHz to 16kHz using linear interpolation."""
    return audioop.ratecv(pcm_8k, 2, 1, 8000, 16000, None)[0]


def is_speech_frame(pcm_frame: bytes, vad, sample_rate: int = 8000) -> bool:
    """Check if a frame contains speech using WebRTC VAD."""
    if VAD_AVAILABLE and vad:
        try:
            # WebRTC VAD requires 10, 20, or 30ms frames
            return vad.is_speech(pcm_frame, sample_rate)
        except Exception:
            pass
    
    # Fallback: energy-based detection
    if len(pcm_frame) < 2:
        return False
    rms = audioop.rms(pcm_frame, 2)
    return rms > 500  # Threshold for speech


async def upload_to_s3(wav_bytes: bytes, s3_key: str) -> bool:
    """Upload WAV to S3."""
    s3 = get_s3_client()
    if not s3:
        print(f"[twilio] S3 not available, skipping upload for {s3_key}")
        return False
    
    try:
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=wav_bytes,
            ContentType='audio/wav',
        )
        print(f"[twilio] Uploaded to S3: {s3_key}")
        return True
    except Exception as e:
        print(f"[twilio] S3 upload failed: {e}")
        return False


async def enqueue_analysis(s3_key: str, user_id: str, call_sid: str, chunk_index: int = 0):
    """Enqueue Celery task for audio analysis."""
    try:
        from services.analyze_tasks import analyze_audio_chunk
        analyze_audio_chunk.delay(s3_key, user_id, call_sid, chunk_index)
        print(f"[twilio] Enqueued analysis task for {s3_key}")
    except ImportError as e:
        print(f"[twilio] Celery not available ({e}), processing synchronously")
        # Fallback: process synchronously (not recommended for production)
        try:
            from services.clinical_features import extract_all_clinical_features
            from services.clinical_storage import save_checkin
            from services.baseline import save_checkin_with_deltas
            
            # Download and process locally
            # This is a fallback for when Celery/Redis is not available
            print(f"[twilio] Skipping synchronous processing - set up Celery for full functionality")
        except Exception as fallback_err:
            print(f"[twilio] Fallback processing failed: {fallback_err}")
    except Exception as e:
        print(f"[twilio] Failed to enqueue task: {e}")


# ============================================================
# POST /twilio/voice - TwiML endpoint
# ============================================================

@router.post("/voice")
async def twilio_voice(request: Request):
    """
    Twilio voice webhook - returns TwiML that:
    1. Plays consent message
    2. Offers opt-out via DTMF
    3. Bridges call with Media Stream
    """
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    from_number = form.get("From", "")
    to_number = form.get("To", "")
    
    # Look up patient and target number from database
    # For now, use environment variable or request parameter
    target_number = form.get("target_number") or os.getenv("DEFAULT_FORWARD_NUMBER", "+15551234567")
    user_id = form.get("user_id") or from_number
    
    # Check consent status
    consent_given = await check_consent(user_id)
    
    response = VoiceResponse()
    
    if consent_given:
        # Consent message with opt-out option
        gather = Gather(
            action="/twilio/handle-dtmf",
            method="POST",
            num_digits=1,
            timeout=3,
        )
        gather.say(
            "This call is being monitored by VocalVitals to support your health care. "
            "To opt out of monitoring for this call, press 9.",
            voice="Polly.Joanna",
        )
        response.append(gather)
        
        # Bridge call with Media Stream
        dial = Dial(caller_id=TWILIO_PHONE_NUMBER)
        
        # Add stream to fork audio
        stream = Stream(
            url=STREAM_WEBSOCKET_URL,
            track="both_tracks",
        )
        # Pass metadata via stream parameters
        stream.parameter(name="user_id", value=user_id)
        stream.parameter(name="call_sid", value=call_sid)
        stream.parameter(name="target_number", value=target_number)
        
        dial.append(stream)
        dial.number(target_number)
        response.append(dial)
    else:
        # No consent - just bridge without monitoring
        response.say(
            "Connecting your call.",
            voice="Polly.Joanna",
        )
        dial = Dial(caller_id=TWILIO_PHONE_NUMBER)
        dial.number(target_number)
        response.append(dial)
    
    return Response(content=str(response), media_type="application/xml")


@router.post("/handle-dtmf")
async def handle_dtmf(request: Request):
    """Handle DTMF input for opt-out."""
    form = await request.form()
    digits = form.get("Digits", "")
    call_sid = form.get("CallSid", "unknown")
    
    response = VoiceResponse()
    
    if digits == "9":
        # User opted out - set flag and bridge without monitoring
        if call_sid in _call_buffers:
            _call_buffers[call_sid]["do_not_monitor"] = True
        
        response.say(
            "Monitoring has been disabled for this call. Connecting you now.",
            voice="Polly.Joanna",
        )
        
        target_number = os.getenv("DEFAULT_FORWARD_NUMBER", "+15551234567")
        dial = Dial(caller_id=TWILIO_PHONE_NUMBER)
        dial.number(target_number)
        response.append(dial)
    else:
        # Continue with monitoring
        response.redirect("/twilio/continue-call", method="POST")
    
    return Response(content=str(response), media_type="application/xml")


@router.post("/continue-call")
async def continue_call(request: Request):
    """Continue call after DTMF handling."""
    form = await request.form()
    call_sid = form.get("CallSid", "unknown")
    target_number = os.getenv("DEFAULT_FORWARD_NUMBER", "+15551234567")
    
    response = VoiceResponse()
    
    dial = Dial(caller_id=TWILIO_PHONE_NUMBER)
    stream = Stream(
        url=STREAM_WEBSOCKET_URL,
        track="both_tracks",
    )
    dial.append(stream)
    dial.number(target_number)
    response.append(dial)
    
    return Response(content=str(response), media_type="application/xml")


async def check_consent(user_id: str) -> bool:
    """Check if user has given consent for monitoring."""
    from services.clinical_storage import get_patient_consent_status
    
    status = get_patient_consent_status(user_id)
    return status.get("consent_given", False) and not status.get("do_not_record", False)


# ============================================================
# WebSocket /twilio/stream - Media Stream handler
# ============================================================

@router.websocket("/stream")
async def twilio_stream(websocket: WebSocket):
    """
    Twilio Media Stream WebSocket endpoint.
    
    Receives base64 µ-law audio, processes with VAD,
    and uploads speech chunks to S3 for analysis.
    """
    await websocket.accept()
    
    call_sid = None
    user_id = None
    
    # Initialize VAD if available
    vad = None
    if VAD_AVAILABLE:
        try:
            vad = webrtcvad.Vad(2)  # Aggressiveness 2
        except Exception as e:
            print(f"[twilio] VAD init failed: {e}")
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")
            
            if event == "connected":
                print(f"[twilio] Media stream connected")
                
            elif event == "start":
                # Stream started - extract metadata
                start_data = data.get("start", {})
                call_sid = start_data.get("callSid", "unknown")
                stream_sid = start_data.get("streamSid", "unknown")
                
                # Get custom parameters
                custom_params = start_data.get("customParameters", {})
                user_id = custom_params.get("user_id", "anonymous")
                target_number = custom_params.get("target_number", "")
                
                # Initialize buffer for this call
                _call_buffers[call_sid]["user_id"] = user_id
                _call_buffers[call_sid]["target_number"] = target_number
                _call_buffers[call_sid]["vad"] = vad
                
                print(f"[twilio] Stream started: call_sid={call_sid}, user_id={user_id}")
                
            elif event == "media":
                if not call_sid:
                    continue
                
                buffer = _call_buffers[call_sid]
                
                # Check if opted out
                if buffer["do_not_monitor"]:
                    continue
                
                # Decode base64 µ-law audio
                media_data = data.get("media", {})
                payload = media_data.get("payload", "")
                track = media_data.get("track", "inbound")
                
                if not payload:
                    continue
                
                try:
                    ulaw_bytes = base64.b64decode(payload)
                    pcm_bytes = ulaw_to_pcm16(ulaw_bytes)
                except Exception as e:
                    print(f"[twilio] Audio decode error: {e}")
                    continue
                
                # Only process inbound (patient) track
                if track != "inbound":
                    continue
                
                # Add to full buffer
                buffer["audio_buffer"].extend(pcm_bytes)
                
                # VAD processing - check 20ms frames
                frame_size = 320  # 20ms at 8kHz, 16-bit = 320 bytes
                while len(pcm_bytes) >= frame_size:
                    frame = pcm_bytes[:frame_size]
                    pcm_bytes = pcm_bytes[frame_size:]
                    
                    if is_speech_frame(frame, buffer["vad"], 8000):
                        buffer["speech_buffer"].extend(frame)
                        buffer["speech_frames"] += 1
                        buffer["silence_frames"] = 0
                    else:
                        buffer["silence_frames"] += 1
                        
                        # After 0.5s of silence, check if we have enough speech
                        if buffer["silence_frames"] > 25:  # 25 frames = 0.5s
                            speech_duration = len(buffer["speech_buffer"]) / (8000 * 2)  # seconds
                            
                            if speech_duration >= 6.0:
                                # Upload speech chunk
                                await process_speech_chunk(call_sid, buffer)
                            elif speech_duration > 0.5:
                                # Too short, but keep accumulating
                                pass
                
            elif event == "stop":
                # Stream ended - flush remaining buffer
                print(f"[twilio] Stream stopped: call_sid={call_sid}")
                
                if call_sid and call_sid in _call_buffers:
                    buffer = _call_buffers[call_sid]
                    
                    if not buffer["do_not_monitor"]:
                        speech_duration = len(buffer["speech_buffer"]) / (8000 * 2)
                        
                        if speech_duration >= 2.0:
                            await process_speech_chunk(call_sid, buffer)
                    
                    # Cleanup
                    del _call_buffers[call_sid]
                
                break
                
    except WebSocketDisconnect:
        print(f"[twilio] WebSocket disconnected: call_sid={call_sid}")
        if call_sid and call_sid in _call_buffers:
            del _call_buffers[call_sid]
    except Exception as e:
        print(f"[twilio] WebSocket error: {e}")
        if call_sid and call_sid in _call_buffers:
            del _call_buffers[call_sid]


async def process_speech_chunk(call_sid: str, buffer: dict):
    """Process and upload a speech chunk."""
    user_id = buffer["user_id"]
    chunk_index = buffer["chunk_index"]
    
    # Get speech buffer
    speech_bytes = bytes(buffer["speech_buffer"])
    
    # Convert to 16kHz WAV
    pcm_16k = resample_8k_to_16k(speech_bytes)
    wav_bytes = pcm16_to_wav(pcm_16k, sample_rate=16000)
    
    # Generate S3 key
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    s3_key = f"audio/{user_id}/{call_sid}/{timestamp}_{chunk_index}.wav"
    
    # Upload to S3
    success = await upload_to_s3(wav_bytes, s3_key)
    
    if success:
        # Enqueue analysis task
        await enqueue_analysis(s3_key, user_id, call_sid, chunk_index)
    
    # Reset buffer
    buffer["speech_buffer"] = bytearray()
    buffer["chunk_index"] += 1
    buffer["speech_frames"] = 0
    buffer["silence_frames"] = 0
    
    print(f"[twilio] Processed chunk {chunk_index} for call {call_sid}: {len(speech_bytes)} bytes")


# ============================================================
# Legacy endpoints (kept for backward compatibility)
# ============================================================

@router.post("/incoming")
async def twilio_incoming(request: Request):
    """
    Twilio webhook: greets caller and records their symptoms for up to 60 seconds.
    Returns TwiML.
    """
    response = VoiceResponse()
    response.say(
        "Welcome to Vocal Vitals. Please describe how you are feeling today after the beep.",
        voice="Polly.Joanna",
    )
    response.record(
        max_length=60,
        action="/twilio/recording",
        method="POST",
        play_beep=True,
        recording_status_callback="/twilio/recording-status",
    )
    return Response(content=str(response), media_type="application/xml")


@router.post("/recording")
async def twilio_recording(request: Request):
    """Twilio callback: receives RecordingUrl, runs analysis, sends SMS."""
    form = await request.form()
    recording_url = form.get("RecordingUrl", "")
    caller_number = form.get("From", "unknown")
    call_sid = form.get("CallSid", "unknown")

    if not recording_url:
        return Response(content="<Response/>", media_type="application/xml")

    # Mask caller number for privacy
    masked_number = caller_number[:4] + "****" + caller_number[-4:] if len(caller_number) > 8 else "****"

    try:
        # Download recording from Twilio
        twilio_url = recording_url + ".wav"
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(
                twilio_url,
                auth=(TWILIO_ACCOUNT_SID or "", TWILIO_AUTH_TOKEN or ""),
            )
            resp.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.write(resp.content)
        tmp.close()
        audio_path = tmp.name

        try:
            acoustic = extract_features(audio_path)
            transcription = transcribe(audio_path)
            transcript_text = transcription.get("text", "")
            speech_feats = compute_speech_features(transcription, acoustic.get("duration", 10))
            full_features = {**acoustic, **speech_feats}

            # Quick Claude analysis
            from services.claude_client import _build_initial_analysis_payload
            import anthropic

            client_ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            from services.claude_client import SYSTEM_INITIAL
            user_msg = f"Acoustic features:\n{json.dumps(full_features, indent=2)}\n\nTranscript: {transcript_text}"

            ai_resp = client_ai.messages.create(
                model="claude-opus-4-5",
                max_tokens=2048,
                system=SYSTEM_INITIAL,
                messages=[{"role": "user", "content": user_msg}],
            )
            analysis_text = ai_resp.content[0].text.strip()
            try:
                analysis = json.loads(analysis_text)
            except Exception:
                analysis = {"severity": "unknown", "conditions": [], "specialist_recommended": "general"}

            severity = analysis.get("severity", "unknown")
            conditions = analysis.get("conditions", [])
            top_condition = conditions[0]["name"] if conditions else "Unknown"

            # Send SMS
            try:
                twilio_cli = get_twilio_client()
                sms_body = (
                    f"Vocal Vitals result: {severity.upper()} risk detected. "
                    f"Possible: {top_condition}. "
                    f"Please consult a healthcare professional."
                )
                twilio_cli.messages.create(
                    body=sms_body,
                    from_=TWILIO_PHONE_NUMBER,
                    to=caller_number,
                )
            except Exception as sms_err:
                print(f"SMS failed: {sms_err}")

        finally:
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    except Exception as e:
        print(f"Recording processing failed: {e}")

    return Response(content="<Response/>", media_type="application/xml")


@router.post("/recording-status")
async def recording_status(request: Request):
    """Handle recording status callback."""
    return Response(content="<Response/>", media_type="application/xml")
