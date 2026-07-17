import unittest
from decimal import Decimal

from .isc_calculator import (
    aggregate_equation_9,
    calculate_isc,
)
from .models import AuthorWeight


class TestISCCalculator(
    unittest.TestCase
):
    def calculate(
        self,
        *,
        citing_pub_id="Q1",
        field_name="FIELD_1",
        cited_authors,
        citing_weights,
        target_author,
        target_weight="1",
        field_weight="1",
    ):
        return calculate_isc(
            cited_pub_id="P1",
            citing_pub_id=citing_pub_id,
            cited_author_ids=(
                cited_authors
            ),
            citing_author_weights=[
                AuthorWeight(
                    author_id=author_id,
                    weight=Decimal(
                        str(weight)
                    ),
                )
                for author_id, weight
                in citing_weights.items()
            ],
            target_author_id=(
                target_author
            ),
            target_author_overall_weight=(
                Decimal(
                    str(target_weight)
                )
            ),
            field_name=field_name,
            field_weight=Decimal(
                str(field_weight)
            ),
            epsilon_zero=Decimal(
                "0.90"
            ),
            weight_tolerance=Decimal(
                "0.0001"
            ),
        )

    def assert_decimal_close(
        self,
        actual,
        expected,
        places=6,
    ):
        self.assertAlmostEqual(
            float(actual),
            expected,
            places=places,
        )

    def test_equation_7_full_self_influence(
        self,
    ):
        result = self.calculate(
            cited_authors=[
                "PETER",
                "NILMANTHA",
            ],
            citing_weights={
                "PETER": 1.0,
            },
            target_author="PETER",
        )

        self.assert_decimal_close(
            result.isc_value,
            1.0,
        )

    def test_equation_7_no_overlap(
        self,
    ):
        result = self.calculate(
            cited_authors=[
                "PETER",
                "NILMANTHA",
            ],
            citing_weights={
                "X1": 0.50,
                "X2": 0.50,
            },
            target_author="PETER",
        )

        self.assert_decimal_close(
            result.isc_value,
            0.0,
        )

    def test_equation_7_core_overlap(
        self,
    ):
        result = self.calculate(
            cited_authors=[
                "PETER",
                "SHEHAN",
            ],
            citing_weights={
                "SHEHAN": 0.30,
                "X1": 0.20,
                "X2": 0.20,
                "X3": 0.15,
                "X4": 0.15,
            },
            target_author="PETER",
        )

        self.assert_decimal_close(
            result.isc_value,
            0.27,
        )

    def test_equation_8_fractional_raw_citation(
        self,
    ):
        result = self.calculate(
            cited_authors=[
                "PETER",
                "NILMANTHA",
            ],
            citing_weights={
                "X1": 1.0,
            },
            target_author="PETER",
            target_weight="0.40",
            field_weight="0.50",
        )

        # Raw:
        # 0.40 author share × 0.50 field share
        # = 0.20
        self.assert_decimal_close(
            result.raw_citation,
            0.20,
        )

        # ISC is zero, therefore adjusted remains 0.20.
        self.assert_decimal_close(
            result.adjusted_citation,
            0.20,
        )

    def test_equation_8_with_isc_discount(
        self,
    ):
        result = self.calculate(
            cited_authors=[
                "PETER",
            ],
            citing_weights={
                "PETER": 0.25,
                "X1": 0.75,
            },
            target_author="PETER",
            target_weight="0.40",
            field_weight="0.50",
        )

        # ISC = 0.25.
        self.assert_decimal_close(
            result.isc_value,
            0.25,
        )

        # Raw = 0.40 × 0.50 = 0.20.
        self.assert_decimal_close(
            result.raw_citation,
            0.20,
        )

        # Adjusted = (1 - 0.25) × 0.20
        #          = 0.15.
        self.assert_decimal_close(
            result.adjusted_citation,
            0.15,
        )

    def test_equation_9_aggregation(
        self,
    ):
        first = self.calculate(
            citing_pub_id="Q1",
            field_name="FIELD_1",
            cited_authors=[
                "PETER",
            ],
            citing_weights={
                "X1": 1.0,
            },
            target_author="PETER",
            target_weight="0.50",
            field_weight="0.60",
        )

        second = self.calculate(
            citing_pub_id="Q1",
            field_name="FIELD_2",
            cited_authors=[
                "PETER",
            ],
            citing_weights={
                "PETER": 1.0,
            },
            target_author="PETER",
            target_weight="0.50",
            field_weight="0.40",
        )

        third = self.calculate(
            citing_pub_id="Q2",
            field_name="FIELD_1",
            cited_authors=[
                "PETER",
            ],
            citing_weights={
                "X2": 1.0,
            },
            target_author="PETER",
            target_weight="0.50",
            field_weight="0.60",
        )

        total = aggregate_equation_9(
            [
                first,
                second,
                third,
            ]
        )

        # Raw:
        # first  = 0.50 × 0.60 = 0.30
        # second = 0.50 × 0.40 = 0.20
        # third  = 0.50 × 0.60 = 0.30
        #
        # Total raw = 0.80.
        self.assert_decimal_close(
            total.total_raw_citation,
            0.80,
        )

        # First adjusted = 0.30
        # Second has ISC=1, adjusted=0
        # Third adjusted = 0.30
        #
        # Total adjusted = 0.60.
        self.assert_decimal_close(
            total.total_adjusted_citation,
            0.60,
        )

        self.assertEqual(
            total.citing_paper_count,
            2,
        )

        self.assertEqual(
            total.field_row_count,
            3,
        )

    def test_rejects_invalid_author_weights(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.calculate(
                cited_authors=[
                    "PETER",
                ],
                citing_weights={
                    "PETER": 0.40,
                    "X1": 0.40,
                },
                target_author="PETER",
            )


if __name__ == "__main__":
    unittest.main()