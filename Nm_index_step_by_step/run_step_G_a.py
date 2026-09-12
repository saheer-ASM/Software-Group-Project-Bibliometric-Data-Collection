"""
Demo / verification run: Step 1 (build the author dataset) + Steps 3-6
(process G_a only -- no log transform, fractional ranking). Read-only
-- connects to the DB to load data, does not write anything back
anywhere.

    python -m Nm_index_step_by_step.run_step_G_a
"""

import pandas as pd

from .build_dataset import build_author_metric_dataset
from .database import get_connection
from .step_G_a import process_G_a


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
    print("STEPS 3-6 -- process G_a (no log transform, fractional ranking)")
    print("=" * 70)

    result = process_G_a(dataset)

    n_available = int(result["N_G"].iloc[0])
    print(f"N_G (authors with non-null G_a): {n_available}")
    print()

    scored = result[result["G_a"].notna()]
    preview = scored[
        ["author_id", "G_a", "rank_G", "P_G", "Nor_G", "Per_G"]
    ]

    print("Lowest G_a (fractional-ranked tie block):")
    print(
        preview.sort_values("G_a").head(5).to_string(index=False)
    )
    print()
    print("Highest G_a (near the 100th percentile):")
    print(
        preview.sort_values("G_a", ascending=False).head(5).to_string(index=False)
    )

    print()
    print("Sanity check -- Per_G should equal 100 * P_G (Phi(Phi^-1(P)) = P):")
    max_diff = (scored["Per_G"] - 100.0 * scored["P_G"]).abs().max()
    print(f"  max |Per_G - 100*P_G| = {max_diff:.2e}")

    print()
    print("Per_G distribution:")
    print(scored["Per_G"].describe().to_string())


if __name__ == "__main__":
    main()
