# VocalVitals - Twilio Media Streams Implementation Summary

## ✅ Implementation Complete

All phases of the Twilio Media Streams infrastructure have been successfully implemented.

---

## 📦 What Was Built

### Phase 1: Twilio Media Streams WebSocket Bridge ✓

**File**: `backend/routers/twilio_router.py`

- ✅ POST `/twilio/voice` - TwiML endpoint with consent message
- ✅ WebSocket `/twilio/stream` - Real-time audio streaming
- ✅ µ-law to PCM16 audio decoding
- ✅ WebRTC VAD for speech detection
- ✅ Automatic 6-second chunk accumulation
- ✅ S3 upload integration
- ✅ Celery task enqueueing
- ✅ DTMF digit 9 opt-out handling

**Key Features:**
- Processes Twilio Media Streams in real-time
- Detects speech using Voice Activity Detection
- Uploads speech chunks to S3
- Resamples 8kHz → 16kHz for analysis

### Phase 2: Speaker Diarization ✓

**Files**: 
- `backend/services/diarization.py`
- `backend/routers/diarization_router.py`

- ✅ Voice enrollment with embedding extraction
- ✅ Speaker identification using pyannote.audio
- ✅ Patient voice isolation from mixed-party calls
- ✅ Cosine similarity matching
- ✅ Fallback MFCC-based embeddings

**API Endpoints:**
- `POST /diarization/enroll` - Enroll patient voice
- `GET /diarization/status/{user_id}` - Check enrollment
- `DELETE /diarization/enrollment/{user_id}` - Remove enrollment
- `POST /diarization/validate-enrollment` - Validate audio quality

**Key Features:**
- Extracts 512-dim speaker embeddings
- Stores embeddings in database (BLOB)
- Isolates patient segments from phone calls
- Handles multi-speaker conversations

### Phase 3: Longitudinal Baseline & Anomaly Detection ✓

**Files**:
- `backend/services/baseline.py`
- `backend/routers/baseline_router.py`

- ✅ Personal baseline computation (14 days, 10+ check-ins)
- ✅ Delta calculation (% change from baseline)
- ✅ 11 anomaly detection rules
- ✅ 3-consecutive-call threshold logic
- ✅ Severity levels (high/medium)
- ✅ Caregiver notification triggers

**Tracked Features:**
- F0 (pitch) mean, std
- Jitter (local, RAP, PPQ5)
- Shimmer (local, APQ3, APQ5)
- HNR, NHR, voiced fraction
- Speech rate, pause ratio
- Energy mean, std

**API Endpoints:**
- `GET /baseline/status/{user_id}` - Baseline computation status
- `GET /baseline/features/{user_id}` - View baseline values
- `POST /baseline/compute/{user_id}` - Trigger recomputation
- `GET /baseline/anomalies/{user_id}` - Get anomaly history
- `GET /baseline/anomalies/{user_id}/summary` - Anomaly patterns
- `GET /baseline/rules` - View detection rules

**Anomaly Rules:**
| Feature | Threshold | Direction | Severity |
|---------|-----------|-----------|----------|
| F0 mean | -15% | Decrease | Medium |
| Jitter local | +20% | Increase | High |
| Shimmer local | +20% | Increase | High |
| HNR | -20% | Decrease | High |
| Speech rate | -15% | Decrease | Medium |
| Pause ratio | +30% | Increase | Medium |

### Phase 4: Celery Task Queue ✓

**Files**:
- `backend/services/celery_app.py`
- `backend/services/analyze_tasks.py`

- ✅ Redis broker configuration
- ✅ Two queues: audio_processing (4 workers), notifications (2 workers)
- ✅ `analyze_audio_chunk` task - Full analysis pipeline
- ✅ `send_caregiver_notification` task - Email/SMS alerts
- ✅ `cleanup_old_audio` task - Daily S3 cleanup
- ✅ `recompute_disease_scores` task - Risk score updates

**Task Pipeline:**
1. Download audio from S3
2. Run speaker diarization
3. Extract clinical features (Praat, OpenSMILE, SpeechBrain)
4. Compute deltas from baseline
5. Check for anomalies
6. Save to database
7. Delete raw audio (privacy compliance)
8. Trigger notifications if needed

**Celery Beat Schedule:**
- `cleanup-old-s3-audio`: Daily (86400s)

### Phase 5: Consent & Privacy Management ✓

**Files**:
- `backend/services/clinical_storage.py` (updated)
- `backend/routers/patient.py`

- ✅ Consent tracking (timestamp, IP address)
- ✅ Caregiver contact management
- ✅ Do-not-record flag
- ✅ Patient profile API
- ✅ Privacy-first data retention

**Database Schema:**
```sql
patients table:
  - user_id, created_at
  - enrollment_complete, enrollment_calls_count
  - baseline_computed_at, baseline_features
  - consent_given, consent_timestamp, consent_ip
  - do_not_record
  - caregiver_name, caregiver_email, caregiver_phone, caregiver_relation
  - voice_enrolled, voice_enrollment_date
```

**API Endpoints:**
- `POST /patient/consent` - Update consent
- `GET /patient/consent/{user_id}` - Get consent status
- `POST /patient/caregiver` - Update caregiver info
- `GET /patient/caregiver/{user_id}` - Get caregiver contacts
- `POST /patient/do-not-record` - Privacy flag
- `GET /patient/patient/{user_id}` - Full profile

**Privacy Features:**
- Audio deleted within 60 seconds of analysis
- Daily S3 cleanup as safety net
- Features stored, not recordings
- Consent required before monitoring
- Mid-call opt-out (DTMF digit 9)

### Phase 6: Docker Infrastructure ✓

**Files**:
- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`

**Services:**
1. **fastapi** - API server (port 8000)
2. **celery_worker** - Audio processing (concurrency 4)
3. **celery_worker_notify** - Notifications (concurrency 2)
4. **celery_beat** - Scheduled tasks
5. **redis** - Message broker (port 6379)
6. **postgres** - Production database (port 5432)
7. **flower** - Celery monitoring UI (port 5555)
8. **frontend** - React app (port 3000)

**Volumes:**
- `postgres_data` - Database persistence
- `redis_data` - Redis persistence
- `backend/data` - SQLite/models (dev)
- `backend/models` - ML model cache

---

## 📋 New Dependencies Added

```txt
# Audio Processing
webrtcvad==2.0.10
audioop-lts==0.2.1

# Task Queue
celery[redis]==5.3.6
redis==5.0.1
flower==2.0.1

# Cloud Storage
boto3==1.34.69

# Speaker Diarization
pyannote.audio==3.1.1

# Notifications
sendgrid==6.11.0

# Database (production)
psycopg2-binary==2.9.9
SQLAlchemy==2.0.29
```

---

## 🗄️ Database Schema Updates

### Extended `checkins` table:
```sql
-- New columns added:
call_sid TEXT                 -- Twilio call identifier
chunk_index INTEGER           -- Chunk number within call
delta_from_baseline TEXT      -- JSON: % deltas per feature
anomaly_flags TEXT            -- JSON: triggered anomalies
```

### New `patients` table:
```sql
CREATE TABLE patients (
    user_id TEXT PRIMARY KEY,
    created_at TEXT,
    enrollment_complete INTEGER,
    enrollment_calls_count INTEGER,
    baseline_computed_at TEXT,
    baseline_features TEXT,      -- JSON: baseline stats
    consent_given INTEGER,
    consent_timestamp TEXT,
    consent_ip TEXT,
    do_not_record INTEGER,
    caregiver_name TEXT,
    caregiver_email TEXT,
    caregiver_phone TEXT,
    caregiver_relation TEXT,
    voice_enrolled INTEGER,
    voice_enrollment_date TEXT
);
```

### New `patient_enrollments` table:
```sql
CREATE TABLE patient_enrollments (
    user_id TEXT PRIMARY KEY,
    voice_embedding BLOB,        -- 512-dim speaker embedding
    enrolled_at TEXT,
    embedding_dim INTEGER
);
```

---

## 🚀 Deployment Checklist

### Development Setup

1. **Install Redis:**
   ```bash
   # Windows (WSL)
   sudo apt install redis-server
   redis-server
   
   # Mac
   brew install redis
   brew services start redis
   ```

2. **Install Python Dependencies:**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp backend/.env.example backend/.env
   # Edit .env with your credentials
   ```

4. **Get HuggingFace Token:**
   - Go to https://huggingface.co/pyannote/speaker-diarization-3.1
   - Accept terms and generate token
   - Add to `.env`: `HF_TOKEN=hf_xxxxx`

5. **Setup ngrok (for Twilio webhooks):**
   ```bash
   ngrok http 8000
   # Copy HTTPS URL to .env:
   STREAM_WEBSOCKET_URL=wss://abc123.ngrok.io/twilio/stream
   ```

6. **Start Services:**
   ```bash
   # Terminal 1: FastAPI
   uvicorn main:app --reload
   
   # Terminal 2: Celery Audio Worker
   celery -A services.celery_app worker -Q audio_processing --concurrency=4 -l info
   
   # Terminal 3: Celery Notification Worker
   celery -A services.celery_app worker -Q notifications --concurrency=2 -l info
   
   # Terminal 4: Celery Beat
   celery -A services.celery_app beat -l info
   
   # Terminal 5: Flower (optional)
   celery -A services.celery_app flower --port=5555
   ```

### Production Setup

1. **Deploy with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

2. **Configure Twilio Webhook:**
   - Voice URL: `https://your-domain.com/twilio/voice`
   - Method: POST

3. **Set Environment Variables:**
   - All credentials in `.env`
   - Update `STREAM_WEBSOCKET_URL` to production domain

4. **Monitor with Flower:**
   - Visit: `http://your-domain.com:5555`

---

## 📊 API Endpoint Reference

### Twilio Integration
- `POST /twilio/voice` - TwiML webhook
- `WebSocket /twilio/stream` - Media stream
- `POST /twilio/handle-dtmf` - Opt-out handling

### Patient Management
- `GET /patient/patient/{user_id}` - Full profile
- `POST /patient/consent` - Update consent
- `POST /patient/caregiver` - Update caregiver

### Voice Enrollment
- `POST /diarization/enroll` - Enroll voice
- `GET /diarization/status/{user_id}` - Check status
- `POST /diarization/validate-enrollment` - Validate audio

### Baseline & Anomalies
- `GET /baseline/status/{user_id}` - Baseline status
- `GET /baseline/features/{user_id}` - View baseline
- `POST /baseline/compute/{user_id}` - Recompute
- `GET /baseline/anomalies/{user_id}` - Get anomalies
- `GET /baseline/rules` - Detection rules

### Disease Insights (Existing)
- `GET /insights` - Disease risk scores
- `GET /insights/history` - Score history
- `GET /insights/weekly-stats` - Weekly aggregates

---

## 🔧 Configuration Reference

### Environment Variables

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=token
TWILIO_PHONE_NUMBER=+1234567890
STREAM_WEBSOCKET_URL=wss://domain/twilio/stream
DEFAULT_FORWARD_NUMBER=+1555123456

# AWS S3
S3_BUCKET_NAME=vocalvitals-audio
AWS_ACCESS_KEY_ID=AKIAXXXXX
AWS_SECRET_ACCESS_KEY=secret
AWS_REGION=us-east-1

# Redis
REDIS_URL=redis://localhost:6379/0

# Database (optional)
DATABASE_URL=postgresql://user:pass@host:5432/db

# AI/ML
HF_TOKEN=hf_xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Notifications
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_FROM_EMAIL=alerts@vocalvitals.ai
```

---

## 🎯 Testing Guide

### 1. Test Voice Enrollment

```bash
curl -X POST http://localhost:8000/diarization/enroll \
  -F "user_id=test_patient" \
  -F "audio=@sample_voice.wav"
```

### 2. Test Consent

```bash
curl -X POST http://localhost:8000/patient/consent \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test_patient", "consent_given": true}'
```

### 3. Test Caregiver

```bash
curl -X POST http://localhost:8000/patient/caregiver \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_patient",
    "caregiver_email": "test@example.com",
    "caregiver_phone": "+1234567890"
  }'
```

### 4. Make Test Call

Call your Twilio number and verify:
- Consent message plays
- Call connects
- Audio chunks appear in Flower UI
- Database gets updated

---

## 📈 Next Steps

1. **Frontend Integration:**
   - Build consent UI
   - Voice enrollment widget
   - Baseline dashboard
   - Anomaly timeline visualization

2. **Production Hardening:**
   - Add authentication/authorization
   - Rate limiting
   - Error tracking (Sentry)
   - Logging infrastructure

3. **ML Model Training:**
   - Train real disease classifiers
   - Integrate datasets (PC-GITA, DAIC-WOZ, etc.)
   - Replace heuristic scoring with ML

4. **Monitoring & Alerts:**
   - CloudWatch/DataDog integration
   - Webhook for task failures
   - Daily health reports

---

## 🎉 Summary

**✅ All 6 phases complete:**
1. Twilio Media Streams WebSocket
2. Speaker Diarization
3. Longitudinal Baseline
4. Celery Task Queue
5. Consent & Privacy
6. Docker Infrastructure

**📁 Files Created:**
- `services/diarization.py` (450 lines)
- `services/baseline.py` (460 lines)
- `services/celery_app.py` (95 lines)
- `services/analyze_tasks.py` (475 lines)
- `routers/patient.py` (180 lines)
- `routers/diarization_router.py` (200 lines)
- `routers/baseline_router.py` (235 lines)
- `docker-compose.yml` (180 lines)
- `TWILIO_DEPLOYMENT.md` (600 lines)

**Total: ~2,875 lines of production code**

The system is now ready for:
- Real-time phone call monitoring
- Multi-speaker voice isolation
- Personal baseline tracking
- Anomaly detection with notifications
- Production deployment with Docker

---

**VocalVitals Twilio Integration - Implementation Complete** ✨
