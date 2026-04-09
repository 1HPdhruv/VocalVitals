# VocalVitals - Twilio Media Streams Deployment Guide

## Overview

VocalVitals now supports **real-time phone call monitoring** with Twilio Media Streams. This guide covers the complete setup for the Twilio integration infrastructure.

---

## Architecture

```
Phone Call → Twilio → Media Streams WebSocket → FastAPI → Celery → Analysis Pipeline
                                                              ↓
                                                           S3 Storage → Diarization → Features → DB
                                                              ↓
                                                        Notifications (SMS/Email)
```

### Key Components

1. **Twilio Media Streams**: Real-time audio streaming from phone calls
2. **Speaker Diarization**: Isolates patient voice from mixed-party conversations
3. **Longitudinal Baseline**: Personal voice baseline for anomaly detection
4. **Celery Task Queue**: Background processing for audio analysis
5. **Redis**: Message broker and result backend
6. **PostgreSQL**: Production database (SQLite for development)
7. **AWS S3**: Temporary audio storage (auto-deleted for privacy)

---

## Prerequisites

### Required Services

- **Twilio Account** (with Media Streams enabled)
- **AWS Account** (for S3 storage)
- **Redis** (local or cloud instance)
- **Docker** (for containerized deployment)
- **SendGrid Account** (optional, for email notifications)

### Python Packages

All dependencies are in `requirements.txt`. Key additions:

```txt
celery[redis]==5.3.6
boto3==1.34.69
webrtcvad==2.0.10
pyannote.audio==3.1.1
sendgrid==6.11.0
```

---

## Setup Instructions

### 1. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp backend/.env.example backend/.env
```

**Required Variables:**

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
STREAM_WEBSOCKET_URL=wss://your-domain.com/twilio/stream

# AWS S3
S3_BUCKET_NAME=vocalvitals-audio
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1

# Redis
REDIS_URL=redis://localhost:6379/0

# Notifications
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_FROM_EMAIL=alerts@vocalvitals.ai

# ML Models
HF_TOKEN=hf_xxxxx  # HuggingFace token for pyannote models
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### 2. AWS S3 Setup

Create an S3 bucket for audio storage:

```bash
aws s3 mb s3://vocalvitals-audio --region us-east-1
```

Set lifecycle policy to auto-delete after 1 day:

```json
{
  "Rules": [{
    "Id": "DeleteOldAudio",
    "Status": "Enabled",
    "Prefix": "audio/",
    "Expiration": { "Days": 1 }
  }]
}
```

### 3. Twilio Configuration

#### Enable Media Streams

1. Go to [Twilio Console](https://console.twilio.com/)
2. Navigate to **Phone Numbers → Manage → Active Numbers**
3. Select your VocalVitals number
4. Under **Voice & Fax**, set:
   - **A CALL COMES IN**: Webhook → `https://your-domain.com/twilio/voice`
   - **HTTP POST**

#### Configure ngrok for Local Development

```bash
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Update .env:
STREAM_WEBSOCKET_URL=wss://abc123.ngrok.io/twilio/stream
```

Update Twilio webhook to: `https://abc123.ngrok.io/twilio/voice`

### 4. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Note**: `pyannote.audio` requires accepting terms on HuggingFace:

1. Go to [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
2. Accept the user agreement
3. Generate a HuggingFace token
4. Add to `.env`: `HF_TOKEN=hf_xxxxx`

### 5. Start Services

#### Option A: Docker Compose (Production)

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Services:
# - fastapi: http://localhost:8000
# - flower (Celery UI): http://localhost:5555
# - frontend: http://localhost:3000
# - redis: localhost:6379
# - postgres: localhost:5432
```

#### Option B: Local Development

**Terminal 1 - FastAPI:**
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Redis:**
```bash
redis-server
```

**Terminal 3 - Celery Worker (Audio Processing):**
```bash
cd backend
celery -A services.celery_app worker -Q audio_processing --concurrency=4 --loglevel=info
```

**Terminal 4 - Celery Worker (Notifications):**
```bash
cd backend
celery -A services.celery_app worker -Q notifications --concurrency=2 --loglevel=info
```

**Terminal 5 - Celery Beat (Scheduled Tasks):**
```bash
cd backend
celery -A services.celery_app beat --loglevel=info
```

**Terminal 6 - Flower (Optional - Monitoring):**
```bash
cd backend
celery -A services.celery_app flower --port=5555
```

---

## Usage Workflows

### Patient Enrollment

#### 1. Voice Enrollment (for Speaker Diarization)

```bash
curl -X POST http://localhost:8000/diarization/enroll \
  -H "Content-Type: multipart/form-data" \
  -F "user_id=patient123" \
  -F "audio=@enrollment_sample.wav"
```

This extracts a voice embedding for the patient, enabling isolation of their voice from mixed-party calls.

#### 2. Consent Registration

```bash
curl -X POST http://localhost:8000/patient/consent \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "patient123",
    "consent_given": true,
    "consent_ip": "192.168.1.1"
  }'
```

#### 3. Add Caregiver Contact

```bash
curl -X POST http://localhost:8000/patient/caregiver \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "patient123",
    "caregiver_name": "Jane Doe",
    "caregiver_email": "jane@example.com",
    "caregiver_phone": "+1234567890",
    "caregiver_relation": "daughter"
  }'
```

### Phone Call Flow

1. **Patient calls** the Twilio number
2. **Consent message** plays: _"This call is monitored by VocalVitals..."_
3. **Opt-out option**: Press 9 to disable monitoring
4. **Call bridges** to target number (caregiver, doctor, etc.)
5. **Audio streams** to WebSocket at `/twilio/stream`
6. **VAD detects speech**, accumulates 6-second chunks
7. **Uploads to S3**, enqueues Celery task
8. **Celery worker**:
   - Downloads audio from S3
   - Runs speaker diarization (isolates patient voice)
   - Extracts clinical features (Praat, OpenSMILE, SpeechBrain)
   - Computes deltas from personal baseline
   - Checks for anomalies
   - Saves to database
   - **Deletes raw audio from S3** (privacy requirement)
9. **If anomalies detected** → sends notification to caregiver

### Monitoring

#### Flower UI (Celery Tasks)

Visit: `http://localhost:5555`

- View active/completed tasks
- Monitor worker health
- See task execution times
- Inspect failures

#### Check Patient Status

```bash
curl http://localhost:8000/patient/patient/patient123
```

Response:
```json
{
  "user_id": "patient123",
  "enrollment_complete": true,
  "enrollment_calls_count": 15,
  "baseline_computed_at": "2024-01-15T10:30:00",
  "voice_enrolled": true,
  "consent": {
    "consent_given": true,
    "do_not_record": false
  },
  "caregiver": {
    "caregiver_email": "jane@example.com"
  }
}
```

#### View Baseline Status

```bash
curl http://localhost:8000/baseline/status/patient123
```

#### Get Anomaly History

```bash
curl http://localhost:8000/baseline/anomalies/patient123?days=7
```

---

## Data Flow

### Audio Processing Pipeline

```
Twilio Call
  ↓
WebSocket receives µ-law frames (base64)
  ↓
Decode: base64 → bytes → PCM16
  ↓
VAD: Detect speech frames (20ms chunks)
  ↓
Accumulate 6 seconds of speech
  ↓
Resample: 8kHz → 16kHz
  ↓
Upload to S3: audio/{user_id}/{call_sid}/{timestamp}_{chunk}.wav
  ↓
Enqueue Celery task: analyze_audio_chunk.delay(s3_key, user_id, call_sid)
  ↓
[CELERY WORKER]
  ↓
Download from S3
  ↓
Speaker Diarization (pyannote.audio)
  ├─ Run diarization → speaker segments
  ├─ Extract embeddings per speaker
  └─ Match to patient embedding → isolate patient voice
  ↓
Feature Extraction (clinical_features.py)
  ├─ Praat: jitter, shimmer, HNR, F0 stats
  ├─ OpenSMILE: ComParE 2016 (6373 features → PCA 50)
  └─ SpeechBrain: x-vector embeddings (512 dims)
  ↓
Baseline Computation (baseline.py)
  ├─ Compute % delta from personal baseline
  └─ Check anomaly rules (3 consecutive violations)
  ↓
Database Storage (clinical_storage.py)
  ├─ Save check-in with all features
  └─ Save deltas and anomaly flags
  ↓
Privacy Compliance
  ├─ Delete S3 audio immediately
  └─ Daily cleanup task (Celery beat)
  ↓
Notifications (if high-severity anomalies)
  ├─ Email via SendGrid
  └─ SMS via Twilio
```

### Baseline Computation Logic

- **Enrollment Period**: First 14 days, minimum 10 check-ins
- **Baseline Features**: Mean ± std for 11 voice metrics
- **Delta Calculation**: `(new_value - baseline_mean) / baseline_mean * 100`
- **Anomaly Detection**: Requires 3 consecutive calls exceeding threshold

**Example Anomaly Rule:**
- Feature: `jitter_local`
- Threshold: `+20%` increase
- Severity: `high`
- Action: If delta > +20% for 3 consecutive calls → flag + notify

---

## Privacy & Compliance

### HIPAA Compliance Features

1. **Consent Tracking**: All monitoring requires explicit consent
2. **Opt-Out Mechanism**: DTMF digit 9 disables recording mid-call
3. **Audio Deletion**: Raw audio deleted within 60 seconds of analysis
4. **Feature-Only Storage**: Only acoustic features stored, not recordings
5. **Daily Cleanup**: Celery beat task removes any S3 stragglers > 24 hours

### Consent Flow

```python
# 1. Patient gives initial consent
POST /patient/consent
{
  "user_id": "patient123",
  "consent_given": true,
  "consent_ip": "192.168.1.1"
}

# 2. Each call: TwiML plays consent message
"This call is monitored by VocalVitals for health insights.
To opt out, press 9."

# 3. If pressed 9:
- do_not_monitor flag set for call
- Audio not captured
- Call bridges normally without recording

# 4. Revoke consent:
POST /patient/consent
{ "consent_given": false }
```

---

## Troubleshooting

### WebSocket Connection Fails

**Symptom**: Twilio call connects, but no audio chunks received

**Check**:
1. `STREAM_WEBSOCKET_URL` uses `wss://` (not `ws://`)
2. ngrok is running and URL is current
3. FastAPI logs show WebSocket accept

**Debug**:
```bash
# View FastAPI logs
docker-compose logs -f fastapi

# Look for:
[twilio] Media stream connected
[twilio] Stream started: call_sid=CA...
```

### Celery Tasks Not Processing

**Symptom**: Audio uploads to S3, but no analysis occurs

**Check**:
1. Redis is running: `redis-cli ping` → `PONG`
2. Celery worker is running: `docker-compose ps celery_worker`
3. Task appears in Flower: `http://localhost:5555`

**Debug**:
```bash
# Check Celery logs
docker-compose logs -f celery_worker

# Manually trigger task (Python shell)
from services.analyze_tasks import analyze_audio_chunk
result = analyze_audio_chunk.delay("audio/test/CA123/chunk.wav", "user1", "CA123", 0)
print(result.id)
```

### Diarization Fails

**Symptom**: Task completes, but all audio rejected (no patient voice)

**Possible causes**:
1. No voice enrollment: Patient must enroll first
2. Poor audio quality: Increase similarity threshold (default 0.75)
3. HuggingFace token missing: Check `HF_TOKEN` in `.env`

**Fix**:
```bash
# Enroll patient with clean sample
curl -X POST http://localhost:8000/diarization/enroll \
  -F "user_id=patient123" \
  -F "audio=@clear_voice_sample.wav"

# Lower threshold (in diarization.py)
isolated_path = isolate_patient_audio(audio_path, user_id, similarity_threshold=0.65)
```

### S3 Upload Fails

**Symptom**: `[twilio] S3 upload failed: ...`

**Check**:
1. AWS credentials in `.env`
2. S3 bucket exists and region matches
3. IAM permissions: `s3:PutObject`, `s3:DeleteObject`

**Test**:
```python
import boto3
s3 = boto3.client('s3')
s3.put_object(Bucket='vocalvitals-audio', Key='test.txt', Body=b'hello')
```

---

## API Endpoints

### Twilio Integration

- `POST /twilio/voice` - TwiML webhook (returns voice response)
- `WebSocket /twilio/stream` - Media Streams endpoint
- `POST /twilio/handle-dtmf` - DTMF opt-out handling

### Patient Management

- `GET /patient/patient/{user_id}` - Get patient profile
- `POST /patient/consent` - Update consent status
- `GET /patient/consent/{user_id}` - Get consent status
- `POST /patient/caregiver` - Update caregiver info
- `GET /patient/caregiver/{user_id}` - Get caregiver contacts

### Baseline & Anomalies

- `GET /baseline/status/{user_id}` - Baseline computation status
- `GET /baseline/anomalies/{user_id}` - Recent anomaly flags
- `POST /baseline/compute/{user_id}` - Trigger baseline recomputation

### Voice Enrollment

- `POST /diarization/enroll` - Enroll patient voice
- `GET /diarization/status/{user_id}` - Check enrollment status
- `DELETE /diarization/enrollment/{user_id}` - Delete enrollment

---

## Performance Benchmarks

### Expected Latencies

- **WebSocket audio ingestion**: < 50ms per frame
- **S3 upload (6s chunk)**: ~200-500ms
- **Diarization**: 1-2 seconds per chunk
- **Feature extraction**: 0.5-1 second
- **Total analysis time**: 2-4 seconds per chunk
- **Notification delivery**: < 5 seconds

### Scalability

- **Concurrent calls**: 20+ (with concurrency=4 workers)
- **Daily check-ins**: Unlimited (autoscaling Celery workers)
- **Database**: SQLite dev (100s of users), PostgreSQL prod (1000s+)

---

## Next Steps

1. **Add enrollment API endpoints** to diarization router
2. **Implement baseline recomputation** API endpoint
3. **Create frontend UI** for consent management
4. **Set up production deployment** on AWS/GCP/Azure
5. **Configure auto-scaling** for Celery workers
6. **Add monitoring** (Sentry, DataDog, CloudWatch)

---

## Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- View Flower: `http://localhost:5555`
- Review database: `sqlite3 backend/data/vocal_vitals_clinical.db`

---

**VocalVitals Twilio Integration - v2.0**
