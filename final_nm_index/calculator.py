"""
Final Nm-index calculator.

Implements Eq. 24-27 of the full paper ("2.5 Final score"), i.e. the
last four steps only:

    Eq. 24  Tra_a(x)  -- transform each raw component metric
    Eq. 25  Nor_a(x)  -- normalise the transformed value
    Eq. 26  Per_a(x)  -- map to a 0-100 percentile
    Eq. 27  Nm_a      -- weighted average of the six percentiles

The six raw component metrics (T_a, S_a, U_a, Hf'_a, Hm'_a, G'_a)
are computed by upstream pipelines and passed in as a single
DataFrame -- one row per author, one column per metric. Any metric
column may contain NaN for authors the upstream pipeline has not
scored yet (or, currently, for the whole modified g-index which is
not yet populated).

Percentiles are computed *relative to the author population passed
in*. In a global deployment the paper ranks against ~100k profiles;
here the reference population is whatever cohort you load. This is a
property of the data you feed the calculator, not of the maths.
"""

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import config


class NmIndexCalculator:

    def __init__(
        self,
        weights: dict | None = None,
        distribution: dict | None = None,
        require_all_metrics: bool | None = None,
    ):
        self.weights = dict(weights or config.NM_WEIGHTS)
        self.distribution = dict(distribution or config.NM_DISTRIBUTION)
        self.require_all_metrics = (
            config.NM_REQUIRE_ALL_METRICS
            if require_all_metrics is None
            else require_all_metrics
        )

        self.metric_names = (
            list(config.LOG_METRICS) + list(config.RANK_METRICS)
        )

        total_weight = sum(self.weights.get(m, 0.0) for m in self.metric_names)
        if not np.isclose(total_weight, 1.0):
            raise ValueError(
                f"NM_WEIGHTS must sum to 1.0 across the six metrics "
                f"(got {total_weight:.6f})."
            )

    # =========================================================
    # MAIN
    # =========================================================

    def calculate(self, metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Parameters
        ----------
        metrics : DataFrame with column "author_id" plus any of the
                  six metric columns:
                      total_cites, citations_per_paper, citation_rate,
                      modified_hf_index, modified_hm_index,
                      modified_g_index

        Returns
        -------
        DataFrame with one row per input author:
            author_id,
            per_<metric>            (6 columns, 0-100 or NaN),
            metrics_available       (int 0..6),
            nm_index                (float or NaN)
        """

        if "author_id" not in metrics.columns:
            raise ValueError("metrics is missing the 'author_id' column.")

        data = metrics.copy()
        data = data.drop_duplicates(subset="author_id")

        # Make sure every metric column exists (absent -> all NaN).
        for metric in self.metric_names:
            if metric not in data.columns:
                data[metric] = np.nan
            data[metric] = pd.to_numeric(data[metric], errors="coerce")

        result = pd.DataFrame({"author_id": data["author_id"].values})

        # -----------------------------------------------------
        # Eq. 24-26: per-metric percentile score Per_a(x_i)
        # -----------------------------------------------------
        percentile_columns = {}

        for metric in config.LOG_METRICS:
            per = self._percentile_log_metric(
                data[metric],
                assumption=self.distribution.get(metric, "lognormal"),
            )
            col = f"per_{metric}"
            result[col] = per.values
            percentile_columns[metric] = col

        for metric in config.RANK_METRICS:
            per = self._percentile_rank_metric(data[metric])
            col = f"per_{metric}"
            result[col] = per.values
            percentile_columns[metric] = col

        # -----------------------------------------------------
        # Eq. 27: weighted average of available percentiles
        # -----------------------------------------------------
        per_matrix = result[[percentile_columns[m] for m in self.metric_names]]
        weight_row = np.array(
            [self.weights.get(m, 0.0) for m in self.metric_names],
            dtype=float,
        )

        available_mask = per_matrix.notna().to_numpy()
        result["metrics_available"] = available_mask.sum(axis=1).astype(int)

        weights_broadcast = np.where(available_mask, weight_row, 0.0)
        weight_sums = weights_broadcast.sum(axis=1)

        per_values = np.nan_to_num(per_matrix.to_numpy(), nan=0.0)
        weighted_sum = (per_values * weights_broadcast).sum(axis=1)

        with np.errstate(invalid="ignore", divide="ignore"):
            nm = np.where(weight_sums > 0, weighted_sum / weight_sums, np.nan)

        if self.require_all_metrics:
            nm = np.where(
                result["metrics_available"].to_numpy() == len(self.metric_names),
                nm,
                np.nan,
            )

        result["nm_index"] = nm

        return result

    # =========================================================
    # Eq. 24-26 for the LOG metrics (T_a, S_a, U_a)
    # =========================================================

    def _percentile_log_metric(
        self,
        values: pd.Series,
        assumption: str,
    ) -> pd.Series:
        """
        Eq. 24:  L(x) = log10(x + 1)
        Eq. 25:  "lognormal" -> Z-score of L(x)
                 "hooked"    -> phi^-1( P(L(x)) )
        Eq. 26:  Per(x) = 100 * phi( Nor(x) )
        """

        x = pd.to_numeric(values, errors="coerce")
        mask = x.notna()

        per = pd.Series(np.nan, index=values.index, dtype=float)
        if mask.sum() == 0:
            return per

        # Negative raw scores are not expected; clip so log is defined.
        log_x = np.log10(x.where(mask).clip(lower=0.0) + 1.0)

        if assumption == "lognormal":
            present = log_x[mask]
            mean = present.mean()
            std = present.std(ddof=0)
            if std == 0 or np.isnan(std):
                z = pd.Series(0.0, index=present.index)
            else:
                z = (present - mean) / std
            per.loc[mask] = 100.0 * norm.cdf(z.to_numpy())

        elif assumption == "hooked":
            # Nor = phi^-1(P(L(x)))  =>  Per = 100 * phi(Nor) = 100 * P
            plotting = self._plotting_position(
                log_x[mask],
                method=config.RANK_METHOD_LOG,
            )
            per.loc[mask] = 100.0 * plotting.to_numpy()

        else:
            raise ValueError(
                f"Unknown distribution assumption '{assumption}'. "
                f"Use 'lognormal' or 'hooked'."
            )

        return per

    # =========================================================
    # Eq. 24-26 for the RANK metrics (Hf'_a, Hm'_a, G'_a)
    # =========================================================

    def _percentile_rank_metric(self, values: pd.Series) -> pd.Series:
        """
        Eq. 24:  P(x) = Blom plotting position on the fractional rank
        Eq. 25:  Nor(x) = phi^-1( P(x) )
        Eq. 26:  Per(x) = 100 * P(x)
        """

        x = pd.to_numeric(values, errors="coerce")
        mask = x.notna()

        per = pd.Series(np.nan, index=values.index, dtype=float)
        if mask.sum() == 0:
            return per

        plotting = self._plotting_position(
            x[mask], method=config.RANK_METHOD_RANK
        )
        per.loc[mask] = 100.0 * plotting.to_numpy()
        return per

    # =========================================================
    # Blom plotting position  P(x) = (r(x) - a) / (N + 1 - 2a)
    # with a = 0.375  ->  (r - 0.375) / (N + 0.25)
    #
    # N defaults to the number of scored authors for this metric;
    # config.NM_REFERENCE_N overrides it with a fixed population
    # size (e.g. the paper's 100000).
    # =========================================================

    @staticmethod
    def _plotting_position(present_values: pd.Series, method: str) -> pd.Series:
        ranks = present_values.rank(method=method)
        n = (
            config.NM_REFERENCE_N
            if config.NM_REFERENCE_N is not None
            else len(present_values)
        )
        a = config.BLOM_A
        return (ranks - a) / (n + 1 - 2 * a)
