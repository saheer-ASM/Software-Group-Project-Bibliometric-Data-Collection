"""
Pure in-memory tests for step_S_a.py -- no database required.

Same shape as test_step_T_a.py; every expected value is either a
direct plug-in of the stated formula or a formula computed once by
calculator and shown in the comment above the assertion.

Run:  pytest Nm_index_step_by_step/test_step_S_a.py -v
"""

import math

import pandas as pd
import pytest

from Nm_index_step_by_step.step_S_a import process_S_a


def _frame(author_ids, s_values):
    return pd.DataFrame({"author_id": author_ids, "S_a": s_values})


# =================================================================
# Step 2: L_S = log10(S_a + 1)
# =================================================================

def test_log_transform():
    # S_a = 10 -> L_S = log10(11) = 1.0414
    df = _frame(["a"], [10.0])
    out = process_S_a(df)
    assert out.loc[0, "L_S"] == pytest.approx(math.log10(11), rel=1e-9)
    assert round(out.loc[0, "L_S"], 4) == 1.0414


# =================================================================
# Step 3: rank(L_S), method="min" ("normal"/competition ranking)
# =================================================================

def test_ranking_ties_share_lower_rank():
    # Author  S_a  L_S      Rank
    # A001    0    0        1
    # A002    0    0        1
    # A003    2    0.477    3
    # A004    5    0.778    4
    # A005    10   1.041    5
    df = _frame(
        ["A001", "A002", "A003", "A004", "A005"],
        [0.0, 0.0, 2.0, 5.0, 10.0],
    )
    out = process_S_a(df).set_index("author_id")

    assert out.loc["A001", "rank_S"] == 1
    assert out.loc["A002", "rank_S"] == 1
    assert out.loc["A003", "rank_S"] == 3
    assert out.loc["A004", "rank_S"] == 4
    assert out.loc["A005", "rank_S"] == 5


# =================================================================
# Step 4/5: Blom plotting position + percentile round trip
# =================================================================

def test_blom_and_percentile_round_trip():
    # N_S = 2321, r_S = 1000
    # P_S   = (1000 - 0.375) / (2321 + 0.25) = 0.43064081852450187
    # Nor_S = norm.ppf(P_S)               = -0.1747429254252167
    # Per_S = 100 * norm.cdf(Nor_S)       = 43.06408185245019
    n_authors = 2321
    target_rank = 1000

    s_values = list(range(n_authors))  # distinct -> ranks 1..N_S unambiguous
    df = _frame([f"auth{i}" for i in range(n_authors)], s_values)

    out = process_S_a(df)
    row = out[out["rank_S"] == target_rank].iloc[0]

    expected_p = (target_rank - 0.375) / (n_authors + 0.25)
    assert expected_p == pytest.approx(0.43064081852450187)
    assert row["P_S"] == pytest.approx(expected_p)
    assert row["Nor_S"] == pytest.approx(-0.1747429254252167)
    assert row["Per_S"] == pytest.approx(43.06408185245019)
    assert int(out["N_S"].iloc[0]) == n_authors

    # Algebraic shortcut check: Per_S == 100 * P_S for every author,
    # since Phi(Phi^-1(P)) == P identically.
    scored = out[out["S_a"].notna()]
    diffs = (scored["Per_S"] - 100.0 * scored["P_S"]).abs()
    assert (diffs < 1e-9).all()


# =================================================================
# Missing data: NULL S_a is dropped, never treated as zero
# =================================================================

def test_null_s_a_is_excluded_not_zeroed():
    df = _frame(["a", "b", "c"], [None, 5.0, 10.0])
    out = process_S_a(df)

    row_a = out.set_index("author_id").loc["a"]
    assert pd.isna(row_a["L_S"])
    assert pd.isna(row_a["rank_S"])
    assert pd.isna(row_a["P_S"])
    assert pd.isna(row_a["Nor_S"])
    assert pd.isna(row_a["Per_S"])

    assert int(out["N_S"].iloc[0]) == 2


def test_all_null_raises():
    df = _frame(["a", "b"], [None, None])
    with pytest.raises(ValueError):
        process_S_a(df)


def test_missing_column_raises():
    with pytest.raises(ValueError):
        process_S_a(pd.DataFrame({"author_id": ["a"]}))


# =================================================================
# Rank method override
# =================================================================

def test_average_ranking_alternative():
    df = _frame(["a", "b", "c"], [0.0, 0.0, 5.0])
    out = process_S_a(df, rank_method="average").set_index("author_id")
    assert out.loc["a", "rank_S"] == pytest.approx(1.5)
    assert out.loc["b", "rank_S"] == pytest.approx(1.5)
    assert out.loc["c", "rank_S"] == 3
