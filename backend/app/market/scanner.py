"""Quality filter scanner: narrows a broad universe down to a small,
ranked list of high-quality candidates. See docs/ARCHITECTURE.md section 3
for why this exists — the goal is cream-of-the-crop, not scanning every
random stock.

Two independent gates must both pass before a candidate is scored:
  - analysis.scoring.evaluate_filters — liquidity/market-cap/trend/volume-surge
  - analysis.filtering.evaluate_quality — liquidity/volatility/trend/volume/
    price-movement (the explicit five-criteria Quality Filter stage)
They overlap somewhat (both check liquidity/trend/volume) but each also
catches things the other doesn't (market cap vs. volatility bounds vs.
today's raw price movement) — together they're a stricter, more complete
gate than either alone.
"""

import logging
from dataclasses import dataclass, field

from app.analysis.filtering import QualityFilterConfig, evaluate_quality
from app.analysis.scoring import CandidateMetrics, ScannerConfig, evaluate_filters, score_candidate
from app.analysis.technical import average_volume, simple_moving_average
from app.core.exceptions import MarketDataError
from app.market.provider import MarketDataProvider

logger = logging.getLogger(__name__)

_SMA_PERIOD = 50
_VOLUME_AVERAGE_PERIOD = 20
_HISTORY_PERIOD = "3mo"  # enough trading days to cover a 50-day SMA


@dataclass(frozen=True, slots=True)
class RankedCandidate:
    symbol: str
    score: int
    reasons: list[str] = field(default_factory=list)


class Scanner:
    def __init__(
        self,
        provider: MarketDataProvider,
        config: ScannerConfig | None = None,
        quality_config: QualityFilterConfig | None = None,
    ) -> None:
        self.provider = provider
        self.config = config or ScannerConfig()
        self.quality_config = quality_config or QualityFilterConfig()

    def scan(self, universe: list[str]) -> list[RankedCandidate]:
        """Ranked, deduplicated candidates that pass every quality filter,
        highest score first. Symbols with unavailable data are skipped
        (logged), not fabricated, and do not abort the rest of the scan.
        """
        results: list[RankedCandidate] = []

        for symbol in dict.fromkeys(universe):  # dedupe, preserve order
            try:
                metrics, closes, volumes = self._build_metrics(symbol)
            except MarketDataError as exc:
                logger.warning("skipping %s: %s", symbol, exc)
                continue

            filter_result = evaluate_filters(metrics, self.config)
            if not filter_result.passed:
                logger.debug("%s failed core filters: %s", symbol, filter_result.failed_reasons)
                continue

            quality_result = evaluate_quality(
                price=metrics.price,
                volume=metrics.volume,
                closes=closes,
                volumes=volumes,
                config=self.quality_config,
            )
            if not quality_result.passed:
                logger.debug("%s failed quality filter: %s", symbol, quality_result.reasons)
                continue

            pass_reasons = [r for r in quality_result.reasons if r.startswith("+")]
            results.append(
                RankedCandidate(symbol=symbol, score=score_candidate(metrics), reasons=pass_reasons)
            )

        return sorted(results, key=lambda candidate: candidate.score, reverse=True)

    def _build_metrics(self, symbol: str) -> tuple[CandidateMetrics, list, list]:
        price = self.provider.get_price(symbol)
        volume = self.provider.get_volume(symbol)
        market_cap = self.provider.get_market_cap(symbol)
        history = self.provider.get_history(symbol, period=_HISTORY_PERIOD)

        closes = [point.close for point in history]
        volumes = [point.volume for point in history]

        moving_average = simple_moving_average(closes, min(_SMA_PERIOD, len(closes)))
        trailing_average_volume = average_volume(volumes, min(_VOLUME_AVERAGE_PERIOD, len(volumes)))

        metrics = CandidateMetrics(
            symbol=symbol,
            price=price,
            volume=volume,
            market_cap=market_cap,
            average_volume=trailing_average_volume,
            moving_average=moving_average,
        )
        return metrics, closes, volumes
