from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SessionCreate(BaseModel):
    prediction: str              # "cough" | "breath" | "background"
    confidence: float
    duration_ms: Optional[int] = None
    features: Optional[List[List[float]]] = None   # frames × 16 dims


class SessionOut(BaseModel):
    id: int
    prediction: str
    confidence: float
    duration_ms: Optional[int]
    drift_detected: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[SessionOut]
