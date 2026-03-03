"""
Author Order Classifier
=======================
Determines whether a journal uses ALPHABETICAL or CONTRIBUTION-BASED author ordering
by analyzing a large sample of papers from that journal via the Crossref API.

Pipeline:
  Step 1 — Fetch paper metadata from Crossref API (by ISSN or journal name)
  Step 2 — Normalize author family names (lowercase, remove punctuation)
  Step 3 — For each paper, check if authors are in alphabetical order
  Step 4 — Filter: only papers with >= 4 authors (reduces false positives)
  Step 5 — Compute AlphabeticalRate = alphabetical_papers / eligible_papers
  Step 6 — Classify journal using threshold rules
  Step 7 — Export per-paper results + summary to a styled Excel file

Classification Rules:
  AlphabeticalRate >= 0.75  →  Alphabetical-dominant
  AlphabeticalRate <= 0.25  →  Contribution-based
  Otherwise                 →  Mixed / Unclear

False Positive Probability (random ordering appearing alphabetical):
  n=2  →  1/2  = 50.0%   (exclude)
  n=3  →  1/6  ≈ 16.7%   (marginal)
  n=4  →  1/24 ≈  4.2%   (include)
  n=5  →  1/120 ≈ 0.8%   (strong evidence)
  n=6+ →  <0.1%           (very strong evidence)

Usage:
  python author_order_classifier.py --issn 1234-5678 --max 500
  python author_order_classifier.py --journal "Nature Communications" --max 300
  python author_order_classifier.py   # interactive prompt
"""

import re
import math
import argparse
import os
from datetime import datetime

import requests
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from dotenv import load_dotenv

load_dotenv()

CROSSREF_BASE = "https://api.crossref.org/works"
CONTACT_EMAIL = os.getenv("contact_email", "researcher@example.com")


# ── Step 1: Fetch metadata from Crossref ────────────────────────────────────

def fetch_papers_crossref(issn=None, journal_name=None, max_papers=500):
    """
    Fetch paper metadata from the Crossref API.

    Parameters
    ----------
    issn        : str  — Journal ISSN (e.g. "1476-4687")
    journal_name: str  — Journal name keyword (used if no ISSN provided)
    max_papers  : int  — Maximum number of papers to fetch

    Returns
    -------
    list of dicts with keys: doi, title, authors, year
    """
    papers = []
    rows_per_page = 100
    offset = 0

    filters = ["type:journal-article"]
    if issn:
        filters.append(f"issn:{issn}")
    filter_str = ",".join(filters)

    base_params = {
        "filter": filter_str,
        "rows": rows_per_page,
        "select": "title,author,published-print,published-online,DOI,container-title",
        "mailto": CONTACT_EMAIL,  # Crossref polite pool — faster responses
    }
    if journal_name and not issn:
        base_params["query.container-title"] = journal_name

    print(f"\n📡 Fetching papers from Crossref (target: {max_papers} papers)...")

    while len(papers) < max_papers:
        params = {**base_params, "offset": offset}
        try:
            resp = requests.get(CROSSREF_BASE, params=params, timeout=20)
            if resp.status_code != 200:
                print(f"  ⚠️  Crossref returned HTTP {resp.status_code}, stopping.")
                break

            data = resp.json()
            items = data.get("message", {}).get("items", [])
            if not items:
                print("  ℹ️  No more items returned.")
                break

            for item in items:
                authors = item.get("author", [])
                if not authors:
                    continue

                # Get publication year
                pub_date = item.get("published-print") or item.get("published-online") or {}
                year_parts = pub_date.get("date-parts", [[None]])
                year = year_parts[0][0] if year_parts and year_parts[0] else None

                # Get journal name
                container = item.get("container-title", [])
                journal = container[0] if container else "N/A"

                papers.append({
                    "doi":     item.get("DOI", "N/A"),
                    "title":   (item.get("title") or ["N/A"])[0],
                    "authors": authors,
                    "year":    year,
                    "journal": journal,
                })

            offset += rows_per_page
            print(f"  Fetched {len(papers)} papers so far...")

            if len(items) < rows_per_page:
                break  # Last page — no more data

        except requests.exceptions.Timeout:
            print("  ⚠️  Request timed out. Stopping fetch.")
            break
        except Exception as e:
            print(f"  ⚠️  Error: {e}")
            break

    print(f"✅ Total papers fetched: {len(papers)}")
    return papers[:max_papers]


# ── Step 2 & 3: Name normalisation & alphabetical check ─────────────────────

def normalize_family_name(name: str) -> str:
    """
    Normalise an author family name for comparison:
      - Convert to lowercase
      - Remove punctuation and special characters
      - Strip whitespace
    """
    name = name.lower()
    name = re.sub(r"[^a-z\s]", "", name)
    return name.strip()


def is_alphabetical(authors: list) -> bool:
    """
    Return True if the author list is in ascending alphabetical order
    by family name (after normalisation).

    Returns False if any author is missing a family name.
    """
    family_names = []
    for author in authors:
        family = author.get("family", "").strip()
        if not family:
            return False  # Cannot determine ordering without family name
        family_names.append(normalize_family_name(family))

    return family_names == sorted(family_names)


def chance_probability(n: int) -> float:
    """
    Probability that a randomly ordered list of n authors
    happens to be alphabetical = 1 / n!

    This quantifies the false-positive risk per paper.
    """
    return 1.0 / math.factorial(n)


# ── Step 4, 5 & 6: Journal-level aggregation & classification ───────────────

def analyze_papers(papers: list, min_authors: int = 4):
    """
    Compute per-paper alphabetical flags and aggregate journal-level statistics.

    Parameters
    ----------
    papers      : list — output of fetch_papers_crossref()
    min_authors : int  — minimum author count to include a paper (default: 4)

    Returns
    -------
    paper_results : list of per-paper dicts
    summary       : dict with journal-level statistics and classification
    """
    paper_results = []
    alpha_count = 0
    total_eligible = 0
    author_contributions_hints = 0

    for paper in papers:
        authors = paper["authors"]
        n = len(authors)

        # Filter: too few authors → high false-positive risk, skip
        if n < min_authors:
            continue

        total_eligible += 1
        alpha = is_alphabetical(authors)
        if alpha:
            alpha_count += 1

        # Extra signal: check if "Author Contributions" keywords appear in title
        # (Full-text would require separate scraping; this is a lightweight proxy)
        title_lower = paper["title"].lower()
        contrib_keywords = ["conceptualization", "methodology", "supervision",
                            "writing", "original draft", "review & editing"]
        has_contrib_hint = any(kw in title_lower for kw in contrib_keywords)
        if has_contrib_hint:
            author_contributions_hints += 1

        paper_results.append({
            "doi":             paper["doi"],
            "title":           paper["title"],
            "journal":         paper["journal"],
            "year":            paper["year"],
            "num_authors":     n,
            "author_names":    " | ".join(a.get("family", "?") for a in authors),
            "is_alphabetical": alpha,
            "chance_prob":     round(chance_probability(n), 8),
        })

    # Compute AlphabeticalRate
    alpha_rate = alpha_count / total_eligible if total_eligible > 0 else 0.0

    # Classification (Table 2 thresholds)
    if total_eligible < 20:
        conclusion = "Insufficient data"
        confidence = "Low"
    elif alpha_rate >= 0.75:
        conclusion = "Alphabetical-dominant"
        confidence = "High" if total_eligible >= 100 else "Medium"
    elif alpha_rate <= 0.25:
        conclusion = "Contribution-based"
        confidence = "High" if total_eligible >= 100 else "Medium"
    else:
        conclusion = "Mixed / Unclear"
        confidence = "Low"

    summary = {
        "total_papers_fetched":      len(papers),
        "eligible_papers":           total_eligible,
        "alphabetical_papers":       alpha_count,
        "contribution_based_papers": total_eligible - alpha_count,
        "alphabetical_rate":         round(alpha_rate, 4),
        "conclusion":                conclusion,
        "confidence":                confidence,
        "min_authors_filter":        min_authors,
    }

    return paper_results, summary


# ── Step 7: Export to Excel ──────────────────────────────────────────────────

def save_to_excel(paper_results: list, summary: dict, journal_label: str):
    """
    Save analysis results to a styled Excel file with two sheets:
      Sheet 1 — Journal Summary (classification result)
      Sheet 2 — Per-Paper Results (one row per paper)
    """
    wb = Workbook()

    # ── Colour palette ──
    dark_blue  = "1F4E79"
    mid_blue   = "366092"
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill   = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    top_align    = Alignment(vertical="top", wrap_text=True)

    def make_header_style(ws, row_num, bg_color):
        fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
        font = Font(bold=True, color="FFFFFF", size=12)
        for cell in ws[row_num]:
            cell.fill = fill
            cell.font = font
            cell.alignment = center_align

    # ────────────────────────────────────────────────────────────────────────
    # Sheet 1: Journal Summary
    # ────────────────────────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Journal Summary"

    ws1.append(["Metric", "Value"])
    make_header_style(ws1, 1, dark_blue)

    conclusion = summary["conclusion"]
    if conclusion == "Contribution-based":
        result_fill = green_fill
    elif conclusion == "Alphabetical-dominant":
        result_fill = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
    else:
        result_fill = yellow_fill

    summary_rows = [
        ("Journal / Query",                   journal_label),
        ("Min Authors Filter",                f"≥ {summary['min_authors_filter']} authors"),
        ("Total Papers Fetched",              summary["total_papers_fetched"]),
        ("Eligible Papers (≥ min authors)",   summary["eligible_papers"]),
        ("Alphabetical Papers",               summary["alphabetical_papers"]),
        ("Contribution-based Papers",         summary["contribution_based_papers"]),
        ("AlphabeticalRate",                  f"{summary['alphabetical_rate']:.2%}"),
        ("Conclusion",                        conclusion),
        ("Confidence",                        summary["confidence"]),
    ]

    for metric, value in summary_rows:
        ws1.append([metric, value])
        row_idx = ws1.max_row
        if metric in ("Conclusion", "Confidence", "AlphabeticalRate"):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = result_fill
                ws1.cell(row_idx, col).font = Font(bold=True, size=11)
        for col in [1, 2]:
            ws1.cell(row_idx, col).alignment = center_align

    ws1.column_dimensions["A"].width = 38
    ws1.column_dimensions["B"].width = 35

    # ── Classification legend table ──
    ws1.append([])  # blank row
    ws1.append(["AlphabeticalRate", "Classification", "Confidence Level"])
    make_header_style(ws1, ws1.max_row, mid_blue)

    legend = [
        ("≥ 75%",       "Alphabetical-dominant", "High (if ≥ 100 papers)"),
        ("26% – 74%",   "Mixed / Unclear",        "Low"),
        ("≤ 25%",       "Contribution-based",     "High (if ≥ 100 papers)"),
    ]
    for row_data in legend:
        ws1.append(list(row_data))
        row_idx = ws1.max_row
        for col in range(1, 4):
            ws1.cell(row_idx, col).alignment = center_align

    # ────────────────────────────────────────────────────────────────────────
    # Sheet 2: Per-Paper Results
    # ────────────────────────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Per-Paper Results")

    paper_headers = [
        "No.",
        "DOI",
        "Publication Title",
        "Journal",
        "Year",
        "# Authors",
        "Author Family Names (in order)",
        "Is Alphabetical?",
        "Chance Prob (1/n!)",
    ]
    ws2.append(paper_headers)
    make_header_style(ws2, 1, mid_blue)

    for i, p in enumerate(paper_results, 1):
        row_data = [
            i,
            p["doi"],
            p["title"],
            p["journal"],
            p["year"],
            p["num_authors"],
            p["author_names"],
            "Yes" if p["is_alphabetical"] else "No",
            p["chance_prob"],
        ]
        ws2.append(row_data)
        row_idx = ws2.max_row

        # Colour-code the "Is Alphabetical?" cell
        cell = ws2.cell(row_idx, 8)
        cell.fill = green_fill if p["is_alphabetical"] else red_fill
        cell.font = Font(bold=True)
        cell.alignment = center_align

        for col in range(1, len(paper_headers) + 1):
            ws2.cell(row_idx, col).alignment = top_align

    # Column widths for Sheet 2
    col_widths = [5, 30, 60, 30, 8, 10, 65, 16, 18]
    for col_idx, width in enumerate(col_widths, 1):
        letter = ws2.cell(1, col_idx).column_letter
        ws2.column_dimensions[letter].width = width

    # ── Save ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_label = re.sub(r"[^\w]", "_", journal_label)
    filename = f"author_order_{safe_label}_{timestamp}.xlsx"
    wb.save(filename)

    print(f"\n📁 Results saved to: {filename}")
    return filename


# ── Main entry point ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Classify journal author ordering (alphabetical vs contribution-based) "
            "by analysing papers via the Crossref API."
        )
    )
    parser.add_argument(
        "--issn",
        type=str,
        help="Journal ISSN (e.g., 1476-4687 for Nature)"
    )
    parser.add_argument(
        "--journal",
        type=str,
        help="Journal name keyword (e.g., 'IEEE Transactions on Networking')"
    )
    parser.add_argument(
        "--max",
        type=int,
        default=500,
        help="Maximum papers to fetch (default: 500)"
    )
    parser.add_argument(
        "--min-authors",
        type=int,
        default=4,
        help="Minimum authors per paper to include (default: 4)"
    )
    args = parser.parse_args()

    if not args.issn and not args.journal:
        user_input = input("Enter journal name or ISSN: ").strip()
        if user_input.replace("-", "").isdigit() or (
            len(user_input) == 9 and user_input[4] == "-"
        ):
            args.issn = user_input
        else:
            args.journal = user_input

    journal_label = args.issn or args.journal

    print(f"\n{'='*60}")
    print(f"  Author Order Classifier")
    print(f"  Journal  : {journal_label}")
    print(f"  Max papers     : {args.max}")
    print(f"  Min authors    : {args.min_authors}+")
    print(f"{'='*60}")

    # Step 1 — Fetch
    papers = fetch_papers_crossref(
        issn=args.issn,
        journal_name=args.journal,
        max_papers=args.max,
    )

    if not papers:
        print("❌ No papers found. Check the ISSN or journal name.")
        return

    # Steps 2–6 — Analyse
    paper_results, summary = analyze_papers(papers, min_authors=args.min_authors)

    # Print summary to console
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total papers fetched        : {summary['total_papers_fetched']}")
    print(f"  Eligible papers (≥{args.min_authors} authors) : {summary['eligible_papers']}")
    print(f"  Alphabetical papers         : {summary['alphabetical_papers']}")
    print(f"  Contribution-based papers   : {summary['contribution_based_papers']}")
    print(f"  AlphabeticalRate            : {summary['alphabetical_rate']:.2%}")
    print(f"  Conclusion                  : {summary['conclusion']}")
    print(f"  Confidence                  : {summary['confidence']}")
    print(f"{'='*60}")

    # Step 7 — Export
    save_to_excel(paper_results, summary, journal_label)


if __name__ == "__main__":
    main()
