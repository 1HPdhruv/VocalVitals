import os
import numpy as np
import librosa
from sklearn.metrics import precision_score, recall_score

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def naive_envelope_cough_detector(audio_path, sr=16000, onset_ratio=1.8, window_ms=60):
    """
    Simulates the v3.1 narrow-envelope cough detector.
    Looks for rapid onsets based on the specified ratio and window.
    Returns True if a cough is detected, False otherwise.
    """
    try:
        y, _ = librosa.load(audio_path, sr=sr)
    except:
        return False
        
    window_length = int(sr * (window_ms / 1000.0))
    if len(y) < window_length:
        return False
        
    rms = librosa.feature.rms(y=y, frame_length=window_length, hop_length=window_length // 2)[0]
    
    # Check for rapid onset: Current window RMS is > onset_ratio * previous window RMS
    for i in range(1, len(rms)):
        if rms[i-1] > 0.01 and (rms[i] / rms[i-1]) >= onset_ratio:
            return True
            
    return False

def evaluate():
    print("Evaluating narrow-envelope cough detector...")
    y_true = []
    y_pred = []
    
    for cls in ["cough", "breath", "background"]:
        cls_dir = os.path.join(DATA_DIR, cls)
        if not os.path.exists(cls_dir):
            continue
            
        is_cough_true = 1 if cls == "cough" else 0
        
        for file in os.listdir(cls_dir):
            if file.endswith(".wav"):
                filepath = os.path.join(cls_dir, file)
                
                # Test with default params
                detected = naive_envelope_cough_detector(filepath)
                
                y_true.append(is_cough_true)
                y_pred.append(1 if detected else 0)
                
    if len(y_true) > 0:
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        print(f"Total samples: {len(y_true)}")
        print(f"Precision: {precision:.2f}")
        print(f"Recall: {recall:.2f}")
        
        print("\nNote: Tuning may be required. Try adjusting onset_ratio (current=1.8) and window_ms (current=60) based on these results on real audio.")
    else:
        print("No data found for evaluation.")

if __name__ == "__main__":
    evaluate()
