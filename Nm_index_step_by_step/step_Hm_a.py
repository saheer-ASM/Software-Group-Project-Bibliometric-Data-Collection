"""
Steps 3-6 -- process Hm_a (Hm'_a, modified hm-index) into its final
percentile score.

Identical recipe to step_Hf_a.py, applied to Hm_a instead of Hf_a:

Same percentile-normalisation framework as T_a / S_a / U_a, but with
NO log transform -- Hm'_a (like Hf'_a and G'_a) is already a small,
index-shaped number with many ties, not a raw skewed citation count,
so Eq. 24 ranks it directly:

    Hm_a
     |
    Step 3: rank_Hm = rank(Hm_a), FRACTIONAL ("average") ranking
     |
    Step 4: P_Hm    = Blom plotting position
                     = (rank_Hm - 0.375) / (N_Hm + 0.25)
     |
    Step 5: Nor_Hm  = Phi^-1(P_Hm)     (explicit inverse normal)
     |
    Step 6: Per_Hm  = 100 * Phi(Nor_Hm)   ( == 100 * P_Hm, since
                                             Phi(Phi^-1(P)) = P;
                                             computed via the explicit
                                             round trip below instead
                                             of taking that shortcut)

Per Eq. 24: "fractional ranking ... for the hm, hf, g indices (as they
contain many ties) ... and normal ranking for the raw citations" --
so Hm_a uses config.RANK_METHOD_RANK ("average"), NOT config.RANK_METHOD
("min", still used by T_a / S_a / U_a).

Authors with a NULL Hm_a are left NaN in every derived column and are
excluded from N_Hm (the ranking population) and from the ranking
itself -- a missing Hm_a is never treated as Hm_a = 0.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_Hm_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD_RANK,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and an
        "Hm_a" column (the Step 1 output).
    rank_method : pandas .rank() method for Step 3.
        Default "average" (fractional ranking -- ties split the rank
        evenly), per the paper's Eq. 24 wording for the hf/hm/g
        indices ("as they contain many ties"). Deliberately different
        from RANK_METHOD ("min") used for T_a / S_a / U_a.
    blom_a : Blom's constant `a` in P = (r - a) / (N + 1 - 2a).
        Default 0.375, per the paper.

    Returns
    -------
    A copy of `dataset` with five new columns appended:
        rank_Hm, N_Hm, P_Hm, Nor_Hm, Per_Hm
    (no L_Hm -- there is no log-transform step for this metric).
    """

    if "Hm_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'Hm_a' column.")

    df = dataset.copy()
    df["Hm_a"] = pd.to_numeric(df["Hm_a"], errors="coerce")

    mask = df["Hm_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null Hm_a value.")

    for column in ("rank_Hm", "P_Hm", "Nor_Hm", "Per_Hm"):
        df[column] = np.nan
    df["N_Hm"] = n_available

    # ---- Step 3: rank the raw Hm_a values directly (no log) ------
    # fractional ("average") ranking -> tied values split the rank
    # evenly (e.g. two ties at positions 1-2 both get rank 1.5)
    df.loc[mask, "rank_Hm"] = df.loc[mask, "Hm_a"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position -------------------------
    # P_Hm = (rank_Hm - a) / (N_Hm + 1 - 2a)  [a=0.375 -> (r-0.375)/(N+0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_Hm"] = (df.loc[mask, "rank_Hm"] - blom_a) / denom

    # ---- Step 5-6: inverse normal, then back to a percentile -----
    # Computed explicitly (Nor_Hm then Per_Hm) to reproduce Eq. 25/26
    # literally, rather than jumping straight to Per_Hm = 100 * P_Hm.
    df.loc[mask, "Nor_Hm"] = norm.ppf(df.loc[mask, "P_Hm"])
    df.loc[mask, "Per_Hm"] = 100.0 * norm.cdf(df.loc[mask, "Nor_Hm"])

    return df
