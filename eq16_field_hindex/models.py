from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class AuthorFieldModifiedHIndexResult:
    """
    Equation 16:
        Hf'_{f,a} = max(h : sum_{p'=1}^{h} TCadj_eff,f,p',i_ap' >= h) / Hf'_f
    """

    author_id: str
    field_name: str

    raw_h_value: int          # numerator: max h satisfying the condition
    papers_used: int          # how many of the author's papers in this field had a value

    field_normalization: Optional[Decimal]   # Hf'_f
    modified_hindex_field: Optional[Decimal] # Hf'_{f,a}

    calculation_status: str