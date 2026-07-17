from decimal import Decimal
from typing import Iterable

from .models import (
    AuthorWeight,
    ISCResult,
    PaperAdjustedCitationResult,
)


ZERO = Decimal("0")
ONE = Decimal("1")


def _as_decimal(
    value: Decimal | float | int | str,
) -> Decimal:
    """
    Convert a supported numeric value to Decimal.
    """

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


class InfluentialSelfCitationCalculator:
    """
    Calculate Equation 7 and Equation 8.
    """

    def calculate(
        self,
        *,
        cited_pub_id: str,
        citing_pub_id: str,
        cited_author_ids: Iterable[str],
        citing_author_weights: Iterable[AuthorWeight],
        target_author_id: str,
        target_author_overall_weight: (
            Decimal | float | int | str
        ),
        field_name: str,
        field_weight: Decimal | float | int | str,
        epsilon_zero: Decimal | float | int | str = Decimal("0.90"),
        weight_tolerance: Decimal | float | int | str = Decimal("0.02"),
    ) -> ISCResult:
        """
        Calculate:

        Equation 7:
            ISC(a, p, q, f)

        Equation 8:
            TC_adjusted =
                (1 - ISC) * TC_raw

        In this implementation:

            TC_raw(p, i, q, f)
                =
            target_author_overall_weight
                *
            cited_paper_field_weight

        This gives W_p^(f,i), the target author's
        fractional contribution in field f of cited paper p.
        """

        epsilon_zero = _as_decimal(
            epsilon_zero
        )

        field_weight = _as_decimal(
            field_weight
        )

        target_author_overall_weight = (
            _as_decimal(
                target_author_overall_weight
            )
        )

        weight_tolerance = _as_decimal(
            weight_tolerance
        )

        if not ZERO <= epsilon_zero <= ONE:
            raise ValueError(
                "epsilon_zero must be between 0 and 1."
            )

        if not ZERO < field_weight <= ONE:
            raise ValueError(
                "field_weight must be greater than 0 "
                "and no greater than 1."
            )

        if not (
            ZERO
            <= target_author_overall_weight
            <= ONE
        ):
            raise ValueError(
                "target_author_overall_weight must "
                "be between 0 and 1."
            )

        if weight_tolerance < ZERO:
            raise ValueError(
                "weight_tolerance cannot be negative."
            )

        cited_authors = (
            self._normalize_author_ids(
                cited_author_ids
            )
        )

        if not cited_authors:
            raise ValueError(
                f"Cited publication {cited_pub_id} "
                "has no authors."
            )

        if target_author_id not in cited_authors:
            raise ValueError(
                f"Target author {target_author_id} "
                "does not belong to cited publication "
                f"{cited_pub_id}."
            )

        citing_weights = (
            self._normalize_author_weights(
                citing_author_weights,
                pub_id=citing_pub_id,
                tolerance=weight_tolerance,
            )
        )

        (
            self_author_ids,
            core_author_ids,
            non_overlap_author_ids,
        ) = self._partition_author_sets(
            cited_authors=cited_authors,
            citing_author_ids=list(
                citing_weights.keys()
            ),
            target_author_id=target_author_id,
        )

        self_influence_sum = (
            self._sum_weights(
                citing_weights,
                self_author_ids,
            )
        )

        core_influence_sum = (
            self._sum_weights(
                citing_weights,
                core_author_ids,
            )
        )

        non_overlap_influence_sum = (
            self._sum_weights(
                citing_weights,
                non_overlap_author_ids,
            )
        )

        core_author_count = len(
            core_author_ids
        )

        core_count_decimal = Decimal(
            core_author_count
        )

        epsilon_value = (
            epsilon_zero
            * core_count_decimal
        )

        # Equation 7 numerator.
        isc_numerator = (
            self_influence_sum
            + epsilon_value
            * core_influence_sum
        )

        # Equation 7 denominator.
        isc_denominator = (
            self_influence_sum
            + core_count_decimal
            * core_influence_sum
            + non_overlap_influence_sum
        )

        if isc_denominator <= ZERO:
            raise ValueError(
                "ISC denominator must be greater "
                "than zero."
            )

        isc_value = (
            isc_numerator
            / isc_denominator
        )

        # Protect against very small numerical errors.
        isc_value = min(
            ONE,
            max(
                ZERO,
                isc_value,
            ),
        )

        # Raw fractional citation:
        #
        # TC_raw(p, i, q, f) = W_p^(f,i)
        raw_citation = (
            target_author_overall_weight
            * field_weight
        )

        # Equation 8:
        #
        # TC_adjusted =
        #     (1 - ISC) * TC_raw
        adjusted_citation = (
            ONE - isc_value
        ) * raw_citation

        return ISCResult(
            cited_pub_id=cited_pub_id,
            citing_pub_id=citing_pub_id,
            target_author_id=target_author_id,
            field_name=field_name,
            field_weight=field_weight,
            target_author_overall_weight=(
                target_author_overall_weight
            ),
            self_author_ids=self_author_ids,
            core_author_ids=core_author_ids,
            non_overlap_author_ids=(
                non_overlap_author_ids
            ),
            self_influence_sum=(
                self_influence_sum
            ),
            core_influence_sum=(
                core_influence_sum
            ),
            non_overlap_influence_sum=(
                non_overlap_influence_sum
            ),
            core_author_count=(
                core_author_count
            ),
            epsilon_zero=epsilon_zero,
            epsilon_value=epsilon_value,
            isc_numerator=isc_numerator,
            isc_denominator=isc_denominator,
            isc_value=isc_value,
            raw_citation=raw_citation,
            adjusted_citation=(
                adjusted_citation
            ),
        )

    @staticmethod
    def _normalize_author_ids(
        author_ids: Iterable[str],
    ) -> set[str]:
        return {
            author_id.strip()
            for author_id in author_ids
            if (
                author_id
                and author_id.strip()
            )
        }

    def _normalize_author_weights(
        self,
        author_weights: Iterable[AuthorWeight],
        *,
        pub_id: str,
        tolerance: Decimal,
    ) -> dict[str, Decimal]:
        """
        Validate that publication author weights
        total approximately 1.

        Small rounding differences are normalized.
        """

        weights: dict[str, Decimal] = {}

        for item in author_weights:
            author_id = (
                item.author_id.strip()
                if item.author_id
                else ""
            )

            if not author_id:
                continue

            weight = _as_decimal(
                item.weight
            )

            if weight < ZERO:
                raise ValueError(
                    "Negative contribution weight "
                    f"for author {author_id}."
                )

            if author_id in weights:
                raise ValueError(
                    f"Duplicate author {author_id} "
                    f"in publication {pub_id}."
                )

            weights[author_id] = weight

        if not weights:
            raise ValueError(
                f"Publication {pub_id} "
                "has no author weights."
            )

        total_weight = sum(
            weights.values(),
            ZERO,
        )

        if total_weight <= ZERO:
            raise ValueError(
                f"Publication {pub_id} "
                "has zero total author weight."
            )

        if abs(total_weight - ONE) > tolerance:
            raise ValueError(
                "Author weights for publication "
                f"{pub_id} must total 1. "
                f"Current total: {total_weight}."
            )

        normalization_factor = (
            ONE / total_weight
        )

        return {
            author_id: (
                weight
                * normalization_factor
            )
            for author_id, weight
            in weights.items()
        }

    @staticmethod
    def _partition_author_sets(
        *,
        cited_authors: set[str],
        citing_author_ids: list[str],
        target_author_id: str,
    ) -> tuple[
        list[str],
        list[str],
        list[str],
    ]:
        """
        I:
            Target author appearing in citing paper q.

        J:
            Other authors appearing in both p and q.

        M:
            Authors appearing in q but not in p.
        """

        self_author_ids = [
            author_id
            for author_id in citing_author_ids
            if author_id == target_author_id
        ]

        core_author_ids = [
            author_id
            for author_id in citing_author_ids
            if (
                author_id in cited_authors
                and author_id
                != target_author_id
            )
        ]

        non_overlap_author_ids = [
            author_id
            for author_id in citing_author_ids
            if author_id not in cited_authors
        ]

        return (
            self_author_ids,
            core_author_ids,
            non_overlap_author_ids,
        )

    @staticmethod
    def _sum_weights(
        weights: dict[str, Decimal],
        author_ids: list[str],
    ) -> Decimal:
        return sum(
            (
                weights[author_id]
                for author_id in author_ids
            ),
            ZERO,
        )


def calculate_isc(
    *,
    cited_pub_id: str,
    citing_pub_id: str,
    cited_author_ids: Iterable[str],
    citing_author_weights: Iterable[AuthorWeight],
    target_author_id: str,
    target_author_overall_weight: (
        Decimal | float | int | str
    ),
    field_name: str,
    field_weight: Decimal | float | int | str,
    epsilon_zero: Decimal | float | int | str = Decimal("0.90"),
    weight_tolerance: Decimal | float | int | str = Decimal("0.02"),
) -> ISCResult:
    """
    Functional wrapper for Equation 7 and 8.
    """

    calculator = (
        InfluentialSelfCitationCalculator()
    )

    return calculator.calculate(
        cited_pub_id=cited_pub_id,
        citing_pub_id=citing_pub_id,
        cited_author_ids=cited_author_ids,
        citing_author_weights=(
            citing_author_weights
        ),
        target_author_id=(
            target_author_id
        ),
        target_author_overall_weight=(
            target_author_overall_weight
        ),
        field_name=field_name,
        field_weight=field_weight,
        epsilon_zero=epsilon_zero,
        weight_tolerance=(
            weight_tolerance
        ),
    )


def aggregate_equation_9(
    results: Iterable[ISCResult],
) -> PaperAdjustedCitationResult:
    """
    Calculate Equation 9 in Python:

        TC_adjusted(p, i)
            =
        sum over every q and every f of
        TC_adjusted(p, i, q, f)

    All supplied rows must belong to the same
    cited publication and target author.
    """

    rows = list(results)

    if not rows:
        raise ValueError(
            "At least one Equation 8 result "
            "is required."
        )

    cited_pub_id = rows[0].cited_pub_id
    target_author_id = rows[0].target_author_id

    for row in rows:
        if row.cited_pub_id != cited_pub_id:
            raise ValueError(
                "Equation 9 rows contain more than "
                "one cited publication."
            )

        if (
            row.target_author_id
            != target_author_id
        ):
            raise ValueError(
                "Equation 9 rows contain more than "
                "one target author."
            )

    citing_paper_ids = {
        row.citing_pub_id
        for row in rows
    }

    total_raw_citation = sum(
        (
            row.raw_citation
            for row in rows
        ),
        ZERO,
    )

    total_adjusted_citation = sum(
        (
            row.adjusted_citation
            for row in rows
        ),
        ZERO,
    )

    return PaperAdjustedCitationResult(
        cited_pub_id=cited_pub_id,
        target_author_id=(
            target_author_id
        ),
        citing_paper_count=len(
            citing_paper_ids
        ),
        field_row_count=len(rows),
        total_raw_citation=(
            total_raw_citation
        ),
        total_adjusted_citation=(
            total_adjusted_citation
        ),
    )