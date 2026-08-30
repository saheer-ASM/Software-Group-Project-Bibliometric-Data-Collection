"""
Regression tests for ModifiedHmIndexCalculator.

Run with:
    pytest test_calculator.py -v

INTERFACE NOTE (changed from earlier versions): calculate() now takes
TWO DataFrames, not four/five:

    calculate(effective_citations, field_classification)

`effective_citations` is unique at (paper_id, author_id, field_id)
and already contains career_factor and the fully combined author-field
weight (author_field_weight = Eq. 1/3/4/5's W_p^{f,i}) directly --
there is no more separate paper_authors / authors input, since those
values are read straight from this table instead of being recombined
from author_contribution_weight and the author table.

`field_classification` (paper_id, field_id, field_weight) is still
required, but now serves ONLY the Eq. 20 cross-field combination --
field_weight is no longer applied inside tc_eff/r_eff, because
author_field_weight in effective_citations already has that baked in
upstream.

Covers:
    1. A hand-verified 2-author single-field example, confirming the
       field-average normalization arithmetic exactly
    2. The solo-contributor edge case: a field with only one author
       must normalize to exactly 1.0 (they ARE the field average)
    3. The Eq. 19 h-index-style threshold ("early break") actually
       firing when a long tail of low-citation papers can't keep pace
       with cumulative contribution rank
    4. field_weight correctly affecting the Eq. 20 OUTER cross-field
       combination (its role after this interface change -- see note
       in the test itself for why this differs from earlier revisions
       of this suite)
    5. A genuine multi-author, multi-field scenario (Eq. 20), checked
       against an independent hand calculation
    6. Validation errors: missing columns, empty data after cleaning

IMPORTANT input-shape note: `effective_citations` must contain
exactly ONE row per (paper_id, author_id, field_id). If a paper spans
multiple fields for the same author, that author needs one row per
field, each with its own author_field_weight already reflecting that
field's share -- NOT one row duplicated across fields, and NOT a
single row with a field-agnostic weight.
"""

import pandas as pd
import pytest

from calculator import ModifiedHmIndexCalculator


# =============================================================
# SHARED FIXTURES
# =============================================================

@pytest.fixture
def calc():
    return ModifiedHmIndexCalculator()


def make_inputs(effective_citations, field_classification):
    """Small helper so each test only supplies the rows that matter."""
    return dict(
        effective_citations=pd.DataFrame(effective_citations),
        field_classification=pd.DataFrame(field_classification),
    )


# =============================================================
# TEST 1: hand-verified 2-author field average
# =============================================================
#
# Author A: author_field_weight=0.6, citations=50
# Author B: author_field_weight=0.4, citations=30
# Both: career_factor=1.0, field_weight=1.0, single field "CS"
#
# max_r_eff_A = 1*0.6 = 0.6
# max_r_eff_B = 1*0.4 = 0.4
# field average (Hm'_CS) = (0.6 + 0.4) / 2 = 0.5
# Hm'_CS,A = 0.6 / 0.5 = 1.2  (above-average contributor)
# Hm'_CS,B = 0.4 / 0.5 = 0.8  (below-average contributor)

def test_two_author_field_average(calc):
    inputs = make_inputs(
        effective_citations={
            "paper_id": [1, 2],
            "author_id": ["A", "B"],
            "field_id": ["CS", "CS"],
            "career_factor": [1.0, 1.0],
            "author_field_weight": [0.6, 0.4],
            "capped_adjusted_citations": [50, 30],
        },
        field_classification={
            "paper_id": [1, 2],
            "field_id": ["CS", "CS"],
            "field_weight": [1.0, 1.0],
        },
    )

    result = calc.calculate(**inputs)
    r = result.set_index("author_id")["modified_hm_index"]

    assert r["A"] == pytest.approx(1.2, rel=1e-9)
    assert r["B"] == pytest.approx(0.8, rel=1e-9)


# =============================================================
# TEST 2: solo contributor in a field normalizes to exactly 1.0
# =============================================================
#
# If an author is the ONLY contributor to a field, the field average
# equals their own max_r_eff exactly, so dividing by it must always
# give 1.0 -- regardless of citations, weight, or career factor.
# This is expected behavior of "relative to peers," not a bug: with
# no peers, you ARE the average.

def test_solo_author_in_field_normalizes_to_one(calc):
    inputs = make_inputs(
        effective_citations={
            "paper_id": [1],
            "author_id": ["Solo"],
            "field_id": ["NICHE"],
            "career_factor": [1.0],
            "author_field_weight": [0.5],
            "capped_adjusted_citations": [40],
        },
        field_classification={
            "paper_id": [1],
            "field_id": ["NICHE"],
            "field_weight": [1.0],
        },
    )

    result = calc.calculate(**inputs)
    hm_value = result.loc[
        result["author_id"] == "Solo", "modified_hm_index"
    ].iloc[0]

    assert hm_value == pytest.approx(1.0, rel=1e-9)


# =============================================================
# TEST 3: Eq. 19 threshold actually breaks early on a long tail
# =============================================================
#
# This is the scenario the old buggy code (unconditional `.max()`)
# would silently get wrong: a long run of near-zero-citation papers
# should NOT all be swept into the effective rank once cumulative
# citations stop keeping pace with cumulative contribution rank. A
# second author with a single strong paper is included so the field
# average isn't trivially 1.0 for everyone.
#
# Hand trace of the threshold condition (citations=[10, 0.01 x19],
# author_field_weight=0.9, career_factor=1.0 for every paper -- so
# each paper's r_eff increment is a constant 0.9):
#
#   cum_tc_eff grows ~10 + 0.01*(k-1); cum_r_eff grows 0.9*k.
#   The condition (cum_tc_eff >= cum_r_eff) fails once k exceeds
#   ~11, and tracing it precisely gives k_valid = 10, so:
#       max_r_eff(Y) = 10 * 0.9 = 9.0   (NOT 20 * 0.9 = 18.0 --
#                                         that would mean the break
#                                         never fired)
#
# Peer (single paper, citations=10, author_field_weight=0.9):
#       max_r_eff(Peer) = 1 * 0.9 = 0.9
#
# Field average = (9.0 + 0.9) / 2 = 4.95
#   Hm'_Y    = 9.0 / 4.95 = 1.818181...
#   Hm'_Peer = 0.9 / 4.95 = 0.181818...
#
# NOTE: a naive "compare against the unbroken case" assertion is NOT
# reliable here, because Peer's small value means the field average
# scales down almost proportionally with Y's own score either way --
# the ratio barely moves even though the raw max_r_eff is genuinely
# halved by the break. Asserting the exact hand-derived value is the
# only way to actually catch a regression of the early-break logic
# in this shape of scenario.

def test_long_tail_triggers_early_break(calc):
    n = 20
    citations = [10] + [0.01] * (n - 1)  # one strong paper, long weak tail

    inputs = make_inputs(
        effective_citations={
            "paper_id": list(range(1, n + 2)),
            "author_id": ["Y"] * n + ["Peer"],
            "field_id": ["CS"] * (n + 1),
            "career_factor": [1.0] * (n + 1),
            "author_field_weight": [0.9] * (n + 1),
            "capped_adjusted_citations": citations + [10],
        },
        field_classification={
            "paper_id": list(range(1, n + 2)),
            "field_id": ["CS"] * (n + 1),
            "field_weight": [1.0] * (n + 1),
        },
    )

    result = calc.calculate(**inputs)
    r = result.set_index("author_id")["modified_hm_index"]

    field_avg = (9.0 + 0.9) / 2
    y_expected = 9.0 / field_avg
    peer_expected = 0.9 / field_avg

    assert r["Y"] == pytest.approx(y_expected, rel=1e-9)
    assert r["Peer"] == pytest.approx(peer_expected, rel=1e-9)


# =============================================================
# TEST 4: field_weight affects the Eq. 20 OUTER combination
# =============================================================
#
# IMPORTANT DESIGN NOTE: in earlier revisions of this suite, this
# test checked that field_weight was applied INSIDE tc_eff/r_eff
# (a bug found and fixed at the time). After this interface change,
# that responsibility moved: author_field_weight in
# effective_citations now already has V_p^f baked in upstream, so
# field_weight from field_classification is used ONLY for the Eq. 20
# cross-field combination -- not inside the per-field rank
# calculation at all. This test now checks THAT role instead.
#
# Author Z has two separate papers -- one in CS, one in BE -- each
# with the SAME raw author_field_weight (0.5), so any difference in
# Z's final score between the two scenarios below can only come from
# how field_weight combines the two fields' ALREADY-DIFFERENT
# normalized scores (0.769... for CS, 1.428... for BE, driven by
# each field's peer).
#
# Hand calculation:
#   CS: Z=0.5, PeerCS=0.8 -> field avg = 0.65 -> Z_CS = 0.5/0.65 = 0.769230...
#   BE: Z=0.5, PeerBE=0.2 -> field avg = 0.35 -> Z_BE = 0.5/0.35 = 1.428571...
#
#   even split (cs=0.5, be=0.5):
#       (0.5*0.769230 + 0.5*1.428571) / 1.0 = 1.098901...
#   skewed split (cs=0.9, be=0.1):
#       (0.9*0.769230 + 0.1*1.428571) / 1.0 = 0.835164...

def test_field_weight_affects_outer_combination(calc):
    def run_with_split(cs_weight, be_weight):
        inputs = make_inputs(
            effective_citations={
                "paper_id": [1, 2, 3, 4],
                "author_id": ["Z", "PeerCS", "PeerBE", "Z"],
                "field_id": ["CS", "CS", "BE", "BE"],
                "career_factor": [1.0, 1.0, 1.0, 1.0],
                "author_field_weight": [0.5, 0.8, 0.2, 0.5],
                "capped_adjusted_citations": [40, 40, 40, 40],
            },
            field_classification={
                "paper_id": [1, 2, 3, 4],
                "field_id": ["CS", "CS", "BE", "BE"],
                "field_weight": [cs_weight, 1.0, 1.0, be_weight],
            },
        )
        result = calc.calculate(**inputs)
        return result.loc[
            result["author_id"] == "Z", "modified_hm_index"
        ].iloc[0]

    hm_even = run_with_split(0.5, 0.5)
    hm_skewed = run_with_split(0.9, 0.1)

    z_cs = 0.5 / 0.65
    z_be = 0.5 / 0.35
    even_expected = (0.5 * z_cs + 0.5 * z_be) / 1.0
    skewed_expected = (0.9 * z_cs + 0.1 * z_be) / 1.0

    assert hm_even == pytest.approx(even_expected, rel=1e-9)
    assert hm_skewed == pytest.approx(skewed_expected, rel=1e-9)
    assert hm_even != pytest.approx(hm_skewed, rel=1e-6)


# =============================================================
# TEST 5: Eq. 20 -- genuine multi-author, multi-field scenario
# =============================================================
#
# Three authors: X (papers in CS and AI), Y (CS only), Z (AI only).
# Both CS and AI have real, non-trivial averages (more than one
# contributor each). X's author_field_weight values are already the
# COMBINED position-weight x field-share (0.5 x 0.7 = 0.35 for CS,
# 0.5 x 0.3 = 0.15 for AI), matching how the real
# author_paper_field_effective_citation table is populated.

def test_eq20_multi_author_multi_field(calc):
    inputs = make_inputs(
        effective_citations={
            "paper_id": [1, 1, 2, 3],
            "author_id": ["X", "X", "Y", "Z"],
            "field_id": ["CS", "AI", "CS", "AI"],
            "career_factor": [1.0, 1.0, 1.0, 1.0],
            "author_field_weight": [0.35, 0.15, 0.60, 0.30],
            "capped_adjusted_citations": [60, 60, 30, 15],
        },
        field_classification={
            "paper_id": [1, 1, 2, 3],
            "field_id": ["CS", "AI", "CS", "AI"],
            "field_weight": [0.7, 0.3, 1.0, 1.0],
        },
    )

    result = calc.calculate(**inputs)
    r = result.set_index("author_id")["modified_hm_index"]

    cs_avg = (0.35 + 0.60) / 2
    ai_avg = (0.15 + 0.30) / 2
    x_cs = 0.35 / cs_avg
    x_ai = 0.15 / ai_avg
    x_expected = (0.7 * x_cs + 0.3 * x_ai) / 1.0
    y_expected = 0.60 / cs_avg
    z_expected = 0.30 / ai_avg

    assert r["X"] == pytest.approx(x_expected, rel=1e-9)
    assert r["Y"] == pytest.approx(y_expected, rel=1e-9)
    assert r["Z"] == pytest.approx(z_expected, rel=1e-9)


# =============================================================
# TEST 6: validation errors
# =============================================================

def test_missing_required_column_raises(calc):
    inputs = make_inputs(
        effective_citations={
            "paper_id": [1],
            "author_id": ["X"],
            "field_id": ["CS"],
            "career_factor": [1.0],
            # "author_field_weight" deliberately omitted
            "capped_adjusted_citations": [10],
        },
        field_classification={
            "paper_id": [1], "field_id": ["CS"], "field_weight": [1.0]
        },
    )

    with pytest.raises(ValueError, match="missing columns"):
        calc.calculate(**inputs)


def test_all_rows_filtered_out_raises(calc):
    # career_factor <= 0 for every row -> everything gets dropped in
    # the cleaning step -> should raise, not silently return empty.
    inputs = make_inputs(
        effective_citations={
            "paper_id": [1],
            "author_id": ["X"],
            "field_id": ["CS"],
            "career_factor": [0.0],
            "author_field_weight": [0.5],
            "capped_adjusted_citations": [10],
        },
        field_classification={
            "paper_id": [1], "field_id": ["CS"], "field_weight": [1.0]
        },
    )

    with pytest.raises(ValueError, match="No valid data remains"):
        calc.calculate(**inputs)


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
