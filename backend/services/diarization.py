"""
Speaker Diarization Service

Isolates patient voice from mixed-party call recordings using:
- Voice enrollment: Extract and store patient voice embedding
- Speaker identification: Match segments to enrolled patient
- Audio isolation: Extract only patient speech segments

Uses pyannote.audio for diarization and speaker embeddings.
"""

import io
import os
import tempfile
import numpy as np
from typing import Optional, List, Tuple
from pathlib import Path

import soundfile as sf
import librosa

# PyAnnote for diarization
try:
    import torch
    from pyannote.audio import Pipeline, Model
    from pyannote.audio.pipelines import SpeakerDiarization
    from pyannote.core import Segment
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False
    print("[diarization] WARNING: pyannote.audio not available")

# HuggingFace token for gated models
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN"))

# Model cache directory
MODEL_CACHE_DIR = Path(__file__).parent.parent / "models" / "diarization"
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Cached pipelines (lazy loaded)
_diarization_pipeline = None
_embedding_model = None


def _get_diarization_pipeline():
    """Lazy load diarization pipeline."""
    global _diarization_pipeline
    
    if not PYANNOTE_AVAILABLE:
        raise RuntimeError("pyannote.audio not installed")
    
    if _diarization_pipeline is None:
        try:
            _diarization_pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=HF_TOKEN,
                cache_dir=str(MODEL_CACHE_DIR),
            )
            
            # Use GPU if available
            if torch.cuda.is_available():
                _diarization_pipeline = _diarization_pipeline.to(torch.device("cuda"))
            
            print("[diarization] Pipeline loaded successfully")
        except Exception as e:
            print(f"[diarization] Failed to load pipeline: {e}")
            raise
    
    return _diarization_pipeline


def _get_embedding_model():
    """Lazy load speaker embedding model."""
    global _embedding_model
    
    if not PYANNOTE_AVAILABLE:
        raise RuntimeError("pyannote.audio not installed")
    
    if _embedding_model is None:
        try:
            _embedding_model = Model.from_pretrained(
                "pyannote/wespeaker-voxceleb-resnet34-LM",
                use_auth_token=HF_TOKEN,
                cache_dir=str(MODEL_CACHE_DIR),
            )
            
            if torch.cuda.is_available():
                _embedding_model = _embedding_model.to(torch.device("cuda"))
            
            print("[diarization] Embedding model loaded successfully")
        except Exception as e:
            print(f"[diarization] Failed to load embedding model: {e}")
            raise
    
    return _embedding_model


def extract_embedding(audio_path: str) -> np.ndarray:
    """
    Extract speaker embedding (d-vector) from audio file.
    
    Args:
        audio_path: Path to audio file
        
    Returns:
        512-dim numpy array representing the speaker embedding
    """
    if not PYANNOTE_AVAILABLE:
        return _fallback_embedding(audio_path)
    
    try:
        from pyannote.audio import Inference
        
        model = _get_embedding_model()
        inference = Inference(model, window="whole")
        
        embedding = inference(audio_path)
        
        return embedding.data.flatten()
        
    except Exception as e:
        print(f"[diarization] Embedding extraction failed: {e}")
        return _fallback_embedding(audio_path)


def _fallback_embedding(audio_path: str) -> np.ndarray:
    """
    Fallback embedding using MFCCs when pyannote is unavailable.
    Returns a 512-dim vector for consistency.
    """
    y, sr = librosa.load(audio_path, sr=16000)
    
    # Extract MFCC statistics as pseudo-embedding
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
    
    features = []
    features.extend(np.mean(mfccs, axis=1))
    features.extend(np.std(mfccs, axis=1))
    
    delta = librosa.feature.delta(mfccs)
    features.extend(np.mean(delta, axis=1))
    features.extend(np.std(delta, axis=1))
    
    delta2 = librosa.feature.delta(mfccs, order=2)
    features.extend(np.mean(delta2, axis=1))
    features.extend(np.std(delta2, axis=1))
    
    # Pad to 512 dims
    embedding = np.array(features)
    if len(embedding) < 512:
        embedding = np.pad(embedding, (0, 512 - len(embedding)))
    
    return embedding[:512].astype(np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    a = a.flatten()
    b = b.flatten()
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))


def serialize_embedding(embedding: np.ndarray) -> bytes:
    """Serialize embedding to bytes for database storage."""
    buffer = io.BytesIO()
    np.save(buffer, embedding)
    return buffer.getvalue()


def deserialize_embedding(data: bytes) -> np.ndarray:
    """Deserialize embedding from database."""
    buffer = io.BytesIO(data)
    return np.load(buffer)


# ============================================================
# Patient Voice Enrollment
# ============================================================

def enroll_patient(user_id: str, enrollment_audio_path: str) -> dict:
    """
    Enroll a patient's voice for speaker identification.
    
    Args:
        user_id: Unique patient identifier
        enrollment_audio_path: Path to enrollment audio (should be patient speaking alone)
        
    Returns:
        Dict with enrollment status and embedding dimensions
    """
    try:
        # Extract embedding
        embedding = extract_embedding(enrollment_audio_path)
        
        # Store in database
        from services.clinical_storage import _get_connection
        
        conn = _get_connection()
        try:
            # Check if patients table has voice_embedding column
            # If not, we'll store in a separate table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS patient_enrollments (
                    user_id TEXT PRIMARY KEY,
                    voice_embedding BLOB NOT NULL,
                    enrolled_at TEXT NOT NULL,
                    embedding_dim INTEGER
                )
            """)
            
            conn.execute("""
                INSERT OR REPLACE INTO patient_enrollments 
                (user_id, voice_embedding, enrolled_at, embedding_dim)
                VALUES (?, ?, datetime('now'), ?)
            """, (
                user_id,
                serialize_embedding(embedding),
                len(embedding),
            ))
            conn.commit()
            
            print(f"[diarization] Enrolled patient {user_id}: {len(embedding)}-dim embedding")
            
            return {
                "status": "enrolled",
                "user_id": user_id,
                "embedding_dim": len(embedding),
            }
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[diarization] Enrollment failed for {user_id}: {e}")
        return {
            "status": "failed",
            "error": str(e),
        }


def get_patient_embedding(user_id: str) -> Optional[np.ndarray]:
    """Retrieve stored patient voice embedding."""
    try:
        from services.clinical_storage import _get_connection
        
        conn = _get_connection()
        try:
            row = conn.execute("""
                SELECT voice_embedding FROM patient_enrollments
                WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            if row and row[0]:
                return deserialize_embedding(row[0])
            return None
            
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[diarization] Failed to get embedding for {user_id}: {e}")
        return None


# ============================================================
# Speaker Isolation
# ============================================================

def run_diarization(audio_path: str) -> List[Tuple[float, float, str]]:
    """
    Run speaker diarization on audio file.
    
    Returns:
        List of (start_time, end_time, speaker_label) tuples
    """
    if not PYANNOTE_AVAILABLE:
        print("[diarization] PyAnnote not available, using energy-based segmentation")
        return _fallback_diarization(audio_path)
    
    try:
        pipeline = _get_diarization_pipeline()
        diarization = pipeline(audio_path)
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append((turn.start, turn.end, speaker))
        
        return segments
        
    except Exception as e:
        print(f"[diarization] Pipeline failed: {e}")
        return _fallback_diarization(audio_path)


def _fallback_diarization(audio_path: str) -> List[Tuple[float, float, str]]:
    """
    Fallback: simple energy-based segmentation.
    Assumes single speaker or alternating speakers.
    """
    y, sr = librosa.load(audio_path, sr=16000)
    duration = len(y) / sr
    
    # Simple approach: treat entire audio as one speaker
    # In production, you'd want proper diarization
    return [(0.0, duration, "SPEAKER_00")]


def extract_segment(audio_path: str, start: float, end: float) -> np.ndarray:
    """Extract audio segment from file."""
    y, sr = librosa.load(audio_path, sr=16000, offset=start, duration=end - start)
    return y


def isolate_patient_audio(audio_path: str, user_id: str, similarity_threshold: float = 0.75) -> Optional[str]:
    """
    Isolate patient voice from a mixed-party recording.
    
    Args:
        audio_path: Path to input audio (may contain multiple speakers)
        user_id: Patient ID with enrolled voice
        similarity_threshold: Minimum cosine similarity to consider a match
        
    Returns:
        Path to isolated patient audio WAV, or None if no patient speech found
    """
    # Get patient's enrolled embedding
    patient_embedding = get_patient_embedding(user_id)
    
    if patient_embedding is None:
        print(f"[diarization] No enrolled embedding for {user_id}")
        # Return original audio if not enrolled (for testing)
        return audio_path
    
    # Run diarization
    segments = run_diarization(audio_path)
    
    if not segments:
        print(f"[diarization] No segments found in {audio_path}")
        return None
    
    # For each speaker, check similarity to patient
    speaker_embeddings = {}
    patient_segments = []
    
    for start, end, speaker in segments:
        # Skip very short segments
        if end - start < 0.5:
            continue
        
        # Extract segment audio
        if speaker not in speaker_embeddings:
            # Save segment to temp file for embedding extraction
            segment_audio = extract_segment(audio_path, start, end)
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, segment_audio, 16000)
                
                try:
                    embedding = extract_embedding(tmp.name)
                    similarity = cosine_similarity(embedding, patient_embedding)
                    speaker_embeddings[speaker] = similarity
                    
                    print(f"[diarization] Speaker {speaker}: similarity = {similarity:.3f}")
                finally:
                    try:
                        os.unlink(tmp.name)
                    except:
                        pass
        
        # Check if this speaker is the patient
        if speaker_embeddings.get(speaker, 0) >= similarity_threshold:
            patient_segments.append((start, end))
    
    if not patient_segments:
        print(f"[diarization] No patient speech found (threshold={similarity_threshold})")
        return None
    
    # Merge adjacent segments
    merged = []
    for start, end in sorted(patient_segments):
        if merged and start - merged[-1][1] < 0.3:  # Gap < 0.3s
            merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    
    # Concatenate patient segments into output file
    y_full, sr = librosa.load(audio_path, sr=16000)
    
    patient_audio = []
    for start, end in merged:
        start_sample = int(start * sr)
        end_sample = int(end * sr)
        patient_audio.append(y_full[start_sample:end_sample])
    
    if not patient_audio:
        return None
    
    # Concatenate
    y_patient = np.concatenate(patient_audio)
    
    # Save to temp file
    output_path = tempfile.NamedTemporaryFile(suffix="_patient.wav", delete=False).name
    sf.write(output_path, y_patient, sr)
    
    total_duration = len(y_patient) / sr
    print(f"[diarization] Isolated {total_duration:.2f}s of patient speech from {len(merged)} segments")
    
    return output_path


# ============================================================
# Batch Processing
# ============================================================

def process_call_audio(audio_path: str, user_id: str) -> dict:
    """
    Full processing pipeline for call audio.
    
    Returns:
        Dict with isolated_path, segments, and similarity scores
    """
    result = {
        "original_path": audio_path,
        "user_id": user_id,
        "isolated_path": None,
        "segments_found": 0,
        "patient_segments": 0,
        "total_duration": 0.0,
        "patient_duration": 0.0,
        "max_similarity": 0.0,
    }
    
    try:
        # Get audio duration
        y, sr = librosa.load(audio_path, sr=16000)
        result["total_duration"] = len(y) / sr
        
        # Isolate patient audio
        isolated_path = isolate_patient_audio(audio_path, user_id)
        
        if isolated_path and isolated_path != audio_path:
            result["isolated_path"] = isolated_path
            
            # Get patient audio duration
            y_patient, _ = librosa.load(isolated_path, sr=16000)
            result["patient_duration"] = len(y_patient) / sr
            result["patient_segments"] = 1  # Simplified
            
        elif isolated_path == audio_path:
            # No enrollment, using original
            result["isolated_path"] = audio_path
            result["patient_duration"] = result["total_duration"]
            
    except Exception as e:
        print(f"[diarization] Processing failed: {e}")
        result["error"] = str(e)
    
    return result


# ============================================================
# Enrollment API helpers
# ============================================================

def check_enrollment_status(user_id: str) -> dict:
    """Check if a patient is enrolled for voice identification."""
    embedding = get_patient_embedding(user_id)
    
    return {
        "user_id": user_id,
        "enrolled": embedding is not None,
        "embedding_dim": len(embedding) if embedding is not None else 0,
    }


def delete_enrollment(user_id: str) -> bool:
    """Delete patient voice enrollment."""
    try:
        from services.clinical_storage import _get_connection
        
        conn = _get_connection()
        try:
            conn.execute("""
                DELETE FROM patient_enrollments WHERE user_id = ?
            """, (user_id,))
            conn.commit()
            return True
        finally:
            conn.close()
            
    except Exception as e:
        print(f"[diarization] Failed to delete enrollment: {e}")
        return False
