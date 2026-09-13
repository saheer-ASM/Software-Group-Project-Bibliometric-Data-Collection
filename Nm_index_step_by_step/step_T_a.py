"""
Steps 2-5 -- process T_a into its final percentile score.

    T_a
     |
    Step 2: L_T   = log10(T_a + 1)
     |
    Step 3: rank_T = rank(L_T), "normal" (min/competition) ranking
     |
    Step 4: P_T   = Blom plotting position = (rank_T - 0.375) / (N_T + 0.25)
     |
    Step 5: Nor_T = Phi^-1(P_T)   (explicit inverse normal, Eq. 25 literally)
            Per_T = 100 * Phi(Nor_T)   ( == 100 * P_T, since Phi(Phi^-1(P)) = P;
                                          computed via the explicit round trip
                                          below instead of taking that shortcut)

Authors with a NULL T_a are left NaN in every derived column and are
excluded from N_T (the ranking population) and from the ranking itself
-- a missing T_a is never treated as T_a = 0.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_T_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and a
        "T_a" column (the Step 1 output).
    rank_method : pandas .rank() method for Step 3.
        Default "min" == the paper's "normal ranking" for raw citations.
    blom_a : Blom's constant `a` in P = (r - a) / (N + 1 - 2a).
        Default 0.375, per the paper.

    Returns
    -------
    A copy of `dataset` with five new columns appended:
        L_T, rank_T, N_T, P_T, Nor_T, Per_T
    """

    if "T_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'T_a' column.")

    df = dataset.copy()
    df["T_a"] = pd.to_numeric(df["T_a"], errors="coerce")

    mask = df["T_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null T_a value.")

    for column in ("L_T", "rank_T", "P_T", "Nor_T", "Per_T"):
        df[column] = np.nan
    df["N_T"] = n_available

    # ---- Step 2: log transform --------------------------------
    # L_T = log10(T_a + 1)
    df.loc[mask, "L_T"] = np.log10(df.loc[mask, "T_a"] + 1.0)

    # ---- Step 3: rank the logged values -------------------------
    # "normal" (competition) ranking -> tied values share the lower rank
    df.loc[mask, "rank_T"] = df.loc[mask, "L_T"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position -------------------------
    # P_T = (rank_T - a) / (N_T + 1 - 2a)   [a = 0.375 -> (r - 0.375)/(N + 0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_T"] = (df.loc[mask, "rank_T"] - blom_a) / denom

    # ---- Step 5: inverse normal, then back to a percentile -------
    # Computed explicitly (Nor_T then Per_T) to reproduce Eq. 25
    # literally, rather than jumping straight to Per_T = 100 * P_T.
    df.loc[mask, "Nor_T"] = norm.ppf(df.loc[mask, "P_T"])
    df.loc[mask, "Per_T"] = 100.0 * norm.cdf(df.loc[mask, "Nor_T"])

    return df
