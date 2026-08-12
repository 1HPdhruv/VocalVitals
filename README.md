# VocalVitals

> **Early-stage vocal health screening prototype** — classifying cough, breath, and background sounds using real-data trained ML models, with personal baseline drift tracking.

---

## Overview

VocalVitals is a browser-based respiratory health screening tool that records short audio clips from a microphone, extracts acoustic features in real time, and classifies them as **cough**, **breath**, or **background** using a pre-trained TensorFlow.js model.

Unlike generic audio classifiers, VocalVitals tracks your own vocal baseline across sessions and flags meaningful drift from it — making it more sensitive to *your* changes rather than population-level thresholds.

> ⚠️ **This is a research prototype only.** It is not a medical device and should not be used as a substitute for clinical diagnosis.

---

## Architecture

```
┌─────────────────────────────────────┐
│             Browser (Frontend)       │
│  Microphone → Web Audio API → Meyda │
│     → 16-dim feature vector/frame   │
│     → TF.js model inference          │
│     → Baseline drift comparison      │
└─────────────────────────────────────┘
               ▲ loads pretrained weights
┌─────────────────────────────────────┐
│         Offline Training Pipeline   │
│  Real audio (COUGHVID / Coswara /   │
│  ICBHI) → librosa feature extract   │
│  → Keras LSTM → tensorflowjs export │
└─────────────────────────────────────┘
```

**Key design decision:** The model is trained *once* offline in Python and the weights are loaded in-browser. Earlier versions (v3.x) generated synthetic samples and trained a fresh model in the browser every session — this replaces that approach with real-data trained weights and proper validation.

---

## Features

- 🎙️ **Real-time microphone recording** via the Web Audio API
- 🔬 **16-dimensional acoustic feature extraction** per frame:
  - 13 MFCCs
  - RMS energy
  - Spectral centroid
  - High-frequency energy ratio (>2 kHz)
- 🤖 **LSTM classifier** trained on real respiratory audio datasets
- 📊 **Feature distribution analysis** comparing real vs. synthetic data assumptions
- 🕵️ **Cough detection validator** with tunable onset ratio and window size
- 📈 **Personal baseline tracking** — flags drift from your own first sessions, not population norms
- 🔄 **Full Python→TF.js export pipeline** for repeatable offline retraining

---

## Project Structure

```
VocalVitals/
├── frontend/
│   ├── index.html          # UI entry point
│   ├── app.js              # Recording, Meyda feature extraction, baseline tracking
│   ├── model.js            # TF.js model loader & inference wrapper
│   └── styles.css          # Glassmorphism dark UI
│
├── training/
│   ├── data_loader.py      # Structures/generates audio data for training
│   ├── feature_extractor.py# librosa 16-dim extractor (mirrors JS exactly)
│   ├── train_vocalvitals.py# Keras LSTM training + TF.js export
│   ├── analyze_distributions.py # Real vs. synthetic feature KDE plots
│   ├── evaluate_cough_detection.py # Precision/recall for cough onset detector
│   └── test_feature_parity.py     # Validates Python↔JS feature math alignment
│
├── model/
│   └── tfjs/               # Exported TF.js model weights (loaded by browser)
│
└── docs/
    └── feature_distributions.png  # RMS / centroid / MFCC-0 distribution plots
```

---

## Getting Started

### 1. Install Python dependencies

```bash
# Recommended: use a clean virtual environment
python -m venv venv && source venv/bin/activate

pip install tensorflow==2.15.0 tensorflowjs==4.17.0 \
    librosa soundfile scikit-learn matplotlib seaborn pytest
```

### 2. Prepare your audio data

Place labeled `.wav` files (16 kHz, mono) in:

```
data/
  cough/      ← real cough clips from COUGHVID / Coswara / ICBHI
  breath/     ← breathing clips
  background/ ← ambient / silence clips
```

No real data yet? Run the mock data generator to validate the pipeline:

```bash
python training/data_loader.py
```

### 3. Analyze feature distributions

Compare your real data against the v3 synthetic assumptions before training:

```bash
python training/analyze_distributions.py
# → saves docs/feature_distributions.png
```

### 4. Train and export the model

```bash
python training/train_vocalvitals.py
# → saves model/tfjs/model.json + weight shards
```

### 5. Validate the cough detector

```bash
python training/evaluate_cough_detection.py
# Reports precision / recall; tune onset_ratio and window_ms as needed
```

### 6. Run the frontend

```bash
cd frontend
python -m http.server 8080
# Open http://localhost:8080 in Chrome/Firefox
```

---

## The 16-Dim Feature Vector

The Python extractor ([`feature_extractor.py`](training/feature_extractor.py)) and the JS extractor ([`app.js`](frontend/app.js) via Meyda) compute identical feature vectors so that a model trained in Python behaves correctly at inference time in the browser.

| Index | Feature | Notes |
|-------|---------|-------|
| 0–12  | MFCCs (13) | `n_fft=1024`, `hop_length=512`, `htk=True` |
| 13    | RMS energy | Frame-level |
| 14    | Spectral centroid | Hz |
| 15    | HF energy ratio | Sum of energy above 2 kHz / total |

> **Parity test:** Run `python training/test_feature_parity.py` to verify the Python pipeline produces vectors of the correct shape and dimensionality.

---

## Personal Baseline Tracking

After the first high-confidence cough is detected (>80% confidence), VocalVitals stores it in `localStorage` as your baseline. Subsequent sessions compare against this reference and flag **significant drift** (e.g., confidence drops below 70% of baseline) directly in the UI.

This is the core differentiator from a generic audio classifier: personalized screening rather than static population thresholds.

---

## Roadmap

- [ ] Replace mock data generator with automated COUGHVID downloader
- [ ] Tune cough onset ratio / window on real dataset (currently: `1.8×`, `60ms`)
- [ ] Field test with 10–15 volunteers (multiple languages)
- [ ] Clinician review of feature thresholds and classification logic
- [ ] Serve model from CDN / cloud storage rather than local file server

---

## Datasets

This prototype is designed to be trained on:

- **[COUGHVID](https://zenodo.org/record/4048312)** — crowd-sourced cough recordings
- **[Coswara](https://github.com/iiscleap/Coswara-Data)** — multi-modal respiratory sound data from IISc
- **[ICBHI 2017](https://bhichallenge.med.auth.gr/)** — respiratory sound challenge dataset

---

## Disclaimer

VocalVitals is a **research and educational prototype**. It has not been clinically validated and must not be used for medical diagnosis, triage, or treatment decisions. Always consult a qualified healthcare professional for any health concerns.

---

## License

MIT