import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models.user import User
from models.session import RecordingSession
from models.baseline import Baseline
from schemas.session import SessionCreate, SessionOut, SessionPage

router = APIRouter(prefix="/sessions", tags=["sessions"])

DRIFT_THRESHOLD = 0.70  # flag if confidence drops below 70% of baseline


def _check_drift(user: User, confidence: float) -> bool:
    if user.baseline and confidence < user.baseline.avg_confidence * DRIFT_THRESHOLD:
        return True
    return False


def _maybe_create_baseline(user: User, session: RecordingSession, db: Session):
    """Auto-establish baseline from first high-confidence cough session."""
    if user.baseline:
        return
    if session.prediction == "cough" and session.confidence >= 0.80:
        feature_summary = None
        if session.features:
            arr = np.array(session.features)
            feature_summary = {"mean": arr.mean(axis=0).tolist(), "std": arr.std(axis=0).tolist()}
        baseline = Baseline(
            user_id=user.id,
            avg_confidence=session.confidence,
            feature_summary=feature_summary,
        )
        db.add(baseline)
        db.commit()


@router.post("", response_model=SessionOut, status_code=201)
def create_session(
    payload: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    drift = _check_drift(current_user, payload.confidence) if payload.prediction == "cough" else False
    session = RecordingSession(
        user_id=current_user.id,
        prediction=payload.prediction,
        confidence=payload.confidence,
        duration_ms=payload.duration_ms,
        features=payload.features,
        drift_detected=drift,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Check if we should auto-create baseline
    _maybe_create_baseline(current_user, session, db)

    return session


@router.get("", response_model=SessionPage)
def list_sessions(
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(RecordingSession).filter(RecordingSession.user_id == current_user.id)
    total = query.count()
    items = query.order_by(RecordingSession.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return SessionPage(total=total, page=page, page_size=page_size, items=items)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(RecordingSession).filter(
        RecordingSession.id == session_id,
        RecordingSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
