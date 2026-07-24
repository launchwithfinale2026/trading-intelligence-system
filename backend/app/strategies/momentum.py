"""Momentum strategy: enters long when a symbol shows trend strength, a
recent price momentum burst, and a volume increase confirming it.

Long-only in v1 — shorting momentum (fading a move) is a materially
different strategy with different risk characteristics and isn't in the
build spec's scope.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.analysis.technical import average_volume, is_uptrend, percent_change, simple_moving_average
from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.base import Signal, Strategy

_SMA_PERIOD = 50
_MOMENTUM_LOOKBACK_DAYS = 10
_VOLUME_AVERAGE_PERIOD = 20
_MIN_MOMENTUM_PERCENT = Decimal(5)
_MIN_VOLUME_SURGE_RATIO = Decimal("1.3")
_STOP_LOSS_PERCENT = Decimal("0.05")
_REWARD_RISK_RATIO = Decimal(2)
_CENT = Decimal("0.01")


class MomentumStrategy(Strategy):
    name = "momentum"

    def evaluate(self, symbol: str, history: list[PricePoint]) -> Signal | None:
        min_required = _SMA_PERIOD + _MOMENTUM_LOOKBACK_DAYS
        if len(history) < min_required:
            return None

        closes = [p.close for p in history]
        volumes = [p.volume for p in history]
        current = history[-1]

        moving_average = simple_moving_average(closes, _SMA_PERIOD)
        if not is_uptrend(current.close, moving_average):
            return None

        lookback_price = closes[-(_MOMENTUM_LOOKBACK_DAYS + 1)]
        momentum_percent = percent_change(lookback_price, current.close)
        if momentum_percent < _MIN_MOMENTUM_PERCENT:
            return None

        trailing_avg_volume = average_volume(volumes[:-1], _VOLUME_AVERAGE_PERIOD)
        if trailing_avg_volume <= 0:
            return None
        volume_ratio = Decimal(current.volume) / trailing_avg_volume
        if volume_ratio < _MIN_VOLUME_SURGE_RATIO:
            return None

        entry = current.close
        stop_loss = (entry * (1 - _STOP_LOSS_PERCENT)).quantize(_CENT, rounding=ROUND_HALF_UP)
        risk_per_share = entry - stop_loss
        target = (entry + risk_per_share * _REWARD_RISK_RATIO).quantize(_CENT, rounding=ROUND_HALF_UP)

        momentum_component = min(Decimal(100), momentum_percent * 5)
        volume_component = min(Decimal(100), (volume_ratio - 1) * 100)
        confidence = int(((momentum_component + volume_component) / 2).to_integral_value())

        reasoning = [
            f"Price is {momentum_percent:.1f}% above its level {_MOMENTUM_LOOKBACK_DAYS} trading days ago",
            f"Price is above its {_SMA_PERIOD}-day moving average",
            f"Volume is {volume_ratio:.2f}x its {_VOLUME_AVERAGE_PERIOD}-day average",
        ]

        return Signal(
            symbol=symbol,
            direction=SignalDirection.LONG,
            entry=entry,
            stop_loss=stop_loss,
            target=target,
            confidence=confidence,
            reasoning=reasoning,
            strategy_name=self.name,
        )
