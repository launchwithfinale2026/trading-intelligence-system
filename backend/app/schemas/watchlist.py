from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


class WatchlistSymbolRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol: str
    created_at: datetime


class WatchlistSymbolCreate(BaseModel):
    symbol: str

    @field_validator("symbol")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("symbol must not be blank")
        return value
