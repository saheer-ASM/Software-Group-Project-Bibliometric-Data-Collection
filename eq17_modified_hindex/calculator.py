from decimal import Decimal
from typing import Optional


def equation_17_final_hindex(
    weighted_numerator_sum: Decimal,
    total_field_weight_sum: Decimal,
) -> Optional[Decimal]:
    """
    Hf'_a = weighted_numerator_sum / total_field_weight_sum
    """

    if total_field_weight_sum is None or total_field_weight_sum == Decimal("0"):
        return None

    return weighted_numerator_sum / total_field_weight_sum