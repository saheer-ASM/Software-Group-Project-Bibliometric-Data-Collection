from decimal import Decimal
from typing import Optional, Tuple


ZERO = Decimal("0")
ONE = Decimal("1")

# k in R_{k,f}^{adj}. The project uses the 99th percentile.
DEFAULT_PERCENTILE_K = Decimal("99")


def cap_adjusted_citation(
    adjusted_citation: Optional[Decimal],
    cap_threshold: Optional[Decimal],
) -> Optional[Decimal]:
    """
    Equation 12:

        TC_cap(p, i_ap)^{adj,k} = min(TC(p, i_ap)^{adj}, R_{k,f}^{adj})

    Returns None when either input is unavailable, since the
    capped value cannot be determined without both the adjusted
    citation and the field's percentile threshold.
    """

    if adjusted_citation is None or cap_threshold is None:
        return None

    return min(adjusted_citation, cap_threshold)


def is_capped(
    adjusted_citation: Optional[Decimal],
    cap_threshold: Optional[Decimal],
) -> bool:
    """
    True when Equation 12 actually pulled the citation count
    down to the field's outlier threshold.
    """

    if adjusted_citation is None or cap_threshold is None:
        return False

    return adjusted_citation > cap_threshold


def equation_13_term(
    author_field_weight: Decimal,
    capped_adjusted_citation: Optional[Decimal],
    publication_count: Optional[int],
    field_average: Optional[Decimal],
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    One (p, f) term inside Equation 13's double summation:

        W_p^{f,i} * TC_cap^{adj,k} / (P * TC_bar_f^{adj})

    Returns (normalized_citation_ratio, paper_field_contribution).
    Both are None when the term cannot be computed (missing capped
    citation, unknown publication count, or a missing/zero field
    average denominator).
    """

    if (
        capped_adjusted_citation is None
        or publication_count is None
        or publication_count <= 0
        or field_average is None
        or field_average == ZERO
    ):
        return None, None

    normalized_citation_ratio = capped_adjusted_citation / (
        Decimal(publication_count) * field_average
    )

    paper_field_contribution = (
        author_field_weight * normalized_citation_ratio
    )

    return normalized_citation_ratio, paper_field_contribution


def equation_13_score(
    career_factor: Decimal,
    normalized_contribution_sum: Decimal,
) -> Decimal:
    """
    Equation 13 final result for one author:

        S_a = CF_com * sum_p sum_f [ ... ]
    """

    return career_factor * normalized_contribution_sum


def years_elapsed(as_of_year: int, publication_year: int) -> int:
    """
    y = max(1, as_of_year - publication_year)
    """

    return max(1, as_of_year - publication_year)


def equation_14_term(
    author_field_weight: Decimal,
    capped_adjusted_citation: Optional[Decimal],
    years: Optional[int],
    field_year_average: Optional[Decimal],
) -> Tuple[Optional[Decimal], Optional[Decimal]]:
    """
    One (p, f) term inside Equation 14's double summation:

        W_p^{f,i} * TC_cap^{adj,k} / (y * TC_bar_{f,y}^{adj})

    Returns (normalized_citation_ratio, paper_field_contribution).
    """

    if (
        capped_adjusted_citation is None
        or years is None
        or years <= 0
        or field_year_average is None
        or field_year_average == ZERO
    ):
        return None, None

    normalized_citation_ratio = capped_adjusted_citation / (
        Decimal(years) * field_year_average
    )

    paper_field_contribution = (
        author_field_weight * normalized_citation_ratio
    )

    return normalized_citation_ratio, paper_field_contribution


def equation_14_score(
    career_factor: Decimal,
    normalized_contribution_sum: Decimal,
) -> Decimal:
    """
    Equation 14 final result for one author:

        U_a = CF_com * sum_p sum_f [ ... ]
    """

    return career_factor * normalized_contribution_sum
