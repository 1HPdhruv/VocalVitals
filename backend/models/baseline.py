from datetime import datetime
from typing import Optional
from sqlalchemy import Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class Baseline(Base):
    __tablename__ = "baselines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # Average confidence of the baseline cough sessions
    avg_confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # Mean 16-dim feature vector across baseline frames
    feature_summary: Mapped[dict] = mapped_column(JSON, nullable=True)

    established_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user = relationship("User", back_populates="baseline")
