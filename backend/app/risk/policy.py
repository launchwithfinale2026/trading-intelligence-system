"""Piecewise-linear risk curves.

Pure, no I/O — same design goal as risk/calculator.py: given the same
breakpoints and account size, resolve_risk_percent always returns the same
answer, so it's exactly reproducible from hand-computed expected values.
The breakpoints themselves (where the data lives, how many policies exist)
are someone else's job — see services/risk_policy_service.py, which reads
them from the database and hands the plain (account_size, risk_percent)
pairs in here.
"""

from decimal import Decimal

Breakpoint = tuple[Decimal, Decimal]  # (account_size, risk_percent)


def resolve_risk_percent(breakpoints: list[Breakpoint], account_size: Decimal) -> Decimal:
    """Flat before the first breakpoint, flat after the last, linearly
    interpolated between adjacent breakpoints in between.

    A single breakpoint means "this risk percent regardless of account
    size" — which is exactly how the flat conservative/moderate/aggressive
    policies are represented, with no special-casing needed here.
    """
    if not breakpoints:
        raise ValueError("a risk policy must have at least one breakpoint")

    points = sorted(breakpoints, key=lambda point: point[0])

    if account_size <= points[0][0]:
        return points[0][1]
    if account_size >= points[-1][0]:
        return points[-1][1]

    for (low_size, low_percent), (high_size, high_percent) in zip(points, points[1:]):
        if low_size <= account_size <= high_size:
            span = high_size - low_size
            if span == 0:
                return low_percent
            fraction = (account_size - low_size) / span
            return low_percent + (high_percent - low_percent) * fraction

    return points[-1][1]  # unreachable: the bounds checks above cover every case
