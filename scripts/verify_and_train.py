import os
from pathlib import Path
import subprocess

VALID_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm"}

ROOT = Path(os.path.abspath(__file__)).resolve().parents[1]
DATA_DIR = ROOT / "backend" / "data"

def count_files(directory):
    if not directory.exists():
        return 0
    return len([p for p in directory.rglob("*") if p.suffix.lower() in VALID_EXTENSIONS])

def main():
    print("--- STEP 1: VERIFY DATASET DOWNLOAD ---")
    datasets = ["cough", "respiratory", "esc50"]
    missing = False
    
    for ds in datasets:
        ds_path = DATA_DIR / ds
        count = count_files(ds_path)
        print(f"Dataset '{ds}': {count} files")
        if count == 0:
            print(f"  WARNING: Directory /data/{ds}/ is empty or missing audio files.")
            missing = True

    if missing:
        print("  Missing data detected. Running download script...")
        try:
            subprocess.run(["python", str(ROOT / "backend" / "ml" / "download_datasets.py")], check=True, cwd=str(ROOT / "backend"))
        except Exception as e:
            print(f"  Failed: {e}")
            print("  Please fix Kaggle API setup and re-run download script manually.")
            return
            
    print("\n--- STEP 2: VERIFY TRAINING ---")
    try:
        subprocess.run(["python", str(ROOT / "backend" / "ml" / "train_audio_classifier.py")], check=True, cwd=str(ROOT / "backend"))
    except Exception as e:
        print(f"  Training failed: {e}")
        return

    model_path = ROOT / "backend" / "models" / "audio_classifier.pkl"
    if model_path.exists():
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"Model file exists: {model_path} (Size: {size_mb:.2f} MB)")
        if size_mb > 1.0:
            print("Model size > 1MB: OK")
        else:
            print("Model size < 1MB: WARNING, model might not be well trained")
    else:
        print(f"Model file NOT found at {model_path}")

if __name__ == "__main__":
    main()
