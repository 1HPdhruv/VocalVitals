import json
from pathlib import Path

import joblib
import librosa
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_PATH = ROOT / "models" / "audio_classifier.pkl"
METRICS_PATH = ROOT / "models" / "audio_classifier_metrics.json"

VALID_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm"}


def collect_files(root: Path):
    return [p for p in root.rglob("*") if p.suffix.lower() in VALID_EXTENSIONS]


def map_label(path: Path) -> str | None:
    p = str(path).lower()
    name = path.name.lower()

    # dataset-level mapping
    if "covid19-cough" in p or "cough" in p:
        if any(k in name for k in ["speech", "talk", "voice"]):
            return "speech"
        return "cough"

    if "respiratory" in p or "zenodo" in p:
        if any(k in name for k in ["wheeze", "crackle", "breath", "resp"]):
            return "breathing"
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


def preprocess_audio(file_path: Path):
    y, sr = librosa.load(file_path, sr=16000, mono=True)
    if y is None or len(y) == 0:
        return None, None

    peak = float(np.max(np.abs(y)))
    if peak <= 1e-8:
        return None, None
    y = y / peak

    y, _ = librosa.effects.trim(y, top_db=25)
    if len(y) < 16000:  # < 1 sec after trim
        return None, None

    return y, sr


def extract_vector(y: np.ndarray, sr: int) -> np.ndarray:
    rms = librosa.feature.rms(y=y)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

    silence_threshold = max(float(np.percentile(rms, 25)), 1e-6)
    pause_ratio = float(np.mean(rms <= silence_threshold))

    feats = [
        float(np.mean(rms)),
        float(np.std(rms)),
        float(np.mean(zcr)),
        float(np.std(zcr)),
        float(np.mean(centroid)),
        float(np.std(centroid)),
        float(np.mean(bandwidth)),
        float(np.std(bandwidth)),
        pause_ratio,
    ]

    mfcc_mean = np.mean(mfcc, axis=1)
    mfcc_std = np.std(mfcc, axis=1)
    feats.extend([float(v) for v in mfcc_mean])
    feats.extend([float(v) for v in mfcc_std])

    return np.array(feats, dtype=np.float32)


def build_dataset():
    files = collect_files(DATA_DIR)
    X, y, kept_files = [], [], []

    for file_path in files:
        label = map_label(file_path)
        if label not in {"cough", "speech", "breathing", "noise"}:
            continue

        y_audio, sr = preprocess_audio(file_path)
        if y_audio is None:
            continue

        vector = extract_vector(y_audio, sr)
        X.append(vector)
        y.append(label)
        kept_files.append(str(file_path))

    if not X:
        raise RuntimeError("No training samples found after preprocessing.")

    return np.stack(X), np.array(y), kept_files


def main():
    X, y, files = build_dataset()
    print(f"Total training samples: {len(X)}")
    unique_classes, counts = np.unique(y, return_counts=True)
    print(f"Class distribution: {dict(zip(unique_classes, counts))}")
    if len(X) < 1000:
        raise ValueError("Model not trained or invalid, < 1000 samples")
    print(f"[train] samples={len(X)} features={X.shape[1]}")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y if len(set(y)) > 1 else None,
    )

    clf = RandomForestClassifier(
        n_estimators=300,
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

    print(f"[train] saved model -> {MODEL_PATH}")
    print(f"[train] accuracy={acc:.4f}")


if __name__ == "__main__":
    main()
