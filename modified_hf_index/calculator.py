from decimal import Decimal
from typing import Optional


def equation_15_effective_citation(
    career_factor: Optional[Decimal],
    author_field_weight: Optional[Decimal],
    capped_adjusted_citation: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Equation 15:

        TCadj_eff(f, p, i_ap) = CFcom * Wf_iap_p * TCadj_k_cap,p,iap

    Returns None if any of the three inputs is missing.
    """

    if (
        career_factor is None
        or author_field_weight is None
        or capped_adjusted_citation is None
    ):
        return None

    return career_factor * author_field_weight * capped_adjusted_citation