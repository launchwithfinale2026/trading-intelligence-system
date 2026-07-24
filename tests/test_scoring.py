from decimal import Decimal

from app.analysis.scoring import CandidateMetrics, ScannerConfig, evaluate_filters, score_candidate

STRONG_CANDIDATE = CandidateMetrics(
    symbol="NVDA",
    price=Decimal(120),
    volume=3_000_000,
    market_cap=Decimal("3000000000000"),
    average_volume=Decimal(1_000_000),  # 3x surge
    moving_average=Decimal(100),  # 20% above trend
)

THIN_VOLUME_CANDIDATE = CandidateMetrics(
    symbol="MICRO",
    price=Decimal(50),
    volume=100_000,
    market_cap=Decimal("500000000"),
    average_volume=Decimal(90_000),
    moving_average=Decimal(45),
)

DOWNTREND_CANDIDATE = CandidateMetrics(
    symbol="LAGGARD",
    price=Decimal(90),
    volume=2_000_000,
    market_cap=Decimal("5000000000"),
    average_volume=Decimal(1_000_000),
    moving_average=Decimal(100),  # price below its average
)

FLAT_VOLUME_CANDIDATE = CandidateMetrics(
    symbol="FLAT",
    price=Decimal(110),
    volume=1_000_000,
    market_cap=Decimal("5000000000"),
    average_volume=Decimal(1_000_000),  # no surge at all
    moving_average=Decimal(100),
)


def test_strong_candidate_passes_all_filters() -> None:
    result = evaluate_filters(STRONG_CANDIDATE)

    assert result.passed is True
    assert result.failed_reasons == []


def test_thin_liquidity_and_small_cap_both_fail() -> None:
    result = evaluate_filters(THIN_VOLUME_CANDIDATE)

    assert result.passed is False
    assert any("liquidity" in reason for reason in result.failed_reasons)
    assert any("quality" in reason for reason in result.failed_reasons)


def test_downtrend_fails_trend_filter() -> None:
    result = evaluate_filters(DOWNTREND_CANDIDATE)

    assert result.passed is False
    assert any("trend" in reason for reason in result.failed_reasons)


def test_flat_volume_fails_momentum_filter() -> None:
    result = evaluate_filters(FLAT_VOLUME_CANDIDATE)

    assert result.passed is False
    assert any("momentum" in reason for reason in result.failed_reasons)


def test_custom_thresholds_are_respected() -> None:
    lenient_config = ScannerConfig(min_volume=50_000, min_market_cap=Decimal("100000000"))

    result = evaluate_filters(THIN_VOLUME_CANDIDATE, lenient_config)

    assert result.passed is False  # still fails momentum (volume/avg ratio ~1.11 < 1.5)
    assert not any("liquidity" in r or "quality" in r for r in result.failed_reasons)


def test_score_is_higher_for_stronger_candidate() -> None:
    strong_score = score_candidate(STRONG_CANDIDATE)
    flat_score = score_candidate(FLAT_VOLUME_CANDIDATE)

    assert 0 <= strong_score <= 100
    assert 0 <= flat_score <= 100
    assert strong_score > flat_score


def test_score_is_capped_at_100() -> None:
    extreme = CandidateMetrics(
        symbol="MOON",
        price=Decimal(1000),
        volume=100_000_000,
        market_cap=Decimal("3000000000000"),
        average_volume=Decimal(1_000_000),
        moving_average=Decimal(10),
    )

    assert score_candidate(extreme) == 100
