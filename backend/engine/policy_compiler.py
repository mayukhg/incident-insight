from __future__ import annotations

from models import DefaultRule, VarianceRow
from seed_data import ScenarioSpec


def compile_policy(
    spec: ScenarioSpec,
    gateway_rows: list[VarianceRow],
    drill_rows: list[VarianceRow],
    *,
    mixed: bool,
) -> DefaultRule | None:
    if mixed:
        return None
    isolated_gateway = next((row.slice for row in gateway_rows if row.is_anomalous), None)
    if isolated_gateway is None:
        return None
    peers = [row for row in gateway_rows if row.slice != isolated_gateway]
    target = spec.default_rule.target_gateway if spec.default_rule else None
    if target is None and peers:
        target = max(peers, key=lambda row: row.incident_auth_pct or 0).slice
    if target is None:
        return None
    country, card_type, card_brand = _filters_from_drill(drill_rows, isolated_gateway)
    if spec.default_rule and spec.default_rule.source_gateway == isolated_gateway:
        seeded = spec.default_rule
        return DefaultRule(
            proposal_id=seeded.proposal_id,
            source_gateway=seeded.source_gateway,
            target_gateway=seeded.target_gateway,
            filter_country=seeded.filter_country or country,
            filter_card_type=seeded.filter_card_type or card_type,
            filter_card_brand=seeded.filter_card_brand or card_brand,
            target_rule=seeded.target_rule
            or f"Route {country or 'impacted'} {card_type or 'cards'} from {isolated_gateway} → {target}",
        )
    return DefaultRule(
        proposal_id=f"{isolated_gateway}_failover",
        source_gateway=isolated_gateway,
        target_gateway=target,
        filter_country=country,
        filter_card_type=card_type,
        filter_card_brand=card_brand,
        target_rule=f"Route {country or 'impacted'} {card_type or 'cards'} from {isolated_gateway} → {target}",
    )


def _filters_from_drill(rows: list[VarianceRow], gateway: str) -> tuple[str | None, str | None, str | None]:
    hit = next((row for row in rows if row.is_anomalous), None)
    if hit is None:
        return None, None, None
    parts = [part.strip() for part in hit.slice.split("/")]
    country = next((part for part in parts if len(part) == 2 and part.isalpha()), None)
    card_type = next((part for part in parts if part in {"debit", "credit"}), None)
    card_brand = next((part for part in parts if part in {"visa", "mastercard", "amex"}), None)
    if gateway in parts and country is None and len(parts) >= 2:
        country = parts[1] if len(parts[1]) == 2 else country
    return country, card_type, card_brand
