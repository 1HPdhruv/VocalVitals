"""
Celery Tasks for Audio Analysis

Implements the core background tasks:
- analyze_audio_chunk: Download, diarize, extract features, compute deltas
- send_caregiver_notification: Email/SMS alerts for anomalies
- cleanup_old_audio: Daily S3 cleanup for privacy compliance
"""

import os
import tempfile
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from celery import shared_task
from celery.utils.log import get_task_logger

from dotenv import load_dotenv
load_dotenv()

logger = get_task_logger(__name__)

# AWS S3 configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "vocalvitals-audio")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Twilio configuration (for SMS notifications)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# SendGrid for email
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "alerts@vocalvitals.ai")


def get_s3_client():
    """Get boto3 S3 client."""
    import boto3
    
    return boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def download_from_s3(s3_key: str, local_path: str) -> bool:
    """Download file from S3."""
    try:
        client = get_s3_client()
        client.download_file(S3_BUCKET_NAME, s3_key, local_path)
        logger.info(f"Downloaded {s3_key} to {local_path}")
        return True
    except Exception as e:
        logger.error(f"S3 download failed: {e}")
        return False


def delete_from_s3(s3_key: str) -> bool:
    """Delete file from S3."""
    try:
        client = get_s3_client()
        client.delete_object(Bucket=S3_BUCKET_NAME, Key=s3_key)
        logger.info(f"Deleted S3 object: {s3_key}")
        return True
    except Exception as e:
        logger.error(f"S3 delete failed: {e}")
        return False


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
)
def analyze_audio_chunk(self, s3_key: str, user_id: str, call_sid: str, chunk_index: int = 0):
    """
    Main audio analysis task.
    
    Pipeline:
    1. Download WAV from S3
    2. Run speaker diarization to isolate patient voice
    3. Extract clinical features (Praat, OpenSMILE, SpeechBrain)
    4. Compute deltas from personal baseline
    5. Check for anomalies
    6. Save to database
    7. Delete raw audio from S3 (privacy)
    8. Trigger caregiver notification if needed
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Starting analysis for {user_id}, call {call_sid}, chunk {chunk_index}")
    
    # Create temp directory for this task
    tmp_dir = tempfile.mkdtemp(prefix=f"vv_{task_id}_")
    local_path = os.path.join(tmp_dir, "chunk.wav")
    isolated_path = None
    
    try:
        # Step 1: Download from S3
        logger.info(f"[{task_id}] Step 1: Downloading from S3")
        if not download_from_s3(s3_key, local_path):
            raise RuntimeError(f"Failed to download {s3_key}")
        
        # Step 2: Speaker diarization
        logger.info(f"[{task_id}] Step 2: Running diarization")
        try:
            from services.diarization import isolate_patient_audio
            isolated_path = isolate_patient_audio(local_path, user_id)
            
            if isolated_path is None:
                logger.warning(f"[{task_id}] No patient voice detected in chunk")
                # Still delete S3 file for privacy
                delete_from_s3(s3_key)
                return {"status": "skipped", "reason": "no_patient_voice"}
            
        except Exception as e:
            logger.warning(f"[{task_id}] Diarization failed, using original: {e}")
            isolated_path = local_path
        
        # Step 3: Extract clinical features
        logger.info(f"[{task_id}] Step 3: Extracting features")
        from services.clinical_features import extract_all_clinical_features
        features = extract_all_clinical_features(isolated_path)
        
        if not features:
            raise RuntimeError("Feature extraction returned no features")
        
        # Step 4 & 5: Compute deltas and check anomalies
        logger.info(f"[{task_id}] Step 4-5: Computing deltas and anomalies")
        from services.baseline import save_checkin_with_deltas, should_notify_caregiver
        
        deltas, anomalies = save_checkin_with_deltas(
            user_id=user_id,
            features=features,
            call_sid=call_sid,
            chunk_index=chunk_index,
        )
        
        # Step 6: Save to clinical storage
        logger.info(f"[{task_id}] Step 6: Saving to database")
        from services.clinical_storage import save_checkin
        
        checkin_id = save_checkin(
            user_id=user_id,
            audio_path=s3_key,  # Reference only, actual audio deleted
            features=features,
        )
        
        # Step 7: Delete raw audio from S3 (privacy requirement)
        logger.info(f"[{task_id}] Step 7: Deleting raw audio from S3")
        delete_from_s3(s3_key)
        
        # Step 8: Check if caregiver notification needed
        if anomalies and should_notify_caregiver(anomalies):
            logger.info(f"[{task_id}] Step 8: Triggering caregiver notification")
            send_caregiver_notification.delay(
                user_id=user_id,
                anomalies=[{
                    "feature": a.feature,
                    "description": a.description,
                    "severity": a.severity,
                    "delta_pct": a.delta_pct,
                } for a in anomalies],
            )
        
        result = {
            "status": "success",
            "user_id": user_id,
            "call_sid": call_sid,
            "chunk_index": chunk_index,
            "checkin_id": checkin_id,
            "features_extracted": len(features),
            "deltas_computed": len(deltas),
            "anomalies_detected": len(anomalies),
            "audio_deleted": True,
        }
        
        logger.info(f"[{task_id}] Analysis complete: {result}")
        return result
        
    except Exception as e:
        logger.error(f"[{task_id}] Analysis failed: {e}")
        # Still try to delete S3 file for privacy
        try:
            delete_from_s3(s3_key)
        except:
            pass
        raise
        
    finally:
        # Clean up temp files
        import shutil
        try:
            if isolated_path and isolated_path != local_path:
                os.unlink(isolated_path)
        except:
            pass
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except:
            pass


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_caregiver_notification(self, user_id: str, anomalies: List[Dict]):
    """
    Send notification to caregiver about detected anomalies.
    
    Supports:
    - Email via SendGrid
    - SMS via Twilio
    """
    task_id = self.request.id
    logger.info(f"[{task_id}] Sending notification for {user_id}, {len(anomalies)} anomalies")
    
    try:
        # Get caregiver contact info
        from services.clinical_storage import _get_connection
        
        conn = _get_connection()
        try:
            # Try to get caregiver info from patients table
            row = conn.execute("""
                SELECT caregiver_email, caregiver_phone FROM patients
                WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            if not row:
                logger.warning(f"[{task_id}] No patient found for {user_id}")
                return {"status": "skipped", "reason": "no_patient"}
            
            caregiver_email = row[0] if row[0] else None
            caregiver_phone = row[1] if row[1] else None
            
        finally:
            conn.close()
        
        # Build notification message
        from services.baseline import get_notification_summary
        from services.baseline import AnomalyFlag
        
        # Reconstruct AnomalyFlag objects
        anomaly_flags = [
            AnomalyFlag(
                feature=a["feature"],
                description=a["description"],
                severity=a["severity"],
                delta_pct=a["delta_pct"],
                threshold_pct=0,  # Not needed for message
                direction="",
                consecutive_count=3,
            )
            for a in anomalies
        ]
        
        message = get_notification_summary(user_id, anomaly_flags)
        
        results = []
        
        # Send email if configured
        if caregiver_email and SENDGRID_API_KEY:
            try:
                email_result = _send_sendgrid_email(
                    to_email=caregiver_email,
                    subject=f"VocalVitals Health Alert - {user_id}",
                    body=message,
                )
                results.append({"channel": "email", **email_result})
            except Exception as e:
                logger.error(f"[{task_id}] Email failed: {e}")
                results.append({"channel": "email", "status": "failed", "error": str(e)})
        
        # Send SMS if configured
        if caregiver_phone and TWILIO_ACCOUNT_SID:
            try:
                # Shorter SMS version
                sms_message = f"VocalVitals Alert: {len(anomalies)} voice health concerns detected for {user_id}. Check dashboard for details."
                sms_result = _send_twilio_sms(caregiver_phone, sms_message)
                results.append({"channel": "sms", **sms_result})
            except Exception as e:
                logger.error(f"[{task_id}] SMS failed: {e}")
                results.append({"channel": "sms", "status": "failed", "error": str(e)})
        
        return {
            "status": "complete",
            "user_id": user_id,
            "notifications_sent": results,
        }
        
    except Exception as e:
        logger.error(f"[{task_id}] Notification failed: {e}")
        raise


def _send_sendgrid_email(to_email: str, subject: str, body: str) -> dict:
    """Send email via SendGrid."""
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    
    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )
    
    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    
    return {
        "status": "sent",
        "status_code": response.status_code,
    }


def _send_twilio_sms(to_phone: str, message: str) -> dict:
    """Send SMS via Twilio."""
    from twilio.rest import Client
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    
    sms = client.messages.create(
        body=message,
        from_=TWILIO_PHONE_NUMBER,
        to=to_phone,
    )
    
    return {
        "status": "sent",
        "message_sid": sms.sid,
    }


@shared_task
def cleanup_old_audio():
    """
    Daily cleanup task: Delete any S3 audio objects older than 24 hours.
    
    This is a safety net - audio should be deleted immediately after analysis,
    but this catches any stragglers.
    """
    logger.info("Starting daily S3 cleanup")
    
    if not AWS_ACCESS_KEY_ID:
        logger.warning("AWS credentials not configured, skipping cleanup")
        return {"status": "skipped", "reason": "no_aws_credentials"}
    
    try:
        import boto3
        from datetime import timezone
        
        client = boto3.client(
            "s3",
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
        
        # List objects in audio/ prefix
        paginator = client.get_paginator("list_objects_v2")
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        deleted_count = 0
        
        for page in paginator.paginate(Bucket=S3_BUCKET_NAME, Prefix="audio/"):
            for obj in page.get("Contents", []):
                if obj["LastModified"] < cutoff:
                    client.delete_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])
                    logger.info(f"Deleted old audio: {obj['Key']}")
                    deleted_count += 1
        
        logger.info(f"Cleanup complete: {deleted_count} files deleted")
        
        return {
            "status": "complete",
            "files_deleted": deleted_count,
        }
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        return {"status": "failed", "error": str(e)}


# Additional helper tasks

@shared_task
def recompute_disease_scores(user_id: str):
    """
    Recompute disease risk scores after new check-in.
    Called automatically after analyze_audio_chunk.
    """
    logger.info(f"Recomputing disease scores for {user_id}")
    
    try:
        from services.disease_model import compute_all_disease_risks
        from services.clinical_storage import get_last_n_checkins, save_disease_scores
        
        # Get last 7 check-ins
        checkins = get_last_n_checkins(user_id, n=7)
        
        if not checkins:
            return {"status": "skipped", "reason": "no_checkins"}
        
        # Compute risks
        risks = compute_all_disease_risks(checkins)
        
        # Save scores
        save_disease_scores(user_id, risks)
        
        return {
            "status": "complete",
            "diseases_scored": len(risks),
        }
        
    except Exception as e:
        logger.error(f"Disease score computation failed: {e}")
        return {"status": "failed", "error": str(e)}
