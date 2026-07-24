"""Quality filter scanner: narrows a broad universe down to a small,
ranked list of high-quality candidates. See docs/ARCHITECTURE.md section 3
for why this exists — the goal is cream-of-the-crop, not scanning every
random stock.
"""

import logging
from dataclasses import dataclass

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


class Scanner:
    def __init__(self, provider: MarketDataProvider, config: ScannerConfig | None = None) -> None:
        self.provider = provider
        self.config = config or ScannerConfig()

    def scan(self, universe: list[str]) -> list[RankedCandidate]:
        """Ranked, deduplicated candidates that pass every quality filter,
        highest score first. Symbols with unavailable data are skipped
        (logged), not fabricated, and do not abort the rest of the scan.
        """
        results: list[RankedCandidate] = []

        for symbol in dict.fromkeys(universe):  # dedupe, preserve order
            try:
                metrics = self._build_metrics(symbol)
            except MarketDataError as exc:
                logger.warning("skipping %s: %s", symbol, exc)
                continue

            filter_result = evaluate_filters(metrics, self.config)
            if not filter_result.passed:
                logger.debug("%s failed filters: %s", symbol, filter_result.failed_reasons)
                continue

            results.append(RankedCandidate(symbol=symbol, score=score_candidate(metrics)))

        return sorted(results, key=lambda candidate: candidate.score, reverse=True)

    def _build_metrics(self, symbol: str) -> CandidateMetrics:
        price = self.provider.get_price(symbol)
        volume = self.provider.get_volume(symbol)
        market_cap = self.provider.get_market_cap(symbol)
        history = self.provider.get_history(symbol, period=_HISTORY_PERIOD)

        closes = [point.close for point in history]
        volumes = [point.volume for point in history]

        moving_average = simple_moving_average(closes, min(_SMA_PERIOD, len(closes)))
        trailing_average_volume = average_volume(volumes, min(_VOLUME_AVERAGE_PERIOD, len(volumes)))

        return CandidateMetrics(
            symbol=symbol,
            price=price,
            volume=volume,
            market_cap=market_cap,
            average_volume=trailing_average_volume,
            moving_average=moving_average,
        )
