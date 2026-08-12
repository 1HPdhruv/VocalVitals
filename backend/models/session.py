from datetime import datetime
from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class RecordingSession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    # Classifier output
    prediction: Mapped[str] = mapped_column(String, nullable=False)   # cough | breath | background
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)

    # 16-dim feature vectors per frame stored as JSON list-of-lists
    features: Mapped[list] = mapped_column(JSON, nullable=True)

    # Drift flag set by the API when comparing against baseline
    drift_detected: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
