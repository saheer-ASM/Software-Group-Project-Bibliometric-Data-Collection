"""Read-only data inventory for the fixed 995-author study cohort.

This module does not calculate bibliometric metrics. All database reads use
the project's SELECT-only, read-only transaction interface.
"""

import csv
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .database import execute_select_batch


ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "995_authors.csv"
RESULTS = ROOT / "results"
SLOTS = range(1, 11)


def read_cohort():
    with COHORT.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["author_id", "author_name"]:
            raise ValueError("Cohort must have author_id,author_name columns")
        rows = list(reader)
    ids = [row["author_id"].strip() for row in rows]
    if len(rows) != 995 or len(set(ids)) != 995 or any(not value for value in ids):
        raise ValueError("Cohort must contain exactly 995 unique, nonblank IDs")
    if any(not row["author_name"].strip() for row in rows):
        raise ValueError("Cohort contains a blank author name")
    return rows, ids


def select_ids(table, columns, ids, id_column="author_id"):
    return (f"SELECT {columns} FROM public.{table} WHERE {id_column} = ANY(%s)", (ids,))


def write_csv(name, columns, rows):
    with (RESULTS / name).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def percentage(numerator, denominator):
    return f"{100 * numerator / denominator:.1f}%" if denominator else "n/a"


def main():
    cohort, ids = read_cohort()
    cohort_set = set(ids)
    digest = hashlib.sha256(COHORT.read_bytes()).hexdigest()
    slot_ids = ", ".join(f"author{i}id" for i in SLOTS)
    slot_weights = ", ".join(f"author{i}id_weight" for i in SLOTS)
    linked_where = " OR ".join(f"author{i}id = ANY(%s)" for i in SLOTS)
    first = execute_select_batch({
        "authors": select_ids("author", "author_id, author_name", ids),
        "links": (
            f"SELECT pub_id, author_ordering_norm, {slot_ids}, {slot_weights} "
            f"FROM public.author_contribution_weight WHERE {linked_where}",
            tuple([ids] * 10),
        ),
        "nm": select_ids(
            "author_nm_index",
            "author_id, nm_index, metrics_available, per_total_cites, "
            "per_citations_per_paper, per_citation_rate, per_modified_hf_index, "
            "per_modified_hm_index, per_modified_g_index", ids,
        ),
        "t": select_ids("author_total_cites", "author_id, total_cites_score, first_publication_year, as_of_year, career_time_years", ids),
        "s": select_ids("author_citations_per_paper", "author_id, citations_per_paper_score", ids),
        "u": select_ids("author_citation_rate", "author_id, citation_rate_score", ids),
        "hf": select_ids("author_modified_hindex", "author_id, modified_hindex_final", ids),
        "hm": select_ids("author", "author_id, modified_hm_index", ids),
        "g": select_ids("modified_g_index_results", "author_id, modified_g_index", ids),
        "adjusted": select_ids("author_paper_adjusted_citations", "cited_pub_id, target_author_id, total_adjusted_citation", ids, "target_author_id"),
        "isc": select_ids("influential_self_citations", "cited_pub_id, citing_pub_id, target_author_id, isc_value", ids, "target_author_id"),
    })
    pub_ids = list({row["pub_id"] for row in first["links"] if row["pub_id"] is not None})
    second = execute_select_batch({
        "pubs": select_ids("publication", "pub_id, year, total_citation, source", pub_ids, "pub_id"),
        "fields": select_ids("field_classification", "pub_id, field1_name, field1_weight, field2_name, field2_weight, field3_name, field3_weight", pub_ids, "pub_id"),
        "citations": select_ids("citation", "pub_id, cites_pub_id", pub_ids, "pub_id"),
        "adjusted_pubs": select_ids("author_paper_adjusted_citations", "cited_pub_id, target_author_id, total_adjusted_citation", pub_ids, "cited_pub_id"),
    })
    citing_ids = list({row["cites_pub_id"] for row in second["citations"] if row["cites_pub_id"] is not None})
    third = execute_select_batch({
        "citing_pubs": select_ids("publication", "pub_id", citing_ids, "pub_id"),
        "citing_authorship": select_ids("author_contribution_weight", f"pub_id, {slot_ids}", citing_ids, "pub_id"),
        "year_benchmarks": ("SELECT field_name, publication_year, citation_avg_field_and_year FROM public.field_year_adjusted_citation_average", ()),
        "field_benchmarks": ("SELECT field_name, citation_avg_field FROM public.field_adjusted_citation_average", ()),
        "field_caps": ("SELECT field_name, percentile_k, cap_threshold FROM public.field_citation_percentile_caps", ()),
    })

    by_author = defaultdict(list)
    by_pub_links = defaultdict(list)
    for row in first["links"]:
        by_pub_links[row["pub_id"]].append(row)
        for i in SLOTS:
            author_id = row[f"author{i}id"]
            if author_id in cohort_set:
                by_author[author_id].append((row["pub_id"], i, row))
    author_rows = defaultdict(list)
    for row in first["authors"]:
        author_rows[row["author_id"]].append(row)
    pubs = defaultdict(list)
    for row in second["pubs"]:
        pubs[row["pub_id"]].append(row)
    fields = defaultdict(list)
    for row in second["fields"]:
        fields[row["pub_id"]].append(row)
    edges = defaultdict(list)
    for row in second["citations"]:
        edges[row["pub_id"]].append(row)
    adjusted = defaultdict(list)
    for row in second["adjusted_pubs"]:
        adjusted[(row["cited_pub_id"], row["target_author_id"])].append(row)
    nm = defaultdict(list)
    for row in first["nm"]:
        nm[row["author_id"]].append(row)
    component_sources = {}
    for key, column in (("t", "total_cites_score"), ("s", "citations_per_paper_score"),
                        ("u", "citation_rate_score"), ("hf", "modified_hindex_final"),
                        ("hm", "modified_hm_index"), ("g", "modified_g_index")):
        component_sources[key] = {row["author_id"] for row in first[key] if row[column] is not None}
    available_citing_pubs = {row["pub_id"] for row in third["citing_pubs"]}
    available_citing_authorship = {row["pub_id"] for row in third["citing_authorship"]}
    field_year_benchmarks = {(row["field_name"], row["publication_year"]) for row in third["year_benchmarks"] if row["citation_avg_field_and_year"] is not None}
    field_benchmarks = {row["field_name"] for row in third["field_benchmarks"] if row["citation_avg_field"] is not None}
    field_caps = {row["field_name"] for row in third["field_caps"] if row["cap_threshold"] is not None}

    authors_output, pubs_output, readiness_output = [], [], []
    for selected in cohort:
        aid, selected_name = selected["author_id"], selected["author_name"]
        db_names = [row["author_name"] for row in author_rows[aid]]
        found = bool(db_names)
        name_match = found and any(" ".join((name or "").split()).casefold() == " ".join(selected_name.split()).casefold() for name in db_names)
        authors_output.append(dict(author_id=aid, selected_author_name=selected_name,
                                   database_author_name=" | ".join(str(name or "") for name in db_names),
                                   author_exists=str(found).lower(), name_match=str(name_match).lower() if found else "",
                                   status="NOT_FOUND" if not found else "FOUND" if name_match else "NAME_DIFFERENCE"))
        links = by_author[aid]
        unique_pubs = {item[0] for item in links if item[0] is not None}
        duplicate_links = len(links) - len(unique_pubs)
        repeated_author_pubs = len(links) - len({(item[0], item[1]) for item in links})
        orphans = sum(len(pubs[pid]) != 1 for pid in unique_pubs)
        pub_status = "NOT_FOUND" if not found else "NO_LINKS" if not links else "INCOMPLETE" if orphans or duplicate_links or repeated_author_pubs else "LINKED"
        pubs_output.append(dict(author_id=aid, publication_count=len(links),
                                unique_publication_count=len(unique_pubs),
                                duplicate_relationship_count=duplicate_links,
                                repeated_author_publication_count=repeated_author_pubs,
                                orphan_relationship_count=orphans, status=pub_status))
        reasons = []
        if found:
            if len(db_names) > 1:
                reasons.append("duplicate author records")
            if not links:
                reasons.append("no linked publications")
            if orphans:
                reasons.append(f"{orphans} orphan or ambiguous publication links")
            if duplicate_links or repeated_author_pubs:
                reasons.append("duplicate author-publication relationship")
            if any(not pubs[pid] or pubs[pid][0]["year"] is None for pid in unique_pubs):
                reasons.append("missing publication year")
            if any(not pubs[pid] or pubs[pid][0]["total_citation"] is None for pid in unique_pubs):
                reasons.append("missing publication citation count")
            if any(not fields[pid] or not any(fields[pid][0][f"field{i}_name"] for i in (1, 2, 3)) for pid in unique_pubs):
                reasons.append("missing publication field")
            if any(item[2]["author_ordering_norm"] is None or item[2][f"author{item[1]}id_weight"] is None for item in links):
                reasons.append("missing ordering or contribution weight")
            if any(pubs[pid] and pubs[pid][0]["total_citation"] and not edges[pid] for pid in unique_pubs):
                reasons.append("positive stored citations but no citation edges")
            if any(not adjusted[(pid, aid)] for pid in unique_pubs):
                reasons.append("missing author-paper adjusted citations")
            if not nm[aid] or all(row["nm_index"] is None for row in nm[aid]):
                reasons.append("missing stored NM-index")
            if len(nm[aid]) > 1:
                reasons.append("duplicate NM-index records")
            if any(aid not in source for source in component_sources.values()):
                reasons.append("missing stored NM component source")
            # The ten-slot relation and an unverified external portfolio cannot prove
            # full publication or coauthor completeness for any selected author.
            reasons.append("complete publication portfolio and coauthor lists not independently verified")
        readiness_output.append(dict(author_id=aid, readiness="NOT_FOUND" if not found else "INCOMPLETE",
                                     reason="author ID absent from database" if not found else "; ".join(reasons)))

    found_ids = {row["author_id"] for row in first["authors"]}
    found_count = len(found_ids)
    linked_pub_ids = set(pub_ids)
    present_pub_ids = set(pubs)
    missing_year = {pid for pid in linked_pub_ids if not pubs[pid] or pubs[pid][0]["year"] is None}
    missing_count = {pid for pid in linked_pub_ids if not pubs[pid] or pubs[pid][0]["total_citation"] is None}
    missing_field = {pid for pid in linked_pub_ids if not fields[pid] or not any(fields[pid][0][f"field{i}_name"] for i in (1, 2, 3))}
    missing_order = {pid for pid in linked_pub_ids if not by_pub_links[pid] or any(row["author_ordering_norm"] is None for row in by_pub_links[pid])}
    missing_weight = {pid for pid in linked_pub_ids if any(row[f"author{i}id"] and row[f"author{i}id_weight"] is None for row in by_pub_links[pid] for i in SLOTS)}
    duplicate_pub_rows = {pid for pid in linked_pub_ids if len(pubs[pid]) > 1}
    duplicate_link_rows = {pid for pid in linked_pub_ids if len(by_pub_links[pid]) > 1}
    duplicate_slots = {pid for pid in linked_pub_ids if any(len([row[f"author{i}id"] for i in SLOTS if row[f"author{i}id"]]) != len(set(row[f"author{i}id"] for i in SLOTS if row[f"author{i}id"])) for row in by_pub_links[pid])}
    empty_slots = {pid for pid in linked_pub_ids if any(not any(row[f"author{i}id"] for i in SLOTS) for row in by_pub_links[pid])}
    full_ten_slots = {pid for pid in linked_pub_ids if any(all(row[f"author{i}id"] for i in SLOTS) for row in by_pub_links[pid])}
    edge_pairs = [(row["pub_id"], row["cites_pub_id"]) for row in second["citations"]]
    duplicate_edges = sum(count - 1 for count in Counter(edge_pairs).values() if count > 1)
    orphan_citing = sum(1 for _, citing in edge_pairs if citing not in available_citing_pubs)
    no_citing_authorship = sum(1 for _, citing in edge_pairs if citing not in available_citing_authorship)
    positive_without_edges = {pid for pid in linked_pub_ids if pubs[pid] and pubs[pid][0]["total_citation"] and not edges[pid]}
    edge_count_mismatch = {pid for pid in linked_pub_ids if pubs[pid] and pubs[pid][0]["total_citation"] is not None and len(edges[pid]) != pubs[pid][0]["total_citation"]}
    field_year_missing = set()
    field_mean_missing = set()
    cap_missing = set()
    for pid in linked_pub_ids:
        if not pubs[pid] or not fields[pid]:
            continue
        year = pubs[pid][0]["year"]
        for index in (1, 2, 3):
            name = fields[pid][0][f"field{index}_name"]
            if not name:
                continue
            if (name, year) not in field_year_benchmarks:
                field_year_missing.add(pid)
            if name not in field_benchmarks:
                field_mean_missing.add(pid)
            if name not in field_caps:
                cap_missing.add(pid)
    affected = lambda paper_set: len({aid for aid in found_ids if any(pid in paper_set for pid, _, _ in by_author[aid])})
    adjusted_coverage = {aid for aid in found_ids if by_author[aid] and all(adjusted[(pid, aid)] for pid, _, _ in by_author[aid])}
    isc_ids = {row["target_author_id"] for row in first["isc"]}
    nm_nonnull = {aid for aid in found_ids if any(row["nm_index"] is not None for row in nm[aid])}
    nm_null = {aid for aid in found_ids if nm[aid] and all(row["nm_index"] is None for row in nm[aid])}
    nm_duplicates = {aid for aid in found_ids if len(nm[aid]) > 1}
    component_names = {
        "t": "T_a — field/year-normalized total cites",
        "s": "S_a — capped citations per paper",
        "u": "U_a — citation rate",
        "hf": "Hf′_a — modified fractional h",
        "hm": "Hm′_a — modified multi-author h",
        "g": "G′_a — modified g",
    }
    component_inputs = {
        "t": "linked papers; years; citation edges/ISC-adjusted author-paper counts; contribution; field/year means; career start",
        "s": "T inputs; field means; field citation percentile caps; paper count",
        "u": "T inputs; field/year means; publication age; caps",
        "hf": "complete authorship; contribution; adjusted counts; caps; career factor; field reference",
        "hm": "Hf′ inputs; complete author order and effective rank",
        "g": "Hf′ inputs; ordered paper citations; field reference",
    }
    # Strict input coverage: all observed linked papers need the common data;
    # unverified full portfolios and beyond-ten coauthors remain separate blockers.
    common_ok = {aid for aid in found_ids if by_author[aid] and all(
        pid in present_pub_ids and pid not in missing_year | missing_count | missing_field | missing_order | missing_weight | field_year_missing
        and bool(adjusted[(pid, aid)]) for pid, _, _ in by_author[aid])}
    provisional = {
        "t": common_ok,
        "s": {aid for aid in common_ok if all(pid not in field_mean_missing | cap_missing for pid, _, _ in by_author[aid])},
        "u": {aid for aid in common_ok if all(pid not in cap_missing for pid, _, _ in by_author[aid])},
        "hf": {aid for aid in common_ok if all(pid not in cap_missing | field_mean_missing | duplicate_slots | empty_slots for pid, _, _ in by_author[aid])},
        "hm": {aid for aid in common_ok if all(pid not in cap_missing | field_mean_missing | duplicate_slots | empty_slots for pid, _, _ in by_author[aid])},
        "g": {aid for aid in common_ok if all(pid not in cap_missing | field_mean_missing | duplicate_slots | empty_slots for pid, _, _ in by_author[aid])},
    }
    for row in readiness_output:
        aid = row["author_id"]
        if aid not in found_ids:
            continue
        author_pubs = {pid for pid, _, _ in by_author[aid]}
        extras = []
        if author_pubs & field_year_missing:
            extras.append("missing field/year adjusted citation benchmark")
        if author_pubs & cap_missing:
            extras.append("missing field citation cap")
        if author_pubs & edge_count_mismatch:
            extras.append("stored citation count differs from edge count")
        if any(row["cites_pub_id"] not in available_citing_authorship for pid in author_pubs for row in edges[pid]):
            extras.append("citing publication lacks authorship row")
        if extras:
            row["reason"] += "; " + "; ".join(extras)
    write_csv("phase6_author_coverage.csv", ["author_id", "selected_author_name", "database_author_name", "author_exists", "name_match", "status"], authors_output)
    write_csv("phase6_publication_coverage.csv", ["author_id", "publication_count", "unique_publication_count", "duplicate_relationship_count", "repeated_author_publication_count", "orphan_relationship_count", "status"], pubs_output)
    write_csv("phase6_author_readiness.csv", ["author_id", "readiness", "reason"], readiness_output)
    component_lines = []
    for key in component_names:
        n = len(provisional[key])
        component_lines.append(f"| {component_names[key]} | {component_inputs[key]} | 0 verified ({n} partial observed-data candidates) | 995 | 0% verified | INCOMPLETE |")

    status_counts = Counter(row["readiness"] for row in readiness_output)
    summary = f"""# Phase 6 — 995-author data readiness summary

Generated {datetime.now(timezone.utc).isoformat()} from the unchanged master cohort `995_authors.csv` (SHA-256 `{digest}`). Exact IDs only; no substitutions or sampling.

**Overall status: DATA_NOT_READY.** Of 995 selected authors, {found_count} ({percentage(found_count, 995)}) exist in `public.author`; {995 - found_count} do not. {status_counts['READY']} are READY, {status_counts['INCOMPLETE']} INCOMPLETE, and {status_counts['NOT_FOUND']} NOT_FOUND. Full publication portfolios and complete coauthor lists are not independently verified for any selected author.

| Requirement | Observed coverage and incomplete requirement |
|---|---|
| Selected authors | 995 unique nonblank IDs and names; {found_count} found, {995 - found_count} absent |
| Publication links | {len(first['links'])} authorship rows, {len(linked_pub_ids)} distinct linked paper IDs for matched authors; {len(present_pub_ids)} paper IDs resolve in `publication`; {len(linked_pub_ids - present_pub_ids)} orphan IDs; {sum(1 for aid in found_ids if not by_author[aid])} matched authors have no links |
| Publication metadata | {len(missing_year)} linked papers lack year ({affected(missing_year)} authors); {len(missing_count)} lack stored citation count ({affected(missing_count)} authors); {len(missing_field)} lack fields ({affected(missing_field)} authors) |
| Citation relationships | {len(edge_pairs)} cited→citing rows on linked papers; {len(positive_without_edges)} positive-count papers have zero edges; {len(edge_count_mismatch)} papers have edge-count/stored-count mismatch; {duplicate_edges} duplicate edges; {orphan_citing} edges point to absent citing publications |
| Authorship/coauthors | {len(missing_order)} papers lack ordering norm; {len(missing_weight)} have missing populated-slot weights; {len(duplicate_slots)} repeat an author within a row; {len(duplicate_link_rows)} have multiple authorship rows; {len(full_ten_slots)} fill all ten slots, so overflow cannot be excluded; {no_citing_authorship} citing edges lack citing-paper authorship rows. Full author counts and portfolio completeness remain unverified. |
| Contribution data | {len(linked_pub_ids) - len(missing_order)} linked papers have non-null ordering norm; {len(linked_pub_ids) - len(missing_weight)} have no missing weights among populated slots. Explicit ACI/CRediT provenance is not established by these columns. |
| Self-citation inputs | {len(citing_ids)} distinct citing paper IDs; {len(available_citing_authorship)} have an authorship row; {len(isc_ids)} selected authors have stored ISC rows; {len(adjusted_coverage)} matched authors have author-paper adjusted-citation rows for every observed linked paper. ISC absence may mean zero self-citations or missing processing; cannot infer which. |
| Field/year reference data | {len(field_year_missing)} papers lack at least one field/year mean; {len(field_mean_missing)} lack a field mean; {len(cap_missing)} lack a field cap; publication-year gaps affect {affected(missing_year)} matched authors. |
| Stored NM-index | {len(nm_nonnull)} matched authors have non-null `author_nm_index.nm_index`; {len(nm_null)} have a null row; {found_count - len(nm_nonnull) - len(nm_null)} have no row; {len(nm_duplicates)} have duplicate rows. `author.nm_index` is not the authoritative source. |
| Baselines | Raw Total Cites, h, g need complete linked publication counts; conventional hf additionally needs verified full coauthor counts. C-score raw/SC, hm, m, Fi, s, AR have unresolved methodology and/or inputs in source specification. No baseline was calculated. |

## Six NM component input checks

The table distinguishes presence of observed database inputs from verified full-cohort readiness. Stored component availability is separately reported below. A score present in a table does not prove its source records are complete.

| Component | Required inputs | Authors with required inputs | Authors missing inputs | Coverage | Status |
|---|---|---:|---|---|---|
{chr(10).join(component_lines)}

Stored non-null component values among matched authors: {', '.join(f'{component_names[key]} {len(component_sources[key])}/{found_count}' for key in component_names)}.

All 995 author classifications and reasons are in `phase6_author_readiness.csv`. Name differences are reported in `phase6_author_coverage.csv`; the stable ID remains authoritative. Observed author-publication relationships are in `phase6_publication_coverage.csv`.
"""
    (RESULTS / "phase6_readiness_summary.md").write_text(summary, encoding="utf-8")
    baseline = """| Baseline | Available inputs | Missing inputs / verification | Methodology status |
|---|---|---|---|
| Total Cites | Linked paper IDs and stored raw citation counts for matched authors | 987 authors absent; complete portfolios and citation semantics unverified | Formula defined; no metric run |
| C-score raw | Some raw counts, positions, fields | Complete author positions, reference distributions, standardization inputs | General algorithm unresolved in sources |
| C-score SC adjusted | Some citation edges, ISC/adjusted rows | Complete self-citation attribution and C-score adjustment rule | Unresolved; NM ISC is not this baseline |
| h-index | Linked paper counts and raw citations | Verified complete publication portfolios | Formula defined; no metric run |
| hm-index | Counts and up to ten author slots | Verified full coauthor counts and threshold rule | Ambiguous between source descriptions |
| hf-index | Counts and up to ten author slots | Independently verified full coauthor count per paper | Formula defined by latest PDF; input gated |
| g-index | Linked paper counts and raw citations | Verified complete portfolios; resolve worked-example contradiction before comparison | Formula defined for observed papers; no metric run |
| m-index | h inputs and publication years | Complete portfolios, as-of date and career-duration convention | Incomplete duration convention |
| Fi-score | Some counts and ISC rows | Threshold/reference data and exact equation | Formula unresolved |
| s-index | Some citation and ISC rows | Exact input attribution and equation | Formula unresolved |
| AR-index | Some counts and years | As-of/age convention and exact equation | Formula unresolved |
"""
    report = f"""# Phase 6 — data readiness report

**Decision: DATA_NOT_READY.** The authoritative 995-ID CSV cannot currently be matched to the connected PostgreSQL database: only {found_count} IDs exist in `public.author`. No experiment or metric calculation should start with this cohort/database pairing.

## 1. Study cohort

Source: `995_authors.csv` at the validation-project root, SHA-256 `{digest}`. Exactly 995 data rows, 995 unique nonblank `author_id` values, no blank names. File was not modified. This is the only cohort used.

## 2. Author coverage

{found_count}/995 found; {995 - found_count}/995 missing. Found IDs: {', '.join(sorted(found_ids))}. {sum(row['status'] == 'NAME_DIFFERENCE' for row in authors_output)} found IDs have a name difference after case-insensitive whitespace normalization. IDs, not names, govern matching. See `phase6_author_coverage.csv` for every selected row.

## 3. Publication coverage

For the matched IDs only: {len(first['links'])} matching authorship rows and {len(linked_pub_ids)} distinct publication IDs; {len(present_pub_ids)} resolve to publication records, {len(linked_pub_ids - present_pub_ids)} do not. {len(duplicate_link_rows)} paper IDs have multiple authorship records; {len(duplicate_pub_rows)} have multiple publication records; {len(duplicate_slots)} have duplicate author IDs within an authorship row. Counts by author and orphan/duplicate flags are in `phase6_publication_coverage.csv`. These observed records do not prove the full portfolio is present.

## 4. Citation coverage

{len(edge_pairs)} citation rows refer to the observed cited papers. {len(citing_ids)} distinct citing paper IDs occur, of which {len(available_citing_pubs)} resolve to publication records; {orphan_citing} edges have no citing publication. {duplicate_edges} repeated cited/citing pairs occur. {len(positive_without_edges)} papers have positive `publication.total_citation` but no matching `citation` rows; {len(edge_count_mismatch)} observed papers have raw edge count different from stored total. A difference may reflect distinct source/ingest semantics; it must be resolved before using edge-derived citation counts. {len(missing_count)} observed papers lack stored citation counts. No Total Cites were recalculated.

## 5. Authorship and contribution coverage

The `author_contribution_weight` relation contains author1–author10 only. There is no independently verified full author-count field in this extract. {len(full_ten_slots)} observed papers fill all ten slots, and even fewer populated slots do not prove completeness. {len(empty_slots)} papers have an empty authorship row, {len(duplicate_slots)} repeat an author ID, {len(missing_order)} lack `author_ordering_norm`, {len(missing_weight)} lack weights in populated slots. Selected-author positions are visible in the matched slots. Explicit ACI/CRediT source and category provenance remain unverified. No contribution weights were calculated.

## 6. Self-citation inputs

The database exposes cited/citing paper IDs and authorship slots. Of {len(citing_ids)} distinct citing IDs, {len(available_citing_authorship)} have authorship rows; {no_citing_authorship} edges lack a citing-paper authorship row. {len(isc_ids)} selected authors have rows in `influential_self_citations`; {len(adjusted_coverage)} matched authors have an `author_paper_adjusted_citations` row for every observed paper. Absence of ISC rows is not automatically evidence of zero self-citations. The source pipeline's cited-paper sampling and ten-slot limit require provenance review. No ISC was calculated.

## 7. Field/year coverage

Of {len(linked_pub_ids)} observed paper IDs, {len(missing_year)} lack a publication year ({affected(missing_year)} matched authors affected) and {len(missing_field)} lack a field ({affected(missing_field)} authors affected). {len(field_year_missing)} have at least one field without a matching field/year adjusted mean; {len(field_mean_missing)} lack a field mean; {len(cap_missing)} lack a field percentile cap. These are input-presence checks, not field normalization.

## 8. Stored NM-index and component input coverage

Authoritative result: `author_nm_index.nm_index`. {len(nm_nonnull)} matched authors have a non-null value, {len(nm_null)} have a null-valued row, {found_count - len(nm_nonnull) - len(nm_null)} have no row, and {len(nm_duplicates)} have duplicate rows. The six latest-manuscript components and strict observed-input candidates are tabulated in `phase6_readiness_summary.md`. None has verified complete portfolio/coauthor coverage for all 995 selected authors. Stored scores do not substitute for input verification.

## 9. Baseline input availability

The latest experiment design requires 11 baselines. The latest manuscript is authoritative for NM methodology and the baseline notes below retain unresolved definitions instead of inventing them.

{baseline}

## 10. Missing data and authors requiring attention

{995 - found_count} selected IDs are absent; exact IDs are in `phase6_author_readiness.csv`. {status_counts['INCOMPLETE']} matched authors require source-data and independent portfolio/coauthor verification. Specific missing-year, count, field, contribution, adjusted-citation, NM, and component flags are in their per-author reason fields. {status_counts['READY']} meet full readiness; nobody was silently excluded.

## 11. Decision and exact next step

**DATA_NOT_READY.** First reconcile the immutable master CSV against the intended PostgreSQL instance or correct upstream author-ID mapping, without changing the cohort or production database. Then rerun this read-only inventory and independently verify full publication portfolios and coauthor counts. Resolve citation-source semantics and unresolved baseline methodology before any experimental execution.

## Scope and safety

This audit queried only the selected cohort, their linked papers, their citing-paper references, and field benchmark metadata, using the validation project's `execute_select_batch`. Each batch enforced `transaction_read_only=on`, used a repeatable-read snapshot, rolled back and closed. Batches are separate snapshots; concurrent database changes could affect cross-batch comparisons. The only SQL statements supplied to the interface were SELECTs. No database writes, migrations, calculation scripts, statistical experiments, figure generation, commits or pushes were performed. The production project was not edited.
"""
    (RESULTS / "phase6_data_readiness_report.md").write_text(report, encoding="utf-8")
    print(f"selected=995 found={found_count} linked_pubs={len(linked_pub_ids)} ready={status_counts['READY']} incomplete={status_counts['INCOMPLETE']} not_found={status_counts['NOT_FOUND']}")


if __name__ == "__main__":
    main()
