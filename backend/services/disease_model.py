"""
Longitudinal Disease Detection Model

Two-stage inference pipeline:
1. Per-session feature extraction (handled by clinical_features.py)
2. 7-day trend analysis for disease risk scoring

Detects:
- Parkinson's disease: jitter/shimmer patterns, F0 range reduction
- Depression: F0 flatness, increased pause ratio, slow speech
- Respiratory (COPD): low voiced fraction, high breathiness
- Cognitive decline: pause frequency, speech rate changes
- Anxiety: high F0 variance, rapid speech
- Cardiovascular: pitch instability patterns
- ALS/Dysarthria: shimmer patterns, imprecise articulation
- Diabetes: vocal tremor markers

Uses delta features (day-over-day changes) and rolling statistics
for robust trend detection.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import json

# Try to import sklearn for XGBoost
try:
    from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.calibration import CalibratedClassifierCV
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[disease_model] WARNING: sklearn not available, using heuristic scoring")

# Disease configurations with clinical markers
DISEASE_CONFIG = {
    "parkinsons": {
        "name": "Parkinson's Disease",
        "icon": "brain",
        "markers": {
            "jitter_local": {"direction": "high", "weight": 0.25, "threshold": 1.5},
            "shimmer_local": {"direction": "high", "weight": 0.2, "threshold": 5.0},
            "hnr": {"direction": "low", "weight": 0.2, "threshold": 15.0},
            "f0_std": {"direction": "low", "weight": 0.15, "threshold": 15.0},  # Monotone
            "f0_max": {"direction": "low", "weight": 0.1, "threshold": 200.0},  # Reduced range
            "speech_rate": {"direction": "low", "weight": 0.1, "threshold": 100.0},
        },
        "description": "Voice tremor and pitch instability patterns",
    },
    "depression": {
        "name": "Depression",
        "icon": "brain",
        "markers": {
            "f0_mean": {"direction": "low", "weight": 0.2, "threshold": 120.0},
            "f0_std": {"direction": "low", "weight": 0.2, "threshold": 15.0},  # Flat prosody
            "pause_ratio": {"direction": "high", "weight": 0.2, "threshold": 0.3},
            "speech_rate": {"direction": "low", "weight": 0.2, "threshold": 100.0},
            "energy_mean": {"direction": "low", "weight": 0.1, "threshold": 0.02},
            "energy_std": {"direction": "low", "weight": 0.1, "threshold": 0.01},
        },
        "description": "Reduced vocal energy and flat prosody",
    },
    "copd": {
        "name": "Respiratory (COPD)",
        "icon": "lungs",
        "markers": {
            "voiced_fraction": {"direction": "low", "weight": 0.25, "threshold": 0.6},
            "hnr": {"direction": "low", "weight": 0.2, "threshold": 12.0},
            "energy_std": {"direction": "high", "weight": 0.15, "threshold": 0.05},
            "pause_freq": {"direction": "high", "weight": 0.2, "threshold": 0.5},
            "f0_std": {"direction": "high", "weight": 0.1, "threshold": 40.0},
            "jitter_local": {"direction": "high", "weight": 0.1, "threshold": 2.0},
        },
        "description": "Breathiness and weak voice onset patterns",
    },
    "cognitive": {
        "name": "Cognitive Decline",
        "icon": "brain",
        "markers": {
            "pause_freq": {"direction": "high", "weight": 0.3, "threshold": 0.6},
            "pause_ratio": {"direction": "high", "weight": 0.2, "threshold": 0.35},
            "speech_rate": {"direction": "low", "weight": 0.2, "threshold": 90.0},
            "f0_std": {"direction": "low", "weight": 0.15, "threshold": 12.0},
            "energy_std": {"direction": "low", "weight": 0.15, "threshold": 0.01},
        },
        "description": "Increased pauses and word-finding hesitations",
    },
    "anxiety": {
        "name": "Anxiety",
        "icon": "heart",
        "markers": {
            "f0_std": {"direction": "high", "weight": 0.25, "threshold": 35.0},
            "speech_rate": {"direction": "high", "weight": 0.2, "threshold": 160.0},
            "pause_freq": {"direction": "high", "weight": 0.15, "threshold": 0.4},
            "energy_std": {"direction": "high", "weight": 0.2, "threshold": 0.04},
            "jitter_local": {"direction": "high", "weight": 0.1, "threshold": 1.2},
            "shimmer_local": {"direction": "high", "weight": 0.1, "threshold": 4.0},
        },
        "description": "High pitch variance and rapid irregular speech",
    },
    "cardiovascular": {
        "name": "Cardiovascular",
        "icon": "heart",
        "markers": {
            "jitter_local": {"direction": "high", "weight": 0.2, "threshold": 1.3},
            "shimmer_local": {"direction": "high", "weight": 0.2, "threshold": 4.5},
            "f0_std": {"direction": "high", "weight": 0.2, "threshold": 30.0},
            "hnr": {"direction": "low", "weight": 0.15, "threshold": 14.0},
            "energy_std": {"direction": "high", "weight": 0.15, "threshold": 0.035},
            "pause_ratio": {"direction": "high", "weight": 0.1, "threshold": 0.25},
        },
        "description": "Pitch instability and irregular vocal patterns",
    },
    "als": {
        "name": "ALS / Dysarthria",
        "icon": "brain",
        "markers": {
            "shimmer_local": {"direction": "high", "weight": 0.25, "threshold": 6.0},
            "shimmer_apq5": {"direction": "high", "weight": 0.15, "threshold": 5.0},
            "speech_rate": {"direction": "low", "weight": 0.2, "threshold": 80.0},
            "hnr": {"direction": "low", "weight": 0.15, "threshold": 10.0},
            "jitter_local": {"direction": "high", "weight": 0.15, "threshold": 2.0},
            "voiced_fraction": {"direction": "low", "weight": 0.1, "threshold": 0.5},
        },
        "description": "Imprecise articulation and reduced speech rate",
    },
    "diabetes": {
        "name": "Diabetes (Type 2)",
        "icon": "heart",
        "markers": {
            "jitter_rap": {"direction": "high", "weight": 0.2, "threshold": 0.8},
            "shimmer_apq3": {"direction": "high", "weight": 0.2, "threshold": 3.5},
            "hnr": {"direction": "low", "weight": 0.2, "threshold": 13.0},
            "f0_std": {"direction": "high", "weight": 0.15, "threshold": 28.0},
            "energy_std": {"direction": "high", "weight": 0.15, "threshold": 0.03},
            "voiced_fraction": {"direction": "low", "weight": 0.1, "threshold": 0.65},
        },
        "description": "Vocal tremor and breathiness patterns",
    },
}

# Feature explanations for UI
FEATURE_EXPLANATIONS = {
    "jitter_local": "voice pitch stability",
    "jitter_rap": "rapid pitch perturbation",
    "jitter_ppq5": "pitch period variability",
    "shimmer_local": "voice amplitude stability",
    "shimmer_apq3": "short-term amplitude variation",
    "shimmer_apq5": "amplitude period variability",
    "hnr": "voice clarity (harmonics-to-noise ratio)",
    "nhr": "voice hoarseness (noise-to-harmonics)",
    "f0_mean": "average pitch",
    "f0_std": "pitch variability",
    "f0_min": "lowest pitch",
    "f0_max": "highest pitch",
    "voiced_fraction": "proportion of voiced speech",
    "speech_rate": "speaking speed",
    "pause_ratio": "silence between words",
    "pause_freq": "frequency of pauses",
    "energy_mean": "voice loudness",
    "energy_std": "loudness variation",
}


def compute_feature_deltas(checkins: List[dict]) -> dict:
    """
    Compute day-over-day feature changes and rolling statistics.
    
    Returns delta features for the past 7 days.
    """
    if len(checkins) < 2:
        return {}
    
    features_to_track = [
        "jitter_local", "jitter_rap", "jitter_ppq5",
        "shimmer_local", "shimmer_apq3", "shimmer_apq5",
        "hnr", "f0_mean", "f0_std", "f0_min", "f0_max",
        "voiced_fraction", "speech_rate", "pause_ratio",
        "energy_mean", "energy_std",
    ]
    
    deltas = {}
    
    for feat in features_to_track:
        values = [c.get(feat) for c in checkins if c.get(feat) is not None]
        
        if len(values) < 2:
            continue
        
        values = np.array(values)
        
        # Day-over-day deltas
        day_deltas = np.diff(values)
        
        # Rolling statistics
        deltas[f"{feat}_mean"] = float(np.mean(values))
        deltas[f"{feat}_std"] = float(np.std(values))
        deltas[f"{feat}_min"] = float(np.min(values))
        deltas[f"{feat}_max"] = float(np.max(values))
        deltas[f"{feat}_range"] = float(np.max(values) - np.min(values))
        
        # Trend (slope via linear regression)
        x = np.arange(len(values))
        if len(values) >= 3:
            slope = np.polyfit(x, values, 1)[0]
            deltas[f"{feat}_slope"] = float(slope)
        
        # Delta statistics
        deltas[f"{feat}_delta_mean"] = float(np.mean(day_deltas))
        deltas[f"{feat}_delta_std"] = float(np.std(day_deltas))
        deltas[f"{feat}_delta_max"] = float(np.max(np.abs(day_deltas)))
        
        # Week-over-week change (if enough data)
        if len(values) >= 7:
            wow_change = (values[-1] - values[0]) / max(abs(values[0]), 1e-6) * 100
            deltas[f"{feat}_wow_pct"] = float(wow_change)
    
    return deltas


def compute_heuristic_risk(
    checkins: List[dict],
    disease: str
) -> Tuple[float, float, float, List[Tuple[str, str, float]]]:
    """
    Compute disease risk using heuristic rules based on clinical markers.
    
    Returns (score, ci_low, ci_high, top_features)
    """
    config = DISEASE_CONFIG.get(disease)
    if not config:
        return 0.0, 0.0, 0.0, []
    
    if len(checkins) == 0:
        return 0.0, 0.0, 0.0, []
    
    markers = config["markers"]
    total_weight = sum(m["weight"] for m in markers.values())
    
    # Compute weighted risk from latest values and trends
    risk_score = 0.0
    top_features = []
    
    # Get latest values
    latest = checkins[-1] if checkins else {}
    
    # Compute deltas if enough data
    deltas = compute_feature_deltas(checkins) if len(checkins) >= 2 else {}
    
    for feature, params in markers.items():
        value = latest.get(feature)
        if value is None:
            continue
        
        threshold = params["threshold"]
        direction = params["direction"]
        weight = params["weight"]
        
        # Compute deviation from threshold
        if direction == "high":
            # Risk increases as value exceeds threshold
            deviation = (value - threshold) / max(threshold, 1e-6)
            feature_risk = max(0, min(1, deviation * 0.5 + 0.5)) if deviation > 0 else 0.25
        else:
            # Risk increases as value falls below threshold
            deviation = (threshold - value) / max(threshold, 1e-6)
            feature_risk = max(0, min(1, deviation * 0.5 + 0.5)) if deviation > 0 else 0.25
        
        # Boost risk if trend is worsening
        slope_key = f"{feature}_slope"
        if slope_key in deltas:
            slope = deltas[slope_key]
            if direction == "high" and slope > 0:
                feature_risk = min(1.0, feature_risk * 1.2)
            elif direction == "low" and slope < 0:
                feature_risk = min(1.0, feature_risk * 1.2)
        
        weighted_risk = feature_risk * weight
        risk_score += weighted_risk
        
        # Track top contributing features
        if feature_risk > 0.4:
            change_desc = ""
            wow_key = f"{feature}_wow_pct"
            if wow_key in deltas:
                wow = deltas[wow_key]
                if abs(wow) > 5:
                    change_desc = f"+{wow:.1f}%" if wow > 0 else f"{wow:.1f}%"
            
            top_features.append((feature, change_desc, feature_risk))
    
    # Normalize score to 0-100
    score = (risk_score / total_weight) * 100
    score = max(0, min(100, score))
    
    # Compute confidence interval based on data quantity
    n_checkins = len(checkins)
    base_uncertainty = 15.0  # Base uncertainty
    
    # Uncertainty decreases with more data
    uncertainty = base_uncertainty * (1.0 / np.sqrt(max(n_checkins, 1)))
    uncertainty = max(5.0, min(25.0, uncertainty))  # Clamp between 5-25
    
    # Wider CI for extreme scores (less confident)
    if score < 20 or score > 80:
        uncertainty *= 1.2
    
    ci_low = max(0, score - uncertainty)
    ci_high = min(100, score + uncertainty)
    
    # Sort top features by risk contribution
    top_features.sort(key=lambda x: x[2], reverse=True)
    
    return score, ci_low, ci_high, top_features[:3]


def compute_all_disease_risks(
    checkins: List[dict]
) -> Tuple[dict, dict]:
    """
    Compute risk scores for all diseases.
    
    Returns (scores_dict, top_features_dict)
    """
    scores = {}
    all_top_features = {}
    
    for disease_key, config in DISEASE_CONFIG.items():
        score, ci_low, ci_high, top_feats = compute_heuristic_risk(checkins, disease_key)
        
        scores[disease_key] = {
            "score": round(score, 1),
            "ci_low": round(ci_low, 1),
            "ci_high": round(ci_high, 1),
            "name": config["name"],
            "icon": config["icon"],
            "description": config["description"],
        }
        
        # Format top features for UI
        formatted_features = []
        for feat, change, risk in top_feats:
            explanation = FEATURE_EXPLANATIONS.get(feat, feat)
            formatted_features.append({
                "feature": feat,
                "explanation": explanation,
                "change": change,
                "severity": "high" if risk > 0.7 else "medium" if risk > 0.5 else "low",
            })
        
        all_top_features[disease_key] = formatted_features
    
    return scores, all_top_features


def generate_trend_explanation(
    disease_key: str,
    score: float,
    top_features: List[dict],
    checkins_count: int
) -> str:
    """
    Generate a human-readable explanation for a disease risk score.
    """
    config = DISEASE_CONFIG.get(disease_key, {})
    disease_name = config.get("name", disease_key)
    
    if checkins_count < 3:
        return f"Complete more check-ins for a reliable {disease_name} assessment."
    
    if score < 20:
        return f"Your voice biomarkers show no significant indicators for {disease_name}."
    
    if not top_features:
        return f"Your {disease_name} risk is {score:.0f}% based on overall voice patterns."
    
    # Build explanation from top features
    parts = []
    for feat in top_features[:2]:
        explanation = feat.get("explanation", feat.get("feature", ""))
        change = feat.get("change", "")
        
        if change:
            parts.append(f"Your {explanation} has changed {change} over the past week")
        else:
            parts.append(f"Your {explanation} shows elevated deviation")
    
    if parts:
        explanation = ". ".join(parts) + "."
        explanation += f" These patterns are associated with {config.get('description', 'this condition').lower()}."
        return explanation
    
    return f"Your voice shows patterns associated with {disease_name} markers."


def get_weekly_stats(checkins: List[dict]) -> dict:
    """
    Compute weekly summary statistics for report card.
    """
    if not checkins:
        return {}
    
    features = [
        "f0_mean", "f0_std", "jitter_local", "shimmer_local",
        "hnr", "speech_rate", "pause_ratio", "voiced_fraction"
    ]
    
    stats = {}
    
    for feat in features:
        values = [c.get(feat) for c in checkins if c.get(feat) is not None]
        
        if not values:
            continue
        
        values = np.array(values)
        
        # Compute baseline (first value) vs current (last value)
        baseline = values[0]
        current = values[-1]
        change = current - baseline
        change_pct = (change / max(abs(baseline), 1e-6)) * 100
        
        # Determine trend
        if len(values) >= 3:
            slope = np.polyfit(np.arange(len(values)), values, 1)[0]
            if slope > 0.1:
                trend = "rising"
            elif slope < -0.1:
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        stats[feat] = {
            "baseline": round(baseline, 2),
            "current": round(current, 2),
            "mean": round(float(np.mean(values)), 2),
            "min": round(float(np.min(values)), 2),
            "max": round(float(np.max(values)), 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 1),
            "trend": trend,
            "label": FEATURE_EXPLANATIONS.get(feat, feat),
        }
    
    return stats


# Model file path
MODEL_PATH = Path(__file__).parent.parent / "models" / "disease_detector.pkl"


def load_disease_model():
    """Load trained disease detection model if available."""
    if MODEL_PATH.exists():
        try:
            return joblib.load(MODEL_PATH)
        except Exception as e:
            print(f"[disease_model] Failed to load model: {e}")
    return None


def save_disease_model(model):
    """Save trained model."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"[disease_model] Model saved to {MODEL_PATH}")
