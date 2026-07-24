from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.enums import SignalDirection
from app.services.signal_service import SignalService
from app.strategies.base import Signal as StrategySignal


def _sample_signal(symbol: str = "NVDA") -> StrategySignal:
    return StrategySignal(
        symbol=symbol,
        direction=SignalDirection.LONG,
        entry=Decimal("175.00"),
        stop_loss=Decimal("168.00"),
        target=Decimal("189.00"),
        confidence=82,
        reasoning=["Price above 50-day MA", "Volume 2.1x average"],
        strategy_name="momentum",
    )


def test_record_signal_persists_all_fields(db_session: Session) -> None:
    service = SignalService(db_session)

    saved = service.record_signal(_sample_signal())

    assert saved.id is not None
    assert saved.symbol == "NVDA"
    assert saved.direction == SignalDirection.LONG
    assert saved.entry == Decimal("175.00")
    assert saved.confidence == 82
    assert saved.reasoning == ["Price above 50-day MA", "Volume 2.1x average"]


def test_list_recent_orders_newest_first(db_session: Session) -> None:
    service = SignalService(db_session)
    service.record_signal(_sample_signal("AAA"))
    service.record_signal(_sample_signal("BBB"))
    service.record_signal(_sample_signal("CCC"))

    recent = service.list_recent(limit=2)

    assert len(recent) == 2
    assert recent[0].symbol == "CCC"
    assert recent[1].symbol == "BBB"
