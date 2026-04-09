"""
Longitudinal Baseline Service

Computes and manages personal voice baselines for each patient.
Tracks deviations from baseline across calls for anomaly detection.

Features:
- Baseline computation from enrollment period (14 days, 10+ check-ins)
- Per-feature delta calculation (% change from personal baseline)
- Anomaly detection rules (3 consecutive calls exceeding thresholds)
- Caregiver notification triggers
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Features tracked for baseline
BASELINE_FEATURES = [
    "f0_mean",
    "f0_std",
    "jitter_local",
    "jitter_rap",
    "shimmer_local",
    "shimmer_apq3",
    "hnr",
    "speech_rate",
    "pause_ratio",
    "energy_mean",
    "voiced_fraction",
]

# Anomaly rules: (feature, threshold_pct, direction, severity, description)
ANOMALY_RULES = [
    ("f0_mean", -15, "decrease", "medium", "Pitch decline"),
    ("f0_std", -20, "decrease", "medium", "Reduced pitch variation"),
    ("jitter_local", 20, "increase", "high", "Jitter elevation"),
    ("jitter_rap", 25, "increase", "high", "Jitter RAP elevation"),
    ("shimmer_local", 20, "increase", "high", "Shimmer elevation"),
    ("shimmer_apq3", 25, "increase", "high", "Shimmer APQ3 elevation"),
    ("hnr", -20, "decrease", "high", "Vocal noise increase"),
    ("speech_rate", -15, "decrease", "medium", "Speech slowing"),
    ("pause_ratio", 30, "increase", "medium", "Increased pausing"),
    ("voiced_fraction", -20, "decrease", "medium", "Reduced voice activity"),
]

# Minimum check-ins required for baseline
MIN_CHECKINS_FOR_BASELINE = 10
BASELINE_WINDOW_DAYS = 14
CONSECUTIVE_ANOMALIES_REQUIRED = 3


@dataclass
class AnomalyFlag:
    feature: str
    description: str
    severity: str
    delta_pct: float
    threshold_pct: float
    direction: str
    consecutive_count: int


def _get_connection():
    """Get database connection."""
    from services.clinical_storage import _get_connection as get_clinical_conn
    return get_clinical_conn()


# ============================================================
# Database Schema Extension
# ============================================================

def ensure_baseline_schema():
    """Ensure baseline-related columns exist in database."""
    conn = _get_connection()
    try:
        # Check if patients table exists, create if not
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                user_id TEXT PRIMARY KEY,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                enrollment_complete INTEGER DEFAULT 0,
                enrollment_calls_count INTEGER DEFAULT 0,
                baseline_computed_at TEXT,
                baseline_features TEXT,
                consent_given INTEGER DEFAULT 0,
                consent_timestamp TEXT,
                consent_ip TEXT,
                do_not_record INTEGER DEFAULT 0
            )
        """)
        
        # Add columns if they don't exist
        cursor = conn.execute("PRAGMA table_info(patients)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        
        new_cols = [
            ("enrollment_complete", "INTEGER DEFAULT 0"),
            ("enrollment_calls_count", "INTEGER DEFAULT 0"),
            ("baseline_computed_at", "TEXT"),
            ("baseline_features", "TEXT"),
            ("consent_given", "INTEGER DEFAULT 0"),
            ("consent_timestamp", "TEXT"),
            ("consent_ip", "TEXT"),
            ("do_not_record", "INTEGER DEFAULT 0"),
        ]
        
        for col_name, col_def in new_cols:
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE patients ADD COLUMN {col_name} {col_def}")
        
        # Ensure checkins table has delta columns
        cursor = conn.execute("PRAGMA table_info(checkins)")
        checkin_cols = {row[1] for row in cursor.fetchall()}
        
        checkin_new_cols = [
            ("call_sid", "TEXT"),
            ("chunk_index", "INTEGER"),
            ("delta_from_baseline", "TEXT"),
            ("anomaly_flags", "TEXT"),
        ]
        
        for col_name, col_def in checkin_new_cols:
            if col_name not in checkin_cols:
                try:
                    conn.execute(f"ALTER TABLE checkins ADD COLUMN {col_name} {col_def}")
                except:
                    pass  # Column might not exist if table doesn't exist
        
        conn.commit()
        
    finally:
        conn.close()


# Initialize schema
ensure_baseline_schema()


# ============================================================
# Patient Management
# ============================================================

def get_or_create_patient(user_id: str) -> dict:
    """Get or create patient record."""
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT user_id, enrollment_complete, enrollment_calls_count,
                   baseline_computed_at, baseline_features
            FROM patients WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if row:
            return {
                "user_id": row[0],
                "enrollment_complete": bool(row[1]),
                "enrollment_calls_count": row[2] or 0,
                "baseline_computed_at": row[3],
                "baseline_features": json.loads(row[4]) if row[4] else None,
            }
        
        # Create new patient
        conn.execute("""
            INSERT INTO patients (user_id, created_at, enrollment_calls_count)
            VALUES (?, datetime('now'), 0)
        """, (user_id,))
        conn.commit()
        
        return {
            "user_id": user_id,
            "enrollment_complete": False,
            "enrollment_calls_count": 0,
            "baseline_computed_at": None,
            "baseline_features": None,
        }
        
    finally:
        conn.close()


def increment_enrollment_count(user_id: str) -> int:
    """Increment and return enrollment call count."""
    conn = _get_connection()
    try:
        conn.execute("""
            UPDATE patients 
            SET enrollment_calls_count = COALESCE(enrollment_calls_count, 0) + 1
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        
        row = conn.execute("""
            SELECT enrollment_calls_count FROM patients WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        return row[0] if row else 0
        
    finally:
        conn.close()


# ============================================================
# Baseline Computation
# ============================================================

def compute_baseline(user_id: str) -> Optional[Dict]:
    """
    Compute personal baseline from last 14 days of check-ins.
    
    Requires minimum 10 check-ins.
    Stores mean and std for each tracked feature.
    """
    conn = _get_connection()
    try:
        # Get recent check-ins
        cutoff = (datetime.now() - timedelta(days=BASELINE_WINDOW_DAYS)).isoformat()
        
        rows = conn.execute("""
            SELECT f0_mean, f0_std, jitter_local, jitter_rap,
                   shimmer_local, shimmer_apq3, hnr,
                   speech_rate, pause_ratio, energy_mean, voiced_fraction
            FROM checkins
            WHERE user_id = ? AND timestamp > ?
            ORDER BY timestamp DESC
        """, (user_id, cutoff)).fetchall()
        
        if len(rows) < MIN_CHECKINS_FOR_BASELINE:
            print(f"[baseline] {user_id}: Only {len(rows)} check-ins, need {MIN_CHECKINS_FOR_BASELINE}")
            return None
        
        import numpy as np
        
        # Compute statistics for each feature
        baseline = {}
        
        for i, feature in enumerate(BASELINE_FEATURES):
            values = [row[i] for row in rows if row[i] is not None]
            
            if len(values) >= 5:
                baseline[feature] = {
                    "mean": float(np.mean(values)),
                    "std": float(np.std(values)),
                    "min": float(np.min(values)),
                    "max": float(np.max(values)),
                    "n": len(values),
                }
            else:
                baseline[feature] = None
        
        # Store baseline
        conn.execute("""
            UPDATE patients SET
                baseline_features = ?,
                baseline_computed_at = datetime('now'),
                enrollment_complete = 1
            WHERE user_id = ?
        """, (json.dumps(baseline), user_id))
        conn.commit()
        
        print(f"[baseline] Computed baseline for {user_id} from {len(rows)} check-ins")
        
        return baseline
        
    finally:
        conn.close()


def get_baseline(user_id: str) -> Optional[Dict]:
    """Get stored baseline for user."""
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT baseline_features FROM patients WHERE user_id = ?
        """, (user_id,)).fetchone()
        
        if row and row[0]:
            return json.loads(row[0])
        return None
        
    finally:
        conn.close()


# ============================================================
# Delta Computation
# ============================================================

def compute_deltas(user_id: str, new_features: Dict) -> Dict[str, float]:
    """
    Compute % change from personal baseline for each feature.
    
    Args:
        user_id: Patient ID
        new_features: Dict of feature values from latest check-in
        
    Returns:
        Dict mapping feature name to delta percentage
    """
    baseline = get_baseline(user_id)
    
    if not baseline:
        # Increment enrollment count since baseline not ready
        count = increment_enrollment_count(user_id)
        print(f"[baseline] {user_id}: enrollment count = {count}")
        
        # Auto-compute baseline if enough check-ins
        if count >= MIN_CHECKINS_FOR_BASELINE:
            baseline = compute_baseline(user_id)
        
        if not baseline:
            return {}
    
    deltas = {}
    
    for feature in BASELINE_FEATURES:
        if feature not in new_features or new_features[feature] is None:
            continue
        
        if feature not in baseline or baseline[feature] is None:
            continue
        
        baseline_mean = baseline[feature].get("mean", 0)
        
        if baseline_mean == 0:
            continue
        
        new_value = new_features[feature]
        delta_pct = ((new_value - baseline_mean) / abs(baseline_mean)) * 100
        
        deltas[feature] = round(delta_pct, 2)
    
    return deltas


# ============================================================
# Anomaly Detection
# ============================================================

def get_recent_deltas(user_id: str, n: int = 3) -> List[Dict]:
    """Get delta values from last N check-ins."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT delta_from_baseline FROM checkins
            WHERE user_id = ? AND delta_from_baseline IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, n)).fetchall()
        
        deltas = []
        for row in rows:
            if row[0]:
                deltas.append(json.loads(row[0]))
        
        return deltas
        
    finally:
        conn.close()


def check_anomalies(user_id: str, current_deltas: Dict[str, float]) -> List[AnomalyFlag]:
    """
    Check for anomalies based on delta rules.
    
    Requires 3 consecutive calls exceeding threshold to trigger.
    
    Returns:
        List of triggered anomaly flags
    """
    if not current_deltas:
        return []
    
    # Get last 2 check-ins (we have current as 3rd)
    recent = get_recent_deltas(user_id, n=2)
    
    # Combine: [oldest, middle, current]
    all_deltas = recent[::-1] + [current_deltas]
    
    anomalies = []
    
    for feature, threshold, direction, severity, description in ANOMALY_RULES:
        consecutive = 0
        latest_delta = None
        
        for delta_dict in all_deltas:
            if feature not in delta_dict:
                consecutive = 0
                continue
            
            delta = delta_dict[feature]
            latest_delta = delta
            
            exceeded = False
            if direction == "increase" and delta > threshold:
                exceeded = True
            elif direction == "decrease" and delta < threshold:
                exceeded = True
            
            if exceeded:
                consecutive += 1
            else:
                consecutive = 0
        
        if consecutive >= CONSECUTIVE_ANOMALIES_REQUIRED and latest_delta is not None:
            anomalies.append(AnomalyFlag(
                feature=feature,
                description=description,
                severity=severity,
                delta_pct=latest_delta,
                threshold_pct=threshold,
                direction=direction,
                consecutive_count=consecutive,
            ))
    
    return anomalies


def format_anomaly_for_storage(anomaly: AnomalyFlag) -> dict:
    """Convert AnomalyFlag to JSON-serializable dict."""
    return {
        "feature": anomaly.feature,
        "description": anomaly.description,
        "severity": anomaly.severity,
        "delta_pct": anomaly.delta_pct,
        "threshold_pct": anomaly.threshold_pct,
        "direction": anomaly.direction,
        "consecutive_count": anomaly.consecutive_count,
    }


# ============================================================
# Storage Integration
# ============================================================

def save_checkin_with_deltas(
    user_id: str,
    features: Dict,
    call_sid: Optional[str] = None,
    chunk_index: Optional[int] = None,
) -> Tuple[Dict[str, float], List[AnomalyFlag]]:
    """
    Save check-in with delta computation and anomaly detection.
    
    Returns:
        Tuple of (deltas dict, list of triggered anomalies)
    """
    # Ensure patient exists
    get_or_create_patient(user_id)
    
    # Compute deltas
    deltas = compute_deltas(user_id, features)
    
    # Check anomalies
    anomalies = check_anomalies(user_id, deltas)
    
    # Store in checkins table
    conn = _get_connection()
    try:
        # Find the most recent checkin for this user to update
        row = conn.execute("""
            SELECT id FROM checkins
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (user_id,)).fetchone()
        
        if row:
            anomaly_json = json.dumps([format_anomaly_for_storage(a) for a in anomalies])
            
            conn.execute("""
                UPDATE checkins SET
                    call_sid = ?,
                    chunk_index = ?,
                    delta_from_baseline = ?,
                    anomaly_flags = ?
                WHERE id = ?
            """, (
                call_sid,
                chunk_index,
                json.dumps(deltas),
                anomaly_json,
                row[0],
            ))
            conn.commit()
        
    finally:
        conn.close()
    
    # Log anomalies
    if anomalies:
        print(f"[baseline] ANOMALIES for {user_id}:")
        for a in anomalies:
            print(f"  - {a.description}: {a.delta_pct:+.1f}% (threshold: {a.threshold_pct}%, severity: {a.severity})")
    
    return deltas, anomalies


# ============================================================
# API Helpers
# ============================================================

def get_baseline_status(user_id: str) -> dict:
    """Get baseline computation status for user."""
    patient = get_or_create_patient(user_id)
    
    return {
        "user_id": user_id,
        "enrollment_complete": patient["enrollment_complete"],
        "enrollment_calls_count": patient["enrollment_calls_count"],
        "baseline_computed_at": patient["baseline_computed_at"],
        "min_required": MIN_CHECKINS_FOR_BASELINE,
        "has_baseline": patient["baseline_features"] is not None,
    }


def get_anomaly_history(user_id: str, days: int = 7) -> List[Dict]:
    """Get anomaly flags from recent check-ins."""
    conn = _get_connection()
    try:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        rows = conn.execute("""
            SELECT timestamp, anomaly_flags FROM checkins
            WHERE user_id = ? AND timestamp > ? AND anomaly_flags IS NOT NULL
            ORDER BY timestamp DESC
        """, (user_id, cutoff)).fetchall()
        
        history = []
        for timestamp, flags_json in rows:
            if flags_json:
                flags = json.loads(flags_json)
                if flags:
                    history.append({
                        "timestamp": timestamp,
                        "anomalies": flags,
                    })
        
        return history
        
    finally:
        conn.close()


def should_notify_caregiver(anomalies: List[AnomalyFlag]) -> bool:
    """Determine if anomalies warrant caregiver notification."""
    for anomaly in anomalies:
        if anomaly.severity == "high":
            return True
    return False


def get_notification_summary(user_id: str, anomalies: List[AnomalyFlag]) -> str:
    """Generate notification message for caregiver."""
    high_severity = [a for a in anomalies if a.severity == "high"]
    
    if not high_severity:
        return ""
    
    lines = [f"VocalVitals Alert for patient {user_id}:"]
    lines.append("")
    
    for a in high_severity:
        direction = "increased" if a.direction == "increase" else "decreased"
        lines.append(f"• {a.description}: {abs(a.delta_pct):.1f}% {direction} from baseline")
    
    lines.append("")
    lines.append("This pattern has persisted for 3 consecutive check-ins.")
    lines.append("Please review the patient's voice health dashboard.")
    
    return "\n".join(lines)
