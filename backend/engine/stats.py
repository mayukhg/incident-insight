from __future__ import annotations

from math import inf

from scipy.stats import chi2_contingency


def auth_rate(authorized: int, volume: int) -> float:
    if volume <= 0:
        return 0.0
    return round(100.0 * authorized / volume, 1)


def delta_pp(incident_auth: float, baseline_auth: float) -> float:
    return round(incident_auth - baseline_auth, 1)


def chi_square_p_value(baseline_auth: int, baseline_n: int, incident_auth: int, incident_n: int) -> float | None:
    baseline_decl = baseline_n - baseline_auth
    incident_decl = incident_n - incident_auth
    if min(baseline_n, incident_n, baseline_auth, incident_auth, baseline_decl, incident_decl) < 0:
        return None
    if baseline_n == 0 or incident_n == 0:
        return None
    table = [
        [max(baseline_auth, 0), max(baseline_decl, 0)],
        [max(incident_auth, 0), max(incident_decl, 0)],
    ]
    if any(sum(row) == 0 for row in table) or any(sum(col) == 0 for col in zip(*table)):
        return None
    try:
        _, p_value, _, _ = chi2_contingency(table, correction=False)
    except ValueError:
        return None
    return float(p_value)


def is_significant(p_value: float | None, alpha: float = 0.05) -> bool:
    if p_value is None:
        return False
    return p_value < alpha


def is_isolated(slice_delta: float, peer_deltas: list[float], p_value: float | None, *, min_gap_pp: float = 8.0) -> bool:
    if not is_significant(p_value):
        return False
    if not peer_deltas:
        return abs(slice_delta) >= 2.0
    median_peer = sorted(peer_deltas)[len(peer_deltas) // 2]
    return (slice_delta - median_peer) <= -min_gap_pp


def safe_p(p_value: float | None) -> float:
    if p_value is None:
        return inf
    return p_value
