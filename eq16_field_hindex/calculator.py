from decimal import Decimal
from typing import List, Tuple


def compute_raw_h_value(
    effective_citations: List[Decimal],
) -> Tuple[int, int]:
    """
    Numerator of Equation 16:

        max(h : sum_{p'=1}^{h} TCadj_eff,f,p',i_ap' >= h)

    Sort the author's papers in this field by effective citation
    (descending), then find the largest h where the cumulative sum
    of the top h papers is >= h.

    Returns (raw_h_value, papers_used).
    """

    sorted_values = sorted(effective_citations, reverse=True)

    cumulative = Decimal("0")
    max_h = 0

    for position, value in enumerate(sorted_values, start=1):
        cumulative += value
        if cumulative >= position:
            max_h = position

    return max_h, len(sorted_values)


def compute_field_normalization(raw_h_values: List[int]) -> Decimal:
    """
    Hf'_f — the field-level normalizer in Equation 16's denominator.

    NOTE: the source text supplied so far defines the NUMERATOR of
    Equation 16 but does not spell out Hf'_f itself. This function
    assumes Hf'_f = the average raw H value across every author who
    has at least one paper in field f (a common normalization
    pattern used elsewhere in this paper, e.g. TC_bar_f in Eq. 13).

    If your paper defines Hf'_f differently (e.g. the MAX raw H
    value in the field, or a fixed benchmark), change ONLY this
    function — nothing else depends on how it's computed.
    """

    if not raw_h_values:
        return Decimal("0")

    total = sum(Decimal(v) for v in raw_h_values)
    return total / Decimal(len(raw_h_values))


def compute_modified_hindex_field(
    raw_h_value: int,
    field_normalization: Decimal,
) -> Decimal | None:
    if field_normalization is None or field_normalization == Decimal("0"):
        return None

    return Decimal(raw_h_value) / field_normalization