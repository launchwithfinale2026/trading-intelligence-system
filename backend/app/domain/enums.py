"""Shared enums used by both database models and API schemas.

Defined once here so the database layer and the API layer can never drift
apart on what a valid value is.
"""

from enum import Enum


class RiskPreference(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class TradingStyle(str, Enum):
    MOMENTUM = "momentum"
    SWING = "swing"
    BREAKOUT = "breakout"
    POSITION = "position"


class AlertPreference(str, Enum):
    ALL_SIGNALS = "all_signals"
    HIGH_CONFIDENCE_ONLY = "high_confidence_only"
    NONE = "none"


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"


class DecisionType(str, Enum):
    OPEN = "open"
    IGNORE = "ignore"
