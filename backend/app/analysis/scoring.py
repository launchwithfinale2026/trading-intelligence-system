"""Quality-filter scoring: turns raw candidate metrics into a pass/fail
filter result and a 0-100 ranking score.

This is deliberately a pure, dependency-free layer (no MarketDataProvider,
no I/O) — everything here operates on CandidateMetrics that the caller
(market/scanner.py) has already fetched, which is what makes filtering and
scoring fully testable with fixture data per Phase 6's success criteria.
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    """Everything the quality filters and scorer need for one symbol."""

    symbol: str
    price: Decimal
    volume: int
    market_cap: Decimal
    average_volume: Decimal  # trailing average, e.g. 20-day
    moving_average: Decimal  # trailing trend average, e.g. 50-day SMA of close


@dataclass(frozen=True, slots=True)
class ScannerConfig:
    """Filter thresholds. Defaults describe a conservative "quality" bar —
    liquid, established, trending, currently showing unusual strength.
    """

    min_volume: int = 1_000_000
    min_market_cap: Decimal = Decimal("2000000000")  # $2B — roughly mid-cap and up
    min_volume_surge_ratio: Decimal = Decimal("1.5")  # today's volume vs. its own average


@dataclass(frozen=True, slots=True)
class FilterResult:
    passed: bool
    failed_reasons: list[str] = field(default_factory=list)


def evaluate_filters(metrics: CandidateMetrics, config: ScannerConfig | None = None) -> FilterResult:
    config = config or ScannerConfig()
    reasons: list[str] = []

    if metrics.volume < config.min_volume:
        reasons.append(f"volume {metrics.volume} below liquidity threshold {config.min_volume}")

    if metrics.market_cap < config.min_market_cap:
        reasons.append(f"market cap {metrics.market_cap} below quality threshold {config.min_market_cap}")

    if metrics.price <= metrics.moving_average:
        reasons.append("price is not above its trend moving average")

    if metrics.average_volume > 0:
        surge_ratio = metrics.volume / metrics.average_volume
    else:
        surge_ratio = Decimal(0)
    if surge_ratio < config.min_volume_surge_ratio:
        reasons.append(
            f"volume surge ratio {surge_ratio:.2f} below momentum threshold {config.min_volume_surge_ratio}"
        )

    return FilterResult(passed=len(reasons) == 0, failed_reasons=reasons)


def score_candidate(metrics: CandidateMetrics) -> int:
    """0-100 score. Only meaningful for candidates that already passed
    evaluate_filters — this does not re-check thresholds, it ranks strength.

    Formula (first-pass heuristic, equally weighted; a natural place to
    incorporate Feedback System data later — see docs/ROADMAP.md Phase 11):
      - trend component: how far price is above its moving average
      - momentum component: how far volume exceeds its own average
    Both are scaled and capped to [0, 100], then averaged.
    """
    trend_pct = (metrics.price - metrics.moving_average) / metrics.moving_average * 100
    trend_component = min(Decimal(100), max(Decimal(0), trend_pct * 10))

    if metrics.average_volume > 0:
        volume_surge_pct = (metrics.volume / metrics.average_volume - 1) * 100
    else:
        volume_surge_pct = Decimal(0)
    momentum_component = min(Decimal(100), max(Decimal(0), volume_surge_pct))

    score = (trend_component + momentum_component) / 2
    return int(score.to_integral_value())
