"""
Steps 2-5 -- process U_a into its final percentile score.

Identical recipe to step_T_a.py / step_S_a.py, applied to U_a instead:

    U_a
     |
    Step 2: L_U   = log10(U_a + 1)
     |
    Step 3: rank_U = rank(L_U), "normal" (min/competition) ranking
     |
    Step 4: P_U   = Blom plotting position = (rank_U - 0.375) / (N_U + 0.25)
     |
    Step 5: Nor_U = Phi^-1(P_U)   (explicit inverse normal, Eq. 25 literally)
            Per_U = 100 * Phi(Nor_U)   ( == 100 * P_U, since Phi(Phi^-1(P)) = P;
                                          computed via the explicit round trip
                                          below instead of taking that shortcut)

Authors with a NULL U_a are left NaN in every derived column and are
excluded from N_U (the ranking population) and from the ranking itself
-- a missing U_a is never treated as U_a = 0.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


def process_U_a(
    dataset: pd.DataFrame,
    rank_method: str = config.RANK_METHOD,
    blom_a: float = config.BLOM_A,
) -> pd.DataFrame:
    """
    Parameters
    ----------
    dataset : DataFrame containing at least an "author_id" and a
        "U_a" column (the Step 1 output).
    rank_method : pandas .rank() method for Step 3.
        Default "min" == the paper's "normal ranking" for raw citations.
    blom_a : Blom's constant `a` in P = (r - a) / (N + 1 - 2a).
        Default 0.375, per the paper.

    Returns
    -------
    A copy of `dataset` with six new columns appended:
        L_U, rank_U, N_U, P_U, Nor_U, Per_U
    """

    if "U_a" not in dataset.columns:
        raise ValueError("dataset is missing the 'U_a' column.")

    df = dataset.copy()
    df["U_a"] = pd.to_numeric(df["U_a"], errors="coerce")

    mask = df["U_a"].notna()
    n_available = int(mask.sum())

    if n_available == 0:
        raise ValueError("No author has a non-null U_a value.")

    for column in ("L_U", "rank_U", "P_U", "Nor_U", "Per_U"):
        df[column] = np.nan
    df["N_U"] = n_available

    # ---- Step 2: log transform --------------------------------
    # L_U = log10(U_a + 1)
    df.loc[mask, "L_U"] = np.log10(df.loc[mask, "U_a"] + 1.0)

    # ---- Step 3: rank the logged values -------------------------
    # "normal" (competition) ranking -> tied values share the lower rank
    df.loc[mask, "rank_U"] = df.loc[mask, "L_U"].rank(
        method=rank_method,
        ascending=True,
    )

    # ---- Step 4: Blom plotting position -------------------------
    # P_U = (rank_U - a) / (N_U + 1 - 2a)   [a = 0.375 -> (r - 0.375)/(N + 0.25)]
    denom = n_available + 1 - 2 * blom_a
    df.loc[mask, "P_U"] = (df.loc[mask, "rank_U"] - blom_a) / denom

    # ---- Step 5: inverse normal, then back to a percentile -------
    # Computed explicitly (Nor_U then Per_U) to reproduce Eq. 25
    # literally, rather than jumping straight to Per_U = 100 * P_U.
    df.loc[mask, "Nor_U"] = norm.ppf(df.loc[mask, "P_U"])
    df.loc[mask, "Per_U"] = 100.0 * norm.cdf(df.loc[mask, "Nor_U"])

    return df
