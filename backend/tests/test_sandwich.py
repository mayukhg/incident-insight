from __future__ import annotations

import unittest

from pydantic import ValidationError

from engine.dag import DagValidationError, HypothesisNode, parse_dag_payload, template_dag
from engine.judge import can_simulate, confidence_score, node_verdict
from engine.query_gate import QueryGateError, reject_if_unsafe
from engine.sql_compiler import compile_node
from engine.stats import sample_size_penalty
from models import VarianceRow


class SandwichGuardrailTests(unittest.TestCase):
    def test_template_dag_validates(self) -> None:
        dag = template_dag("scenario_a")
        self.assertEqual(len(dag.nodes), 3)

    def test_invalid_sql_shaped_payload_is_dropped(self) -> None:
        with self.assertRaises(Exception):
            parse_dag_payload(
                {
                    "nodes": [
                        {
                            "id": "n1",
                            "hypothesis_type": "global_shift",
                            "dimension": "global",
                            "test": "chi_square",
                            "filter_column": "gateway_id",
                            "filter_value": "'; DROP TABLE transactions;--",
                        }
                    ]
                }
            )

    def test_unknown_dimension_is_dropped(self) -> None:
        with self.assertRaises((DagValidationError, ValidationError)):
            parse_dag_payload(
                {
                    "nodes": [
                        {
                            "id": "n1",
                            "hypothesis_type": "dimensional_slice",
                            "dimension": "merchant_email",
                            "test": "chi_square",
                        }
                    ]
                }
            )

    def test_compiler_binds_filters_as_parameters(self) -> None:
        node = HypothesisNode(
            id="n2",
            hypothesis_type="gateway_isolation",
            dimension="gateway_id",
            test="chi_square",
            filter_column="gateway_id",
            filter_value="adyen",
        )
        compiled = compile_node(node)
        self.assertNotIn("adyen", compiled.sql)
        self.assertEqual(compiled.params("2026-09-15 12:00:00", "2026-09-15 14:00:00")[0], "adyen")

    def test_query_gate_rejects_non_select(self) -> None:
        with self.assertRaises(QueryGateError):
            reject_if_unsafe("DELETE FROM transactions")

    def test_small_n_caps_confidence_not_mixed(self) -> None:
        self.assertGreater(sample_size_penalty(12), 0)
        self.assertTrue(can_simulate(0.85, mixed=False))
        self.assertFalse(can_simulate(0.41, mixed=True))
        self.assertEqual(confidence_score(mixed=True, isolated_volume=12, correlated=False), 0.41)

    def test_two_isolated_slices_are_mixed(self) -> None:
        rows = [
            VarianceRow(slice="adyen", delta_pct=-20, p_value=0.001, is_anomalous=True),
            VarianceRow(slice="stripe", delta_pct=-19, p_value=0.001, is_anomalous=True),
        ]
        self.assertEqual(node_verdict(rows), "MIXED")


if __name__ == "__main__":
    unittest.main()
