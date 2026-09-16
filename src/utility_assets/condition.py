"""Condition bands used on the map file and in reports (PDF 3.4.6)."""

from enum import StrEnum


class ConditionBand(StrEnum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"
    CRITICAL = "CRITICAL"


def condition_band(score: int) -> ConditionBand:
    if 8 <= score <= 10:
        return ConditionBand.GOOD
    if 5 <= score <= 7:
        return ConditionBand.FAIR
    if 3 <= score <= 4:
        return ConditionBand.POOR
    if 0 <= score <= 2:
        return ConditionBand.CRITICAL
    raise ValueError("condition_score must be a whole number between 0 and 10")
