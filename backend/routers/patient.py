"""
Consent and Patient Management Router

Handles patient consent, caregiver contact info, and privacy settings.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from services.clinical_storage import (
    get_or_create_patient,
    update_patient_consent,
    update_caregiver_info,
    get_patient_consent_status,
    set_do_not_record,
    get_caregiver_contacts,
)

router = APIRouter()


class ConsentRequest(BaseModel):
    user_id: str
    consent_given: bool
    consent_ip: Optional[str] = None


class CaregiverInfoRequest(BaseModel):
    user_id: str
    caregiver_name: Optional[str] = None
    caregiver_email: Optional[str] = None
    caregiver_phone: Optional[str] = None
    caregiver_relation: Optional[str] = None


class DoNotRecordRequest(BaseModel):
    user_id: str
    do_not_record: bool


# ============================================================
# Consent Management
# ============================================================

@router.post("/consent")
async def update_consent(request: ConsentRequest):
    """
    Update patient consent for voice monitoring.
    
    Required for HIPAA and privacy compliance.
    """
    try:
        success = update_patient_consent(
            user_id=request.user_id,
            consent_given=request.consent_given,
            consent_ip=request.consent_ip,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update consent")
        
        return {
            "status": "success",
            "user_id": request.user_id,
            "consent_given": request.consent_given,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/consent/{user_id}")
async def get_consent(user_id: str):
    """Get patient consent status."""
    try:
        status = get_patient_consent_status(user_id)
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Caregiver Management
# ============================================================

@router.post("/caregiver")
async def update_caregiver(request: CaregiverInfoRequest):
    """
    Update caregiver contact information.
    
    Used for sending health alerts and notifications.
    """
    try:
        success = update_caregiver_info(
            user_id=request.user_id,
            caregiver_name=request.caregiver_name,
            caregiver_email=request.caregiver_email,
            caregiver_phone=request.caregiver_phone,
            caregiver_relation=request.caregiver_relation,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update caregiver info")
        
        return {
            "status": "success",
            "user_id": request.user_id,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/caregiver/{user_id}")
async def get_caregiver(user_id: str):
    """Get caregiver contact information."""
    try:
        contacts = get_caregiver_contacts(user_id)
        return {
            "user_id": user_id,
            **contacts,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Privacy Settings
# ============================================================

@router.post("/do-not-record")
async def update_do_not_record(request: DoNotRecordRequest):
    """
    Set do-not-record flag for a patient.
    
    When enabled, no audio will be captured or analyzed.
    """
    try:
        success = set_do_not_record(
            user_id=request.user_id,
            do_not_record=request.do_not_record,
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update privacy setting")
        
        return {
            "status": "success",
            "user_id": request.user_id,
            "do_not_record": request.do_not_record,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Patient Profile
# ============================================================

@router.get("/patient/{user_id}")
async def get_patient_profile(user_id: str):
    """Get complete patient profile including consent and caregiver info."""
    try:
        patient = get_or_create_patient(user_id)
        consent = get_patient_consent_status(user_id)
        caregiver = get_caregiver_contacts(user_id)
        
        return {
            "user_id": user_id,
            "created_at": patient.get("created_at"),
            "enrollment_complete": bool(patient.get("enrollment_complete", 0)),
            "enrollment_calls_count": patient.get("enrollment_calls_count", 0),
            "baseline_computed_at": patient.get("baseline_computed_at"),
            "voice_enrolled": bool(patient.get("voice_enrolled", 0)),
            "consent": consent,
            "caregiver": caregiver,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
