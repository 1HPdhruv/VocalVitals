# Real Audio Classifier Training (VocalVitals)

## ✅ Quick Start (Windows)

**Ready to run:**
```batch
setup.bat     # First time: verifies setup
start.bat     # Start backend + frontend
```

**Model status:** 99.1% accuracy, 2,284 samples trained  
**Open:** http://localhost:3000

---

This project now supports a real dataset-trained audio classifier for:
- cough
- speech
- breathing
- noise

## 1) Prepare backend environment

From [backend](backend):

```bash
pip install -r requirements.txt
```

## 2) Configure Kaggle API (required)

Place `kaggle.json` in:
- Windows: `%USERPROFILE%\\.kaggle\\kaggle.json`

## 3) Download datasets

Run:

```bash
python ml/download_datasets.py
```

This script downloads/unpacks:
- `andrewmvd/covid19-cough-audio-classification` -> [backend/data/cough](backend/data/cough)
- `vbookshelf/respiratory-sound-database` -> [backend/data/respiratory](backend/data/respiratory)
- ESC-50 mirror -> [backend/data/esc50](backend/data/esc50)

Set `KAGGLE_ESC50_DATASET` if you want a specific ESC-50 Kaggle mirror.

For Zenodo, set `ZENODO_RESPIRATORY_URL` and rerun.

## 4) Train classifier

Run:

```bash
python ml/train_audio_classifier.py
```

Outputs:
- model: [backend/models/audio_classifier.pkl](backend/models/audio_classifier.pkl)
- metrics: [backend/models/audio_classifier_metrics.json](backend/models/audio_classifier_metrics.json)

## 5) Backend inference behavior

At runtime, [backend/routers/analyze.py](backend/routers/analyze.py):
1. preprocesses uploaded audio (mono, 16kHz, normalized)
2. extracts real signal features
3. uses trained classifier `predict_proba` if [backend/models/audio_classifier.pkl](backend/models/audio_classifier.pkl) exists
4. falls back to pretrained AST (`MIT/ast-finetuned-audioset`) if trained model is unavailable
5. computes VocalVitals risk scores deterministically from features + model probabilities (no randomness)

# Vocal Vitals — AI Voice Health Screening Platform

<div align="center">
  <h3>🎙️ Clinical-grade voice biomarker analysis powered by Claude AI</h3>
  <p>React + FastAPI · Whisper · librosa · parselmouth · Firebase · Twilio</p>
</div>

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- A Firebase project (see Firebase Setup below)
- Anthropic API key (for Claude)
- Twilio account (for phone screening)
- ngrok (for Twilio webhooks in development)

---

## Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate      # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env from template
copy .env.example .env       # Windows
cp .env.example .env          # Mac/Linux
# Fill in your keys (see Environment Variables below)

# Start backend
uvicorn main:app --reload --port 8000
```

### Windows — parselmouth Note
If `praat-parselmouth` fails to install on Windows, ensure you have Visual C++ Build Tools:
```
https://visualstudio.microsoft.com/visual-cpp-build-tools/
```
Or skip it — the app automatically falls back to librosa-only feature extraction.

---

## Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create .env from template
copy .env.example .env.local  # Windows
cp .env.example .env.local     # Mac/Linux
# Fill in your Firebase config

# Generate demo WAV file
cd ..
python generate_demo_wav.py

# Start frontend
cd frontend
npm run dev
```

The app will be available at `http://localhost:3000`

---

## Firebase Setup

### 1. Create Firebase Project
1. Go to https://console.firebase.google.com/
2. Create new project: **Vocal Vitals**
3. Enable **Google Analytics** (optional)

### 2. Enable Services
- **Authentication**: Enable Email/Password + Google providers
- **Firestore Database**: Create in production mode
- **Storage**: Enable with default rules

### 3. Get Web Config
Project Settings → Your apps → Add web app → Copy config:
```js
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_AUTH_DOMAIN",
  projectId: "YOUR_PROJECT_ID",
  ...
}
```
Paste into `frontend/.env.local`

### 4. Get Service Account (for backend)
Project Settings → Service Accounts → Generate New Private Key  
Extract and set in `backend/.env`:
```
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-xxx@your-project.iam.gserviceaccount.com
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

### 5. Firestore Security Rules
In Firebase Console → Firestore → Rules:
```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId} {
      allow read, write: if request.auth.uid == userId;
    }
    match /analyses/{id} {
      allow read, write: if request.auth != null;
    }
    match /journal/{id} {
      allow read, write: if request.auth != null;
    }
    match /callLogs/{id} {
      allow read: if request.auth != null;
      allow write: if true; // Twilio webhook writes without auth
    }
    match /caregiverLinks/{id} {
      allow read, write: if request.auth != null;
    }
  }
}
```

---

## 🔴 Live Call Streaming (NEW)

Real-time phone call analysis with live dashboard updates:

```
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌───────────┐
│ Phone Call  │───▶│  Twilio  │───▶│ Backend │───▶│ Dashboard │
│   (Voice)   │    │  Stream  │    │   WS    │    │  /calls   │
└─────────────┘    └──────────┘    └─────────┘    └───────────┘
```

### Quick Start
```batch
start_live.bat   # Start backend with live streaming
```

### Manual Setup
```bash
cd backend
uvicorn main:app --reload

# In another terminal:
ngrok http 8000

# Configure Twilio webhook:
# https://[ngrok-url]/twilio/incoming
```

### Endpoints
- `POST /twilio/incoming` - Twilio webhook (returns TwiML)
- `WebSocket /twilio/stream-live` - Twilio media stream
- `WebSocket /twilio/ws/live` - Frontend real-time updates
- `GET /twilio/active-calls` - Currently active calls
- `GET /twilio/recent-results` - Call analysis history
- `GET /twilio/stats` - Aggregate statistics

### Frontend Dashboard
The `/calls` page shows:
- **Live call cards** with real-time risk scores
- **Risk gauges** (cough, respiratory, speech quality)
- **Completed call history** with severity badges
- **Connection status** indicator

---

## Twilio Setup + ngrok (Phone Screening)

### 1. Install ngrok
```bash
# Windows (winget)
winget install ngrok

# Or download from https://ngrok.com/download
```

### 2. Expose backend with ngrok
```bash
ngrok http 8000
```
Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

### 3. Configure Twilio Webhook
1. Go to [Twilio Console](https://console.twilio.com/) → Phone Numbers → Your Number
2. Under **Voice & Fax** → **A CALL COMES IN**:
   - Set to **Webhook**
   - URL: `https://abc123.ngrok-free.app/twilio/incoming`
   - Method: **HTTP POST**
3. Save

### 4. Test
Call your Twilio number → hear the greeting → speak → receive SMS with results

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key from console.anthropic.com |
| `TWILIO_ACCOUNT_SID` | Twilio Account SID |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token |
| `TWILIO_PHONE_NUMBER` | Your Twilio phone number (+1234567890) |
| `WHISPER_MODEL` | `base` (fast) or `small`/`medium` (more accurate) |
| `FIREBASE_PROJECT_ID` | Firebase project ID |
| `FIREBASE_PRIVATE_KEY` | Service account private key |
| `FIREBASE_CLIENT_EMAIL` | Service account email |
| `FIREBASE_STORAGE_BUCKET` | Firebase Storage bucket name |

### Frontend (`frontend/.env.local`)
| Variable | Description |
|---|---|
| `VITE_FIREBASE_API_KEY` | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | Storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Messaging sender ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |

---

## Features

| Feature | Description |
|---|---|
| 🎙️ **Live Analysis** | Real-time waveform + Claude AI diagnosis |
| 💬 **Socratic Interview** | 3-round adaptive follow-up questioning |
| 📈 **Voice Journal** | 30-day biomarker trend graphs (Recharts) |
| 📞 **Phone Screening** | Twilio incoming call → SMS result |
| 🏥 **Elder Care** | Cognitive decline detection for caregivers |
| 🔬 **Second Opinion** | Compare two recordings side-by-side |
| 📄 **PDF Reports** | Pre-consultation notes (reportlab) |
| 🗺️ **Nearby Clinics** | OpenStreetMap Nominatim API |
| 🎯 **Demo Mode** | Full flow without microphone or Firebase |

## Architecture

```
frontend/          React + Tailwind (Vite)
  src/
    pages/         Landing, Screen, Journal, Calls, Caregiver, Compare, Report, Login
    components/    WaveformVisualizer, StreamingResponse, SocraticChat, ClinicCard, ConsistencyScore
    hooks/         useAudioRecorder
    contexts/      AuthContext
    
backend/           FastAPI (Python)
  routers/         analyze, journal, twilio_router, caregiver, compare, report
  services/        audio_features, whisper_client, claude_client, clinic_finder, pdf_generator
```

## Biomarkers Extracted

| Biomarker | Tool | Clinical Relevance |
|---|---|---|
| MFCC (13) | librosa | Vocal tract shape, articulation |
| Pitch Mean/Std | librosa YIN | Emotional state, laryngeal health |
| Jitter | parselmouth Praat | Vocal fold irregularity (Parkinson's) |
| Shimmer | parselmouth Praat | Amplitude variation, breathiness |
| HNR | parselmouth Praat | Signal-to-noise, dysphonia severity |
| Speech Rate | Whisper timestamps | Cognitive processing, fatigue |
| Pause Frequency | Whisper timestamps | Fluency, word-finding difficulty |
| Breathiness | HNR inverse | Vocal fold closure, COPD |

---

## Disclaimer
Vocal Vitals is an AI screening tool and **NOT** a medical diagnostic device. Always consult a qualified healthcare professional for medical advice.
