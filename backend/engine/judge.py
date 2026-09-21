from __future__ import annotations

from engine.stats import is_isolated, is_significant, sample_size_penalty
from engine.taxonomy import CONFIDENCE_GATE
from models import VarianceRow

CONFIRMED = "CONFIRMED"
REFUTED = "REFUTED"
MIXED = "MIXED"
FAILED = "FAILED"


def node_verdict(rows: list[VarianceRow], *, query_failed: bool = False) -> str:
    if query_failed or not rows:
        return MIXED if not query_failed else FAILED
    isolated = [row for row in rows if row.is_anomalous]
    if len(isolated) == 1:
        return CONFIRMED
    if len(isolated) > 1:
        return MIXED
    if rows and all(not is_significant(row.p_value) for row in rows):
        return REFUTED
    return MIXED


def case_status(*, isolated: bool, correlated: bool, query_failed: bool, conflicting: bool) -> str:
    if query_failed or conflicting or not isolated:
        return "MIXED_EVIDENCE"
    if isolated and correlated:
        return "DEFINITIVE_RCA"
    if isolated:
        return "DEFINITIVE_RCA"
    return "MIXED_EVIDENCE"


def confidence_score(
    *,
    mixed: bool,
    isolated_volume: int,
    correlated: bool,
    expected: float | None = None,
) -> float:
    if mixed:
        return 0.41
    penalty = sample_size_penalty(isolated_volume)
    if expected is not None:
        return max(0.0, round(min(expected, expected - penalty), 2))
    base = 0.93 if correlated else 0.85
    return max(0.0, round(base - penalty, 2))


def can_simulate(confidence: float, mixed: bool) -> bool:
    return (not mixed) and confidence >= CONFIDENCE_GATE


def isolated_row(rows: list[VarianceRow]) -> VarianceRow | None:
    hits = [row for row in rows if row.is_anomalous]
    if len(hits) == 1:
        return hits[0]
    return None
