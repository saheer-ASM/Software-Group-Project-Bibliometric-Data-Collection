from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class Equation15DetailRow:
    """
    Equation 15: TCadj_eff(f, p, i_ap) = CFcom * Wf_iap_p * TCadj_k_cap

    One row per (author, publication, field).
    """

    author_id: str
    pub_id: str
    field_name: str

    career_factor: Optional[Decimal]
    author_field_weight: Optional[Decimal]
    capped_adjusted_citation: Optional[Decimal]

    effective_citation: Optional[Decimal]

    calculation_status: str