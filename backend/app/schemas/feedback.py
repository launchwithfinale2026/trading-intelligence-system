from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class StrategyPerformanceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    strategy_name: str
    signals_generated: int
    accepted: int
    ignored: int
    trades_closed: int
    wins: int
    win_rate: Decimal | None
    average_r_multiple: Decimal | None
