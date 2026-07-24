from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import SignalDirection


class SignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    strategy_name: str
    direction: SignalDirection
    entry: Decimal
    stop_loss: Decimal
    target: Decimal
    confidence: int
    reasoning: list[str]
    created_at: datetime
