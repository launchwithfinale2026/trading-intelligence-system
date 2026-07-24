from datetime import date, timedelta
from decimal import Decimal

from app.analysis.scoring import ScannerConfig
from app.core.exceptions import MarketDataError
from app.market.provider import MarketDataProvider, MarketStatus, PricePoint
from app.market.scanner import Scanner


def _history(closes: list[float], volumes: list[int]) -> list[PricePoint]:
    return [
        PricePoint(
            date=date(2026, 1, 1) + timedelta(days=i),
            open=Decimal(str(c)),
            high=Decimal(str(c)),
            low=Decimal(str(c)),
            close=Decimal(str(c)),
            volume=v,
        )
        for i, (c, v) in enumerate(zip(closes, volumes, strict=True))
    ]


class FakeProvider(MarketDataProvider):
    """A fully in-memory MarketDataProvider double for deterministic tests."""

    def __init__(self) -> None:
        self._history_by_symbol: dict[str, list[PricePoint]] = {}
        self._price_by_symbol: dict[str, Decimal] = {}
        self._volume_by_symbol: dict[str, int] = {}
        self._market_cap_by_symbol: dict[str, Decimal] = {}

    def register(self, symbol: str, *, price: Decimal, volume: int, market_cap: Decimal, closes: list[float], volumes: list[int]) -> None:
        self._price_by_symbol[symbol] = price
        self._volume_by_symbol[symbol] = volume
        self._market_cap_by_symbol[symbol] = market_cap
        self._history_by_symbol[symbol] = _history(closes, volumes)

    def get_price(self, symbol: str) -> Decimal:
        if symbol not in self._price_by_symbol:
            raise MarketDataError(f"unknown symbol {symbol!r}")
        return self._price_by_symbol[symbol]

    def get_volume(self, symbol: str) -> int:
        return self._volume_by_symbol[symbol]

    def get_market_cap(self, symbol: str) -> Decimal:
        return self._market_cap_by_symbol[symbol]

    def get_history(self, symbol: str, *, period: str = "3mo", interval: str = "1d") -> list[PricePoint]:
        return self._history_by_symbol[symbol]

    def get_market_status(self) -> MarketStatus:
        raise NotImplementedError("not needed for scanner tests")


def _flat_series(value: float, length: int) -> list[float]:
    return [value] * length


def test_scan_ranks_passing_candidates_highest_score_first() -> None:
    provider = FakeProvider()
    # NVDA: strong uptrend + big volume surge -> should pass and score high
    provider.register(
        "NVDA",
        price=Decimal(120),
        volume=3_000_000,
        market_cap=Decimal("3000000000000"),
        closes=_flat_series(100.0, 49) + [120.0],
        volumes=_flat_series(1_000_000, 49) + [3_000_000],
    )
    # AMD: milder uptrend + smaller surge -> should pass, score lower than NVDA
    provider.register(
        "AMD",
        price=Decimal(105),
        volume=2_000_000,
        market_cap=Decimal("200000000000"),
        closes=_flat_series(100.0, 49) + [105.0],
        volumes=_flat_series(1_000_000, 49) + [2_000_000],
    )
    # PENNY: fails liquidity and quality filters entirely
    provider.register(
        "PENNY",
        price=Decimal(2),
        volume=10_000,
        market_cap=Decimal("10000000"),
        closes=_flat_series(1.5, 49) + [2.0],
        volumes=_flat_series(9_000, 49) + [10_000],
    )

    scanner = Scanner(provider)
    results = scanner.scan(["NVDA", "AMD", "PENNY"])

    symbols = [r.symbol for r in results]
    assert symbols == ["NVDA", "AMD"]  # PENNY excluded, NVDA ranked above AMD
    assert results[0].score >= results[1].score


def test_scan_skips_symbols_with_unavailable_data() -> None:
    provider = FakeProvider()
    provider.register(
        "NVDA",
        price=Decimal(120),
        volume=3_000_000,
        market_cap=Decimal("3000000000000"),
        closes=_flat_series(100.0, 49) + [120.0],
        volumes=_flat_series(1_000_000, 49) + [3_000_000],
    )

    scanner = Scanner(provider)
    results = scanner.scan(["NVDA", "GHOST"])  # GHOST was never registered

    assert [r.symbol for r in results] == ["NVDA"]


def test_scan_deduplicates_universe() -> None:
    provider = FakeProvider()
    provider.register(
        "NVDA",
        price=Decimal(120),
        volume=3_000_000,
        market_cap=Decimal("3000000000000"),
        closes=_flat_series(100.0, 49) + [120.0],
        volumes=_flat_series(1_000_000, 49) + [3_000_000],
    )

    scanner = Scanner(provider)
    results = scanner.scan(["NVDA", "NVDA", "NVDA"])

    assert len(results) == 1


def test_scan_respects_custom_config() -> None:
    provider = FakeProvider()
    provider.register(
        "AMD",
        price=Decimal(105),
        volume=2_000_000,
        market_cap=Decimal("200000000000"),
        closes=_flat_series(100.0, 49) + [105.0],
        volumes=_flat_series(1_000_000, 49) + [2_000_000],
    )

    strict_config = ScannerConfig(min_volume_surge_ratio=Decimal("10"))  # AMD's 2x surge won't clear this
    scanner = Scanner(provider, config=strict_config)

    assert scanner.scan(["AMD"]) == []
