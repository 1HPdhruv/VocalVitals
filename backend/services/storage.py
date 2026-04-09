"""
SQLite storage service for persisting voice analysis results.
Provides historical data for graphs and trend analysis.
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "vocal_vitals.db"


def _get_connection() -> sqlite3.Connection:
    """Get SQLite connection, creating database if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    """Initialize database tables if they don't exist."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                
                -- Acoustic features
                pitch_mean REAL,
                pitch_std REAL,
                jitter REAL,
                shimmer REAL,
                hnr REAL,
                energy_mean REAL,
                zcr_mean REAL,
                duration REAL,
                breathiness REAL,
                
                -- Risk scores
                fatigue_score REAL,
                stress_score REAL,
                respiratory_risk REAL,
                depression_risk REAL,
                nervousness_score REAL,
                consistency_score REAL,
                cough_score REAL,
                
                -- Model predictions (JSON)
                model_predictions TEXT,
                
                -- Full analysis data (JSON)
                full_analysis TEXT,
                
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_timestamp 
            ON analysis_results(user_id, timestamp DESC)
        """)
        conn.commit()
    finally:
        conn.close()


# Initialize on module load
_init_db()


def save_analysis_result(
    user_id: str,
    features: dict,
    risk_scores: dict,
    model_predictions: dict,
    full_analysis: dict
) -> int:
    """
    Save analysis result to database.
    Returns the inserted row ID.
    """
    conn = _get_connection()
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        
        cursor = conn.execute("""
            INSERT INTO analysis_results (
                user_id, timestamp,
                pitch_mean, pitch_std, jitter, shimmer, hnr,
                energy_mean, zcr_mean, duration, breathiness,
                fatigue_score, stress_score, respiratory_risk,
                depression_risk, nervousness_score, consistency_score, cough_score,
                model_predictions, full_analysis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            timestamp,
            features.get("pitch_mean"),
            features.get("pitch_std"),
            features.get("jitter"),
            features.get("shimmer"),
            features.get("hnr"),
            features.get("energy_mean"),
            features.get("zcr_mean"),
            features.get("duration"),
            features.get("breathiness"),
            risk_scores.get("fatigue_score"),
            risk_scores.get("stress_score"),
            risk_scores.get("respiratory_risk"),
            risk_scores.get("depression_risk"),
            risk_scores.get("nervousness_score"),
            risk_scores.get("consistency_score"),
            risk_scores.get("cough_score"),
            json.dumps(model_predictions),
            json.dumps(full_analysis),
        ))
        conn.commit()
        
        row_id = cursor.lastrowid
        print(f"[storage] Saved analysis result id={row_id} for user={user_id}")
        return row_id
        
    finally:
        conn.close()


def get_user_history(user_id: str, limit: int = 60) -> list[dict]:
    """
    Get historical analysis results for a user.
    Returns list of dicts with date and acoustic features.
    """
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT 
                timestamp,
                pitch_mean,
                pitch_std,
                jitter,
                shimmer,
                hnr,
                energy_mean,
                zcr_mean,
                duration,
                breathiness,
                fatigue_score,
                stress_score,
                respiratory_risk,
                cough_score
            FROM analysis_results
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit)).fetchall()
        
        results = []
        for row in rows:
            results.append({
                "timestamp": row["timestamp"],
                "date": row["timestamp"][:10],  # YYYY-MM-DD
                "pitch_mean": row["pitch_mean"],
                "pitch_std": row["pitch_std"],
                "jitter": row["jitter"],
                "shimmer": row["shimmer"],
                "hnr": row["hnr"],
                "energy_mean": row["energy_mean"],
                "zcr_mean": row["zcr_mean"],
                "duration": row["duration"],
                "breathiness": row["breathiness"],
                "fatigue_score": row["fatigue_score"],
                "stress_score": row["stress_score"],
                "respiratory_risk": row["respiratory_risk"],
                "cough_score": row["cough_score"],
            })
        
        # Return in chronological order (oldest first) for graphing
        return list(reversed(results))
        
    finally:
        conn.close()


def get_all_history(limit: int = 100) -> list[dict]:
    """Get all historical results (for demo/testing)."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT 
                user_id,
                timestamp,
                pitch_mean,
                jitter,
                shimmer,
                hnr,
                cough_score,
                fatigue_score,
                stress_score
            FROM analysis_results
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()
        
        return [dict(row) for row in rows]
        
    finally:
        conn.close()
