"""
Disease Insights API

Endpoints for disease risk analysis and longitudinal trends:
- GET /insights - Get disease risk scores and explanations
- GET /insights/history - Get historical disease score trends
- POST /insights/report - Generate weekly report
"""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.clinical_storage import (
    get_last_n_checkins,
    get_user_checkins,
    get_latest_disease_scores,
    get_disease_score_history,
    save_disease_scores,
    get_checkin_count,
)
from services.disease_model import (
    compute_all_disease_risks,
    generate_trend_explanation,
    get_weekly_stats,
    DISEASE_CONFIG,
)
from services.claude_client import get_weekly_insights_narrative

router = APIRouter()


@router.get("")
async def get_disease_insights(
    userId: str = Query(..., description="User ID"),
    force_refresh: bool = Query(False, description="Force recomputation of scores"),
    demo: bool = Query(False, description="Return demo data")
):
    """
    Get disease risk insights for a user.
    
    Returns risk scores for all tracked diseases with:
    - Risk score (0-100)
    - Confidence interval (CI low, CI high)
    - Top driving features
    - Trend explanation
    - Reliability status (based on check-in count)
    """
    # Demo mode - return sample data
    if demo:
        return _get_demo_insights()
    
    # Get check-in count first
    checkin_count = get_checkin_count(userId)
    
    if checkin_count == 0:
        return {
            "status": "no_data",
            "message": "No check-ins found. Complete your first voice check-in to start tracking.",
            "checkins_count": 0,
            "is_reliable": False,
            "diseases": {},
        }
    
    # Get recent check-ins for analysis
    checkins = get_last_n_checkins(userId, n=7)
    
    # Compute disease risks
    scores, top_features = compute_all_disease_risks(checkins)
    
    # Add explanations
    diseases = {}
    for disease_key, score_data in scores.items():
        explanation = generate_trend_explanation(
            disease_key,
            score_data["score"],
            top_features.get(disease_key, []),
            len(checkins)
        )
        
        diseases[disease_key] = {
            **score_data,
            "top_features": top_features.get(disease_key, []),
            "explanation": explanation,
        }
    
    # Save scores to database
    try:
        save_disease_scores(userId, scores, top_features, len(checkins))
    except Exception as e:
        print(f"[insights] Failed to save scores: {e}")
    
    # Determine reliability
    is_reliable = len(checkins) >= 7
    
    # Get flagged diseases (score > 30)
    flagged = [
        {"key": k, **v}
        for k, v in diseases.items()
        if v["score"] > 30
    ]
    flagged.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "status": "ok",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "checkins_count": checkin_count,
        "checkins_used": len(checkins),
        "is_reliable": is_reliable,
        "diseases": diseases,
        "flagged": flagged,
        "disclaimer": "VocalVitals is a screening aid, not a diagnostic tool. Consult a healthcare provider for medical advice.",
    }


@router.get("/history")
async def get_insights_history(
    userId: str = Query(..., description="User ID"),
    days: int = Query(30, ge=7, le=90, description="Number of days to retrieve")
):
    """
    Get historical disease score trends.
    
    Returns time series of disease scores for trend visualization.
    """
    history = get_disease_score_history(userId, days=days)
    
    if not history:
        return {
            "status": "no_history",
            "message": "No disease score history available yet.",
            "trends": {},
        }
    
    # Organize by disease for sparkline rendering
    trends = {key: [] for key in DISEASE_CONFIG.keys()}
    
    for entry in history:
        timestamp = entry.get("computed_at")
        for disease_key in DISEASE_CONFIG.keys():
            score = entry.get(f"{disease_key}_score")
            if score is not None:
                trends[disease_key].append({
                    "date": timestamp[:10] if timestamp else None,
                    "score": round(score, 1),
                })
    
    return {
        "status": "ok",
        "days": days,
        "trends": trends,
    }


@router.get("/weekly-stats")
async def get_weekly_statistics(
    userId: str = Query(..., description="User ID")
):
    """
    Get weekly voice biomarker statistics for report card.
    
    Returns baseline, current, min, max, mean, and trend for each metric.
    """
    checkins = get_last_n_checkins(userId, n=7)
    
    if len(checkins) < 2:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 2 check-ins for weekly stats. Current: {len(checkins)}",
            "stats": {},
        }
    
    stats = get_weekly_stats(checkins)
    
    return {
        "status": "ok",
        "checkins_count": len(checkins),
        "period_start": checkins[0].get("timestamp", "")[:10] if checkins else None,
        "period_end": checkins[-1].get("timestamp", "")[:10] if checkins else None,
        "stats": stats,
    }


class WeeklyReportRequest(BaseModel):
    userId: str


@router.post("/weekly-report")
async def generate_weekly_report(req: WeeklyReportRequest):
    """
    Generate AI-powered weekly voice health report.
    
    Returns narrative summary and recommendations.
    """
    checkins = get_last_n_checkins(req.userId, n=7)
    
    if len(checkins) < 3:
        return {
            "status": "insufficient_data",
            "message": f"Need at least 3 check-ins for weekly report. Current: {len(checkins)}",
        }
    
    # Get disease scores
    scores, top_features = compute_all_disease_risks(checkins)
    
    # Get weekly stats
    stats = get_weekly_stats(checkins)
    
    # Generate AI narrative
    try:
        narrative = await get_weekly_insights_narrative(scores, stats, len(checkins))
    except Exception as e:
        print(f"[insights] AI narrative failed: {e}")
        narrative = _generate_fallback_narrative(scores, stats)
    
    # Get flagged concerns
    concerns = []
    for disease_key, score_data in scores.items():
        if score_data["score"] > 40:
            concerns.append({
                "disease": score_data["name"],
                "score": score_data["score"],
                "explanation": generate_trend_explanation(
                    disease_key,
                    score_data["score"],
                    top_features.get(disease_key, []),
                    len(checkins)
                ),
            })
    
    concerns.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checkins_analyzed": len(checkins),
        "narrative": narrative,
        "concerns": concerns,
        "stats_summary": {
            k: {
                "current": v["current"],
                "change_pct": v["change_pct"],
                "trend": v["trend"],
            }
            for k, v in stats.items()
        },
        "disclaimer": "This report is for informational purposes only. Please consult a healthcare provider for medical advice.",
    }


def _generate_fallback_narrative(scores: dict, stats: dict) -> str:
    """Generate a simple narrative when AI is unavailable."""
    parts = ["This week's voice analysis shows:"]
    
    # Summarize key stats
    if "f0_mean" in stats:
        f0 = stats["f0_mean"]
        trend = f0["trend"]
        parts.append(f"Your average pitch is {f0['current']:.0f} Hz, {trend} from baseline.")
    
    if "hnr" in stats:
        hnr = stats["hnr"]
        parts.append(f"Voice clarity (HNR) is {hnr['current']:.1f} dB.")
    
    # Note any elevated risks
    elevated = [s for s in scores.values() if s["score"] > 30]
    if elevated:
        parts.append(f"There are {len(elevated)} areas showing elevated markers that may warrant attention.")
    else:
        parts.append("No significant concerns were detected in your voice patterns this week.")
    
    parts.append("Continue your daily check-ins for more accurate trend tracking.")
    
    return " ".join(parts)


@router.get("/feature-definitions")
async def get_feature_definitions():
    """
    Get definitions for all tracked features.
    
    Useful for building UI tooltips and help text.
    """
    from services.disease_model import FEATURE_EXPLANATIONS
    
    return {
        "features": FEATURE_EXPLANATIONS,
        "diseases": {
            key: {
                "name": config["name"],
                "icon": config["icon"],
                "description": config["description"],
                "markers": list(config["markers"].keys()),
            }
            for key, config in DISEASE_CONFIG.items()
        },
    }


def _get_demo_insights():
    """Return demo insights data for demonstration."""
    return {
        "status": "ok",
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "checkins_count": 12,
        "checkins_used": 7,
        "is_reliable": True,
        "is_demo": True,
        "diseases": {
            "parkinsons": {
                "name": "Parkinson's Disease",
                "icon": "brain",
                "score": 18,
                "ci_low": 12,
                "ci_high": 24,
                "confidence": "high",
                "top_features": ["jitter_local", "shimmer_local"],
                "explanation": "Your voice stability metrics are within normal ranges. Jitter and shimmer values show healthy vocal cord function.",
            },
            "depression": {
                "name": "Depression",
                "icon": "brain",
                "score": 42,
                "ci_low": 35,
                "ci_high": 49,
                "confidence": "medium",
                "top_features": ["f0_std", "speech_rate", "pause_ratio"],
                "explanation": "Slightly elevated markers detected. Your pitch variation has decreased 12% and speech rate is slower than your baseline. This may indicate fatigue or low mood.",
            },
            "respiratory": {
                "name": "Respiratory Issues",
                "icon": "lungs",
                "score": 15,
                "ci_low": 10,
                "ci_high": 20,
                "confidence": "high",
                "top_features": ["hnr", "voiced_fraction"],
                "explanation": "Respiratory markers look healthy. Good voice clarity and normal breathing patterns detected.",
            },
            "anxiety": {
                "name": "Anxiety/Stress",
                "icon": "heart",
                "score": 55,
                "ci_low": 48,
                "ci_high": 62,
                "confidence": "medium",
                "top_features": ["f0_mean", "f0_std", "speech_rate"],
                "explanation": "Elevated stress indicators. Your average pitch is 8% higher than baseline with increased variability. Consider relaxation techniques.",
            },
            "cognitive": {
                "name": "Cognitive Decline",
                "icon": "brain",
                "score": 12,
                "ci_low": 8,
                "ci_high": 16,
                "confidence": "high",
                "top_features": ["pause_ratio", "speech_rate"],
                "explanation": "Speech fluency and word-finding patterns are normal. No concerning cognitive markers detected.",
            },
            "als": {
                "name": "ALS/Motor Neuron",
                "icon": "activity",
                "score": 8,
                "ci_low": 5,
                "ci_high": 12,
                "confidence": "high",
                "top_features": ["jitter_rap", "shimmer_apq5"],
                "explanation": "Motor speech function appears normal. No signs of dysarthria or muscle weakness in vocal patterns.",
            },
        },
        "flagged": [
            {
                "key": "anxiety",
                "name": "Anxiety/Stress",
                "score": 55,
                "explanation": "Elevated stress indicators detected in your voice patterns.",
            },
            {
                "key": "depression",
                "name": "Depression",
                "score": 42,
                "explanation": "Some markers associated with low mood are present.",
            },
        ],
        "weekly_trend": [
            {"day": "Mon", "anxiety": 48, "depression": 38},
            {"day": "Tue", "anxiety": 52, "depression": 40},
            {"day": "Wed", "anxiety": 58, "depression": 44},
            {"day": "Thu", "anxiety": 55, "depression": 42},
            {"day": "Fri", "anxiety": 50, "depression": 41},
            {"day": "Sat", "anxiety": 53, "depression": 43},
            {"day": "Sun", "anxiety": 55, "depression": 42},
        ],
        "disclaimer": "VocalVitals is a screening aid, not a diagnostic tool. Consult a healthcare provider for medical advice.",
    }
