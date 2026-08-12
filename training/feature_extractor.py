import numpy as np
import librosa

def extract_features(audio_path, sr=16000, n_fft=1024, hop_length=512):
    """
    Extracts a 16-dimensional feature vector per frame.
    Matches the JS implementation (Meyda or custom Web Audio API):
    - 13 MFCCs
    - 1 RMS
    - 1 Spectral Centroid
    - 1 High-Frequency Energy Ratio (e.g. > 2000Hz)
    
    Returns:
        np.ndarray of shape (num_frames, 16)
    """
    try:
        y, sr = librosa.load(audio_path, sr=sr)
    except Exception as e:
        print(f"Error loading {audio_path}: {e}")
        return None

    # Ensure minimum length for FFT
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))

    # 1. 13 MFCCs
    # Note: htk=True is often used to match standard speech processing setups.
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=n_fft, hop_length=hop_length, htk=True)

    # 2. RMS Energy
    rms = librosa.feature.rms(y=y, frame_length=n_fft, hop_length=hop_length)

    # 3. Spectral Centroid
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=n_fft, hop_length=hop_length)

    # 4. High-frequency energy ratio
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    
    # Define "high frequency" as > 2000 Hz
    hf_mask = freqs > 2000
    
    hf_energy = np.sum(S[hf_mask, :], axis=0)
    total_energy = np.sum(S, axis=0)
    
    # Avoid division by zero
    hf_ratio = np.divide(hf_energy, total_energy, out=np.zeros_like(hf_energy), where=total_energy!=0)
    hf_ratio = hf_ratio.reshape(1, -1)

    # Stack features into (16, num_frames)
    features = np.vstack([mfcc, rms, cent, hf_ratio])
    
    # Transpose to (num_frames, 16) for standard sequence modeling
    return features.T

if __name__ == "__main__":
    # Quick test
    import os
    dummy_file = os.path.join(os.path.dirname(__file__), "..", "data", "cough", "cough_000.wav")
    if os.path.exists(dummy_file):
        feats = extract_features(dummy_file)
        print(f"Extracted feature shape: {feats.shape}")
        print(f"First frame features: \n{feats[0]}")
    else:
        print("Run data_loader.py first to generate dummy data.")
