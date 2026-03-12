"""
Author Order Classifier
=======================
Determines whether a journal uses ALPHABETICAL or CONTRIBUTION-BASED author ordering
by analyzing a large sample of papers from that journal via the Crossref API.

Pipeline:
  Step 0 — Field culture prior: map journal name keywords → expected ordering type
  Step 1 — Fetch paper metadata from Crossref API (by ISSN or journal name)
           Optional: supplement with Semantic Scholar API
  Step 2 — Normalize author family names (lowercase, remove punctuation)
  Step 3 — For each paper, check if authors are in alphabetical order
  Step 4 — Filter: only papers with >= 4 authors (reduces false positives)
  Step 5 — Compute AlphabeticalRate = alphabetical_papers / eligible_papers
  Step 6 — Classify journal using threshold rules
  Step 6b — Optional full-text CRediT check: scrape paper HTML for Author Contributions keywords
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
  python author_order_classifier.py --issn 1558-2566 --max 500
  python author_order_classifier.py --journal "Nature Communications" --max 300 --check-fulltext
  python author_order_classifier.py --journal "IEEE Transactions on Networking" --source both
  python author_order_classifier.py   # interactive prompt
"""

import re
import math
import argparse
import os
import time
import random
from datetime import datetime

import requests
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from dotenv import load_dotenv

load_dotenv()

CROSSREF_BASE          = "https://api.crossref.org/works"
SEMANTIC_SCHOLAR_BASE  = "https://api.semanticscholar.org/graph/v1"
CONTACT_EMAIL          = os.getenv("contact_email", "researcher@example.com")


# ── Step 0a: Field Culture Map ───────────────────────────────────────────────
# Keyword → expected author ordering convention (based on established academic norms)

FIELD_CULTURE_MAP = {
    "alphabetical": [
        # Mathematics & Statistics
        "mathematics", "mathematical", "math",
        "annals of mathematics", "statistics", "statistical",
        "probability", "stochastic",
        # Economics & Finance
        "economics", "econometrics", "econometric",
        "finance", "financial", "journal of political economy",
        "american economic review",
        # Pure / Theoretical CS
        "theoretical computer science", "theory of computing",
        "combinatorics", "discrete mathematics",
        # Logic & Pure Math
        "logic", "algebra", "topology", "geometry", "analysis",
        "operations research",
    ],
    "contribution": [
        # Engineering & Networks
        "engineering", "networking", "network", "networks",
        "ieee transactions", "communications", "signal processing",
        "wireless", "antenna", "radar", "sensors",
        # Computer Science (applied)
        "computer science", "software", "systems", "computing",
        "security", "cybersecurity", "cyber", "information security",
        "cryptography", "data mining", "database",
        "machine learning", "deep learning", "artificial intelligence",
        "computer vision", "natural language processing",
        "robotics", "control systems", "automation",
        # Electrical & Mechanical
        "electrical", "mechanical", "civil", "chemical engineering",
        "materials", "nanotechnology",
        # Life Sciences & Medicine
        "medicine", "medical", "biology", "clinical", "health",
        "neuroscience", "bioinformatics", "genomics", "proteomics",
        "oncology", "cardiology", "pharmacology",
        # Physical Sciences
        "physics", "chemistry", "astrophysics", "geophysics",
    ],
}


# ── Step 0b: CRediT Author Contributions Keywords ────────────────────────────
# Standardised CRediT taxonomy – if these appear in paper HTML → contribution-based culture

CREDIT_KEYWORDS = [
    "conceptualization",
    "methodology",
    "writing – original draft",
    "writing - original draft",
    "writing – review",
    "writing - review",
    "review & editing",
    "review and editing",
    "supervision",
    "data curation",
    "formal analysis",
    "funding acquisition",
    "investigation",
    "project administration",
    "resources",
    "validation",
    "visualization",
    "author contributions",
    "authors' contributions",
    "contributions of authors",
]


# ── Step 0c: Field Culture Detection ────────────────────────────────────────

def detect_field_culture(journal_name: str) -> dict:
    """
    Infer the expected author ordering convention from journal/field name keywords.

    Returns a dict with:
      field_type       : "Likely Contribution-based" | "Likely Alphabetical" | "Unknown"
      matched_keyword  : the keyword that triggered the match (or None)
      prior_confidence : "Medium" (keyword match) | "Low" (no match found)
    """
    name_lower = journal_name.lower()

    for keyword in FIELD_CULTURE_MAP["contribution"]:
        if keyword in name_lower:
            return {
                "field_type": "Likely Contribution-based",
                "matched_keyword": keyword,
                "prior_confidence": "Medium",
            }

    for keyword in FIELD_CULTURE_MAP["alphabetical"]:
        if keyword in name_lower:
            return {
                "field_type": "Likely Alphabetical",
                "matched_keyword": keyword,
                "prior_confidence": "Medium",
            }

    return {
        "field_type": "Unknown",
        "matched_keyword": None,
        "prior_confidence": "Low",
    }


# ── Step 1a: Fetch metadata from Crossref ────────────────────────────────────

def fetch_papers_crossref(issn=None, journal_name=None, max_papers=500):
    """
    Fetch paper metadata from the Crossref API.

    Parameters
    ----------
    issn        : str  — Journal ISSN (e.g. "1558-2566" for IEEE Trans. Networking)
    journal_name: str  — Journal name keyword (used if no ISSN provided)
    max_papers  : int  — Maximum number of papers to fetch

    Returns
    -------
    list of dicts with keys: doi, title, authors, year, journal, source
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

    print(f"\n📡 [Crossref] Fetching papers (target: {max_papers} papers)...")

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

                pub_date = item.get("published-print") or item.get("published-online") or {}
                year_parts = pub_date.get("date-parts", [[None]])
                year = year_parts[0][0] if year_parts and year_parts[0] else None

                container = item.get("container-title", [])
                journal = container[0] if container else "N/A"

                papers.append({
                    "doi":     item.get("DOI", "N/A"),
                    "title":   (item.get("title") or ["N/A"])[0],
                    "authors": authors,
                    "year":    year,
                    "journal": journal,
                    "source":  "Crossref",
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

    print(f"✅ Crossref: {len(papers)} papers fetched.")
    return papers[:max_papers]


# ── Step 1b: Fetch metadata from Semantic Scholar ────────────────────────────

def fetch_papers_semantic_scholar(journal_name: str, max_papers: int = 200) -> list:
    """
    Fetch paper metadata from the Semantic Scholar API as a supplement to Crossref.

    Uses the /paper/search endpoint with a journal name query.
    Fields: title, authors, year, externalIds (for DOI), venue

    Parameters
    ----------
    journal_name : str — Journal name to query
    max_papers   : int — Maximum papers to fetch

    Returns
    -------
    list of dicts with keys: doi, title, authors, year, journal, source
    """
    papers = []
    fields = "title,authors,year,externalIds,venue"
    limit = min(100, max_papers)
    offset = 0

    print(f"\n📡 [Semantic Scholar] Fetching papers (target: {max_papers} papers)...")

    while len(papers) < max_papers:
        try:
            params = {
                "query": journal_name,
                "fields": fields,
                "limit": limit,
                "offset": offset,
            }
            resp = requests.get(
                f"{SEMANTIC_SCHOLAR_BASE}/paper/search",
                params=params,
                timeout=20,
                headers={"User-Agent": f"AuthorOrderClassifier/1.0 (mailto:{CONTACT_EMAIL})"},
            )

            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 15))
                print(f"  ⏳ Rate-limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                print(f"  ⚠️  Semantic Scholar returned HTTP {resp.status_code}, stopping.")
                break

            data = resp.json()
            items = data.get("data", [])
            if not items:
                print("  ℹ️  No more items from Semantic Scholar.")
                break

            for item in items:
                raw_authors = item.get("authors", [])
                if not raw_authors:
                    continue

                # Semantic Scholar gives {"authorId": ..., "name": "First Last"}
                # Convert to Crossref-style {"family": ..., "given": ...}
                authors = []
                for a in raw_authors:
                    name_parts = a.get("name", "").strip().split()
                    if name_parts:
                        family = name_parts[-1]
                        given = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""
                        authors.append({"family": family, "given": given})

                external_ids = item.get("externalIds") or {}
                doi = external_ids.get("DOI", "N/A")

                papers.append({
                    "doi":     doi,
                    "title":   item.get("title", "N/A") or "N/A",
                    "authors": authors,
                    "year":    item.get("year"),
                    "journal": item.get("venue", "N/A") or "N/A",
                    "source":  "SemanticScholar",
                })

            offset += len(items)
            print(f"  Fetched {len(papers)} papers so far...")

            if len(items) < limit:
                break

            time.sleep(1)  # polite delay — Semantic Scholar has rate limits

        except requests.exceptions.Timeout:
            print("  ⚠️  Semantic Scholar request timed out.")
            break
        except Exception as e:
            print(f"  ⚠️  Semantic Scholar error: {e}")
            break

    print(f"✅ Semantic Scholar: {len(papers)} papers fetched.")
    return papers[:max_papers]


# ── Step 1c: Author Contributions full-text detection ────────────────────────

def check_author_contributions_html(doi: str) -> bool:
    """
    Fetch the paper's landing page via DOI and search for CRediT taxonomy keywords.

    Returns True  if ≥ 2 CRediT keywords found (strong signal of contribution-based culture).
    Returns False if insufficient keywords or the fetch fails.
    """
    if not doi or doi == "N/A":
        return False

    try:
        url = f"https://doi.org/{doi}"
        headers = {
            "User-Agent": (
                f"AuthorOrderClassifier/1.0 "
                f"(mailto:{CONTACT_EMAIL}; academic research bot)"
            ),
            "Accept": "text/html,application/xhtml+xml",
        }
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)

        if resp.status_code != 200:
            return False

        html_lower = resp.text.lower()
        matched = [kw for kw in CREDIT_KEYWORDS if kw.lower() in html_lower]
        return len(matched) >= 2  # ≥ 2 keywords = confident CRediT section present

    except Exception:
        return False


# ── Step 2 & 3: Name normalisation & alphabetical check ──────────────────────

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


# ── Steps 4, 5 & 6: Journal-level aggregation & classification ───────────────

def analyze_papers(papers: list, min_authors: int = 4,
                   check_fulltext: bool = False, fulltext_sample: int = 30):
    """
    Compute per-paper alphabetical flags and aggregate journal-level statistics.

    Parameters
    ----------
    papers          : list — output of fetch_papers_*()
    min_authors     : int  — minimum author count to include a paper (default: 4)
    check_fulltext  : bool — if True, sample papers and check HTML for CRediT keywords
    fulltext_sample : int  — number of papers to sample for full-text check

    Returns
    -------
    paper_results : list of per-paper dicts
    summary       : dict with journal-level statistics and classification
    """
    paper_results = []
    alpha_count = 0
    total_eligible = 0
    credit_section_hits = 0
    credit_checked = 0

    # Decide which DOIs to check for full-text CRediT
    dois_to_check = set()
    if check_fulltext:
        eligible_dois = [
            p["doi"] for p in papers
            if len(p["authors"]) >= min_authors and p["doi"] != "N/A"
        ]
        sample_size = min(fulltext_sample, len(eligible_dois))
        dois_to_check = set(random.sample(eligible_dois, sample_size))
        print(f"\n🔍 Full-text CRediT check: sampling {len(dois_to_check)} papers...")

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

        # Full-text CRediT check (only for sampled DOIs)
        has_credit = None
        if check_fulltext and paper["doi"] in dois_to_check:
            credit_checked += 1
            has_credit = check_author_contributions_html(paper["doi"])
            if has_credit:
                credit_section_hits += 1
            print(
                f"  [{credit_checked}/{len(dois_to_check)}] "
                f"{paper['doi'][:35]}... → "
                f"{'✅ CRediT found' if has_credit else '❌ No CRediT'}"
            )
            time.sleep(random.uniform(1.5, 3.0))  # polite delay

        paper_results.append({
            "doi":                paper["doi"],
            "title":              paper["title"],
            "journal":            paper["journal"],
            "year":               paper["year"],
            "num_authors":        n,
            "author_names":       " | ".join(a.get("family", "?") for a in authors),
            "is_alphabetical":    alpha,
            "chance_prob":        round(chance_probability(n), 8),
            "source":             paper.get("source", "N/A"),
            "has_credit_section": has_credit,  # True / False / None (not checked)
        })

    # Compute AlphabeticalRate
    alpha_rate = alpha_count / total_eligible if total_eligible > 0 else 0.0

    # CRediT section rate
    credit_rate = credit_section_hits / credit_checked if credit_checked > 0 else None

    # Classification (threshold rules)
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
        "credit_checked":            credit_checked,
        "credit_section_hits":       credit_section_hits,
        "credit_rate":               round(credit_rate, 4) if credit_rate is not None else None,
    }

    return paper_results, summary


# ── Step 7: Export to Excel ───────────────────────────────────────────────────

def save_to_excel(paper_results: list, summary: dict, journal_label: str,
                  field_culture: dict = None):
    """
    Save analysis results to a styled Excel file with two sheets:
      Sheet 1 — Journal Summary  (statistical result + field culture prior + CRediT signal)
      Sheet 2 — Per-Paper Results (one row per paper)
    """
    wb = Workbook()

    # ── Colour palette ──
    dark_blue  = "1F4E79"
    mid_blue   = "366092"
    green_fill  = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill    = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    blue_fill   = PatternFill(start_color="BDD7EE", end_color="BDD7EE", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    top_align    = Alignment(vertical="top", wrap_text=True)

    def make_header_style(ws, row_num, bg_color):
        fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")
        font = Font(bold=True, color="FFFFFF", size=12)
        for cell in ws[row_num]:
            cell.fill = fill
            cell.font = font
            cell.alignment = center_align

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet 1: Journal Summary
    # ─────────────────────────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Journal Summary"

    ws1.append(["Metric", "Value"])
    make_header_style(ws1, 1, dark_blue)

    conclusion = summary["conclusion"]
    if conclusion == "Contribution-based":
        result_fill = green_fill
    elif conclusion == "Alphabetical-dominant":
        result_fill = blue_fill
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
        ("Conclusion (Statistical)",          conclusion),
        ("Confidence",                        summary["confidence"]),
    ]

    for metric, value in summary_rows:
        ws1.append([metric, value])
        row_idx = ws1.max_row
        if metric in ("Conclusion (Statistical)", "Confidence", "AlphabeticalRate"):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = result_fill
                ws1.cell(row_idx, col).font = Font(bold=True, size=11)
        for col in [1, 2]:
            ws1.cell(row_idx, col).alignment = center_align

    # ── Section 2: Field Culture Prior Signal ──
    ws1.append([])
    ws1.append(["── Field Culture Prior Signal ──", ""])
    make_header_style(ws1, ws1.max_row, "5B9BD5")

    if field_culture:
        ft = field_culture["field_type"]
        fc_fill = (
            green_fill if "Contribution" in ft
            else blue_fill if "Alphabetical" in ft
            else yellow_fill
        )
        field_rows = [
            ("Field Culture (Prior)",    ft),
            ("Matched Keyword",          field_culture.get("matched_keyword") or "None"),
            ("Prior Confidence",         field_culture["prior_confidence"]),
            ("Interpretation",           (
                "1st author = main contributor; last author may be PI/supervisor"
                if "Contribution" in ft
                else "Author list likely sorted A→Z by family name"
                if "Alphabetical" in ft
                else "No strong prior — rely on statistical analysis"
            )),
        ]
        for metric, value in field_rows:
            ws1.append([metric, value])
            row_idx = ws1.max_row
            if metric == "Field Culture (Prior)":
                for col in [1, 2]:
                    ws1.cell(row_idx, col).fill = fc_fill
                    ws1.cell(row_idx, col).font = Font(bold=True, size=11)
            for col in [1, 2]:
                ws1.cell(row_idx, col).alignment = center_align

    # ── Section 3: Author Contributions (CRediT) Signal ──
    ws1.append([])
    ws1.append(["── Author Contributions (CRediT) Signal ──", ""])
    make_header_style(ws1, ws1.max_row, "70AD47")

    credit_rate = summary.get("credit_rate")  # float or None
    if credit_rate is not None:
        credit_rate_display = f"{credit_rate:.2%}"
        credit_signal = (
            "Contribution-based (CRediT section present)"
            if credit_rate >= 0.5
            else "Likely NOT CRediT culture (low CRediT rate)"
        )
        credit_signal_fill = green_fill if credit_rate >= 0.5 else red_fill
    else:
        credit_rate_display = "Not checked"
        credit_signal = "Run with --check-fulltext to enable"
        credit_signal_fill = yellow_fill

    credit_rows = [
        ("Papers Sampled for Full-text Check",  summary.get("credit_checked", 0)),
        ("Papers with CRediT Section Found",    summary.get("credit_section_hits", 0)),
        ("CRediT Section Rate",                 credit_rate_display),
        ("CRediT Signal",                       credit_signal),
    ]
    for metric, value in credit_rows:
        ws1.append([metric, value])
        row_idx = ws1.max_row
        if metric == "CRediT Signal":
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = credit_signal_fill
                ws1.cell(row_idx, col).font = Font(bold=True, size=11)
        for col in [1, 2]:
            ws1.cell(row_idx, col).alignment = center_align

    # ── Classification legend ──
    ws1.append([])
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

    ws1.column_dimensions["A"].width = 42
    ws1.column_dimensions["B"].width = 40
    ws1.column_dimensions["C"].width = 25

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet 2: Per-Paper Results
    # ─────────────────────────────────────────────────────────────────────────
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
        "Data Source",
        "CRediT Section?",
    ]
    ws2.append(paper_headers)
    make_header_style(ws2, 1, mid_blue)

    for i, p in enumerate(paper_results, 1):
        credit_val = p.get("has_credit_section")
        if credit_val is True:
            credit_display = "Yes"
        elif credit_val is False:
            credit_display = "No"
        else:
            credit_display = "Not checked"

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
            p.get("source", "N/A"),
            credit_display,
        ]
        ws2.append(row_data)
        row_idx = ws2.max_row

        # Colour-code "Is Alphabetical?"
        cell = ws2.cell(row_idx, 8)
        cell.fill = green_fill if p["is_alphabetical"] else red_fill
        cell.font = Font(bold=True)
        cell.alignment = center_align

        # Colour-code CRediT column
        credit_cell = ws2.cell(row_idx, 11)
        if credit_display == "Yes":
            credit_cell.fill = green_fill
            credit_cell.font = Font(bold=True)
        elif credit_display == "No":
            credit_cell.fill = red_fill

        for col in range(1, len(paper_headers) + 1):
            ws2.cell(row_idx, col).alignment = top_align

    col_widths = [5, 30, 60, 30, 8, 10, 65, 16, 18, 15, 14]
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


# ── Main entry point ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Classify journal author ordering (alphabetical vs contribution-based) "
            "by analysing papers via Crossref and/or Semantic Scholar API."
        )
    )
    parser.add_argument(
        "--issn",
        type=str,
        help="Journal ISSN (e.g., 1558-2566 for IEEE Trans. on Networking)"
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
    parser.add_argument(
        "--source",
        choices=["crossref", "semantic", "both"],
        default="crossref",
        help="Data source: crossref (default) | semantic | both"
    )
    parser.add_argument(
        "--check-fulltext",
        action="store_true",
        help="Sample paper HTML pages and check for CRediT Author Contributions keywords"
    )
    parser.add_argument(
        "--fulltext-sample",
        type=int,
        default=30,
        help="Number of papers to sample for full-text CRediT check (default: 30)"
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
    print(f"  Journal        : {journal_label}")
    print(f"  Max papers     : {args.max}")
    print(f"  Min authors    : {args.min_authors}+")
    print(f"  Source         : {args.source}")
    print(f"  Full-text check: {'Yes' if args.check_fulltext else 'No'}")
    print(f"{'='*60}")

    # ── Step 0: Field Culture Prior ──
    field_culture = detect_field_culture(journal_label)
    print(f"\n🏷️  Field Culture Prior  : {field_culture['field_type']}")
    if field_culture["matched_keyword"]:
        print(f"   Matched keyword    : '{field_culture['matched_keyword']}'")
    print(f"   Prior confidence   : {field_culture['prior_confidence']}")

    # ── Step 1: Fetch papers ──
    papers = []

    if args.source in ("crossref", "both"):
        crossref_papers = fetch_papers_crossref(
            issn=args.issn,
            journal_name=args.journal,
            max_papers=args.max,
        )
        papers.extend(crossref_papers)

    if args.source in ("semantic", "both"):
        sem_max = args.max if args.source == "semantic" else max(100, args.max // 3)
        sem_papers = fetch_papers_semantic_scholar(
            journal_name=journal_label,
            max_papers=sem_max,
        )
        # Deduplicate by DOI before merging
        existing_dois = {p["doi"] for p in papers if p["doi"] != "N/A"}
        new_papers = [p for p in sem_papers if p["doi"] not in existing_dois]
        papers.extend(new_papers)
        print(f"  Added {len(new_papers)} unique papers from Semantic Scholar.")

    if not papers:
        print("❌ No papers found. Check the ISSN or journal name.")
        return

    # ── Steps 2–6: Analyse ──
    paper_results, summary = analyze_papers(
        papers,
        min_authors=args.min_authors,
        check_fulltext=args.check_fulltext,
        fulltext_sample=args.fulltext_sample,
    )

    # ── Print summary to console ──
    credit_rate = summary.get("credit_rate")
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Total papers fetched          : {summary['total_papers_fetched']}")
    print(f"  Eligible papers (≥{args.min_authors} authors)  : {summary['eligible_papers']}")
    print(f"  Alphabetical papers           : {summary['alphabetical_papers']}")
    print(f"  Contribution-based papers     : {summary['contribution_based_papers']}")
    print(f"  AlphabeticalRate              : {summary['alphabetical_rate']:.2%}")
    print(f"  Conclusion (Statistical)      : {summary['conclusion']}")
    print(f"  Confidence                    : {summary['confidence']}")
    print(f"  ─────────────────────────────────────────────────")
    print(f"  Field Culture Prior           : {field_culture['field_type']}")
    print(f"  Prior Confidence              : {field_culture['prior_confidence']}")
    if args.check_fulltext:
        print(f"  CRediT Section Rate           : "
              f"{credit_rate:.2%}" if isinstance(credit_rate, float)
              else f"  CRediT Section Rate           : N/A")
    print(f"{'='*60}")

    # ── Step 7: Export ──
    save_to_excel(paper_results, summary, journal_label, field_culture=field_culture)


if __name__ == "__main__":
    main()
