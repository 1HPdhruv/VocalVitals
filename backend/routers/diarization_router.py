"""
Voice Enrollment and Speaker Diarization Router

API endpoints for patient voice enrollment and speaker identification management.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
import tempfile
import os

from services.diarization import (
    enroll_patient,
    check_enrollment_status,
    delete_enrollment,
    get_patient_embedding,
)

router = APIRouter()


class EnrollmentResponse(BaseModel):
    status: str
    user_id: str
    embedding_dim: int = 0
    message: str = ""


# ============================================================
# Voice Enrollment
# ============================================================

@router.post("/enroll")
async def enroll_voice(
    user_id: str,
    audio: UploadFile = File(...)
):
    """
    Enroll a patient's voice for speaker identification.
    
    Upload Requirements:
    - Clean audio sample of patient speaking alone
    - Minimum 10 seconds duration
    - WAV, MP3, or any librosa-supported format
    - Clear speech without background noise
    
    This enables speaker diarization to isolate the patient's voice
    from mixed-party phone calls.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    
    # Save uploaded file to temp location
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        contents = await audio.read()
        temp_file.write(contents)
        temp_file.close()
        
        # Enroll the patient
        result = enroll_patient(user_id, temp_file.name)
        
        if result.get("status") == "enrolled":
            return EnrollmentResponse(
                status="success",
                user_id=user_id,
                embedding_dim=result.get("embedding_dim", 512),
                message=f"Voice enrolled successfully with {result.get('embedding_dim')}-dim embedding",
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Enrollment failed"),
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Enrollment failed: {str(e)}")
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_file.name)
        except:
            pass


@router.get("/status/{user_id}")
async def get_enrollment_status(user_id: str):
    """
    Check if a patient has been enrolled for voice identification.
    
    Returns:
    - enrolled: boolean
    - embedding_dim: dimension of stored voice embedding
    """
    try:
        status = check_enrollment_status(user_id)
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/enrollment/{user_id}")
async def delete_voice_enrollment(user_id: str):
    """
    Delete a patient's voice enrollment.
    
    Use this to re-enroll if initial sample was poor quality,
    or to remove enrollment when patient leaves program.
    """
    try:
        success = delete_enrollment(user_id)
        
        if success:
            return {
                "status": "deleted",
                "user_id": user_id,
                "message": "Voice enrollment deleted successfully",
            }
        else:
            raise HTTPException(status_code=404, detail="No enrollment found for user")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Enrollment Validation
# ============================================================

@router.post("/validate-enrollment")
async def validate_enrollment_audio(
    audio: UploadFile = File(...)
):
    """
    Validate an audio sample for enrollment quality.
    
    Checks:
    - Duration (minimum 10 seconds)
    - Speech detection (must contain clear speech)
    - Audio quality metrics
    
    Returns quality score and recommendations.
    """
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        contents = await audio.read()
        temp_file.write(contents)
        temp_file.close()
        
        # Load and analyze audio
        import librosa
        y, sr = librosa.load(temp_file.name, sr=16000)
        duration = len(y) / sr
        
        # Basic quality checks
        issues = []
        recommendations = []
        
        if duration < 10:
            issues.append("Audio too short")
            recommendations.append(f"Record at least 10 seconds (current: {duration:.1f}s)")
        
        # Check for silence
        rms = librosa.feature.rms(y=y)[0]
        silence_ratio = (rms < 0.01).sum() / len(rms)
        if silence_ratio > 0.5:
            issues.append("Too much silence")
            recommendations.append("Ensure continuous speech without long pauses")
        
        # Check signal level
        max_amplitude = abs(y).max()
        if max_amplitude < 0.1:
            issues.append("Audio level too low")
            recommendations.append("Increase recording volume or speak closer to microphone")
        
        # Quality score
        quality_score = 100
        quality_score -= len(issues) * 20
        quality_score -= int(silence_ratio * 30)
        quality_score = max(0, quality_score)
        
        return {
            "quality_score": quality_score,
            "duration": round(duration, 2),
            "issues": issues,
            "recommendations": recommendations,
            "suitable_for_enrollment": quality_score >= 60 and len(issues) == 0,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
    finally:
        try:
            os.unlink(temp_file.name)
        except:
            pass
