import os
import numpy as np
from feature_extractor import extract_features

def test_feature_parity():
    """
    Test to ensure the feature extractor runs correctly on dummy audio.
    In a real scenario, this would compare outputs against a saved JSON
    from the JS `app.js` Meyda extraction to ensure numeric parity.
    """
    dummy_file = os.path.join(os.path.dirname(__file__), "..", "data", "cough", "cough_000.wav")
    
    if not os.path.exists(dummy_file):
        print(f"Skipping parity test: {dummy_file} not found.")
        return
        
    feats = extract_features(dummy_file)
    
    assert feats is not None, "Feature extraction failed."
    assert feats.shape[1] == 16, f"Expected 16 features, got {feats.shape[1]}"
    
    print(f"Feature parity basic test passed. Shape: {feats.shape}")
    print("TODO: Add strict mathematical parity checks against Meyda JS output.")

if __name__ == "__main__":
    test_feature_parity()
