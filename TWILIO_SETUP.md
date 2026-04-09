# VocalVitals - Twilio Live Call Setup Guide

## Quick Start (3 Steps)

### Step 1: Start ngrok
```bash
ngrok http 8000
```
Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

### Step 2: Configure Twilio
1. Go to [Twilio Console](https://console.twilio.com/)
2. Phone Numbers → **+17625722165**
3. Voice & Fax → "A Call Comes In"
4. Set:
   - Webhook URL: `https://YOUR_NGROK_URL/twilio/incoming`
   - Method: **HTTP POST**
5. Save

### Step 3: Start the App
```bash
# Terminal 1 - Backend
cd backend
uvicorn main:app --reload

# Terminal 2 - Frontend  
cd frontend
npm run dev
```

Open: http://localhost:3000/live

---

## Test Without Calling

### Simulate a Call (Backend API)
```bash
curl -X POST http://localhost:8000/twilio/test/simulate-call
```

### Check System Status
```bash
curl http://localhost:8000/twilio/test
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/twilio/incoming` | POST | Twilio webhook - returns TwiML |
| `/twilio/media-stream` | WebSocket | Twilio audio stream |
| `/twilio/ws/dashboard` | WebSocket | Frontend real-time updates |
| `/twilio/calls/active` | GET | List active calls |
| `/twilio/calls/history` | GET | Recent call history |
| `/twilio/test` | GET | System status |
| `/twilio/test/simulate-call` | POST | Simulate a call |

---

## How It Works

```
┌──────────────┐      ┌───────────┐      ┌──────────────┐
│  Phone Call  │─────▶│  Twilio   │─────▶│   ngrok      │
│              │      │  Cloud    │      │  (HTTPS)     │
└──────────────┘      └───────────┘      └──────┬───────┘
                                                │
                                                ▼
┌──────────────┐      ┌───────────┐      ┌──────────────┐
│   Browser    │◀────▶│  FastAPI  │◀─────│ POST /twilio │
│   /live      │  WS  │  Backend  │      │   /incoming  │
└──────────────┘      └─────┬─────┘      └──────────────┘
                            │
                            ▼ TwiML Response
                      ┌───────────┐
                      │  <Stream> │
                      │    wss:// │
                      └─────┬─────┘
                            │
                            ▼
                      ┌───────────┐
                      │ WebSocket │
                      │ /media-   │
                      │  stream   │
                      └─────┬─────┘
                            │
                   Audio Processing
                   AI Insights
                            │
                            ▼
                      ┌───────────┐
                      │ Broadcast │
                      │ to /live  │
                      │ dashboard │
                      └───────────┘
```

---

## Twilio Settings

- **Account SID**: `YOUR_TWILIO_ACCOUNT_SID`
- **Phone Number**: `YOUR_TWILIO_PHONE_NUMBER`

### Webhook Configuration
- URL: `https://[ngrok-url]/twilio/incoming`
- Method: `HTTP POST`
- Fallback: Leave empty

### Media Stream
The TwiML automatically configures media streaming:
```xml
<Response>
    <Say>Welcome to Vocal Vitals...</Say>
    <Connect>
        <Stream url="wss://[ngrok-url]/twilio/media-stream"/>
    </Connect>
</Response>
```

---

## Troubleshooting

### "Connection refused"
- Make sure backend is running on port 8000
- Check: `curl http://localhost:8000/health`

### "WebSocket failed"
- Ensure ngrok is running
- Twilio requires `wss://` (not `ws://`)
- Check ngrok dashboard: http://localhost:4040

### "No audio received"
- Verify Twilio webhook URL is correct
- Check ngrok logs for incoming requests
- Look at backend console for `[STREAM]` messages

### "Frontend not updating"
- Open browser DevTools → Network → WS
- Check WebSocket connection to `/twilio/ws/dashboard`
- Verify backend logs show `[DASHBOARD] Frontend connected`

---

## Debug Checklist

1. [ ] ngrok running: `ngrok http 8000`
2. [ ] Backend running: `uvicorn main:app --reload`
3. [ ] Twilio webhook set to ngrok URL
4. [ ] Test endpoint works: `curl http://localhost:8000/twilio/test`
5. [ ] Frontend connected: Check for "Live" indicator
6. [ ] Simulate call works: `curl -X POST .../test/simulate-call`
7. [ ] Real call: Dial +17625722165

---

## Code Files

| File | Purpose |
|------|---------|
| `backend/routers/twilio_live.py` | All Twilio handling |
| `frontend/src/pages/TwilioLive.jsx` | Live dashboard UI |
| `backend/main.py` | FastAPI app with routers |

---

## Environment Variables (Optional)

```bash
# backend/.env
NGROK_URL=abc123.ngrok-free.app  # Auto-detected from request if not set
```
