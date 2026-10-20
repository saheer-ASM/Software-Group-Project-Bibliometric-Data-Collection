"""Phase 3: stored-value coverage and descriptive quality only; no metric calculation."""

import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from statistics import mean, median, stdev

from src.config import PROJECT_ROOT
from src.data_loader import inspect_sources, NM_COLUMNS
from src.metric_mapping import SOURCES, REQUIRED, required_mapping


def finite(value):
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError, OverflowError):
        return False


def describe(source, records, authors):
    ids = Counter(str(row[source.id_column]) for row in records if row.get(source.id_column) is not None)
    values = [float(row[source.column]) for row in records if finite(row.get(source.column))]
    eligible = {str(row[source.id_column]) for row in records if row.get(source.id_column) is not None and finite(row.get(source.column))} & authors
    valid_rows = [row for row in records if finite(row.get(source.column))]
    result = dict(metric=source.label, source_table=source.table, source_column=source.column,
                  grain=source.grain, rows=len(records), null_count=sum(row.get(source.column) is None for row in records),
                  nonfinite_count=sum(row.get(source.column) is not None and not finite(row[source.column]) for row in records),
                  null_author_ids=sum(row.get(source.id_column) is None for row in records),
                  duplicate_author_ids=sum(n > 1 for n in ids.values()),
                  excess_author_rows=sum(n - 1 for n in ids.values()),
                  orphan_author_ids=len(set(ids) - authors), authors_available=len(eligible),
                  minimum=min(values) if values else None, maximum=max(values) if values else None,
                  mean=mean(values) if values else None, median=median(values) if values else None,
                  sample_stddev=stdev(values) if len(values) > 1 else None,
                  negative_values=sum(value < 0 for value in values),
                  values_with_incomplete_status=sum(row.get(source.status) not in (True, 'READY') for row in valid_rows) if source.status else None)
    if source.grain == 'paper-author':
        keys = Counter((row.get('cited_pub_id'), row.get(source.id_column)) for row in records)
        result['duplicate_composite_keys'] = sum(n > 1 for n in keys.values())
    return result, eligible


def save_csv(name, rows, fields):
    with (PROJECT_ROOT / 'results' / name).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def build_preview(data, usable, authors):
    author_rows = data.get('author', [])
    counts = Counter(str(row['author_id']) for row in author_rows if row.get('author_id') is not None)
    names = {str(row['author_id']): row.get('author_name') for row in author_rows if row.get('author_id') is not None and counts[str(row['author_id'])] == 1}
    maps = {}
    for source in SOURCES:
        if source.grain != 'author' or 'legacy' in source.output or not usable.get(source.label):
            continue
        rows = data.get(source.table, [])
        ids = Counter(str(row[source.id_column]) for row in rows if row.get(source.id_column) is not None)
        maps[source.output] = {str(row[source.id_column]): row[source.column] for row in rows
                               if row.get(source.id_column) is not None and ids[str(row[source.id_column])] == 1
                               and finite(row.get(source.column)) and str(row[source.id_column]) in authors}
    candidates = sorted(set(names) & set().union(*(set(m) for m in maps.values()))) if maps else []
    selected = sorted(candidates, key=lambda key: (key not in maps.get('nm_index', {}), key))[:20]
    nm_rows = data.get('author_nm_index', [])
    nm_counts = Counter(str(row['author_id']) for row in nm_rows if row.get('author_id') is not None)
    nm = {str(row['author_id']): row for row in nm_rows if row.get('author_id') is not None and nm_counts[str(row['author_id'])] == 1}
    metadata = [key for key in NM_COLUMNS if key not in ('author_id', 'nm_index') and any(row.get(key) is not None for row in nm_rows)]
    preview = []
    for key in selected:
        row = dict(author_id=key, author_name=names[key])
        row.update({column: records.get(key) for column, records in maps.items()})
        row.update({column: nm.get(key, {}).get(column) for column in metadata})
        preview.append(row)
    return preview, ['author_id', 'author_name', *maps.keys(), *metadata]


def write_report(summary, mapping, quality, coverage, schema):
    lines = ['# Phase 3: source mapping and stored-value inspection', '',
             f"Author cohort: {summary['distinct_authors']} distinct authors.",
             f"Inspection interval (UTC): {summary['started_at_utc']} to {summary['finished_at_utc']}", '',
             '## Required metric availability', '',
             '| Metric | Available | Needs future calculation | Notes |', '|---|---|---|---|']
    for row in mapping:
        lines.append(f"| {row['metric']} | {row['available']} | {row['requires_calculation']} | {row['notes']} |")
    lines += ['', '## Stored sources and coverage', '',
              '| Source | Exact column | Authors | NULL rows | Duplicate author IDs | Min | Max | Mean | Median |',
              '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for row in quality:
        lines.append('| ' + ' | '.join(str(row.get(key, '')) for key in ('metric',)) +
                     f" | {row['source_table']}.{row['source_column']} | " +
                     ' | '.join(str(row.get(key, '')) for key in ('authors_available', 'null_count', 'duplicate_author_ids', 'minimum', 'maximum', 'mean', 'median')) + ' |')
    lines += ['', 'NULL counts refer to rows actually present in each source, not missing author rows. Coverage counts finite values (including zero) on distinct IDs in public.author.',
              'Repeated author IDs are expected for paper-author rows; use (cited_pub_id, target_author_id) to check duplicate records. No paper values were aggregated into author metrics.', '',
              '## Exact source contracts', '',
              '- NM: author_nm_index.author_id is the author key; nm_index is final. The six per_* columns are stored component percentiles. metrics_available is the component-count indicator, not a separate boolean completeness flag; calculated_at is its timestamp.',
              '- Total Cites Score: author_total_cites.author_id, total_cites_score, career_factor, calculation_complete, calculated_at. This table has no separately stored raw/adjusted citation totals. Its score is normalized/weighted, not raw Total cites.',
              '- Adjusted citation inputs: author_paper_adjusted_citations.cited_pub_id, target_author_id, citing_paper_count, field_row_count, total_raw_citation, total_adjusted_citation, calculated_at. Values are per paper-author, and raw_citation here must not be assumed to be a simple integer citation count.',
              '- Modified hm is author.modified_hm_index. Modified g has two locations, reported separately. author.nm_index is only a mirror and is not used as the final source.', '',
              '## NM-index distribution', '', '```json', json.dumps(summary['nm_index'], indent=2), '```', '',
              '## Quality and interpretation', '',
              '- See metric_data_quality.csv for nonfinite/negative values, orphan IDs, duplicate IDs, status conflicts, and sample standard deviation. Values marked incomplete are reported, never silently discarded.',
              '- Per-metric summaries are descriptive statistics of stored values, not recalculated metrics.',
              '- Source reads use separate read-only transactions. Concurrent pipeline updates can cause cross-table timing differences; this is not a single consistent snapshot.',
              '- This is a Phase 3 stored-value snapshot. For current conventional baseline definitions and source conflicts, see results/baseline_metric_specification.md and results/source_consistency_audit.md.', '',
              '## Proposed final dataset', '',
              'One row per public.author.author_id with author_name, the verified NM result, its six percentile components, metrics_available, and calculation timestamp. Store the required 11 baselines only after their definitions/sources have been verified in a later authorized phase. Keep modified component values and any mirror columns explicitly labelled as auxiliary fields; include provenance and completeness flags.',
              'The current preview contains at most 20 deterministic IDs with available stored values. It is not a representative sample. Unknown values are blank, never imputed as zero. Duplicate author-level source IDs are excluded from preview joins rather than arbitrarily collapsed.',
              'Actual preview columns: ' + ', '.join(summary['preview_columns']), '',
              '## Execution and safety', '',
              'Run `.\\.venv\\Scripts\\python.exe -B -m experiments.inspect_author_coverage` from the validation project.',
              'All database operations use src.database.execute_select. No existing calculation scripts are imported or run. No metrics, correlations, paired tests, ICC, PCA, or ROC/AUC are calculated. No database writes, migrations, commits, or pushes are performed.', '']
    (PROJECT_ROOT / 'results' / 'phase3_mapping_report.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    started = datetime.now(timezone.utc).isoformat()
    schema, columns, verified, data = inspect_sources()
    author_rows = data.get('author', [])
    authors = {str(row['author_id']) for row in author_rows if row.get('author_id') is not None}
    if not authors:
        raise RuntimeError('No author cohort available; no coverage report can be generated.')
    quality, usable, coverage = [], {}, []
    for source in SOURCES:
        if {source.column, source.id_column} <= columns.get(source.table, set()):
            stats, available = describe(source, data.get(source.table, []), authors)
            quality.append(stats)
            usable[source.label] = available
            coverage.append(dict(metric=source.label, authors_available=len(available), total_authors=len(authors), coverage_percentage=100 * len(available) / len(authors)))
    for metric, *_ in REQUIRED:
        if metric != 'NM-index':
            coverage.append(dict(metric=metric, authors_available=None, total_authors=len(authors), coverage_percentage=None))
    mapping = required_mapping({key: len(value) for key, value in usable.items()})
    preview, preview_fields = build_preview(data, usable, authors)
    nm_rows = data.get('author_nm_index', [])
    percentile_cols = [c for c in NM_COLUMNS if c.startswith('per_')]
    scores = [float(row['nm_index']) for row in nm_rows if finite(row.get('nm_index'))]
    nm_summary = dict(rows=len(nm_rows), nonnull_finite_scores=len(scores),
                      minimum=min(scores) if scores else None, maximum=max(scores) if scores else None,
                      mean=mean(scores) if scores else None, median=median(scores) if scores else None,
                      sample_standard_deviation=stdev(scores) if len(scores) > 1 else None,
                      number_ge_90=sum(v >= 90 for v in scores), number_ge_95=sum(v >= 95 for v in scores),
                      number_ge_99=sum(v >= 99 for v in scores), number_eq_100=sum(v == 100 for v in scores),
                      outside_0_100=sum(v < 0 or v > 100 for v in scores),
                      metrics_available_distribution=dict(Counter(str(row.get('metrics_available')) for row in nm_rows)),
                      component_count_mismatches=sum(row.get('metrics_available') != sum(row.get(c) is not None for c in percentile_cols) for row in nm_rows),
                      component_null_counts={c: sum(row.get(c) is None for row in nm_rows) for c in percentile_cols},
                      scored_with_fewer_than_six_components=sum(finite(row.get('nm_index')) and (row.get('metrics_available') or 0) < 6 for row in nm_rows))
    save_csv('metric_availability.csv', mapping, ['metric', 'available', 'source_table', 'source_columns', 'requires_calculation', 'notes'])
    save_csv('author_metric_coverage.csv', coverage, ['metric', 'authors_available', 'total_authors', 'coverage_percentage'])
    save_csv('validation_dataset_preview.csv', preview, preview_fields)
    quality_fields = list(dict.fromkeys(key for row in quality for key in row))
    save_csv('metric_data_quality.csv', quality, quality_fields)
    save_csv('phase3_schema_columns.csv', schema, ['table_name', 'column_name', 'data_type', 'is_nullable'])
    save_csv('phase3_table_verification.csv', verified, ['table', 'status', 'columns'])
    candidates = [row for row in schema if any(term in row['column_name'].lower() for term in ('index', 'score', 'citation', 'cites'))]
    save_csv('metric_column_candidates.csv', candidates, ['table_name', 'column_name', 'data_type', 'is_nullable'])
    summary = dict(started_at_utc=started, finished_at_utc=datetime.now(timezone.utc).isoformat(),
                   total_author_rows=len(author_rows), distinct_authors=len(authors),
                   duplicate_author_rows=len(author_rows) - len(authors), nm_index=nm_summary,
                   preview_rows=len(preview), preview_columns=preview_fields,
                   scope='Stored values only. No metric recomputation; sample stddev uses n-1. Each SELECT has its own read-only transaction, not a shared snapshot.',
                   baseline_definitions='Phase 3 checked stored values only. For current definitions, see baseline_metric_specification.md; modified components and legacy candidates are separate from conventional baselines.',
                   coverage_notes='Unique non-null finite-valued author IDs intersected with public.author. Missing baseline coverage is blank (unknown), not zero. Paper-author values are not aggregated into author-level metrics.',
                   preview_notes='Deterministic first 20 eligible IDs, prioritizing NM availability; not a representative sample. Blank cells mean missing values or duplicate source IDs; no zero imputation. Mirrors are labelled separately.')
    (PROJECT_ROOT / 'results' / 'phase3_inspection_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    write_report(summary, mapping, quality, coverage, schema)
    print(json.dumps(summary, indent=2))
    for row in coverage:
        print(f"{row['metric']}: {row['authors_available']} / {row['total_authors']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
