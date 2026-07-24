from decimal import Decimal

from app.analysis.filtering import QualityFilterConfig, evaluate_quality


def _flat_closes(base: Decimal, length: int) -> list[Decimal]:
    return [base] * length


def _flat_volumes(base: int, length: int) -> list[int]:
    return [base] * length


def test_passes_all_five_criteria() -> None:
    # 50 flat bars at 100, then today bumps to 103 on 2x volume.
    closes = _flat_closes(Decimal("100.0"), 50)
    closes[-1] = Decimal("103.0")
    volumes = _flat_volumes(1_000_000, 50)
    volumes[-1] = 2_000_000

    result = evaluate_quality(price=closes[-1], volume=volumes[-1], closes=closes, volumes=volumes)

    assert result.passed is True
    assert len(result.reasons) == 5
    assert all(reason.startswith("+") for reason in result.reasons)


def test_fails_liquidity_on_low_volume_and_low_price() -> None:
    closes = _flat_closes(Decimal("100.0"), 50)
    closes[-1] = Decimal("103.0")
    volumes = _flat_volumes(1_000_000, 50)
    volumes[-1] = 2_000_000

    result = evaluate_quality(price=Decimal("2.00"), volume=100_000, closes=closes, volumes=volumes)

    assert result.passed is False
    assert any("liquidity" in r and "volume" in r for r in result.reasons)
    assert any("liquidity" in r and "price" in r for r in result.reasons)


def test_fails_trend_on_downtrend_while_everything_else_passes() -> None:
    closes = _flat_closes(Decimal("100.0"), 50)
    closes[-1] = Decimal("97.0")  # down instead of up
    volumes = _flat_volumes(1_000_000, 50)
    volumes[-1] = 2_000_000

    result = evaluate_quality(price=closes[-1], volume=volumes[-1], closes=closes, volumes=volumes)

    assert result.passed is False
    failed = [r for r in result.reasons if r.startswith("-")]
    assert len(failed) == 1
    assert "trend" in failed[0] and "down" in failed[0]


def test_fails_volatility_trend_volume_and_movement_when_completely_flat() -> None:
    closes = _flat_closes(Decimal("100.0"), 51)
    volumes = _flat_volumes(1_000_000, 51)

    result = evaluate_quality(price=Decimal("100.0"), volume=1_000_000, closes=closes, volumes=volumes)

    assert result.passed is False
    reasons_text = " ".join(result.reasons)
    assert not any("liquidity" in r for r in result.reasons if r.startswith("-"))
    assert "volatility" in reasons_text
    assert "not a confirmed uptrend" in reasons_text
    assert "price movement" in reasons_text


def test_fails_volatility_when_too_erratic() -> None:
    closes = [Decimal("100.0")]
    for i in range(50):
        prev = closes[-1]
        closes.append(prev * Decimal("1.15") if i % 2 == 0 else prev * Decimal("0.85"))
    volumes = _flat_volumes(1_000_000, 51)

    result = evaluate_quality(price=closes[-1], volume=volumes[-1], closes=closes, volumes=volumes)

    assert result.passed is False
    assert any("volatility" in r and "15.00%" in r for r in result.reasons)


def test_custom_config_thresholds_are_respected() -> None:
    closes = _flat_closes(Decimal("100.0"), 50)
    closes[-1] = Decimal("100.3")  # a very small bump
    volumes = _flat_volumes(1_000_000, 50)
    volumes[-1] = 1_100_000  # a very small surge

    lenient_config = QualityFilterConfig(
        min_volatility_pct=Decimal("0.01"),
        min_volume_surge_ratio=Decimal("1.0"),
        min_price_movement_pct=Decimal("0.01"),
    )

    result = evaluate_quality(
        price=closes[-1], volume=volumes[-1], closes=closes, volumes=volumes, config=lenient_config
    )

    assert result.passed is True
