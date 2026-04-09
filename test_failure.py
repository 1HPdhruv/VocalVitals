import requests

# We assume FastAPI is running, but let's test the `predict_audio_proba` directly instead
try:
    from services.trained_classifier import predict_audio_proba
except ImportError:
    import sys
    sys.path.append(r"c:\Users\maste\Desktop\hacker\backend")
    from services.trained_classifier import predict_audio_proba

if __name__ == "__main__":
    print("Testing ML module...")
    try:
        # this should raise FileNotFoundError because we added explicit raise
        probs = predict_audio_proba("dummy.wav")
        print("Probs:", probs)
    except Exception as e:
        print(f"Caught expected error: {type(e).__name__} - {str(e)}")
