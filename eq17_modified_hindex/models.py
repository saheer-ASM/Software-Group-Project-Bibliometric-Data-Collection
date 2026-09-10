from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class AuthorModifiedHIndexResult:
    """
    Equation 17 (final result):
        Hf'_a = sum_f (sum_p Vf_p * Hf'_{f,a}) / sum_f sum_p Vf_p
    """

    author_id: str

    weighted_numerator_sum: Decimal
    total_field_weight_sum: Decimal
    modified_hindex_final: Optional[Decimal]

    field_count: int
    calculation_status: str