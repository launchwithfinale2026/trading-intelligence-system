from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import DecisionType


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: int
    decision: DecisionType
    created_at: datetime
