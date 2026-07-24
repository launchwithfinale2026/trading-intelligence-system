from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import SignalDirection
from app.risk.calculator import PositionSize
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal
from app.telegram.alerts import extract_signal_id, format_alert


def _persisted_signal(db_session: Session):
    return SignalService(db_session).record_signal(
        StrategySignal(
            symbol="NVDA",
            direction=SignalDirection.LONG,
            entry=Decimal("175.00"),
            stop_loss=Decimal("168.00"),
            target=Decimal("189.00"),
            confidence=88,
            reasoning=["Volume expansion", "Trend confirmation"],
            strategy_name="momentum",
        )
    )


def test_format_alert_includes_all_required_fields(db_session: Session) -> None:
    signal = _persisted_signal(db_session)
    position_size = PositionSize(
        shares=250, position_value=Decimal("43750.00"), dollar_risk=Decimal("1750.00"), risk_percent=Decimal("0.02")
    )

    text = format_alert(signal, position_size)

    assert "NVDA" in text
    assert "momentum" in text
    assert "175.00" in text
    assert "250 shares" in text
    assert "168.00" in text
    assert "189.00" in text
    assert "88%" in text
    assert "Volume expansion" in text
    assert "Trend confirmation" in text
    assert "OPEN" in text and "IGNORE" in text
    assert f"Signal ID: {signal.id}" in text


def test_extract_signal_id_round_trips_with_format_alert(db_session: Session) -> None:
    signal = _persisted_signal(db_session)
    position_size = PositionSize(
        shares=10, position_value=Decimal("1750.00"), dollar_risk=Decimal("70.00"), risk_percent=Decimal("0.02")
    )

    text = format_alert(signal, position_size)

    assert extract_signal_id(text) == signal.id


def test_extract_signal_id_returns_none_for_unrelated_text() -> None:
    assert extract_signal_id("just a normal message") is None
