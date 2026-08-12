from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.auth import get_current_user
from database import get_db
from models.user import User
from models.baseline import Baseline
from schemas.baseline import BaselineOut

router = APIRouter(prefix="/baseline", tags=["baseline"])


@router.get("", response_model=BaselineOut)
def get_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.baseline:
        raise HTTPException(status_code=404, detail="No baseline established yet. Record a high-confidence cough first.")
    return current_user.baseline


@router.put("/reset", response_model=dict)
def reset_baseline(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.baseline:
        raise HTTPException(status_code=404, detail="No baseline to reset")
    current_user.baseline.reset_at = datetime.utcnow()
    db.delete(current_user.baseline)
    db.commit()
    return {"message": "Baseline cleared. It will re-establish on your next high-confidence cough session."}
