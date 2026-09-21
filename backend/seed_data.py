from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

# ~4.3M ledger rows across the three ground-truth scenarios.
VOLUME_SCALE = 8

SCHEMA_SQL = [
    """
    CREATE TABLE IF NOT EXISTS transactions (
        txn_id VARCHAR PRIMARY KEY,
        timestamp TIMESTAMP NOT NULL,
        merchant_id VARCHAR NOT NULL,
        gateway_id VARCHAR NOT NULL,
        card_brand VARCHAR NOT NULL,
        card_type VARCHAR NOT NULL,
        bin_country VARCHAR(2) NOT NULL,
        amount DECIMAL(10, 2) NOT NULL,
        currency VARCHAR(3) NOT NULL,
        status VARCHAR NOT NULL,
        decline_code VARCHAR,
        raw_gateway_response VARCHAR,
        latency_ms INTEGER,
        three_ds_version VARCHAR
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS system_deployments (
        deploy_id VARCHAR PRIMARY KEY,
        service_name VARCHAR NOT NULL,
        git_sha VARCHAR NOT NULL,
        deployed_at TIMESTAMP NOT NULL,
        config_changes JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS gateway_incidents (
        incident_id VARCHAR PRIMARY KEY,
        gateway_id VARCHAR NOT NULL,
        start_time TIMESTAMP NOT NULL,
        end_time TIMESTAMP,
        reported_severity VARCHAR NOT NULL,
        description VARCHAR
    )
    """,
]


@dataclass(frozen=True)
class ProbeSpec:
    probe_id: str
    title: str
    description: str
    sql: str


@dataclass(frozen=True)
class DefaultRule:
    proposal_id: str
    source_gateway: str
    target_gateway: str
    filter_country: str | None = None
    filter_card_type: str | None = None
    filter_card_brand: str | None = None
    target_rule: str = ""


@dataclass(frozen=True)
class ScenarioSpec:
    id: str
    name: str
    short_name: str
    status: str
    baseline_start: str
    baseline_end: str
    anomaly_start: str
    anomaly_end: str
    telemetry_start: str
    expected_confidence: float
    abandonment_pct: float
    isolation_gateway: str | None
    isolation_title: str
    culprit_trigger: str
    default_rule: DefaultRule | None
    counter_evidence: list[str] = field(default_factory=list)
    probes: list[ProbeSpec] = field(default_factory=list)


SCENARIOS: dict[str, ScenarioSpec] = {
    "scenario_a": ScenarioSpec(
        id="scenario_a",
        name="Auth rate dropped -5.2% on Tuesday (Adyen UK 3DS Timeout)",
        short_name="Scenario A · Adyen UK 3DS timeout",
        status="DEFINITIVE_RCA",
        baseline_start="2026-09-15 12:00:00",
        baseline_end="2026-09-15 14:00:00",
        anomaly_start="2026-09-15 14:00:00",
        anomaly_end="2026-09-15 16:00:00",
        telemetry_start="2026-09-15 13:40:00",
        expected_confidence=0.96,
        abandonment_pct=14.2,
        isolation_gateway="adyen",
        isolation_title="Adyen UK 3DS Method URL Parse Timeout",
        culprit_trigger="Deploy #4481 introduced a regression in handling 3DS challenge redirects at 14:02 UTC",
        default_rule=DefaultRule(
            proposal_id="gb_debit_adyen_to_checkout",
            source_gateway="adyen",
            target_gateway="checkout",
            filter_country="GB",
            filter_card_type="debit",
            target_rule="Route GB Debit Cards from Adyen → Checkout.com",
        ),
    ),
    "scenario_b": ScenarioSpec(
        id="scenario_b",
        name="Card Brand Visa Latency Spike & Soft Decline Ramp (-3.8%)",
        short_name="Scenario B · Visa latency & soft declines",
        status="DEFINITIVE_RCA",
        baseline_start="2026-09-16 08:00:00",
        baseline_end="2026-09-16 10:00:00",
        anomaly_start="2026-09-16 10:00:00",
        anomaly_end="2026-09-16 12:00:00",
        telemetry_start="2026-09-16 09:40:00",
        expected_confidence=0.93,
        abandonment_pct=9.0,
        isolation_gateway="checkout",
        isolation_title="Checkout.com Visa processing latency",
        culprit_trigger="Checkout.com Visa authorization latency crossed 1.8s as soft declines ramped at 10:03 UTC",
        default_rule=DefaultRule(
            proposal_id="visa_credit_checkout_to_stripe",
            source_gateway="checkout",
            target_gateway="stripe",
            filter_card_brand="visa",
            filter_card_type="credit",
            target_rule="Route Visa Credit from Checkout.com → Stripe",
        ),
    ),
    "scenario_c": ScenarioSpec(
        id="scenario_c",
        name="Mixed / Inconclusive Evidence: Broad NSF Spikes Post-Holiday (-4.1%)",
        short_name="Scenario C · Broad NSF spike",
        status="MIXED_EVIDENCE",
        baseline_start="2026-09-17 09:00:00",
        baseline_end="2026-09-17 11:00:00",
        anomaly_start="2026-09-17 11:00:00",
        anomaly_end="2026-09-17 13:00:00",
        telemetry_start="2026-09-17 10:40:00",
        expected_confidence=0.41,
        abandonment_pct=6.0,
        isolation_gateway=None,
        isolation_title="No isolated causal factor",
        culprit_trigger="Observed decline increase is distributed across gateways, issuers, and card cohorts with no overlapping deploy or provider event",
        default_rule=None,
        counter_evidence=[
            "Decline variance is uniform across Adyen, Stripe, and Checkout.com.",
            "No gateway slice passes the isolation gate versus peer PSPs.",
            "No deployment, configuration change, or provider incident overlaps the window.",
        ],
        probes=[
            ProbeSpec(
                probe_id="expand_28d_baseline",
                title="Expand to 28-day baseline",
                description="Control for post-holiday issuer behavior.",
                sql=(
                    "SELECT bin_country, date_trunc('day', timestamp) AS day, "
                    "COUNT(*) FILTER (WHERE status='authorized') * 1.0 / COUNT(*) AS auth_rate "
                    "FROM transactions WHERE timestamp BETWEEN TIMESTAMP '2026-08-20 00:00:00' "
                    "AND TIMESTAMP '2026-09-17 13:00:00' GROUP BY 1, 2 ORDER BY 2, 1;"
                ),
            ),
            ProbeSpec(
                probe_id="segment_issuer_bin",
                title="Segment by issuer BIN",
                description="Search for low-volume issuer clusters.",
                sql=(
                    "SELECT bin_country, card_brand, decline_code, COUNT(*) AS volume, "
                    "COUNT(*) FILTER (WHERE status='authorized') * 1.0 / COUNT(*) AS auth_rate "
                    "FROM transactions WHERE timestamp BETWEEN TIMESTAMP '2026-09-17 09:00:00' "
                    "AND TIMESTAMP '2026-09-17 13:00:00' GROUP BY 1, 2, 3 HAVING COUNT(*) > 100 "
                    "ORDER BY volume DESC;"
                ),
            ),
            ProbeSpec(
                probe_id="compare_merchant_mix",
                title="Compare merchant mix",
                description="Test whether portfolio composition shifted.",
                sql=(
                    "SELECT merchant_id, COUNT(*) AS volume, "
                    "COUNT(*) FILTER (WHERE status='authorized') * 1.0 / COUNT(*) AS auth_rate "
                    "FROM transactions WHERE timestamp BETWEEN TIMESTAMP '2026-09-17 09:00:00' "
                    "AND TIMESTAMP '2026-09-17 13:00:00' GROUP BY merchant_id ORDER BY volume DESC;"
                ),
            ),
        ],
    ),
}


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def iso_z(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%dT%H:%M:%SZ")


def _insert_cohort(
    con: Any,
    *,
    prefix: str,
    start: datetime,
    minutes: int,
    n: int,
    auth_rate: float,
    gateway: str,
    brand: str,
    card_type: str,
    country: str,
    amount: float,
    decline_code: str,
    ok_latency: int,
    fail_latency: int,
    three_ds: str,
    merchant: str,
) -> None:
    if n <= 0:
        return
    n_auth = int(round(n * auth_rate))
    n_auth = min(max(n_auth, 0), n)
    span_sec = max(minutes * 60, 1)
    fail_response = decline_code.replace("_", " ").upper()
    con.execute(
        f"""
        INSERT INTO transactions
        SELECT
          '{prefix}-' || i::VARCHAR AS txn_id,
          TIMESTAMP '{start.strftime("%Y-%m-%d %H:%M:%S")}'
            + (((i * {span_sec}) // {n})) * INTERVAL 1 SECOND AS timestamp,
          '{merchant}' AS merchant_id,
          '{gateway}' AS gateway_id,
          '{brand}' AS card_brand,
          '{card_type}' AS card_type,
          '{country}' AS bin_country,
          {amount}::DECIMAL(10,2) AS amount,
          'USD' AS currency,
          CASE WHEN i < {n_auth} THEN 'authorized' ELSE 'declined' END AS status,
          CASE WHEN i < {n_auth} THEN NULL ELSE '{decline_code}' END AS decline_code,
          CASE WHEN i < {n_auth} THEN 'APPROVED'
               ELSE '{fail_response}' END AS raw_gateway_response,
          CASE WHEN i < {n_auth} THEN {ok_latency} ELSE {fail_latency} END AS latency_ms,
          '{three_ds}' AS three_ds_version
        FROM range({n}) t(i)
        """
    )


def _bucket_starts(start: datetime, end: datetime, minutes: int = 5) -> list[datetime]:
    out: list[datetime] = []
    cursor = start
    delta = timedelta(minutes=minutes)
    while cursor < end:
        out.append(cursor)
        cursor += delta
    return out


def _seed_window(
    con: Any,
    *,
    scenario: str,
    window: str,
    start: datetime,
    end: datetime,
    slices: list[dict[str, Any]],
    degraded_from: datetime | None = None,
) -> None:
    buckets = _bucket_starts(start, end)
    n_buckets = max(len(buckets), 1)
    for spec in slices:
        total = int(spec["n"]) * VOLUME_SCALE
        per = total // n_buckets
        remainder = total % n_buckets
        for index, bucket in enumerate(buckets):
            n = per + (1 if index < remainder else 0)
            rate = spec["auth"]
            latency_fail = spec["fail_latency"]
            decline = spec["decline"]
            if degraded_from is not None and bucket < degraded_from:
                rate = spec["baseline_auth"]
                latency_fail = spec["ok_latency"] + 40
                if spec.get("healthy_decline"):
                    decline = spec["healthy_decline"]
            _insert_cohort(
                con,
                prefix=f"{scenario}-{window}-{spec['key']}-b{index}",
                start=bucket,
                minutes=5,
                n=n,
                auth_rate=rate,
                gateway=spec["gateway"],
                brand=spec["brand"],
                card_type=spec["card_type"],
                country=spec["country"],
                amount=spec["amount"],
                decline_code=decline,
                ok_latency=spec["ok_latency"],
                fail_latency=latency_fail,
                three_ds=spec["three_ds"],
                merchant=spec["merchant"],
            )


def seed_if_empty(con: Any) -> None:
    count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    if count and count > 0:
        return
    seed_all(con)


def seed_all(con: Any) -> None:
    con.execute("DELETE FROM transactions")
    con.execute("DELETE FROM system_deployments")
    con.execute("DELETE FROM gateway_incidents")

    a_base = parse_ts(SCENARIOS["scenario_a"].baseline_start)
    a_anom = parse_ts(SCENARIOS["scenario_a"].anomaly_start)
    a_end = parse_ts(SCENARIOS["scenario_a"].anomaly_end)
    a_slices = [
        {
            "key": "adyen-gb-debit",
            "n": 18200,
            "auth": 0.892,
            "gateway": "adyen",
            "brand": "visa",
            "card_type": "debit",
            "country": "GB",
            "amount": 14.50,
            "decline": "insufficient_funds",
            "ok_latency": 280,
            "fail_latency": 420,
            "three_ds": "2.2",
            "merchant": "merchant_uk_1",
            "baseline_auth": 0.892,
        },
        {
            "key": "adyen-gb-credit",
            "n": 9800,
            "auth": 0.878,
            "gateway": "adyen",
            "brand": "visa",
            "card_type": "credit",
            "country": "GB",
            "amount": 28.00,
            "decline": "do_not_honor",
            "ok_latency": 290,
            "fail_latency": 410,
            "three_ds": "2.2",
            "merchant": "merchant_uk_1",
            "baseline_auth": 0.878,
        },
        {
            "key": "adyen-de-debit",
            "n": 8600,
            "auth": 0.885,
            "gateway": "adyen",
            "brand": "mastercard",
            "card_type": "debit",
            "country": "DE",
            "amount": 16.20,
            "decline": "insufficient_funds",
            "ok_latency": 275,
            "fail_latency": 390,
            "three_ds": "2.2",
            "merchant": "merchant_eu_2",
            "baseline_auth": 0.885,
        },
        {
            "key": "adyen-us-credit",
            "n": 5500,
            "auth": 0.902,
            "gateway": "adyen",
            "brand": "amex",
            "card_type": "credit",
            "country": "US",
            "amount": 41.00,
            "decline": "do_not_honor",
            "ok_latency": 260,
            "fail_latency": 380,
            "three_ds": "exempt",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.902,
        },
        {
            "key": "stripe-mix",
            "n": 52000,
            "auth": 0.885,
            "gateway": "stripe",
            "brand": "visa",
            "card_type": "credit",
            "country": "US",
            "amount": 22.40,
            "decline": "insufficient_funds",
            "ok_latency": 240,
            "fail_latency": 360,
            "three_ds": "2.1",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.885,
        },
        {
            "key": "checkout-mix",
            "n": 29900,
            "auth": 0.882,
            "gateway": "checkout",
            "brand": "mastercard",
            "card_type": "credit",
            "country": "GB",
            "amount": 19.80,
            "decline": "do_not_honor",
            "ok_latency": 255,
            "fail_latency": 370,
            "three_ds": "2.2",
            "merchant": "merchant_uk_1",
            "baseline_auth": 0.882,
        },
    ]
    _seed_window(con, scenario="a", window="base", start=a_base, end=a_anom, slices=a_slices)
    a_anom_slices = [
        {**a_slices[0], "n": 18100, "auth": 0.614, "decline": "3ds_timeout", "fail_latency": 1860, "healthy_decline": "insufficient_funds"},
        {**a_slices[1], "n": 9700, "auth": 0.784, "decline": "3ds_timeout", "fail_latency": 1420, "healthy_decline": "do_not_honor"},
        {**a_slices[2], "n": 8550, "auth": 0.880, "fail_latency": 400},
        {**a_slices[3], "n": 5500, "auth": 0.900, "fail_latency": 390},
        {**a_slices[4], "n": 52100, "auth": 0.881, "fail_latency": 365},
        {**a_slices[5], "n": 29850, "auth": 0.880, "fail_latency": 375},
    ]
    _seed_window(
        con,
        scenario="a",
        window="anom",
        start=a_anom,
        end=a_end,
        slices=a_anom_slices,
        degraded_from=parse_ts("2026-09-15 14:05:00"),
    )

    con.execute(
        """
        INSERT INTO system_deployments VALUES (
          'deploy-4481',
          'routing-engine',
          'e9a2f1b',
          TIMESTAMP '2026-09-15 14:02:00',
          '{"challenge_timeout_ms": 1500, "previous_timeout_ms": 10000, "scope": "GB debit 3DS"}'::JSON
        )
        """
    )

    b_base = parse_ts(SCENARIOS["scenario_b"].baseline_start)
    b_anom = parse_ts(SCENARIOS["scenario_b"].anomaly_start)
    b_end = parse_ts(SCENARIOS["scenario_b"].anomaly_end)
    b_slices = [
        {
            "key": "checkout-visa-credit",
            "n": 18400,
            "auth": 0.887,
            "gateway": "checkout",
            "brand": "visa",
            "card_type": "credit",
            "country": "US",
            "amount": 31.20,
            "decline": "do_not_honor",
            "ok_latency": 310,
            "fail_latency": 480,
            "three_ds": "2.2",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.887,
        },
        {
            "key": "checkout-mc",
            "n": 11200,
            "auth": 0.892,
            "gateway": "checkout",
            "brand": "mastercard",
            "card_type": "credit",
            "country": "US",
            "amount": 27.10,
            "decline": "insufficient_funds",
            "ok_latency": 300,
            "fail_latency": 430,
            "three_ds": "2.1",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.892,
        },
        {
            "key": "stripe-visa",
            "n": 42000,
            "auth": 0.893,
            "gateway": "stripe",
            "brand": "visa",
            "card_type": "credit",
            "country": "US",
            "amount": 24.00,
            "decline": "do_not_honor",
            "ok_latency": 250,
            "fail_latency": 370,
            "three_ds": "2.2",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.893,
        },
        {
            "key": "adyen-mix",
            "n": 36000,
            "auth": 0.890,
            "gateway": "adyen",
            "brand": "visa",
            "card_type": "debit",
            "country": "GB",
            "amount": 18.40,
            "decline": "insufficient_funds",
            "ok_latency": 270,
            "fail_latency": 400,
            "three_ds": "2.2",
            "merchant": "merchant_uk_1",
            "baseline_auth": 0.890,
        },
    ]
    _seed_window(con, scenario="b", window="base", start=b_base, end=b_anom, slices=b_slices)
    b_anom_slices = [
        {**b_slices[0], "n": 18350, "auth": 0.662, "decline": "do_not_honor", "fail_latency": 1920, "healthy_decline": "do_not_honor"},
        {**b_slices[1], "n": 11180, "auth": 0.880, "fail_latency": 460},
        {**b_slices[2], "n": 42100, "auth": 0.891, "fail_latency": 380},
        {**b_slices[3], "n": 35950, "auth": 0.888, "fail_latency": 405},
    ]
    _seed_window(
        con,
        scenario="b",
        window="anom",
        start=b_anom,
        end=b_end,
        slices=b_anom_slices,
        degraded_from=parse_ts("2026-09-16 10:05:00"),
    )
    con.execute(
        """
        INSERT INTO gateway_incidents VALUES (
          'inc-visa-checkout-0916',
          'checkout',
          TIMESTAMP '2026-09-16 10:03:00',
          TIMESTAMP '2026-09-16 12:40:00',
          'degraded_performance',
          'Visa authorization latency and soft declines on Checkout.com'
        )
        """
    )
    con.execute(
        """
        INSERT INTO system_deployments VALUES (
          'deploy-4470',
          'checkout-api',
          '91c0aa2',
          TIMESTAMP '2026-09-16 06:10:00',
          '{"note": "unrelated cache warmup"}'::JSON
        )
        """
    )

    c_base = parse_ts(SCENARIOS["scenario_c"].baseline_start)
    c_anom = parse_ts(SCENARIOS["scenario_c"].anomaly_start)
    c_end = parse_ts(SCENARIOS["scenario_c"].anomaly_end)
    c_slices = [
        {
            "key": "adyen",
            "n": 15400,
            "auth": 0.879,
            "gateway": "adyen",
            "brand": "visa",
            "card_type": "debit",
            "country": "US",
            "amount": 21.00,
            "decline": "insufficient_funds",
            "ok_latency": 300,
            "fail_latency": 360,
            "three_ds": "2.2",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.879,
        },
        {
            "key": "stripe",
            "n": 14600,
            "auth": 0.881,
            "gateway": "stripe",
            "brand": "mastercard",
            "card_type": "credit",
            "country": "US",
            "amount": 23.50,
            "decline": "insufficient_funds",
            "ok_latency": 295,
            "fail_latency": 350,
            "three_ds": "2.1",
            "merchant": "merchant_us_3",
            "baseline_auth": 0.881,
        },
        {
            "key": "checkout",
            "n": 9120,
            "auth": 0.876,
            "gateway": "checkout",
            "brand": "visa",
            "card_type": "credit",
            "country": "GB",
            "amount": 20.10,
            "decline": "insufficient_funds",
            "ok_latency": 305,
            "fail_latency": 355,
            "three_ds": "2.2",
            "merchant": "merchant_uk_1",
            "baseline_auth": 0.876,
        },
    ]
    _seed_window(con, scenario="c", window="base", start=c_base, end=c_anom, slices=c_slices)
    c_anom_slices = [
        {**c_slices[0], "n": 15320, "auth": 0.837},
        {**c_slices[1], "n": 14540, "auth": 0.841},
        {**c_slices[2], "n": 9080, "auth": 0.835},
    ]
    _seed_window(con, scenario="c", window="anom", start=c_anom, end=c_end, slices=c_anom_slices)
    con.execute(
        """
        INSERT INTO system_deployments VALUES (
          'deploy-4412',
          'routing-engine',
          'b12ee90',
          TIMESTAMP '2026-09-16 18:00:00',
          '{"note": "outside mixed-evidence window"}'::JSON
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_txn_timestamp ON transactions(timestamp)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_txn_gateway_ts ON transactions(gateway_id, timestamp)")
    con.execute("CHECKPOINT")
