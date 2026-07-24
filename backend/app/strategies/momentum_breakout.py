"""Momentum Breakout: the flagship strategy combining a structure break
with momentum and volume confirmation, plus an RSI sanity check that the
simpler momentum.py/breakout.py strategies don't have.

Conditions (all required):
  - close breaks above the prior N-day high (structure break)
  - price momentum over the lookback window clears a minimum threshold
  - volume confirms the move (surge vs. its own trailing average)
  - RSI is not already deep into overbought territory — this strategy is
    for catching a breakout early, not for chasing an already-extended move

Deterministic and explainable: same history in, same signal-or-None out,
with reasoning built entirely from the real thresholds that were checked.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.analysis.technical import average_volume, percent_change, rsi
from app.domain.enums import SignalDirection
from app.market.provider import PricePoint
from app.strategies.base import Signal, Strategy

_STRUCTURE_LOOKBACK = 20
_MOMENTUM_LOOKBACK_DAYS = 10
_VOLUME_AVERAGE_PERIOD = 20
_RSI_PERIOD = 14
_MIN_MOMENTUM_PERCENT = Decimal(3)
_MIN_VOLUME_SURGE_RATIO = Decimal("1.4")
_MAX_RSI = Decimal(80)  # above this, the move is already extended -- skip it
_REWARD_RISK_RATIO = Decimal("2.5")
_CENT = Decimal("0.01")


class MomentumBreakoutStrategy(Strategy):
    name = "momentum_breakout"

    def evaluate(self, symbol: str, history: list[PricePoint]) -> Signal | None:
        min_required = max(_STRUCTURE_LOOKBACK, _VOLUME_AVERAGE_PERIOD, _RSI_PERIOD + 1) + _MOMENTUM_LOOKBACK_DAYS
        if len(history) < min_required:
            return None

        closes = [p.close for p in history]
        volumes = [p.volume for p in history]
        current = history[-1]
        prior_bars = history[:-1]

        resistance_level = max(p.high for p in prior_bars[-_STRUCTURE_LOOKBACK:])
        if current.close <= resistance_level:
            return None  # no structure break

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

        current_rsi = rsi(closes, period=_RSI_PERIOD)
        if current_rsi > _MAX_RSI:
            return None  # already overbought -- this breakout is late, not early

        entry = current.close
        stop_loss = resistance_level
        risk_per_share = entry - stop_loss
        if risk_per_share <= 0:
            return None
        target = (entry + risk_per_share * _REWARD_RISK_RATIO).quantize(_CENT, rounding=ROUND_HALF_UP)

        breakout_percent = percent_change(resistance_level, entry)
        breakout_component = min(Decimal(100), breakout_percent * 15)
        volume_component = min(Decimal(100), (volume_ratio - 1) * 100)
        confidence = int(((breakout_component + volume_component) / 2).to_integral_value())

        reasoning = [
            f"Price broke above its {_STRUCTURE_LOOKBACK}-day high of {resistance_level}",
            f"Momentum: {momentum_percent:.1f}% over the last {_MOMENTUM_LOOKBACK_DAYS} trading days",
            f"Volume is {volume_ratio:.2f}x its {_VOLUME_AVERAGE_PERIOD}-day average",
            f"RSI is {current_rsi:.0f}, not yet overbought (limit {_MAX_RSI})",
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
