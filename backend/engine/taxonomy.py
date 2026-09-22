from __future__ import annotations

HYPOTHESIS_TYPES = frozenset(
    {"global_shift", "gateway_isolation", "dimensional_slice"}
)

TESTS = frozenset({"chi_square"})

DIMENSIONS = frozenset(
    {
        "global",
        "gateway_id",
        "bin_country",
        "card_type",
        "card_brand",
        "three_ds_version",
        "decline_code",
        "gateway_country_card",
        "gateway_country_card_3ds",
        "brand_type",
        "gateway_decline",
    }
)

FILTER_COLUMNS = frozenset(
    {"gateway_id", "bin_country", "card_type", "card_brand", "three_ds_version", "decline_code"}
)

CATALOG = {
    "gateway_id": frozenset({"adyen", "stripe", "checkout"}),
    "bin_country": frozenset({"GB", "US", "DE", "FR", "NL", "IE", "ES", "IT"}),
    "card_type": frozenset({"debit", "credit"}),
    "card_brand": frozenset({"visa", "mastercard", "amex"}),
    "three_ds_version": frozenset({"2.1.0", "2.2.0", "none"}),
    "decline_code": frozenset(
        {
            "authorized",
            "timeout",
            "issuer_unavailable",
            "do_not_honor",
            "insufficient_funds",
            "soft_decline",
        }
    ),
}

MAX_DAG_NODES = 5
MAX_REPLANS = 2
CONFIDENCE_GATE = 0.80
JEV_MODEL = "typesafe/jev-latest"

REPLAN_DIMENSIONS = ("card_brand", "bin_country", "card_type", "three_ds_version", "decline_code")

DIMENSION_EXPR = {
    "global": "'Global Traffic'",
    "gateway_id": "gateway_id",
    "bin_country": "bin_country",
    "card_type": "card_type",
    "card_brand": "card_brand",
    "three_ds_version": "COALESCE(three_ds_version, 'none')",
    "decline_code": "COALESCE(decline_code, 'authorized')",
    "gateway_country_card": "gateway_id || ' / ' || bin_country || ' / ' || card_type",
    "gateway_country_card_3ds": (
        "gateway_id || ' / ' || bin_country || ' / ' || card_type || ' / ' || COALESCE(three_ds_version, 'none')"
    ),
    "brand_type": "card_brand || ' / ' || card_type",
    "gateway_decline": "gateway_id || ' / ' || COALESCE(decline_code, 'authorized')",
}

DRILL_DIMENSION = {
    "scenario_a": "gateway_country_card_3ds",
    "scenario_b": "brand_type",
    "scenario_c": "gateway_decline",
}
