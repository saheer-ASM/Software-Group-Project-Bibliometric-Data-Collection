"""Entry point.

    python run_extraction.py --all                # both cohorts
    python run_extraction.py --general            # 1,000 field-spread authors
    python run_extraction.py --laureates          # 50 prize winners
    python run_extraction.py --all --general-target 200   # quick smoke run

Re-running resumes from cache/*.jsonl; pass --fresh to start over.
"""

import argparse
import os
import sys

import pandas as pd

import collect_general
import collect_laureates
import config
from openalex import BudgetExhausted, OpenAlexClient
from profiling import career_factor, classify_high_self_citer
from wikidata import WikidataClient

# Author names carry accents; a Windows console defaults to cp1252 and would
# crash on them.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GENERAL_COLUMNS = [
    "openalex_id", "display_name", "orcid", "assigned_field", "slot_bucket",
    "openalex_top_topic", "openalex_subfield", "openalex_field",
    "works_count", "cited_by_count", "h_index", "i10_index",
    "mean_citedness_2yr", "first_publication_year",
    "years_since_first_publication", "career_bucket", "bucket_matched",
    "career_factor_cf_com",
    "self_citation_ratio", "self_references", "total_references",
    "works_inspected", "high_self_citer", "last_known_institution",
    "country_code",
]
LAUREATE_COLUMNS = (["assigned_prize", "awards", "award_year", "match_method",
                     "wikidata_id"]
                    + [c for c in GENERAL_COLUMNS
                       if c not in ("assigned_field", "slot_bucket",
                                    "bucket_matched")])


def _frame(rows, columns):
    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=columns)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    # Rows replayed from a checkpoint carry the flag computed under whatever
    # threshold was in force when they were collected.  Re-derive it from the
    # stored ratio so --self-citation-threshold applies to cached rows too,
    # without spending a single API call.
    frame["high_self_citer"] = frame["self_citation_ratio"].map(
        lambda ratio: classify_high_self_citer(
            None if pd.isna(ratio) else float(ratio)))
    # Likewise derived, so rows checkpointed before CF_com existed still get it.
    frame["career_factor_cf_com"] = frame["years_since_first_publication"].map(
        lambda t: None if pd.isna(t) else round(career_factor(int(t)), 6))
    return frame[columns]


def _ratio_percentiles(cohort, frame):
    """Self-citation ratio spread, so HIGH_SELF_CITATION_MIN can be re-picked
    from the collected data instead of guessed before collecting."""
    measured = frame["self_citation_ratio"].dropna()
    rows = [{"cohort": cohort, "dimension": "self_citation_ratio",
             "value": "measurable authors", "authors": int(len(measured)),
             "share": round(len(measured) / len(frame), 4) if len(frame) else 0.0}]
    if measured.empty:
        return rows
    for label, quantile in (("median", 0.50), ("p75", 0.75),
                            ("p90", 0.90), ("max", 1.00)):
        rows.append({"cohort": cohort, "dimension": "self_citation_ratio",
                     "value": label, "authors": None,
                     "share": round(float(measured.quantile(quantile)), 4)})
    return rows


def _distribution(general, laureates):
    """The checks the sheet actually asks for, as a one-look table."""
    lines = []

    def add(cohort, dimension, value, count, total):
        lines.append({"cohort": cohort, "dimension": dimension,
                      "value": value, "authors": count,
                      "share": round(count / total, 4) if total else 0.0})

    if not general.empty:
        total = len(general)
        add("general", "total", "authors", total, total)
        add("general", "field_coverage", "fields with >=1 author",
            general["assigned_field"].nunique(), len(config.FIELDS))
        for bucket, count in general["career_bucket"].value_counts(dropna=False).items():
            add("general", "career_bucket", str(bucket), int(count), total)
        for flag, count in general["high_self_citer"].value_counts(dropna=False).items():
            add("general", "high_self_citer", str(flag), int(count), total)
        add("general", "bucket_matched", "career bucket as planned",
            int(general["bucket_matched"].fillna(False).sum()), total)
        lines.extend(_ratio_percentiles("general", general))

    if not laureates.empty:
        total = len(laureates)
        add("laureate", "total", "authors", total, total)
        for prize, count in laureates["assigned_prize"].value_counts().items():
            add("laureate", "prize", str(prize), int(count), total)
        for bucket, count in laureates["career_bucket"].value_counts(dropna=False).items():
            add("laureate", "career_bucket", str(bucket), int(count), total)
        for method, count in laureates["match_method"].value_counts().items():
            add("laureate", "match_method", str(method), int(count), total)
        for flag, count in laureates["high_self_citer"].value_counts(dropna=False).items():
            add("laureate", "high_self_citer", str(flag), int(count), total)
        lines.extend(_ratio_percentiles("laureate", laureates))

    if not general.empty and not laureates.empty:
        overlap = set(general["openalex_id"]) & set(laureates["openalex_id"])
        add("both", "overlap", "authors in both cohorts", len(overlap),
            len(general) + len(laureates))

    return pd.DataFrame(lines)


def write_outputs(general, laureates, field_report, prize_report):
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    if not general.empty:
        general.to_csv(config.GENERAL_CSV, index=False, encoding="utf-8-sig")
    if not laureates.empty:
        laureates.to_csv(config.LAUREATE_CSV, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(config.WORKBOOK, engine="openpyxl") as writer:
        _distribution(general, laureates).to_excel(
            writer, sheet_name="distribution_summary", index=False)
        if not general.empty:
            general.to_excel(writer, sheet_name="general_authors", index=False)
        if not laureates.empty:
            laureates.to_excel(writer, sheet_name="laureate_authors", index=False)
        if field_report:
            pd.DataFrame(field_report).to_excel(
                writer, sheet_name="field_coverage", index=False)
        if prize_report:
            pd.DataFrame(prize_report).to_excel(
                writer, sheet_name="prize_coverage", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--general", action="store_true")
    parser.add_argument("--laureates", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--general-target", type=int,
                        default=config.TARGET_GENERAL_AUTHORS)
    parser.add_argument("--laureate-target", type=int,
                        default=config.TARGET_LAUREATE_AUTHORS)
    parser.add_argument("--fresh", action="store_true",
                        help="ignore checkpoints and collect from scratch")
    parser.add_argument("--self-citation-threshold", type=float, default=None,
                        help="override HIGH_SELF_CITATION_MIN; re-reports cached "
                             "rows at the new cut with no extra API calls")
    args = parser.parse_args()

    if args.self_citation_threshold is not None:
        config.HIGH_SELF_CITATION_MIN = args.self_citation_threshold
        print(f"high self-citer threshold: {config.HIGH_SELF_CITATION_MIN}")

    run_general = args.general or args.all or not (args.general or args.laureates)
    run_laureates = args.laureates or args.all

    client = OpenAlexClient()
    general_rows, field_report = [], []
    laureate_rows, prize_report = [], []

    try:
        _run(client, args, run_general, run_laureates,
             general_rows, field_report, laureate_rows, prize_report)
    except BudgetExhausted as exc:
        # Raised only from the field-map build; the collectors handle their own.
        print(f"\n!! {exc}")
        print(f"   resumes at {exc.reset_text}; re-run to continue")

    general = _frame(general_rows, GENERAL_COLUMNS)
    laureates = _frame(laureate_rows, LAUREATE_COLUMNS)
    write_outputs(general, laureates, field_report, prize_report)

    print(f"\ngeneral authors : {len(general)} / {args.general_target}")
    print(f"laureate authors: {len(laureates)} / {args.laureate_target}")
    print(f"openalex calls  : {client.request_count}")
    if client.requests_remaining is not None:
        print(f"daily budget    : {client.requests_remaining} requests "
              f"(${client.budget_remaining_usd}) left today")
    print(f"workbook        : {config.WORKBOOK}")
    print("\n" + _distribution(general, laureates).to_string(index=False))


def _run(client, args, run_general, run_laureates,
         general_rows, field_report, laureate_rows, prize_report):
    if run_general:
        print(f"== general cohort: target {args.general_target} "
              f"over {len(config.FIELDS)} fields ==")
        rows, report = collect_general.collect(
            client, target=args.general_target, resume=not args.fresh)
        general_rows.extend(rows)
        field_report.extend(report)

    if run_laureates:
        print(f"== laureate cohort: target {args.laureate_target} "
              f"over {len(config.PRIZES)} prizes ==")
        rows, report = collect_laureates.collect(
            client, WikidataClient(), target=args.laureate_target,
            resume=not args.fresh)
        laureate_rows.extend(rows)
        prize_report.extend(report)


if __name__ == "__main__":
    main()
