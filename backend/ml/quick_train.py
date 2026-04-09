"""
Quick inline model trainer for VocalVitals.
Run this directly with Python to train the audio classifier.
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("=" * 60)
    print("VocalVitals Audio Classifier Training")
    print("=" * 60)
    
    # First install required packages
    print("\n[1/5] Checking/installing required packages...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", 
                               "imageio-ffmpeg", "pydub", "-q"])
        print("✓ Packages installed")
    except Exception as e:
        print(f"Warning: Package installation issue: {e}")
    
    # Verify ffmpeg
    print("\n[2/5] Verifying ffmpeg...")
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"✓ ffmpeg found at: {ffmpeg_path}")
    except Exception as e:
        print(f"✗ ffmpeg verification failed: {e}")
        return 1
    
    # Import training dependencies
    print("\n[3/5] Loading training modules...")
    try:
        import json
        from pathlib import Path
        import joblib
        import librosa
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report, accuracy_score
        print("✓ All modules loaded")
    except ImportError as e:
        print(f"✗ Missing module: {e}")
        return 1
    
    ROOT = Path(__file__).resolve().parents[1]
    DATA_DIR = ROOT / "data"
    MODEL_PATH = ROOT / "models" / "audio_classifier.pkl"
    METRICS_PATH = ROOT / "models" / "audio_classifier_metrics.json"
    
    VALID_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
    
    def collect_files(root):
        return [p for p in root.rglob("*") if p.suffix.lower() in VALID_EXTENSIONS]
    
    def map_label(path):
        p = str(path).lower()
        name = path.name.lower()
        
        if "covid19-cough" in p or "cough" in p:
            if any(k in name for k in ["speech", "talk", "voice"]):
                return "speech"
            return "cough"
        
        if "respiratory" in p or "zenodo" in p:
            return "breathing"
        
        if "esc50" in p or "esc-50" in p:
            if any(k in name for k in ["cough"]):
                return "cough"
            if any(k in name for k in ["speech", "talk", "crowd"]):
                return "speech"
            return "noise"
        
        if "speech" in p:
            return "speech"
        
        return None
    
    def preprocess_audio(file_path):
        try:
            y, sr = librosa.load(file_path, sr=16000, mono=True)
            if y is None or len(y) == 0:
                return None, None
            
            peak = float(np.max(np.abs(y)))
            if peak <= 1e-8:
                return None, None
            y = y / peak
            
            y, _ = librosa.effects.trim(y, top_db=25)
            if len(y) < 16000:
                return None, None
            
            return y, sr
        except Exception:
            return None, None
    
    def extract_vector(y, sr):
        rms = librosa.feature.rms(y=y)[0]
        zcr = librosa.feature.zero_crossing_rate(y)[0]
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)
        
        silence_threshold = max(float(np.percentile(rms, 25)), 1e-6)
        pause_ratio = float(np.mean(rms <= silence_threshold))
        
        feats = [
            float(np.mean(rms)), float(np.std(rms)),
            float(np.mean(zcr)), float(np.std(zcr)),
            float(np.mean(centroid)), float(np.std(centroid)),
            float(np.mean(bandwidth)), float(np.std(bandwidth)),
            pause_ratio,
        ]
        
        feats.extend([float(v) for v in np.mean(mfcc, axis=1)])
        feats.extend([float(v) for v in np.std(mfcc, axis=1)])
        
        return np.array(feats, dtype=np.float32)
    
    # Collect and process files
    print("\n[4/5] Building dataset...")
    print(f"Scanning: {DATA_DIR}")
    
    files = collect_files(DATA_DIR)
    print(f"Found {len(files)} audio files")
    
    X, y, kept_files = [], [], []
    processed = 0
    
    for file_path in files:
        label = map_label(file_path)
        if label not in {"cough", "speech", "breathing", "noise"}:
            continue
        
        y_audio, sr = preprocess_audio(file_path)
        if y_audio is None:
            continue
        
        try:
            vector = extract_vector(y_audio, sr)
            X.append(vector)
            y.append(label)
            kept_files.append(str(file_path))
            processed += 1
            
            if processed % 100 == 0:
                print(f"  Processed {processed} files...")
        except Exception:
            continue
    
    if not X:
        print("✗ No training samples found!")
        print("  Make sure audio files exist in backend/data/")
        return 1
    
    X = np.stack(X)
    y = np.array(y)
    
    unique_classes, counts = np.unique(y, return_counts=True)
    print(f"\n✓ Dataset built: {len(X)} samples")
    print(f"  Class distribution: {dict(zip(unique_classes, counts))}")
    
    if len(X) < 100:
        print("⚠ Warning: Small dataset, model may not be reliable")
    
    # Train model
    print("\n[5/5] Training model...")
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42,
        stratify=y if len(set(y)) > 1 else None
    )
    
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)
    
    y_pred = clf.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))
    report = classification_report(y_test, y_pred, output_dict=True)
    
    payload = {
        "model": clf,
        "classes": list(clf.classes_),
        "feature_dim": int(X.shape[1]),
        "sample_rate": 16000,
        "labels": ["cough", "speech", "breathing", "noise"],
    }
    
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, MODEL_PATH)
    
    metrics = {
        "accuracy": acc,
        "report": report,
        "num_samples": int(len(X)),
        "class_distribution": {k: int(v) for k, v in zip(*np.unique(y, return_counts=True))},
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    
    print(f"\n✓ Model saved to: {MODEL_PATH}")
    print(f"✓ Model size: {MODEL_PATH.stat().st_size / 1024:.1f} KB")
    print(f"✓ Accuracy: {acc * 100:.1f}%")
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
