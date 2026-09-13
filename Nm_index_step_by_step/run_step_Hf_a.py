"""
Demo / verification run: Step 1 (build the author dataset) + Steps 3-6
(process Hf_a only -- no log transform). Read-only -- connects to the
DB to load data, does not write anything back anywhere.

    python -m Nm_index_step_by_step.run_step_Hf_a
"""

import pandas as pd

from .build_dataset import build_author_metric_dataset
from .database import get_connection
from .step_Hf_a import process_Hf_a


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
    print("STEPS 3-6 -- process Hf_a (no log transform)")
    print("=" * 70)

    result = process_Hf_a(dataset)

    n_available = int(result["N_Hf"].iloc[0])
    print(f"N_Hf (authors with non-null Hf_a): {n_available}")
    print()

    scored = result[result["Hf_a"].notna()]
    preview = scored[
        ["author_id", "Hf_a", "rank_Hf", "P_Hf", "Nor_Hf", "Per_Hf"]
    ]

    print("Lowest Hf_a (ties at rank 1, near the 0th percentile):")
    print(
        preview.sort_values("Hf_a").head(5).to_string(index=False)
    )
    print()
    print("Highest Hf_a (near the 100th percentile):")
    print(
        preview.sort_values("Hf_a", ascending=False).head(5).to_string(index=False)
    )

    print()
    print("Sanity check -- Per_Hf should equal 100 * P_Hf (Phi(Phi^-1(P)) = P):")
    max_diff = (scored["Per_Hf"] - 100.0 * scored["P_Hf"]).abs().max()
    print(f"  max |Per_Hf - 100*P_Hf| = {max_diff:.2e}")

    print()
    print("Per_Hf distribution:")
    print(scored["Per_Hf"].describe().to_string())


if __name__ == "__main__":
    main()
