"""
Clinical Storage Service

Extended database schema for clinical voice analysis:
- Full feature storage per check-in
- Disease risk scores with confidence intervals
- Longitudinal tracking for trend analysis
"""

import sqlite3
import json
import base64
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "vocal_vitals_clinical.db"


def _get_connection() -> sqlite3.Connection:
    """Get SQLite connection, creating database if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_clinical_db():
    """Initialize clinical database tables."""
    conn = _get_connection()
    try:
        # Extended check-ins table with full clinical features
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                duration_sec REAL,
                audio_path TEXT,
                
                -- F0 (pitch) statistics
                f0_mean REAL,
                f0_std REAL,
                f0_min REAL,
                f0_max REAL,
                
                -- Jitter variants (%)
                jitter_local REAL,
                jitter_rap REAL,
                jitter_ppq5 REAL,
                
                -- Shimmer variants (%)
                shimmer_local REAL,
                shimmer_apq3 REAL,
                shimmer_apq5 REAL,
                
                -- Harmonicity
                hnr REAL,
                nhr REAL,
                voiced_fraction REAL,
                
                -- Speech timing
                speech_rate REAL,
                pause_ratio REAL,
                pause_freq REAL,
                pause_count INTEGER,
                
                -- Energy dynamics
                energy_mean REAL,
                energy_std REAL,
                energy_range REAL,
                
                -- MFCC (JSON array, 40 coefficients)
                mfcc_vector TEXT,
                
                -- X-vector embedding (base64 encoded, 512 dims)
                xvector_b64 TEXT,
                
                -- ComParE features (JSON array, top 50 PCA components)
                compare_features TEXT,
                
                -- Transcript
                transcript TEXT,
                
                -- Call metadata (for Twilio integration)
                call_sid TEXT,
                chunk_index INTEGER,
                delta_from_baseline TEXT,
                anomaly_flags TEXT,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Patients table for enrollment and consent tracking
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                user_id TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                
                -- Enrollment status
                enrollment_complete INTEGER DEFAULT 0,
                enrollment_calls_count INTEGER DEFAULT 0,
                baseline_computed_at TEXT,
                baseline_features TEXT,
                
                -- Consent tracking
                consent_given INTEGER DEFAULT 0,
                consent_timestamp TEXT,
                consent_ip TEXT,
                do_not_record INTEGER DEFAULT 0,
                
                -- Caregiver contact info
                caregiver_name TEXT,
                caregiver_email TEXT,
                caregiver_phone TEXT,
                caregiver_relation TEXT,
                
                -- Voice enrollment
                voice_enrolled INTEGER DEFAULT 0,
                voice_enrollment_date TEXT
            )
        """)
        
        # Disease risk scores table with confidence intervals
        conn.execute("""
            CREATE TABLE IF NOT EXISTS disease_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                computed_at TEXT NOT NULL,
                
                -- Parkinson's disease
                parkinsons_score REAL,
                parkinsons_ci_low REAL,
                parkinsons_ci_high REAL,
                
                -- Depression
                depression_score REAL,
                depression_ci_low REAL,
                depression_ci_high REAL,
                
                -- Diabetes (Type 2)
                diabetes_score REAL,
                diabetes_ci_low REAL,
                diabetes_ci_high REAL,
                
                -- ALS / Dysarthria
                als_score REAL,
                als_ci_low REAL,
                als_ci_high REAL,
                
                -- COPD / Respiratory
                copd_score REAL,
                copd_ci_low REAL,
                copd_ci_high REAL,
                
                -- Anxiety
                anxiety_score REAL,
                anxiety_ci_low REAL,
                anxiety_ci_high REAL,
                
                -- Cognitive decline
                cognitive_score REAL,
                cognitive_ci_low REAL,
                cognitive_ci_high REAL,
                
                -- Cardiovascular
                cardiovascular_score REAL,
                cardiovascular_ci_low REAL,
                cardiovascular_ci_high REAL,
                
                -- Top driving features (JSON)
                top_driving_features TEXT,
                
                -- Number of check-ins used for computation
                checkins_used INTEGER,
                
                -- Whether this is a reliable score (7+ checkins)
                is_reliable INTEGER DEFAULT 0,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Patient enrollments for voice identification (diarization)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_enrollments (
                user_id TEXT PRIMARY KEY,
                voice_embedding BLOB NOT NULL,
                enrolled_at TEXT NOT NULL,
                embedding_dim INTEGER
            )
        """)
        
        # Indexes for efficient queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_checkins_user_time 
            ON checkins(user_id, timestamp DESC)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_user_time 
            ON disease_scores(user_id, computed_at DESC)
        """)
        
        conn.commit()
        print(f"[clinical_storage] Database initialized at {DB_PATH}")
        
    finally:
        conn.close()


# Initialize on module load
_init_clinical_db()


def save_checkin(
    user_id: str,
    features: dict,
    audio_path: Optional[str] = None,
    transcript: Optional[str] = None
) -> int:
    """
    Save a check-in with full clinical features.
    Returns the inserted row ID.
    """
    conn = _get_connection()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        cursor = conn.execute("""
            INSERT INTO checkins (
                user_id, timestamp, duration_sec, audio_path,
                f0_mean, f0_std, f0_min, f0_max,
                jitter_local, jitter_rap, jitter_ppq5,
                shimmer_local, shimmer_apq3, shimmer_apq5,
                hnr, nhr, voiced_fraction,
                speech_rate, pause_ratio, pause_freq, pause_count,
                energy_mean, energy_std, energy_range,
                mfcc_vector, xvector_b64, compare_features,
                transcript
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            timestamp,
            features.get("duration"),
            audio_path,
            features.get("f0_mean"),
            features.get("f0_std"),
            features.get("f0_min"),
            features.get("f0_max"),
            features.get("jitter_local"),
            features.get("jitter_rap"),
            features.get("jitter_ppq5"),
            features.get("shimmer_local"),
            features.get("shimmer_apq3"),
            features.get("shimmer_apq5"),
            features.get("hnr"),
            features.get("nhr"),
            features.get("voiced_fraction"),
            features.get("speech_rate"),
            features.get("pause_ratio"),
            features.get("pause_freq"),
            features.get("pause_count"),
            features.get("energy_mean"),
            features.get("energy_std"),
            features.get("energy_range"),
            json.dumps(features.get("mfcc", [])),
            features.get("xvector_b64", ""),
            json.dumps(features.get("compare_features", [])),
            transcript,
        ))
        conn.commit()
        
        return cursor.lastrowid
        
    finally:
        conn.close()


def get_user_checkins(user_id: str, days: int = 30, limit: int = 60) -> List[dict]:
    """
    Get recent check-ins for a user.
    Returns list of dicts with all features.
    """
    conn = _get_connection()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        rows = conn.execute("""
            SELECT * FROM checkins
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, cutoff, limit)).fetchall()
        
        results = []
        for row in rows:
            entry = dict(row)
            # Parse JSON fields
            entry["mfcc"] = json.loads(entry.get("mfcc_vector") or "[]")
            entry["compare_features"] = json.loads(entry.get("compare_features") or "[]")
            del entry["mfcc_vector"]
            results.append(entry)
        
        # Return in chronological order
        return list(reversed(results))
        
    finally:
        conn.close()


def get_last_n_checkins(user_id: str, n: int = 7) -> List[dict]:
    """Get the last N check-ins for longitudinal analysis."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT * FROM checkins
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, n)).fetchall()
        
        results = []
        for row in rows:
            entry = dict(row)
            entry["mfcc"] = json.loads(entry.get("mfcc_vector") or "[]")
            entry["compare_features"] = json.loads(entry.get("compare_features") or "[]")
            del entry["mfcc_vector"]
            results.append(entry)
        
        return list(reversed(results))
        
    finally:
        conn.close()


def save_disease_scores(
    user_id: str,
    scores: dict,
    top_features: dict,
    checkins_used: int
) -> int:
    """
    Save computed disease risk scores.
    Returns the inserted row ID.
    """
    conn = _get_connection()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        is_reliable = 1 if checkins_used >= 7 else 0
        
        cursor = conn.execute("""
            INSERT INTO disease_scores (
                user_id, computed_at,
                parkinsons_score, parkinsons_ci_low, parkinsons_ci_high,
                depression_score, depression_ci_low, depression_ci_high,
                diabetes_score, diabetes_ci_low, diabetes_ci_high,
                als_score, als_ci_low, als_ci_high,
                copd_score, copd_ci_low, copd_ci_high,
                anxiety_score, anxiety_ci_low, anxiety_ci_high,
                cognitive_score, cognitive_ci_low, cognitive_ci_high,
                cardiovascular_score, cardiovascular_ci_low, cardiovascular_ci_high,
                top_driving_features, checkins_used, is_reliable
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            timestamp,
            scores.get("parkinsons", {}).get("score"),
            scores.get("parkinsons", {}).get("ci_low"),
            scores.get("parkinsons", {}).get("ci_high"),
            scores.get("depression", {}).get("score"),
            scores.get("depression", {}).get("ci_low"),
            scores.get("depression", {}).get("ci_high"),
            scores.get("diabetes", {}).get("score"),
            scores.get("diabetes", {}).get("ci_low"),
            scores.get("diabetes", {}).get("ci_high"),
            scores.get("als", {}).get("score"),
            scores.get("als", {}).get("ci_low"),
            scores.get("als", {}).get("ci_high"),
            scores.get("copd", {}).get("score"),
            scores.get("copd", {}).get("ci_low"),
            scores.get("copd", {}).get("ci_high"),
            scores.get("anxiety", {}).get("score"),
            scores.get("anxiety", {}).get("ci_low"),
            scores.get("anxiety", {}).get("ci_high"),
            scores.get("cognitive", {}).get("score"),
            scores.get("cognitive", {}).get("ci_low"),
            scores.get("cognitive", {}).get("ci_high"),
            scores.get("cardiovascular", {}).get("score"),
            scores.get("cardiovascular", {}).get("ci_low"),
            scores.get("cardiovascular", {}).get("ci_high"),
            json.dumps(top_features),
            checkins_used,
            is_reliable,
        ))
        conn.commit()
        
        return cursor.lastrowid
        
    finally:
        conn.close()


def get_latest_disease_scores(user_id: str) -> Optional[dict]:
    """Get the most recent disease scores for a user."""
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM disease_scores
            WHERE user_id = ?
            ORDER BY computed_at DESC
            LIMIT 1
        """, (user_id,)).fetchone()
        
        if row is None:
            return None
        
        result = dict(row)
        result["top_driving_features"] = json.loads(result.get("top_driving_features") or "{}")
        return result
        
    finally:
        conn.close()


def get_disease_score_history(user_id: str, days: int = 30) -> List[dict]:
    """Get disease score history for trend analysis."""
    conn = _get_connection()
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        
        rows = conn.execute("""
            SELECT * FROM disease_scores
            WHERE user_id = ? AND computed_at > ?
            ORDER BY computed_at ASC
        """, (user_id, cutoff)).fetchall()
        
        results = []
        for row in rows:
            entry = dict(row)
            entry["top_driving_features"] = json.loads(entry.get("top_driving_features") or "{}")
            results.append(entry)
        
        return results
        
    finally:
        conn.close()


def get_checkin_count(user_id: str) -> int:
    """Get total number of check-ins for a user."""
    conn = _get_connection()
    try:
        result = conn.execute("""
            SELECT COUNT(*) FROM checkins WHERE user_id = ?
        """, (user_id,)).fetchone()
        return result[0] if result else 0
    finally:
        conn.close()


# ============================================================
# Patient Management
# ============================================================

def get_or_create_patient(user_id: str) -> dict:
    """Get or create patient record."""
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT * FROM patients WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if row:
            return dict(row)
        
        # Create new patient
        conn.execute("""
            INSERT INTO patients (user_id, created_at)
            VALUES (?, datetime('now'))
        """, (user_id,))
        conn.commit()
        
        # Fetch the newly created record
        row = conn.execute("""
            SELECT * FROM patients WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        return dict(row) if row else {}
        
    finally:
        conn.close()


def update_patient_consent(
    user_id: str,
    consent_given: bool,
    consent_ip: Optional[str] = None
) -> bool:
    """Update patient consent status."""
    conn = _get_connection()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        conn.execute("""
            UPDATE patients
            SET consent_given = ?,
                consent_timestamp = ?,
                consent_ip = ?
            WHERE user_id = ?
        """, (1 if consent_given else 0, timestamp, consent_ip, user_id))
        conn.commit()
        
        return True
        
    finally:
        conn.close()


def update_caregiver_info(
    user_id: str,
    caregiver_name: Optional[str] = None,
    caregiver_email: Optional[str] = None,
    caregiver_phone: Optional[str] = None,
    caregiver_relation: Optional[str] = None
) -> bool:
    """Update caregiver contact information."""
    conn = _get_connection()
    try:
        # Ensure patient exists
        get_or_create_patient(user_id)
        
        conn.execute("""
            UPDATE patients
            SET caregiver_name = ?,
                caregiver_email = ?,
                caregiver_phone = ?,
                caregiver_relation = ?
            WHERE user_id = ?
        """, (caregiver_name, caregiver_email, caregiver_phone, caregiver_relation, user_id))
        conn.commit()
        
        return True
        
    finally:
        conn.close()


def get_patient_consent_status(user_id: str) -> dict:
    """Get patient consent status."""
    patient = get_or_create_patient(user_id)
    
    return {
        "user_id": user_id,
        "consent_given": bool(patient.get("consent_given", 0)),
        "consent_timestamp": patient.get("consent_timestamp"),
        "do_not_record": bool(patient.get("do_not_record", 0)),
    }


def set_do_not_record(user_id: str, do_not_record: bool) -> bool:
    """Set do-not-record flag for a patient."""
    conn = _get_connection()
    try:
        conn.execute("""
            UPDATE patients
            SET do_not_record = ?
            WHERE user_id = ?
        """, (1 if do_not_record else 0, user_id))
        conn.commit()
        
        return True
        
    finally:
        conn.close()


def get_caregiver_contacts(user_id: str) -> dict:
    """Get caregiver contact information."""
    patient = get_or_create_patient(user_id)
    
    return {
        "caregiver_name": patient.get("caregiver_name"),
        "caregiver_email": patient.get("caregiver_email"),
        "caregiver_phone": patient.get("caregiver_phone"),
        "caregiver_relation": patient.get("caregiver_relation"),
    }
