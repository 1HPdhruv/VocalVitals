"""
Baseline Management Router

API endpoints for managing patient voice baselines and anomaly detection.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.baseline import (
    get_baseline_status,
    get_anomaly_history,
    compute_baseline,
    get_baseline,
)

router = APIRouter()


# ============================================================
# Baseline Status
# ============================================================

@router.get("/status/{user_id}")
async def baseline_status(user_id: str):
    """
    Get baseline computation status for a patient.
    
    Returns:
    - enrollment_complete: Whether baseline has been computed
    - enrollment_calls_count: Number of check-ins recorded
    - min_required: Minimum check-ins needed for baseline (10)
    - has_baseline: Whether baseline exists
    """
    try:
        status = get_baseline_status(user_id)
        return status
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/{user_id}")
async def baseline_features(user_id: str):
    """
    Get computed baseline feature values.
    
    Returns mean, std, min, max for each tracked voice metric.
    Only available after baseline is computed (10+ check-ins).
    """
    try:
        baseline = get_baseline(user_id)
        
        if baseline is None:
            raise HTTPException(
                status_code=404,
                detail="Baseline not computed yet. Need minimum 10 check-ins.",
            )
        
        return {
            "user_id": user_id,
            "baseline": baseline,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compute/{user_id}")
async def recompute_baseline(user_id: str):
    """
    Manually trigger baseline recomputation.
    
    Useful after:
    - Patient recovers from illness (want new healthy baseline)
    - Initial baseline computed during sick period
    - Significant life changes affecting voice
    
    Requires minimum 10 check-ins from last 14 days.
    """
    try:
        baseline = compute_baseline(user_id)
        
        if baseline is None:
            # Get status to see why it failed
            status = get_baseline_status(user_id)
            raise HTTPException(
                status_code=400,
                detail=f"Cannot compute baseline. Need {status['min_required']} check-ins, have {status['enrollment_calls_count']}",
            )
        
        return {
            "status": "success",
            "user_id": user_id,
            "message": "Baseline recomputed successfully",
            "features_tracked": len(baseline),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Anomaly Detection
# ============================================================

@router.get("/anomalies/{user_id}")
async def get_anomalies(user_id: str, days: int = 7):
    """
    Get recent anomaly flags for a patient.
    
    Returns check-ins where voice metrics exceeded thresholds.
    
    Params:
    - days: Number of days to look back (default: 7)
    """
    try:
        history = get_anomaly_history(user_id, days=days)
        
        return {
            "user_id": user_id,
            "days": days,
            "anomalies_count": len(history),
            "anomalies": history,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies/{user_id}/summary")
async def get_anomaly_summary(user_id: str, days: int = 7):
    """
    Get summary of anomaly patterns over time.
    
    Groups anomalies by:
    - Feature (which voice metrics are problematic)
    - Severity (high vs medium)
    - Frequency (how often each anomaly occurs)
    """
    try:
        history = get_anomaly_history(user_id, days=days)
        
        if not history:
            return {
                "user_id": user_id,
                "days": days,
                "total_anomalies": 0,
                "summary": {},
            }
        
        # Count by feature
        feature_counts = {}
        severity_counts = {"high": 0, "medium": 0}
        
        for entry in history:
            for anomaly in entry["anomalies"]:
                feature = anomaly["feature"]
                severity = anomaly["severity"]
                
                if feature not in feature_counts:
                    feature_counts[feature] = {
                        "count": 0,
                        "description": anomaly["description"],
                        "severity": severity,
                    }
                
                feature_counts[feature]["count"] += 1
                severity_counts[severity] += 1
        
        # Sort by count
        sorted_features = sorted(
            feature_counts.items(),
            key=lambda x: x[1]["count"],
            reverse=True,
        )
        
        return {
            "user_id": user_id,
            "days": days,
            "total_anomalies": len(history),
            "severity_breakdown": severity_counts,
            "top_concerns": [
                {
                    "feature": feature,
                    **data,
                }
                for feature, data in sorted_features[:5]
            ],
            "needs_attention": severity_counts["high"] > 0,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Baseline Rules Info
# ============================================================

@router.get("/rules")
async def get_anomaly_rules():
    """
    Get the list of anomaly detection rules.
    
    Returns thresholds and severity levels for each voice metric.
    Useful for frontend display and patient education.
    """
    from services.baseline import ANOMALY_RULES, BASELINE_FEATURES
    
    rules_formatted = []
    for feature, threshold, direction, severity, description in ANOMALY_RULES:
        rules_formatted.append({
            "feature": feature,
            "description": description,
            "threshold_percent": threshold,
            "direction": direction,
            "severity": severity,
            "triggers_when": f"Delta {direction}s by more than {abs(threshold)}% for 3 consecutive calls",
        })
    
    return {
        "total_rules": len(rules_formatted),
        "features_monitored": BASELINE_FEATURES,
        "consecutive_required": 3,
        "rules": rules_formatted,
    }
