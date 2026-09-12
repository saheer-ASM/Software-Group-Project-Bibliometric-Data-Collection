"""
Steps 2-5 -- process S_a into its final percentile score.

Identical recipe to step_T_a.py, applied to S_a instead of T_a:

    S_a
     |
    Step 2: L_S   = log10(S_a + 1)
     |
    Step 3: rank_S = rank(L_S), "normal" (min/competition) ranking
     |
    Step 4: P_S   = Blom plotting position = (rank_S - 0.375) / (N_S + 0.25)
     |
    Step 5: Nor_S = Phi^-1(P_S)   (explicit inverse normal, Eq. 25 literally)
            Per_S = 100 * Phi(Nor_S)   ( == 100 * P_S, since Phi(Phi^-1(P)) = P;
                                          computed via the explicit round trip
                                          below instead of taking that shortcut)

Authors with a NULL S_a are left NaN in every derived column and are
excluded from N_S (the ranking population) and from the ranking itself
-- a missing S_a is never treated as S_a = 0.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_S_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and an
        "S_a" column (the Step 1 output).
    rank_method : pandas .rank() method for Step 3.
        Default "min" == the paper's "normal ranking" for raw citations.
    blom_a : Blom's constant `a` in P = (r - a) / (N + 1 - 2a).
        Default 0.375, per the paper.

    Returns
    -------
    A copy of `dataset` with six new columns appended:
        L_S, rank_S, N_S, P_S, Nor_S, Per_S
    """

    if "S_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'S_a' column.")

    df = dataset.copy()
    df["S_a"] = pd.to_numeric(df["S_a"], errors="coerce")

    mask = df["S_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null S_a value.")

    for column in ("L_S", "rank_S", "P_S", "Nor_S", "Per_S"):
        df[column] = np.nan
    df["N_S"] = n_available

    # ---- Step 2: log transform --------------------------------
    # L_S = log10(S_a + 1)
    df.loc[mask, "L_S"] = np.log10(df.loc[mask, "S_a"] + 1.0)

    # ---- Step 3: rank the logged values -------------------------
    # "normal" (competition) ranking -> tied values share the lower rank
    df.loc[mask, "rank_S"] = df.loc[mask, "L_S"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position -------------------------
    # P_S = (rank_S - a) / (N_S + 1 - 2a)   [a = 0.375 -> (r - 0.375)/(N + 0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_S"] = (df.loc[mask, "rank_S"] - blom_a) / denom

    # ---- Step 5: inverse normal, then back to a percentile -------
    # Computed explicitly (Nor_S then Per_S) to reproduce Eq. 25
    # literally, rather than jumping straight to Per_S = 100 * P_S.
    df.loc[mask, "Nor_S"] = norm.ppf(df.loc[mask, "P_S"])
    df.loc[mask, "Per_S"] = 100.0 * norm.cdf(df.loc[mask, "Nor_S"])

    return df
