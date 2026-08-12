from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class BaselineOut(BaseModel):
    id: int
    avg_confidence: float
    feature_summary: Optional[dict]
    established_at: datetime
    reset_at: Optional[datetime]

    model_config = {"from_attributes": True}
