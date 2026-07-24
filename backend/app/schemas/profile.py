from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AlertPreference, RiskPreference, TradingStyle


class ProfileCreate(BaseModel):
    account_size: Decimal = Field(gt=0)
    risk_preference: RiskPreference
    trading_style: TradingStyle
    alert_preference: AlertPreference = AlertPreference.ALL_SIGNALS


class ProfileUpdate(BaseModel):
    account_size: Decimal | None = Field(default=None, gt=0)
    risk_preference: RiskPreference | None = None
    trading_style: TradingStyle | None = None
    alert_preference: AlertPreference | None = None


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    account_size: Decimal
    risk_preference: RiskPreference
    trading_style: TradingStyle
    alert_preference: AlertPreference
