import os
import numpy as np
import soundfile as sf
import librosa

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CLASSES = ["cough", "breath", "background"]
SAMPLE_RATE = 16000
DURATION_SEC = 2
NUM_SAMPLES_PER_CLASS = 10

def generate_dummy_audio(class_name, duration, sr):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    
    if class_name == "cough":
        # Simulate a cough: short bursts of noise + low frequency oscillation
        signal = np.zeros_like(t)
        burst_starts = [0.2, 0.7, 1.2]
        for start in burst_starts:
            start_idx = int(start * sr)
            end_idx = start_idx + int(0.1 * sr)
            if end_idx < len(signal):
                signal[start_idx:end_idx] = np.random.normal(0, 0.8, end_idx - start_idx) * np.hanning(end_idx - start_idx)
        # Add some low frequency body
        signal += 0.3 * np.sin(2 * np.pi * 150 * t) * (signal > 0.01)
        
    elif class_name == "breath":
        # Simulate breathing: broad-spectrum noise shaped by a slow sine wave
        noise = np.random.normal(0, 0.1, len(t))
        envelope = np.sin(2 * np.pi * 0.5 * t) ** 2
        signal = noise * envelope
        
    else:  # background
        # Ambient noise
        signal = np.random.normal(0, 0.05, len(t))
        
    # Normalize
    max_val = np.max(np.abs(signal))
    if max_val > 0:
        signal /= max_val
        
    return signal

def setup_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for cls in CLASSES:
        cls_dir = os.path.join(DATA_DIR, cls)
        os.makedirs(cls_dir, exist_ok=True)
        
        for i in range(NUM_SAMPLES_PER_CLASS):
            file_path = os.path.join(cls_dir, f"{cls}_{i:03d}.wav")
            if not os.path.exists(file_path):
                audio = generate_dummy_audio(cls, DURATION_SEC, SAMPLE_RATE)
                sf.write(file_path, audio, SAMPLE_RATE)
                
    print(f"Data generated at {DATA_DIR}. Please replace with real Coswara/COUGHVID data for actual training.")

if __name__ == "__main__":
    setup_data()
