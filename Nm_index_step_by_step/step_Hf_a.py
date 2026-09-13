"""
Steps 3-6 -- process Hf_a (Hf'_a, modified hf-index) into its final
percentile score.

Same percentile-normalisation framework as T_a / S_a / U_a, but with
NO log transform -- Hf'_a (and Hm'_a, G'_a after it) are already
small, index-shaped numbers with many ties, not raw skewed citation
counts, so Eq. 24 ranks them directly:

    Hf_a
     |
    Step 3: rank_Hf = rank(Hf_a), FRACTIONAL ("average") ranking
     |
    Step 4: P_Hf    = Blom plotting position
                     = (rank_Hf - 0.375) / (N_Hf + 0.25)
     |
    Step 5: Nor_Hf  = Phi^-1(P_Hf)     (explicit inverse normal)
     |
    Step 6: Per_Hf  = 100 * Phi(Nor_Hf)   ( == 100 * P_Hf, since
                                             Phi(Phi^-1(P)) = P;
                                             computed via the explicit
                                             round trip below instead
                                             of taking that shortcut)

Authors with a NULL Hf_a are left NaN in every derived column and are
excluded from N_Hf (the ranking population) and from the ranking
itself -- a missing Hf_a is never treated as Hf_a = 0.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_Hf_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD_RANK,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and an
        "Hf_a" column (the Step 1 output).
    rank_method : pandas .rank() method for Step 3.
        Default "average" (fractional ranking -- ties split the rank
        evenly), per the paper's Eq. 24 wording for the hf/hm/g
        indices ("as they contain many ties"). This is deliberately
        different from RANK_METHOD ("min") used for T_a / S_a / U_a.
    blom_a : Blom's constant `a` in P = (r - a) / (N + 1 - 2a).
        Default 0.375, per the paper.

    Returns
    -------
    A copy of `dataset` with five new columns appended:
        rank_Hf, N_Hf, P_Hf, Nor_Hf, Per_Hf
    (no L_Hf -- there is no log-transform step for this metric).
    """

    if "Hf_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'Hf_a' column.")

    df = dataset.copy()
    df["Hf_a"] = pd.to_numeric(df["Hf_a"], errors="coerce")

    mask = df["Hf_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null Hf_a value.")

    for column in ("rank_Hf", "P_Hf", "Nor_Hf", "Per_Hf"):
        df[column] = np.nan
    df["N_Hf"] = n_available

    # ---- Step 3: rank the raw Hf_a values directly (no log) ------
    # fractional ("average") ranking -> tied values split the rank
    # evenly (e.g. two ties at positions 1-2 both get rank 1.5)
    df.loc[mask, "rank_Hf"] = df.loc[mask, "Hf_a"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position -------------------------
    # P_Hf = (rank_Hf - a) / (N_Hf + 1 - 2a)  [a=0.375 -> (r-0.375)/(N+0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_Hf"] = (df.loc[mask, "rank_Hf"] - blom_a) / denom

    # ---- Step 5-6: inverse normal, then back to a percentile -----
    # Computed explicitly (Nor_Hf then Per_Hf) to reproduce Eq. 25/26
    # literally, rather than jumping straight to Per_Hf = 100 * P_Hf.
    df.loc[mask, "Nor_Hf"] = norm.ppf(df.loc[mask, "P_Hf"])
    df.loc[mask, "Per_Hf"] = 100.0 * norm.cdf(df.loc[mask, "Nor_Hf"])

    return df
