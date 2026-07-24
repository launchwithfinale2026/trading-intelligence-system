"""Turns raw signal/decision/trade-result rows into the system's track
record: per-strategy acceptance rate and win rate. This is what makes "we
sent 40 alerts" into "momentum has a 61% acceptance rate and a 1.8R average
outcome" (see docs/ARCHITECTURE.md section 3).
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.database.models.position import Position
from app.database.models.signal import Signal
from app.database.models.trade_result import TradeResult
from app.domain.enums import DecisionType, PositionStatus, SignalDirection
from app.repositories.decision_repository import DecisionRepository
from app.repositories.signal_repository import SignalRepository
from app.repositories.trade_result_repository import TradeResultRepository

_CENT = Decimal("0.01")
_CLOSED_STATUSES = {PositionStatus.CLOSED_STOP, PositionStatus.CLOSED_TARGET, PositionStatus.CLOSED_MANUAL}


@dataclass(frozen=True, slots=True)
class StrategyPerformance:
    strategy_name: str
    signals_generated: int
    accepted: int
    ignored: int
    trades_closed: int
    wins: int
    win_rate: Decimal | None  # percent, e.g. Decimal("61.5"); None if no closed trades yet
    average_r_multiple: Decimal | None


class FeedbackService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.trade_results = TradeResultRepository(db)

    def record_trade_result(self, *, position: Position, signal: Signal) -> TradeResult:
        if position.status not in _CLOSED_STATUSES or position.close_price is None:
            raise ValueError(f"position {position.id} is not closed")
        if self.trade_results.get_by_position(position.id) is not None:
            raise ConflictError(f"trade result already recorded for position {position.id}")

        is_long = signal.direction == SignalDirection.LONG
        pnl_per_share = (position.close_price - position.entry) if is_long else (position.entry - position.close_price)
        pnl = (pnl_per_share * position.shares).quantize(_CENT)

        initial_risk_per_share = abs(position.entry - position.stop_loss)
        r_multiple = (
            (pnl_per_share / initial_risk_per_share).quantize(_CENT) if initial_risk_per_share else Decimal("0.00")
        )

        result = self.trade_results.add(
            TradeResult(
                position_id=position.id,
                user_id=position.user_id,
                signal_id=signal.id,
                strategy_name=signal.strategy_name,
                is_win=pnl > 0,
                r_multiple=r_multiple,
                pnl=pnl,
            )
        )
        self.db.commit()
        self.db.refresh(result)
        return result

    def get_performance_by_strategy(self) -> list[StrategyPerformance]:
        signals = SignalRepository(self.db).list()
        decisions = DecisionRepository(self.db).list()
        results = self.trade_results.list_all()

        signal_strategy = {signal.id: signal.strategy_name for signal in signals}

        buckets: dict[str, dict] = {}

        def bucket(name: str) -> dict:
            return buckets.setdefault(
                name,
                {"signals_generated": 0, "accepted": 0, "ignored": 0, "trades_closed": 0, "wins": 0, "r_sum": Decimal(0), "r_count": 0},
            )

        for signal in signals:
            bucket(signal.strategy_name)["signals_generated"] += 1

        for decision in decisions:
            strategy_name = signal_strategy.get(decision.signal_id)
            if strategy_name is None:
                continue
            b = bucket(strategy_name)
            if decision.decision == DecisionType.OPEN:
                b["accepted"] += 1
            else:
                b["ignored"] += 1

        for result in results:
            b = bucket(result.strategy_name)
            b["trades_closed"] += 1
            if result.is_win:
                b["wins"] += 1
            b["r_sum"] += result.r_multiple
            b["r_count"] += 1

        performance = [
            StrategyPerformance(
                strategy_name=name,
                signals_generated=b["signals_generated"],
                accepted=b["accepted"],
                ignored=b["ignored"],
                trades_closed=b["trades_closed"],
                wins=b["wins"],
                win_rate=(
                    (Decimal(b["wins"]) / b["trades_closed"] * 100).quantize(Decimal("0.1"))
                    if b["trades_closed"]
                    else None
                ),
                average_r_multiple=(b["r_sum"] / b["r_count"]).quantize(_CENT) if b["r_count"] else None,
            )
            for name, b in buckets.items()
        ]
        return sorted(performance, key=lambda p: p.strategy_name)
