#!/usr/bin/env python3
"""
Test script for VocalVitals Twilio Live Streaming

Run this script to verify everything is working:
  cd backend
  python test_live_streaming.py
"""

import sys
import os

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    errors = []
    
    # Test audioop
    try:
        try:
            import audioop
        except ImportError:
            import audioop_lts as audioop
        print("  [OK] audioop")
    except ImportError as e:
        errors.append(f"audioop: {e}")
        print(f"  [FAIL] audioop: {e}")
    
    # Test numpy
    try:
        import numpy as np
        print("  [OK] numpy")
    except ImportError as e:
        errors.append(f"numpy: {e}")
        print(f"  [FAIL] numpy: {e}")
    
    # Test FastAPI
    try:
        from fastapi import APIRouter, WebSocket
        print("  [OK] fastapi")
    except ImportError as e:
        errors.append(f"fastapi: {e}")
        print(f"  [FAIL] fastapi: {e}")
    
    # Test live_streaming router
    try:
        from routers.live_streaming import router
        print("  [OK] live_streaming router")
    except ImportError as e:
        errors.append(f"live_streaming: {e}")
        print(f"  [FAIL] live_streaming: {e}")
    
    # Test main app
    try:
        from main import app
        print("  [OK] main app")
    except Exception as e:
        errors.append(f"main: {e}")
        print(f"  [FAIL] main: {e}")
    
    return errors

def test_audio_processing():
    """Test audio processing functions."""
    print("\nTesting audio processing...")
    
    try:
        from routers.live_streaming import ulaw_to_pcm16, resample_8k_to_16k, compute_audio_energy
        
        # Create test µ-law data (silence)
        ulaw_silence = bytes([0xFF] * 160)  # 20ms of silence at 8kHz
        
        # Convert to PCM
        pcm = ulaw_to_pcm16(ulaw_silence)
        print(f"  [OK] ulaw_to_pcm16: {len(ulaw_silence)} bytes -> {len(pcm)} bytes")
        
        # Resample
        pcm_16k = resample_8k_to_16k(pcm)
        print(f"  [OK] resample_8k_to_16k: {len(pcm)} bytes -> {len(pcm_16k)} bytes")
        
        # Compute energy
        energy = compute_audio_energy(pcm)
        print(f"  [OK] compute_audio_energy: {energy}")
        
        return []
    except Exception as e:
        print(f"  [FAIL] Audio processing: {e}")
        return [str(e)]

def test_endpoints():
    """Test that endpoints are registered."""
    print("\nTesting endpoints...")
    
    try:
        from main import app
        
        routes = [r.path for r in app.routes]
        
        expected = [
            "/twilio/incoming",
            "/twilio/stream-live",
            "/twilio/ws/live",
            "/twilio/active-calls",
            "/twilio/recent-results",
            "/twilio/stats",
        ]
        
        missing = []
        for ep in expected:
            if ep in routes:
                print(f"  [OK] {ep}")
            else:
                # Check for patterns (WebSocket routes show differently)
                found = any(ep in str(r) for r in app.routes)
                if found:
                    print(f"  [OK] {ep} (found in routes)")
                else:
                    print(f"  [MISSING] {ep}")
                    missing.append(ep)
        
        return missing
    except Exception as e:
        print(f"  [FAIL] {e}")
        return [str(e)]

def main():
    print("=" * 60)
    print("VocalVitals Live Streaming - System Test")
    print("=" * 60)
    
    all_errors = []
    
    all_errors.extend(test_imports())
    all_errors.extend(test_audio_processing())
    all_errors.extend(test_endpoints())
    
    print("\n" + "=" * 60)
    if all_errors:
        print(f"RESULT: {len(all_errors)} errors found")
        for err in all_errors:
            print(f"  - {err}")
        print("\nFix these issues, then run:")
        print("  uvicorn main:app --reload")
    else:
        print("RESULT: All tests passed!")
        print("\nStart the server:")
        print("  cd backend")
        print("  uvicorn main:app --reload")
        print("\nThen open in browser:")
        print("  http://localhost:8000/docs")
        print("\nFor Twilio testing:")
        print("  1. Run: ngrok http 8000")
        print("  2. Configure Twilio webhook: https://<ngrok-url>/twilio/incoming")
        print("  3. Call your Twilio number")
    print("=" * 60)
    
    return len(all_errors)

if __name__ == "__main__":
    sys.exit(main())
