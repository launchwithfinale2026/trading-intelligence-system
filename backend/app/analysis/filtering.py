"""Quality Filter: the explicit pipeline stage between Market Universe and
Technical Analysis (see docs/ARCHITECTURE.md). Removes low-quality setups
before any strategy spends effort evaluating them.

Evaluates exactly five things, each independently and each producing a
human-readable reason (pass or fail) rather than a bare boolean — this is
what lets a rejected candidate be explained, not just discarded:
  - liquidity        (is there enough volume to actually trade this?)
  - volatility        (is it moving enough to offer opportunity, without
                        being so erratic that stops become noise?)
  - trend              (is it in a confirmed directional move?)
  - volume             (is today's participation elevated vs. normal?)
  - price movement      (is today itself showing real activity?)

Deliberately separate from analysis/scoring.py: this module is a pass/fail
gate (Quality Filter), scoring.py is the 0-100 ranking (Opportunity
Ranking) that runs on whatever survives this gate — two distinct stages in
the pipeline, not overlapping responsibilities.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from app.analysis.technical import average_volume, historical_volatility, percent_change, trend_direction


@dataclass(frozen=True, slots=True)
class QualityFilterConfig:
    min_volume: int = 1_000_000
    min_price: Decimal = Decimal("5.00")  # excludes penny stocks as a liquidity/quality proxy
    volatility_period: int = 20
    min_volatility_pct: Decimal = Decimal("0.5")  # excludes essentially dead/no-movement symbols
    max_volatility_pct: Decimal = Decimal("8.0")  # excludes erratic names where stops are just noise
    trend_short_period: int = 20
    trend_long_period: int = 50
    volume_average_period: int = 20
    min_volume_surge_ratio: Decimal = Decimal("1.2")  # today's volume vs. its own recent average
    min_price_movement_pct: Decimal = Decimal("0.3")  # today's move must show real activity


@dataclass(frozen=True, slots=True)
class QualityFilterResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)  # "+ ..." pass reasons and "- ..." fail reasons


def evaluate_quality(
    *,
    price: Decimal,
    volume: int,
    closes: list[Decimal],
    volumes: list[int],
    config: QualityFilterConfig | None = None,
) -> QualityFilterResult:
    """closes/volumes are OHLCV history, oldest first, most recent last —
    the same shape as [p.close for p in provider.get_history(...)].
    """
    config = config or QualityFilterConfig()
    reasons: list[str] = []
    passed = True

    # --- liquidity ---
    if volume >= config.min_volume and price >= config.min_price:
        reasons.append(f"+ liquidity: volume {volume:,} on a ${price} symbol clears the bar")
    else:
        passed = False
        if volume < config.min_volume:
            reasons.append(f"- liquidity: volume {volume:,} below minimum {config.min_volume:,}")
        if price < config.min_price:
            reasons.append(f"- liquidity: price {price} below minimum {config.min_price}")

    # --- volatility ---
    volatility_pct = historical_volatility(closes, period=config.volatility_period)
    if config.min_volatility_pct <= volatility_pct <= config.max_volatility_pct:
        reasons.append(f"+ volatility: {volatility_pct:.2f}% daily is in the tradeable range")
    else:
        passed = False
        reasons.append(
            f"- volatility: {volatility_pct:.2f}% outside the "
            f"{config.min_volatility_pct}-{config.max_volatility_pct}% range"
        )

    # --- trend ---
    direction = trend_direction(closes, config.trend_short_period, config.trend_long_period)
    if direction == "up":
        reasons.append("+ trend: short-term average above long-term average (confirmed uptrend)")
    else:
        passed = False
        reasons.append(f"- trend: not a confirmed uptrend (direction={direction})")

    # --- volume (today's participation vs. its own recent average) ---
    trailing_avg_volume = average_volume(volumes[:-1], config.volume_average_period)
    surge_ratio = Decimal(volume) / trailing_avg_volume if trailing_avg_volume > 0 else Decimal(0)
    if surge_ratio >= config.min_volume_surge_ratio:
        reasons.append(f"+ volume: {surge_ratio:.2f}x its {config.volume_average_period}-day average")
    else:
        passed = False
        reasons.append(
            f"- volume: {surge_ratio:.2f}x average is below the {config.min_volume_surge_ratio}x minimum"
        )

    # --- price movement (today's actual move) ---
    today_change_pct = percent_change(closes[-2], closes[-1])
    if abs(today_change_pct) >= config.min_price_movement_pct:
        reasons.append(f"+ price movement: {today_change_pct:.2f}% today shows real activity")
    else:
        passed = False
        reasons.append(f"- price movement: {today_change_pct:.2f}% today is too flat")

    return QualityFilterResult(passed=passed, reasons=reasons)
