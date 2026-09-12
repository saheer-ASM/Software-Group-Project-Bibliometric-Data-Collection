"""
Steps 3-6 -- process G_a (G'_a, modified g-index) into its final
percentile score.

Identical recipe to step_Hf_a.py / step_Hm_a.py, applied to G_a
instead:

Same percentile-normalisation framework as T_a / S_a / U_a, but with
NO log transform -- G'_a (like Hf'_a and Hm'_a) is already a small,
index-shaped number with many ties, not a raw skewed citation count,
so Eq. 24 ranks it directly:

    G_a
     |
    Step 3: rank_G = rank(G_a), FRACTIONAL ("average") ranking
     |
    Step 4: P_G    = Blom plotting position
                    = (rank_G - 0.375) / (N_G + 0.25)
     |
    Step 5: Nor_G  = Phi^-1(P_G)     (explicit inverse normal)
     |
    Step 6: Per_G  = 100 * Phi(Nor_G)   ( == 100 * P_G, since
                                           Phi(Phi^-1(P)) = P;
                                           computed via the explicit
                                           round trip below instead
                                           of taking that shortcut)

Per Eq. 24: "fractional ranking ... for the hm, hf, g indices (as they
contain many ties) ... and normal ranking for the raw citations" --
so G_a uses config.RANK_METHOD_RANK ("average"), NOT config.RANK_METHOD
("min", still used by T_a / S_a / U_a).

Authors with a NULL G_a are left NaN in every derived column and are
excluded from N_G (the ranking population) and from the ranking
itself -- a missing G_a is never treated as G_a = 0.

With this, all six component metrics (T_a, S_a, U_a, Hf'_a, Hm'_a,
G'_a) have their own step_*.py in this walkthrough. The final Eq. 27
weighted average across the six Per_* columns is the next step.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_G_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD_RANK,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and a
        "G_a" column (the Step 1 output).
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
        rank_G, N_G, P_G, Nor_G, Per_G
    (no L_G -- there is no log-transform step for this metric).
    """

    if "G_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'G_a' column.")

    df = dataset.copy()
    df["G_a"] = pd.to_numeric(df["G_a"], errors="coerce")

    mask = df["G_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null G_a value.")

    for column in ("rank_G", "P_G", "Nor_G", "Per_G"):
        df[column] = np.nan
    df["N_G"] = n_available

    # ---- Step 3: rank the raw G_a values directly (no log) -------
    # fractional ("average") ranking -> tied values split the rank
    # evenly (e.g. two ties at positions 1-2 both get rank 1.5)
    df.loc[mask, "rank_G"] = df.loc[mask, "G_a"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position --------------------------
    # P_G = (rank_G - a) / (N_G + 1 - 2a)  [a=0.375 -> (r-0.375)/(N+0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_G"] = (df.loc[mask, "rank_G"] - blom_a) / denom

    # ---- Step 5-6: inverse normal, then back to a percentile ------
    # Computed explicitly (Nor_G then Per_G) to reproduce Eq. 25/26
    # literally, rather than jumping straight to Per_G = 100 * P_G.
    df.loc[mask, "Nor_G"] = norm.ppf(df.loc[mask, "P_G"])
    df.loc[mask, "Per_G"] = 100.0 * norm.cdf(df.loc[mask, "Nor_G"])

    return df
