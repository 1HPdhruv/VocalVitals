# VocalVitals — AI Voice Health Screening for Parkinson's & Diabetes

<div align="center">
  <h3>🎙️ Clinical-grade voice biomarker analysis</h3>
  <p>React + FastAPI · Whisper · librosa · parselmouth · Firebase · Twilio</p>
</div>

---

## 🌟 Overview
VocalVitals has evolved beyond basic respiratory analysis (coughs and breathing) into an advanced **neurological and systemic disease screening platform**. Our primary focus is now on the early detection and ongoing monitoring of **Parkinson's Disease** and **Diabetes** through subtle vocal biomarkers.

### 📞 Live Call Integration for Friends & Family
We have integrated a **Live Call Analysis** feature using Twilio. You can now connect with friends and family over the phone, and our system will perform real-time voice analysis during the call. This provides immediate, live insights into their health status (detecting vocal tremors, speech rate changes, and breathiness associated with Parkinson's and Diabetes neuropathy) to help you care for your loved ones from afar.

---

## 🚀 Quick Start (Windows)
**Ready to run:**
```batch
setup.bat     # First time: verifies setup
start.bat     # Start backend + frontend
start_live.bat # Start live call streaming 
```
**Open:** http://localhost:3000

---

## 🔴 Live Call Streaming (Friends & Family Integration)
Real-time phone call analysis with live dashboard updates:

```text
┌─────────────┐    ┌──────────┐    ┌─────────┐    ┌───────────┐
│ Family Call │───▶│  Twilio  │───▶│ Backend │───▶│ Dashboard │
│   (Voice)   │    │  Stream  │    │   WS    │    │  /calls   │
└─────────────┘    └──────────┘    └─────────┘    └───────────┘
```

You can set up Twilio Webhooks to route your loved ones' calls through our Live Dashboard. As you speak with them, VocalVitals analyzes their speech patterns for signs of cognitive and motor function changes.

## 🔬 How It Works: Parkinson's & Diabetes

| Disease | Relevant Vocal Biomarkers | Clinical Significance |
|---|---|---|
| **Parkinson's** | Jitter, Shimmer, HNR, Pitch Variance | Detects vocal fold rigidity, micro-tremors, and dysphonia long before physical tremors appear. |
| **Diabetes** | Speech Rate, Pause Frequency, Energy | Detects signs of diabetic neuropathy affecting laryngeal nerves, leading to vocal fatigue and muscle weakness. |

---

## 🛠️ Project Setup

### 1. Backend Environment
```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn main:app --reload --port 8000
```
*Note: Make sure to install Visual C++ Build Tools on Windows if praat-parselmouth fails to install.*

### 2. Frontend Environment
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

### 3. Twilio Configuration (For Live Calls)
```bash
# Expose backend with ngrok
ngrok http 8000
```
Configure your Twilio Webhook to point to `https://[your-ngrok-url]/twilio/incoming`.

---

## 📊 Datasets & Training (Optional)
If you want to train your own models instead of using our pre-trained weights:
1. Configure your Kaggle API key (`%USERPROFILE%\.kaggle\kaggle.json`).
2. Run `python ml/download_datasets.py` to fetch audio samples.
3. Run `python ml/train_audio_classifier.py` to generate the `.pkl` models for disease classification.

---

## ⚠️ Disclaimer
VocalVitals is an AI screening tool and **NOT** a medical diagnostic device. Always consult a qualified healthcare professional.
