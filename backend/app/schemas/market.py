from datetime import datetime

from pydantic import BaseModel


class MarketStatusRead(BaseModel):
    is_open: bool
    session: str
    as_of: datetime
