# VocalVitals - Quick Reference Card

## 🚀 Start Commands

### Development (Local)
```bash
# Terminal 1: Redis
redis-server

# Terminal 2: FastAPI
cd backend
uvicorn main:app --reload

# Terminal 3: Celery Audio Worker
cd backend
celery -A services.celery_app worker -Q audio_processing --concurrency=4 -l info

# Terminal 4: Celery Notification Worker
cd backend
celery -A services.celery_app worker -Q notifications --concurrency=2 -l info

# Terminal 5: Celery Beat (scheduled tasks)
cd backend
celery -A services.celery_app beat -l info

# Terminal 6: Flower (monitoring UI)
cd backend
celery -A services.celery_app flower --port=5555
```

### Production (Docker)
```bash
docker-compose up -d           # Start all services
docker-compose logs -f         # View logs
docker-compose ps              # Check status
docker-compose down            # Stop all services
```

---

## 🔗 Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| FastAPI | http://localhost:8000 | Main API server |
| API Docs | http://localhost:8000/docs | Auto-generated OpenAPI docs |
| Flower | http://localhost:5555 | Celery task monitoring |
| Frontend | http://localhost:3000 | React application |
| Redis | localhost:6379 | Message broker |
| PostgreSQL | localhost:5432 | Database (Docker only) |

---

## 📞 Phone Call Flow

```
1. Patient calls Twilio number
   ↓
2. TwiML plays consent message
   "This call is monitored... Press 9 to opt out"
   ↓
3. Call bridges to target number (caregiver/doctor)
   ↓
4. Audio streams to WebSocket: /twilio/stream
   ↓
5. VAD detects speech → accumulates 6s chunks
   ↓
6. Chunk uploads to S3: audio/{user_id}/{call_sid}/{chunk}.wav
   ↓
7. Celery task enqueued: analyze_audio_chunk.delay()
   ↓
8. [BACKGROUND WORKER]
   - Download from S3
   - Run speaker diarization (isolate patient voice)
   - Extract clinical features (Praat, OpenSMILE, SpeechBrain)
   - Compute % deltas from personal baseline
   - Check anomaly rules
   - Save to database
   - DELETE raw audio from S3 (privacy!)
   ↓
9. If high-severity anomalies:
   → Send email/SMS to caregiver
```

---

## 🎯 Essential API Calls

### 1. Enroll Patient Voice
```bash
curl -X POST http://localhost:8000/diarization/enroll \
  -F "user_id=patient123" \
  -F "audio=@enrollment_sample.wav"
```

### 2. Give Consent
```bash
curl -X POST http://localhost:8000/patient/consent \
  -H "Content-Type: application/json" \
  -d '{"user_id":"patient123","consent_given":true}'
```

### 3. Add Caregiver
```bash
curl -X POST http://localhost:8000/patient/caregiver \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"patient123",
    "caregiver_email":"jane@example.com",
    "caregiver_phone":"+1234567890",
    "caregiver_name":"Jane Doe"
  }'
```

### 4. Check Baseline Status
```bash
curl http://localhost:8000/baseline/status/patient123
```

### 5. View Anomalies
```bash
curl http://localhost:8000/baseline/anomalies/patient123?days=7
```

### 6. Get Patient Profile
```bash
curl http://localhost:8000/patient/patient/patient123
```

---

## 🗄️ Database Tables

### patients
- `user_id`, `consent_given`, `baseline_computed_at`
- `caregiver_email`, `caregiver_phone`
- `enrollment_calls_count`, `baseline_features` (JSON)

### patient_enrollments
- `user_id`, `voice_embedding` (BLOB), `embedding_dim`

### checkins
- All voice features: `f0_mean`, `jitter_local`, `shimmer_local`, etc.
- Call metadata: `call_sid`, `chunk_index`
- Baseline data: `delta_from_baseline` (JSON), `anomaly_flags` (JSON)

### disease_scores
- 8 diseases with `score`, `ci_low`, `ci_high`
- `top_driving_features` (JSON), `checkins_used`

---

## 🔔 Anomaly Detection Rules

| Feature | Threshold | Direction | Severity | Triggers When |
|---------|-----------|-----------|----------|---------------|
| jitter_local | +20% | Increase | High | 3 consecutive calls |
| shimmer_local | +20% | Increase | High | 3 consecutive calls |
| hnr | -20% | Decrease | High | 3 consecutive calls |
| f0_mean | -15% | Decrease | Medium | 3 consecutive calls |
| speech_rate | -15% | Decrease | Medium | 3 consecutive calls |
| pause_ratio | +30% | Increase | Medium | 3 consecutive calls |

**High severity** = Immediate caregiver notification

---

## 🔧 Environment Variables (Minimum)

```env
# Twilio
TWILIO_ACCOUNT_SID=ACxxxxx
TWILIO_AUTH_TOKEN=your_token
TWILIO_PHONE_NUMBER=+1234567890
STREAM_WEBSOCKET_URL=wss://your-domain.com/twilio/stream

# AWS S3
S3_BUCKET_NAME=vocalvitals-audio
AWS_ACCESS_KEY_ID=AKIAXXXXX
AWS_SECRET_ACCESS_KEY=secret

# Redis
REDIS_URL=redis://localhost:6379/0

# HuggingFace (for pyannote.audio)
HF_TOKEN=hf_xxxxx

# Notifications (optional)
SENDGRID_API_KEY=SG.xxxxx
SENDGRID_FROM_EMAIL=alerts@vocalvitals.ai
```

---

## 🐛 Troubleshooting

### "Connection refused" on Redis
```bash
# Start Redis server
redis-server

# Check if running
redis-cli ping  # Should return PONG
```

### WebSocket not connecting
1. Check `STREAM_WEBSOCKET_URL` uses `wss://` (not `ws://`)
2. Verify ngrok is running: `ngrok http 8000`
3. Update Twilio webhook with ngrok URL

### Celery tasks not running
```bash
# Check Flower UI
open http://localhost:5555

# Verify worker is running
celery -A services.celery_app inspect active
```

### Diarization fails (no patient voice)
1. Ensure patient is enrolled: `GET /diarization/status/{user_id}`
2. Check HF_TOKEN is set in `.env`
3. Verify pyannote.audio installed: `pip show pyannote.audio`

### S3 upload fails
1. Check AWS credentials in `.env`
2. Verify bucket exists: `aws s3 ls s3://vocalvitals-audio`
3. Test permissions: `aws s3 cp test.txt s3://vocalvitals-audio/`

---

## 📊 Monitoring Checklist

### Before Each Call
- [ ] Redis is running
- [ ] Celery workers active (check Flower)
- [ ] Patient enrolled (voice + consent)
- [ ] Caregiver info added
- [ ] ngrok tunnel active (dev) or domain configured (prod)

### After Each Call
- [ ] Tasks appear in Flower UI
- [ ] Tasks complete successfully (check status)
- [ ] Database updated (`checkins` table)
- [ ] S3 audio deleted (privacy check)
- [ ] Notifications sent (if anomalies detected)

---

## 📚 Documentation Files

| File | Description |
|------|-------------|
| `TWILIO_DEPLOYMENT.md` | Full deployment guide (600 lines) |
| `IMPLEMENTATION_SUMMARY.md` | Technical implementation details |
| `QUICK_REFERENCE.md` | This file - fast lookup |
| `README.md` | Project overview |
| `backend/.env.example` | Environment template |

---

## 🎉 System Status

✅ **All 6 Phases Complete:**
1. Twilio Media Streams WebSocket
2. Speaker Diarization
3. Longitudinal Baseline
4. Celery Task Queue
5. Consent & Privacy
6. Docker Infrastructure

**Ready for:** Real-time phone call monitoring with HIPAA-compliant data handling.

---

**VocalVitals - Production Ready** 🚀
