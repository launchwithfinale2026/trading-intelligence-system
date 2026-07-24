"""Breakout strategy: enters long when price closes above its recent
resistance level (a structure break) on confirming volume.

The stop loss is placed at the broken resistance level itself (which
becomes the new support) rather than a fixed percentage — if price falls
back below the level it broke out from, the breakout thesis has failed.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.analysis.technical import average_volume, percent_change
from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.base import Signal, Strategy

_LOOKBACK_PERIOD = 20
_VOLUME_AVERAGE_PERIOD = 20
_MIN_VOLUME_SURGE_RATIO = Decimal("1.5")
_REWARD_RISK_RATIO = Decimal(2)
_CENT = Decimal("0.01")


class BreakoutStrategy(Strategy):
    name = "breakout"

    def evaluate(self, symbol: str, history: list[PricePoint]) -> Signal | None:
        min_required = max(_LOOKBACK_PERIOD, _VOLUME_AVERAGE_PERIOD) + 1
        if len(history) < min_required:
            return None

        current = history[-1]
        prior_bars = history[:-1]
        resistance_level = max(p.high for p in prior_bars[-_LOOKBACK_PERIOD:])

        if current.close <= resistance_level:
            return None  # no structure break

        volumes = [p.volume for p in history]
        trailing_avg_volume = average_volume(volumes[:-1], _VOLUME_AVERAGE_PERIOD)
        if trailing_avg_volume <= 0:
            return None
        volume_ratio = Decimal(current.volume) / trailing_avg_volume
        if volume_ratio < _MIN_VOLUME_SURGE_RATIO:
            return None

        entry = current.close
        stop_loss = resistance_level
        risk_per_share = entry - stop_loss
        if risk_per_share <= 0:
            return None
        target = (entry + risk_per_share * _REWARD_RISK_RATIO).quantize(_CENT, rounding=ROUND_HALF_UP)

        breakout_percent = percent_change(resistance_level, entry)
        breakout_component = min(Decimal(100), breakout_percent * 20)
        volume_component = min(Decimal(100), (volume_ratio - 1) * 100)
        confidence = int(((breakout_component + volume_component) / 2).to_integral_value())

        reasoning = [
            f"Price broke above its {_LOOKBACK_PERIOD}-day high of {resistance_level}",
            f"Breakout close is {breakout_percent:.1f}% above that resistance level",
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
