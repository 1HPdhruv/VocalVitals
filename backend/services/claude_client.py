import os
import json
import anthropic
from typing import AsyncGenerator

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY) if _ANTHROPIC_API_KEY else None


def _safe_float(value, default=0.0):
    try:
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp_score(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _feature_context(features: dict) -> dict:
    return {
        "pitch_mean": _safe_float(features.get("pitch_mean"), 0.0),
        "pitch_std": _safe_float(features.get("pitch_std"), 0.0),
        "jitter": _safe_float(features.get("jitter"), 0.0),
        "shimmer": _safe_float(features.get("shimmer"), 0.0),
        "hnr": _safe_float(features.get("hnr"), 10.0),
        "breathiness": _safe_float(features.get("breathiness"), 0.0),
        "speech_rate": _safe_float(features.get("speech_rate"), 0.0),
        "pause_freq": _safe_float(features.get("pause_freq"), 0.0),
        "mean_pause_duration": _safe_float(features.get("mean_pause_duration"), 0.0),
        "long_pauses": _safe_float(features.get("long_pauses"), 0.0),
        "energy_mean": _safe_float(features.get("energy_mean"), 0.0),
        "energy_std": _safe_float(features.get("energy_std"), 0.0),
        "amplitude_variation": _safe_float(features.get("amplitude_variation"), 0.0),
    }


def _build_initial_analysis_payload(features: dict, transcript: str) -> dict:
    ctx = _feature_context(features)

    respiratory_score = _clamp_score(
        22
        + ctx["breathiness"] * 42
        + max(0.0, 18.0 - ctx["hnr"]) * 2.0
        + ctx["jitter"] * 1.1
        + ctx["shimmer"] * 0.9
    )
    fatigue_score = _clamp_score(
        20
        + max(0.0, 3.8 - ctx["speech_rate"]) * 14.0
        + min(ctx["pause_freq"] * 5.0, 18.0)
        + max(0.0, ctx["mean_pause_duration"] - 0.5) * 10.0
        + min(ctx["amplitude_variation"] * 0.08, 14.0)
    )
    depression_stress_score = _clamp_score(
        18
        + max(0.0, 32.0 - ctx["pitch_std"]) * 0.8
        + max(0.0, 3.6 - ctx["speech_rate"]) * 12.0
        + max(0.0, ctx["pause_freq"] - 2.0) * 4.0
        + max(0.0, 12.0 - ctx["pitch_mean"]) * 0.2
    )
    type2_diabetes_score = _clamp_score(
        14
        + max(0.0, 3.4 - ctx["speech_rate"]) * 10.0
        + max(0.0, 18.0 - ctx["pitch_std"]) * 0.6
        + max(0.0, ctx["amplitude_variation"] - 22.0) * 0.6
        + max(0.0, ctx["breathiness"] - 0.22) * 24.0
    )

    risk_scores = {
        "type2_diabetes": {
            "score": type2_diabetes_score,
            "confidence": _clamp_score(52 + abs(type2_diabetes_score - 50) * 0.5),
            "signals": [
                "Reduced speech vigor" if ctx["speech_rate"] < 3.4 else "Speech rate within expected range",
                "Broader amplitude instability" if ctx["amplitude_variation"] > 20 else "No strong amplitude instability",
            ],
            "uncertainty": "Voice biomarkers are indirect and non-diagnostic.",
        },
        "depression_stress": {
            "score": depression_stress_score,
            "confidence": _clamp_score(54 + abs(depression_stress_score - 50) * 0.45),
            "signals": [
                "Reduced pitch variability" if ctx["pitch_std"] < 28 else "Pitch variability not markedly reduced",
                "Slower phrasing or longer pauses" if ctx["speech_rate"] < 3.6 or ctx["pause_freq"] > 2 else "Pause pattern not strongly abnormal",
            ],
            "uncertainty": "Prosody can reflect many factors including sleep, context, and microphone quality.",
        },
        "respiratory_issues": {
            "score": respiratory_score,
            "confidence": _clamp_score(58 + abs(respiratory_score - 50) * 0.4),
            "signals": [
                f"HNR {ctx['hnr']:.1f} dB",
                f"Breathiness {ctx['breathiness']:.2f}",
            ],
            "uncertainty": "Respiratory patterns in voice data can be influenced by transient throat irritation.",
        },
        "general_fatigue": {
            "score": fatigue_score,
            "confidence": _clamp_score(56 + abs(fatigue_score - 50) * 0.4),
            "signals": [
                f"Speech rate {ctx['speech_rate']:.2f} words/sec",
                f"Mean pause duration {ctx['mean_pause_duration']:.2f}s",
            ],
            "uncertainty": "Fatigue-like signals are suggestive only and should be interpreted with context.",
        },
    }

    ordered_risks = sorted(
        risk_scores.items(),
        key=lambda item: item[1]["score"],
        reverse=True,
    )

    top_name, top_risk = ordered_risks[0]
    secondary_name, secondary_risk = ordered_risks[1]

    key_insights = [
        f"Highest signal: {top_name.replace('_', ' ')} at {top_risk['score']}/100, but this is a screening estimate rather than a diagnosis.",
        f"Voice stability appears {'reduced' if ctx['jitter'] > 0.9 or ctx['shimmer'] > 3.5 else 'fairly steady'} based on jitter, shimmer, and HNR.",
        f"Speech pacing is {'slower' if ctx['speech_rate'] < 3.6 else 'within a typical screening range'} with {ctx['pause_freq']:.0f} detected pauses.",
        f"Energy variation is {'elevated' if ctx['amplitude_variation'] > 20 else 'not strongly elevated'}, which can be consistent with fatigue or recording conditions.",
    ]

    anomalies = []
    if ctx["breathiness"] > 0.35:
        anomalies.append(f"Breathiness is elevated ({ctx['breathiness']:.2f}).")
    if ctx["hnr"] < 15:
        anomalies.append(f"Harmonic-to-noise ratio is low ({ctx['hnr']:.1f} dB), indicating a noisier signal.")
    if ctx["speech_rate"] < 2.8:
        anomalies.append(f"Speech rate is slow ({ctx['speech_rate']:.2f} words/sec).")
    if ctx["mean_pause_duration"] > 0.9:
        anomalies.append(f"Pause duration is longer than expected ({ctx['mean_pause_duration']:.2f}s average).")
    if ctx["amplitude_variation"] > 25:
        anomalies.append(f"Amplitude variation is elevated ({ctx['amplitude_variation']:.2f}%).")

    if not anomalies:
        anomalies.append("No major vocal biomarker anomalies were detected in this recording.")

    suggestions = [
        "Compare this recording with past samples to watch for trend changes rather than relying on a single result.",
        "Record in a quiet room at a similar distance from the microphone for more stable comparisons.",
        "If symptoms are noticeable in daily life, consider tracking them alongside voice recordings for context.",
    ]

    conditions = [
        {
            "name": "Respiratory-pattern voice strain",
            "confidence": respiratory_score,
            "triggered_features": top_risk["signals"],
        },
        {
            "name": "Fatigue-related vocal changes",
            "confidence": fatigue_score,
            "triggered_features": [f"Speech rate {ctx['speech_rate']:.2f}", f"Mean pause {ctx['mean_pause_duration']:.2f}s"],
        },
    ]

    severity = "high" if max(r["score"] for r in risk_scores.values()) >= 75 else "medium" if max(r["score"] for r in risk_scores.values()) >= 45 else "low"
    explanation = (
        "This is a screening result, not a diagnosis. The voice pattern shows relative changes in stability, pacing, "
        "and breathiness that can reflect fatigue, stress, or airway irritation."
    )

    return {
        "risk_scores": risk_scores,
        "key_insights": key_insights,
        "anomalies": anomalies,
        "suggestions": suggestions,
        "conditions": conditions,
        "severity": severity,
        "explanation": explanation,
        "follow_up_questions": [
            "Have you noticed your voice changing after long conversations or at the end of the day?",
            "Have you been sleeping poorly, feeling stressed, or recovering from a recent illness?",
            "Does your voice feel breathier, weaker, or more effortful than usual?",
        ],
        "consistency_score": _clamp_score(100 - max(r["score"] for r in risk_scores.values()) * 0.35),
        "specialist_recommended": "Primary care / ENT review if the symptoms persist",
    }


def _normalize_initial_analysis_response(parsed: dict, features: dict, transcript: str) -> dict:
    if not isinstance(parsed, dict):
        return _build_initial_analysis_payload(features, transcript)

    if "risk_scores" in parsed:
        normalized = _build_initial_analysis_payload(features, transcript)
        normalized.update(parsed)
        normalized.setdefault("conditions", normalized["conditions"])
        normalized.setdefault("severity", normalized["severity"])
        normalized.setdefault("explanation", normalized["explanation"])
        normalized.setdefault("follow_up_questions", normalized["follow_up_questions"])
        normalized.setdefault("consistency_score", normalized["consistency_score"])
        normalized.setdefault("specialist_recommended", normalized["specialist_recommended"])
        return normalized

    conditions = parsed.get("conditions", []) or []
    if conditions:
        risk_scores = {}
        for index, condition in enumerate(conditions):
            name = condition.get("name", f"signal_{index + 1}")
            confidence = _clamp_score(condition.get("confidence", 50))
            risk_scores[name.lower().replace(" ", "_")] = {
                "score": confidence,
                "confidence": confidence,
                "signals": condition.get("triggered_features", []),
                "uncertainty": "Converted from legacy analysis output.",
            }
        parsed = {
            **_build_initial_analysis_payload(features, transcript),
            **parsed,
            "risk_scores": risk_scores,
        }
    else:
        parsed = {**_build_initial_analysis_payload(features, transcript), **parsed}

    return parsed


def _mock_initial_analysis(features: dict, transcript: str) -> dict:
    return _normalize_initial_analysis_response({}, features, transcript)


def _mock_socratic(original_features: dict, original_analysis: dict, conversation_history: list, new_answer: str, new_features: dict | None = None) -> dict:
    base_conditions = original_analysis.get("conditions", []) if isinstance(original_analysis, dict) else []
    if not base_conditions:
        base_conditions = [{"name": "Vocal strain / laryngeal irritation", "confidence": 70, "triggered_features": []}]

    updated_conditions = []
    for condition in base_conditions[:2]:
        updated_conditions.append(
            {
                "name": condition.get("name", "Vocal strain / laryngeal irritation"),
                "confidence": min(int(condition.get("confidence", 70)) + 3, 95),
                "triggered_features": condition.get("triggered_features", []),
            }
        )

    return {
        "updated_conditions": updated_conditions,
        "new_question": "Have your symptoms changed after rest, hydration, or avoiding extended speaking?",
        "reasoning": (
            "The added history does not rule out a voice-related cause, so the most likely explanation remains "
            "a reversible strain pattern rather than an acute emergency."
        ),
    }


def _mock_final_report(features: dict, transcript: str, interview_rounds: list) -> dict:
    return {
        "chief_complaint": "Voice screening suggests persistent vocal strain with low harmonic clarity.",
        "timeline": [
            "Symptoms reported during screening",
            "Acoustic markers consistent with ongoing irritation",
        ],
        "acoustic_indicators": [
            f"HNR {float(features.get('hnr', 10.0) or 10.0):.1f} dB",
            f"Jitter {float(features.get('jitter', 0.0) or 0.0):.2f}%",
            f"Shimmer {float(features.get('shimmer', 0.0) or 0.0):.2f}%",
        ],
        "specialist": "ENT / otolaryngology",
        "urgency": "soon",
        "full_note": (
            "Screening-only voice report generated locally because no Anthropic API key is configured. "
            "Findings are compatible with vocal strain or irritation and should be reviewed clinically."
        ),
    }


def _mock_caregiver_summary(features: dict, transcript: str, patient_name: str, history: list) -> dict:
    return {
        "summary": f"{patient_name or 'The patient'}'s voice pattern suggests strain or fatigue, but the result is only a screening signal.",
        "flags": ["Reduced vocal clarity", "Possible breathiness", "Monitor for progression"],
        "severity": "medium",
        "recommended_action": "Encourage hydration, rest, and clinical follow-up if symptoms persist or worsen.",
    }


def _mock_weekly_journal_summary(entries: list) -> dict:
    return {
        "summary": "The weekly trend looks broadly stable, with a mild signal of vocal fatigue if recordings were taken later in the day.",
        "trend": "stable",
        "key_changes": ["No major deterioration detected", "Small fluctuations in roughness metrics"],
        "recommendation": "Continue regular recordings and review with a clinician if symptoms become more noticeable.",
    }


def _mock_second_opinion(features_a: dict, features_b: dict, transcript_a: str, transcript_b: str) -> dict:
    pitch_a = float(features_a.get("pitch_mean", 0.0) or 0.0)
    pitch_b = float(features_b.get("pitch_mean", 0.0) or 0.0)
    return {
        "comparison_summary": "The second recording appears slightly less stable and more breathy, consistent with transient voice fatigue.",
        "key_changes": [
            {
                "metric": "pitch_mean",
                "value_a": pitch_a,
                "value_b": pitch_b,
                "delta": round(pitch_b - pitch_a, 3),
                "interpretation": "Small pitch change without a strong safety signal.",
            }
        ],
        "overall_trend": "stable",
        "clinical_note": "Screening-only comparison generated locally because no Anthropic API key is configured.",
    }

# ── System Prompts ────────────────────────────────────────────────────────────

SYSTEM_INITIAL = """You are VocalVitals, an AI health intelligence system for voice screening.
Analyze vocal biomarkers from audio and transcript context.

Rules:
- Do not claim a diagnosis.
- Use cautious, screening-only language.
- Always include uncertainty.
- Prioritize clarity for non-experts.
- Return ONLY valid JSON with no markdown.

Required output format:
{
    "risk_scores": {
        "type2_diabetes": {"score": number, "confidence": number, "signals": [string], "uncertainty": string},
        "depression_stress": {"score": number, "confidence": number, "signals": [string], "uncertainty": string},
        "respiratory_issues": {"score": number, "confidence": number, "signals": [string], "uncertainty": string},
        "general_fatigue": {"score": number, "confidence": number, "signals": [string], "uncertainty": string}
    },
    "key_insights": [string],
    "anomalies": [string],
    "suggestions": [string]
}

Use the provided biomarker values to estimate risk scores from 0 to 100. Focus on jitter, shimmer, HNR, breathiness, pitch variation, speech rate, pause distribution, and energy/amplitude variation when available."""

SYSTEM_SOCRATIC = """You are continuing a voice health screening interview. You have the original acoustic analysis and the patient's answers so far. Refine your differential diagnosis based on new information. Respond ONLY in valid JSON with no markdown: {updated_conditions: [{name: string, confidence: number, triggered_features: [string]}], new_question: string, reasoning: string}"""

SYSTEM_FINAL_REPORT = """Generate a final pre-consultation voice health note for a GP. Synthesize all acoustic data, transcript, and interview answers. Be specific, cite acoustic feature values. Respond ONLY in valid JSON with no markdown: {chief_complaint: string, timeline: [string], acoustic_indicators: [string], specialist: string, urgency: routine|soon|urgent, full_note: string}"""

SYSTEM_CAREGIVER = """Analyze this voice recording for cognitive or physical decline in an elderly patient. Write for a non-medical caregiver. Be compassionate and actionable. Respond ONLY in valid JSON with no markdown: {summary: string, flags: [string], severity: low|medium|high, recommended_action: string}"""

SYSTEM_WEEKLY_JOURNAL = """Review 7 days of voice biomarker data. Identify trends, flag concerns, write a plain-language weekly summary. Respond ONLY in valid JSON with no markdown: {summary: string, trend: improving|stable|worsening, key_changes: [string], recommendation: string}"""

SYSTEM_SECOND_OPINION = """You are comparing two voice recordings taken at different times from the same patient. Explain what changed acoustically and what it likely means clinically. Be specific with numbers. Respond ONLY in valid JSON with no markdown: {comparison_summary: string, key_changes: [{metric: string, value_a: number, value_b: number, delta: number, interpretation: string}], overall_trend: improving|stable|worsening, clinical_note: string}"""


def _parse_json_with_retry(text: str, system: str, user_msg: str) -> dict:
    """Parse JSON from Claude response, retry once if invalid."""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        if client is None:
            raise
        # Retry with stricter prompt
        retry_msg = user_msg + "\n\nYour previous response was not valid JSON. Return ONLY the JSON object."
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": retry_msg}],
        )
        return json.loads(response.content[0].text.strip())


async def stream_initial_analysis(features: dict, transcript: str) -> AsyncGenerator[str, None]:
    """Stream initial analysis from Claude, yield SSE chunks."""
    if client is None:
        yield f"data: {json.dumps({'result': _mock_initial_analysis(features, transcript), 'done': True})}\n\n"
        return

    transcript_note = transcript if transcript else "[Transcript unavailable — acoustic features only]"

    user_msg = f"""Acoustic features:
{json.dumps(features, indent=2)}

Patient transcript:
{transcript_note}

Analyze and return the JSON assessment."""

    accumulated = ""
    with client.messages.stream(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_INITIAL,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            accumulated += text
            yield f"data: {json.dumps({'chunk': text, 'done': False})}\n\n"

    # Validate JSON
    try:
        parsed = json.loads(accumulated.strip())
        normalized = _normalize_initial_analysis_response(parsed, features, transcript)
        yield f"data: {json.dumps({'result': normalized, 'done': True})}\n\n"
    except json.JSONDecodeError:
        # Retry non-streaming
        try:
            parsed = _parse_json_with_retry(accumulated, SYSTEM_INITIAL, user_msg)
            normalized = _normalize_initial_analysis_response(parsed, features, transcript)
            yield f"data: {json.dumps({'result': normalized, 'done': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"


async def stream_socratic_continuation(
    original_features: dict,
    original_analysis: dict,
    conversation_history: list,
    new_answer: str,
    new_features: dict | None = None,
) -> AsyncGenerator[str, None]:
    """Stream Socratic refinement."""
    if client is None:
        yield f"data: {json.dumps({'result': _mock_socratic(original_features, original_analysis, conversation_history, new_answer, new_features), 'done': True})}\n\n"
        return

    user_msg = f"""Original acoustic features:
{json.dumps(original_features, indent=2)}

Original analysis:
{json.dumps(original_analysis, indent=2)}

Conversation history so far:
{json.dumps(conversation_history, indent=2)}

Patient's latest answer: {new_answer}
"""
    if new_features:
        user_msg += f"\nNew recording acoustic features:\n{json.dumps(new_features, indent=2)}"

    accumulated = ""
    with client.messages.stream(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=SYSTEM_SOCRATIC,
        messages=[{"role": "user", "content": user_msg}],
    ) as stream:
        for text in stream.text_stream:
            accumulated += text
            yield f"data: {json.dumps({'chunk': text, 'done': False})}\n\n"

    try:
        parsed = json.loads(accumulated.strip())
        yield f"data: {json.dumps({'result': parsed, 'done': True})}\n\n"
    except json.JSONDecodeError:
        parsed = _parse_json_with_retry(accumulated, SYSTEM_SOCRATIC, user_msg)
        yield f"data: {json.dumps({'result': parsed, 'done': True})}\n\n"


async def get_final_report(
    features: dict,
    transcript: str,
    interview_rounds: list,
) -> dict:
    """Non-streaming final report generation (used for PDF)."""
    if client is None:
        return _mock_final_report(features, transcript, interview_rounds)

    user_msg = f"""Acoustic features:
{json.dumps(features, indent=2)}

Full transcript: {transcript}

Interview Q&A rounds:
{json.dumps(interview_rounds, indent=2)}

Generate the final pre-consultation note."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_FINAL_REPORT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _parse_json_with_retry(response.content[0].text, SYSTEM_FINAL_REPORT, user_msg)


async def get_caregiver_summary(features: dict, transcript: str, patient_name: str, history: list) -> dict:
    if client is None:
        return _mock_caregiver_summary(features, transcript, patient_name, history)

    user_msg = f"""Patient name: {patient_name}

Acoustic features (current recording):
{json.dumps(features, indent=2)}

Transcript: {transcript}

Prior submission history (if any):
{json.dumps(history[-3:] if history else [], indent=2)}

Analyze for cognitive or physical decline."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=SYSTEM_CAREGIVER,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _parse_json_with_retry(response.content[0].text, SYSTEM_CAREGIVER, user_msg)


async def get_weekly_journal_summary(entries: list) -> dict:
    if client is None:
        return _mock_weekly_journal_summary(entries)

    user_msg = f"""Last 7 days of voice biomarker data:
{json.dumps(entries, indent=2)}

Review and summarize the weekly trends."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=2048,
        system=SYSTEM_WEEKLY_JOURNAL,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _parse_json_with_retry(response.content[0].text, SYSTEM_WEEKLY_JOURNAL, user_msg)


async def get_second_opinion(features_a: dict, features_b: dict, transcript_a: str, transcript_b: str) -> dict:
    if client is None:
        return _mock_second_opinion(features_a, features_b, transcript_a, transcript_b)

    user_msg = f"""Recording A acoustic features:
{json.dumps(features_a, indent=2)}

Recording A transcript: {transcript_a}

Recording B acoustic features:
{json.dumps(features_b, indent=2)}

Recording B transcript: {transcript_b}

Compare these two recordings and explain what changed clinically."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_SECOND_OPINION,
        messages=[{"role": "user", "content": user_msg}],
    )
    return _parse_json_with_retry(response.content[0].text, SYSTEM_SECOND_OPINION, user_msg)


SYSTEM_WEEKLY_INSIGHTS = """You are a clinical voice health analyst. Generate a weekly health narrative based on disease risk scores and voice biomarker statistics.

Write in second person ("Your voice shows..."). Be encouraging but honest about any concerns. Keep the tone professional and caring.

Return a single paragraph summary (3-5 sentences) that:
1. Highlights the overall voice health status
2. Mentions any improving or concerning trends
3. Provides actionable advice if risks are elevated
4. Encourages continued monitoring

Do NOT use medical jargon. Write for a general audience."""


async def get_weekly_insights_narrative(scores: dict, stats: dict, checkins_count: int) -> str:
    """Generate AI narrative for weekly insights report."""
    if client is None:
        return _mock_weekly_insights_narrative(scores, stats)
    
    user_msg = f"""Disease risk scores (0-100 scale):
{json.dumps(scores, indent=2)}

Weekly voice biomarker statistics:
{json.dumps(stats, indent=2)}

Check-ins analyzed: {checkins_count}

Write a personalized weekly voice health summary paragraph."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            system=SYSTEM_WEEKLY_INSIGHTS,
            messages=[{"role": "user", "content": user_msg}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"[claude_client] Insights narrative error: {e}")
        return _mock_weekly_insights_narrative(scores, stats)


def _mock_weekly_insights_narrative(scores: dict, stats: dict) -> str:
    """Fallback narrative when API is unavailable."""
    elevated = [k for k, v in scores.items() if v.get("score", 0) > 30]
    
    if not elevated:
        return "Your voice patterns this week show healthy baseline markers across all tracked areas. Continue your daily check-ins to build a comprehensive health profile. No significant concerns were detected."
    
    concerns = ", ".join(scores[k].get("name", k) for k in elevated[:2])
    return f"Your voice analysis this week shows some elevated markers in {concerns}. While these readings may fluctuate naturally, consistent elevation over multiple weeks could warrant a conversation with your healthcare provider. Continue daily check-ins for more accurate trend tracking."
