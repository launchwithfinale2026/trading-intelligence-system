import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, MarketDataError, RiskLimitError
from app.database.models.position import Position
from app.database.models.signal import Signal
from app.database.models.user import User
from app.domain.enums import PositionStatus, SignalDirection
from app.market.provider import MarketDataProvider
from app.repositories.position_repository import PositionRepository
from app.repositories.signal_repository import SignalRepository
from app.services.risk_policy_service import RiskPolicyService

logger = logging.getLogger(__name__)


class PositionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.positions = PositionRepository(db)
        self.signals = SignalRepository(db)

    def open_position(self, *, user: User, signal: Signal) -> Position:
        if self.positions.get_by_user_and_signal(user.id, signal.id) is not None:
            raise ConflictError(f"user {user.id} already has a position for signal {signal.id}")

        position_size = RiskPolicyService(self.db).size_position(
            account_size=user.profile.account_size,
            risk_preference=user.profile.risk_preference,
            entry=signal.entry,
            stop_loss=signal.stop_loss,
        )
        if position_size.shares <= 0:
            raise RiskLimitError(
                f"risk budget affords 0 shares of {signal.symbol} at entry {signal.entry}/stop {signal.stop_loss}"
            )

        position = self.positions.add(
            Position(
                user_id=user.id,
                signal_id=signal.id,
                entry=signal.entry,
                stop_loss=signal.stop_loss,
                target=signal.target,
                shares=position_size.shares,
            )
        )
        self.db.commit()
        self.db.refresh(position)
        return position

    def close_position(self, position: Position, *, close_price: Decimal, status: PositionStatus) -> Position:
        position.close_price = close_price
        position.status = status
        position.closed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(position)
        return position

    def check_and_close_open_positions(self, provider: MarketDataProvider) -> list[Position]:
        """Fetches one current price per distinct symbol (not per position —
        several users can hold the same symbol) and closes any position
        whose stop or target has been crossed. Returns the positions closed
        during this call.
        """
        open_positions = self.positions.list_open()

        positions_by_symbol: dict[str, list[tuple[Position, Signal]]] = {}
        for position in open_positions:
            signal = self.signals.get(position.signal_id)
            if signal is None:
                logger.warning("position %s references missing signal %s", position.id, position.signal_id)
                continue
            positions_by_symbol.setdefault(signal.symbol, []).append((position, signal))

        closed: list[Position] = []
        for symbol, entries in positions_by_symbol.items():
            try:
                price = provider.get_price(symbol)
            except MarketDataError as exc:
                logger.warning("skipping position check for %s: %s", symbol, exc)
                continue

            for position, signal in entries:
                outcome = self._evaluate_close(position, signal.direction, price)
                if outcome is not None:
                    closed.append(self.close_position(position, close_price=price, status=outcome))

        return closed

    @staticmethod
    def _evaluate_close(position: Position, direction: SignalDirection, price: Decimal) -> PositionStatus | None:
        if direction == SignalDirection.LONG:
            if price <= position.stop_loss:
                return PositionStatus.CLOSED_STOP
            if price >= position.target:
                return PositionStatus.CLOSED_TARGET
        else:
            if price >= position.stop_loss:
                return PositionStatus.CLOSED_STOP
            if price <= position.target:
                return PositionStatus.CLOSED_TARGET
        return None
