from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import PositionStatus


class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_id: int
    entry: Decimal
    stop_loss: Decimal
    target: Decimal
    shares: int
    status: PositionStatus
    close_price: Decimal | None
    closed_at: datetime | None
    created_at: datetime
