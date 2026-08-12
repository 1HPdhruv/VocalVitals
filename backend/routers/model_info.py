from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.auth import require_admin
from database import get_db
from models.model_version import ModelVersion
from models.user import User

router = APIRouter(prefix="/model", tags=["model"])


@router.get("/version")
def get_model_version(db: Session = Depends(get_db)):
    """Return the currently active model version info."""
    version = db.query(ModelVersion).filter(ModelVersion.is_active == True).order_by(ModelVersion.trained_at.desc()).first()  # noqa: E712
    if not version:
        return {"version": "v4.0-dummy", "accuracy": None, "notes": "No model version recorded yet."}
    return {
        "version": version.version,
        "accuracy": version.accuracy,
        "notes": version.notes,
        "trained_at": version.trained_at,
    }


@router.post("/admin/retrain")
def trigger_retrain(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """
    Admin-only endpoint. In a real deployment this would enqueue a background
    retraining job (e.g. via Celery or a Render background worker).
    For now it returns a 202 Accepted with instructions.
    """
    return {
        "status": "accepted",
        "message": (
            "Retraining is not yet automated. "
            "Run `python training/train_vocalvitals.py` locally, "
            "copy the weights to `frontend/model/`, then push to trigger a Vercel redeploy."
        ),
    }
