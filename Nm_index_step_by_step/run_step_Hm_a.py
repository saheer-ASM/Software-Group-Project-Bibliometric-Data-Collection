"""
Demo / verification run: Step 1 (build the author dataset) + Steps 3-6
(process Hm_a only -- no log transform, fractional ranking). Read-only
-- connects to the DB to load data, does not write anything back
anywhere.

    python -m Nm_index_step_by_step.run_step_Hm_a
"""

import pandas as pd

from .build_dataset import build_author_metric_dataset
from .database import get_connection
from .step_Hm_a import process_Hm_a


def main() -> None:
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)

    print("=" * 70)
    print("STEP 1 -- build author_id, T_a, S_a, U_a, Hf_a, Hm_a, G_a")
    print("=" * 70)

    connection = get_connection()
    try:
        dataset = build_author_metric_dataset(connection)
    finally:
        connection.close()

    print(f"Authors loaded: {len(dataset)}")
    for column in ("T_a", "S_a", "U_a", "Hf_a", "Hm_a", "G_a"):
        print(f"  {column:<6} non-null: {dataset[column].notna().sum()}")
    print()
    print(dataset.head(5).to_string(index=False))

    print()
    print("=" * 70)
    print("STEPS 3-6 -- process Hm_a (no log transform, fractional ranking)")
    print("=" * 70)

    result = process_Hm_a(dataset)

    n_available = int(result["N_Hm"].iloc[0])
    print(f"N_Hm (authors with non-null Hm_a): {n_available}")
    print()

    scored = result[result["Hm_a"].notna()]
    preview = scored[
        ["author_id", "Hm_a", "rank_Hm", "P_Hm", "Nor_Hm", "Per_Hm"]
    ]

    print("Lowest Hm_a (fractional-ranked tie block):")
    print(
        preview.sort_values("Hm_a").head(5).to_string(index=False)
    )
    print()
    print("Highest Hm_a (near the 100th percentile):")
    print(
        preview.sort_values("Hm_a", ascending=False).head(5).to_string(index=False)
    )

    print()
    print("Sanity check -- Per_Hm should equal 100 * P_Hm (Phi(Phi^-1(P)) = P):")
    max_diff = (scored["Per_Hm"] - 100.0 * scored["P_Hm"]).abs().max()
    print(f"  max |Per_Hm - 100*P_Hm| = {max_diff:.2e}")

    print()
    print("Per_Hm distribution:")
    print(scored["Per_Hm"].describe().to_string())


if __name__ == "__main__":
    main()
