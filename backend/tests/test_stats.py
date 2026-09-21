from __future__ import annotations

import unittest

from engine.stats import chi_square_p_value, is_isolated, is_significant


class StatsTests(unittest.TestCase):
    def test_isolated_gateway_is_significant(self) -> None:
        p_value = chi_square_p_value(37200, 42100, 26800, 41850)
        self.assertIsNotNone(p_value)
        assert p_value is not None
        self.assertTrue(is_significant(p_value))
        self.assertTrue(is_isolated(-24.3, [-0.4, -0.2], p_value))

    def test_uniform_shift_is_not_isolated(self) -> None:
        p_value = chi_square_p_value(13500, 15400, 12800, 15320)
        self.assertFalse(is_isolated(-4.2, [-4.0, -4.1], p_value, min_gap_pp=8.0))


if __name__ == "__main__":
    unittest.main()
