"""
Author Order Classifier
=======================
Determines whether a journal uses ALPHABETICAL/RANDOM (A/R), RELATIVE CONTRIBUTION (RC),
or EXPLICIT CONTRIBUTION (EC) author ordering by analysing a large sample of papers from
that journal via Crossref, Semantic Scholar, and/or Google Scholar.

3-Tier Classification Framework (per paper — highest priority first):
  Tier 1 — EC  (Explicit Contribution) : CRediT / ACI Author Contributions section found
  Tier 2 — A/R (Alphabetical / Random) : authors sorted A→Z by family name (no EC signal)
  Tier 3 — RC  (Relative Contribution) : default when NOT EC and NOT alphabetical
                                          (1st author = main contributor, harmonic position model)

Per-paper Contribution Strength Scores (α, β, γ):
  α = 1.0 if classified A/R  (uniform weights, Eq. 1 of Nm-index framework)
  β = 1.0 if classified RC   (harmonic positional weights, Eqs. 2–3)
  γ = 1.0 if classified EC   (CRediT/ACI weights, Eqs. 4–5)

Journal-level 3-Layer Decision (as described in Nm-index framework):
  EC_rate  >= 0.30  →  Explicit Contribution (EC)          [γ dominant]
  A/R_rate >= 0.75  →  Alphabetical / Random  (A/R)        [α dominant]
  A/R_rate <= 0.25  →  Relative Contribution  (RC)         [β dominant]
  Otherwise         →  Mixed / Hybrid

Co-authorship Patterns (detected per paper):
  - Co-first authors  : multiple authors flagged as "first" in Crossref sequence field
                        OR equal-contribution markers in full text
  - Co-last  authors  : last two authors share equal weighting signal

False Positive Probability (random ordering appearing alphabetical):
  n=2  →  1/2  = 50.0%   (exclude)
  n=3  →  1/6  ≈ 16.7%   (marginal)
  n=4  →  1/24 ≈  4.2%   (include)
  n=5  →  1/120 ≈ 0.8%   (strong evidence)
  n=6+ →  <0.1%           (very strong evidence)

Pipeline:
  Step 0  — Field culture prior: map journal name keywords → expected ordering type
  Step 1  — Fetch paper metadata (Crossref / Semantic Scholar / Google Scholar)
  Step 2  — Normalize author family names
  Step 3  — Per-paper: 3-tier EC → A/R → RC classification + α/β/γ + co-authorship
  Step 4  — Filter: only papers with >= 4 authors (reduces false positives)
  Step 5  — Compute rates: EC_rate, A/R_rate, RC_rate
  Step 6  — Journal-level classification via 3-layer decision + optional CRediT full-text
  Step 7  — Export per-paper results + summary to a styled Excel file

Usage:
  python author_order_classifier.py --issn 1558-2566 --max 500
  python author_order_classifier.py --journal "Nature Communications" --max 300 --check-fulltext
  python author_order_classifier.py --journal "IEEE Transactions" --source all --max 200
  python author_order_classifier.py --journal "Mathematics Review" --source google --max 100
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

# Try to import scholarly for Google Scholar support
try:
    from scholarly import scholarly
    SCHOLARLY_AVAILABLE = True
except ImportError:
    SCHOLARLY_AVAILABLE = False
    print("⚠️  scholarly library not installed. Google Scholar support disabled.")
    print("   Install with: pip install scholarly")

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
    "software",
    "validation",
    "visualization",
    "author contributions",
    "authors' contributions",
    "contributions of authors",
]

# ── Step 0c: ACI (Author Contribution Index) Detection Patterns ─────────────
# ACI signals: percentage-based explicit contribution declarations per author.
# Detect any of these → EC-ACI classification.

ACI_SECTION_HEADERS = [
    "author contribution index",
    "percentage contribution",
    "percentage of contribution",
    "authors' percentage",
    "author percentage",
]

# Regex patterns for percentage-based contribution statements
# e.g. "50%", "contributed 40% to this work", "Author A: 30%, Author B: 70%"
ACI_PERCENT_PATTERNS = [
    r"\d{1,3}\s*%\s*(of|to)\s*(this|the)\s*(work|study|paper|manuscript|research)",
    r"(contributed?|contribution)\s*:?\s*\d{1,3}\s*%",
    r"\d{1,3}\s*%\s*(contribution|contributed)",
    r"(equal\s+contribution\s+of\s+\d{1,3}\s*%)",
    r"(authors?\s+\w[\w\s]*:\s*\d{1,3}\s*%)",   # "Author A: 50%"
]


def check_aci_markers(html_lower: str) -> bool:
    """
    Return True if ACI (Author Contribution Index) markers are detected in the
    paper's HTML text (already lowercased).

    ACI signals (any one is sufficient):
      1. ACI section header keyword match
      2. Percentage-based contribution pattern match (regex)
    """
    # Check ACI section headers
    if any(hdr in html_lower for hdr in ACI_SECTION_HEADERS):
        return True

    # Check percentage patterns
    for pat in ACI_PERCENT_PATTERNS:
        if re.search(pat, html_lower):
            return True

    return False


# ── Step 0d: Field Culture Detection ────────────────────────────────────────

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


# ── Step 1a: Fetch metadata from Google Scholar ──────────────────────────────

def fetch_papers_google_scholar(journal_name: str, max_papers: int = 100) -> list:
    """
    Fetch paper metadata from Google Scholar using the scholarly library.
    
    This is a lightweight scraping-based approach that doesn't require an API key.
    Note: Google Scholar may rate-limit or block requests. Use responsibly.

    Parameters
    ----------
    journal_name : str — Journal name to search for
    max_papers   : int — Maximum papers to fetch (default: 100)

    Returns
    -------
    list of dicts with keys: doi, title, authors, year, journal, source
    """
    if not SCHOLARLY_AVAILABLE:
        print("⚠️  scholarly library not available. Skipping Google Scholar fetch.")
        return []

    papers = []
    
    print(f"\n📡 [Google Scholar] Searching for papers (target: {max_papers} papers)...")
    
    try:
        # Search for papers by journal name
        search_query = scholarly.search_pubs(f'"{journal_name}"')
        
        for pub in search_query:
            if len(papers) >= max_papers:
                break
            
            try:
                # Try to get full publication details
                pub_details = pub
                
                # Extract authors with family names
                authors = []
                raw_authors = pub_details.get("author", [])
                if isinstance(raw_authors, str):
                    # Sometimes authors come as a comma-separated string
                    author_names = raw_authors.split(" and ")
                    for name in author_names:
                        name = name.strip()
                        if name:
                            name_parts = name.split()
                            if name_parts:
                                family = name_parts[-1]
                                given = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""
                                authors.append({"family": family, "given": given})
                elif isinstance(raw_authors, list):
                    for author in raw_authors:
                        if isinstance(author, str):
                            name_parts = author.strip().split()
                            if name_parts:
                                family = name_parts[-1]
                                given = " ".join(name_parts[:-1]) if len(name_parts) > 1 else ""
                                authors.append({"family": family, "given": given})
                
                if not authors:
                    continue  # Skip papers without author info
                
                paper_dict = {
                    "doi":     pub_details.get("eprint", "N/A") or "N/A",
                    "title":   pub_details.get("title", "N/A") or "N/A",
                    "authors": authors,
                    "year":    pub_details.get("pub_year"),
                    "journal": pub_details.get("journal", "N/A") or "N/A",
                    "source":  "GoogleScholar",
                }
                
                papers.append(paper_dict)
                print(f"  Fetched {len(papers)} papers so far...")
                
                # Polite delay to avoid rate-limiting
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                # Skip papers that fail to parse
                continue
    
    except Exception as e:
        print(f"  ⚠️  Google Scholar error: {e}")
        print("  This is normal if Google Scholar is blocking requests.")
        return []
    
    print(f"✅ Google Scholar: {len(papers)} papers fetched.")
    return papers[:max_papers]


# ── Step 1b: Fetch metadata from Crossref ────────────────────────────────────

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
                print(f"    Crossref returned HTTP {resp.status_code}, stopping.")
                break

            data = resp.json()
            items = data.get("message", {}).get("items", [])
            if not items:
                print("  No more items returned.")
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


# ── Step 1c: Fetch metadata from Semantic Scholar ────────────────────────────

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
                print(f"  Rate-limited. Waiting {wait}s...")
                time.sleep(wait)
                continue

            if resp.status_code != 200:
                print(f"    Semantic Scholar returned HTTP {resp.status_code}, stopping.")
                break

            data = resp.json()
            items = data.get("data", [])
            if not items:
                print("  No more items from Semantic Scholar.")
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
            print("    Semantic Scholar request timed out.")
            break
        except Exception as e:
            print(f"    Semantic Scholar error: {e}")
            break

    print(f" Semantic Scholar: {len(papers)} papers fetched.")
    return papers[:max_papers]


# ── Step 1d: Author Contributions full-text detection ────────────────────────

def check_author_contributions_html(doi: str) -> dict:
    """
    Fetch the paper's landing page via DOI and search for both CRediT taxonomy
    keywords (Step 2) and ACI markers (Step 3) per the classification method.

    Returns a dict:
      {
        "credit" : bool  — True if ≥ 2 CRediT keywords found (EC-CRediT signal)
        "aci"    : bool  — True if ACI percentage/section markers found (EC-ACI signal)
        "credit_count": int — number of CRediT keywords matched
      }

    Returns {"credit": False, "aci": False, "credit_count": 0} on fetch failure.
    """
    _empty = {"credit": False, "aci": False, "credit_count": 0}

    if not doi or doi == "N/A":
        return _empty

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
            return _empty

        html_lower = resp.text.lower()

        # Step 2: CRediT keyword scan — need ≥ 2 keywords for confident detection
        matched_credit = [kw for kw in CREDIT_KEYWORDS if kw.lower() in html_lower]
        has_credit = len(matched_credit) >= 2

        # Step 3: ACI marker scan (only checked if CRediT not found, per method)
        has_aci = False
        if not has_credit:
            has_aci = check_aci_markers(html_lower)

        return {
            "credit": has_credit,
            "aci": has_aci,
            "credit_count": len(matched_credit),
        }

    except Exception:
        return _empty


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
    # For large n, factorial becomes huge and overflows float conversion
    # For n >= 20, probability is effectively 0 (< 2.4e-19)
    if n > 20:
        return 1e-20  # Essentially zero probability
    try:
        return 1.0 / math.factorial(n)
    except (OverflowError, ValueError):
        return 1e-20  # Fallback for edge cases


# ── Step 3a: Co-authorship pattern detection ─────────────────────────────────

# Keywords that signal equal/shared first or last authorship in full text or metadata
CO_FIRST_KEYWORDS = [
    "contributed equally", "equal contribution", "co-first author",
    "co first author", "joint first", "shared first", "these authors contributed equally",
    "both authors contributed equally",
]
CO_LAST_KEYWORDS = [
    "co-last author", "co last author", "joint senior", "joint corresponding",
    "co-senior author", "co senior author", "shared senior",
]


def detect_co_authorship_pattern(authors: list, raw_text: str = "") -> dict:
    """
    Detect co-first / co-last author patterns from two signals:

    Signal A — Crossref sequence field:
      Crossref marks the first author with sequence="first"; all others get "additional".
      If more than one author has sequence="first" → co-first authors detected.

    Signal B — Full-text / abstract keyword scan:
      Search raw_text (paper HTML or abstract) for equal-contribution phrases.

    Returns
    -------
    dict with:
      has_co_first     : bool
      num_co_first     : int  (number of first-sequence authors)
      has_co_last      : bool
      co_first_signal  : "sequence" | "text" | "both" | None
      co_last_signal   : "text" | None
      rc_variant       : "RC-MultiFA" | "RC-MultiLA" | "RC-MultiFA-MultiLA" | "RC" | None
    """
    text_lower = raw_text.lower()

    # Signal A: Crossref sequence field
    first_seq_authors = [a for a in authors if a.get("sequence", "").lower() == "first"]
    has_co_first_seq = len(first_seq_authors) > 1
    num_co_first_seq = len(first_seq_authors)

    # Signal B: keyword scan
    has_co_first_text = any(kw in text_lower for kw in CO_FIRST_KEYWORDS)
    has_co_last_text  = any(kw in text_lower for kw in CO_LAST_KEYWORDS)

    has_co_first = has_co_first_seq or has_co_first_text
    has_co_last  = has_co_last_text  # Crossref doesn't mark last authors specially

    # Determine which signals fired
    if has_co_first_seq and has_co_first_text:
        co_first_signal = "both"
    elif has_co_first_seq:
        co_first_signal = "sequence"
    elif has_co_first_text:
        co_first_signal = "text"
    else:
        co_first_signal = None

    co_last_signal = "text" if has_co_last_text else None

    # Map to RC variant label (from Nm-index framework)
    if has_co_first and has_co_last:
        rc_variant = "RC-MultiFA-MultiLA"
    elif has_co_first:
        rc_variant = "RC-MultiFA"
    elif has_co_last:
        rc_variant = "RC-MultiLA"
    else:
        rc_variant = None  # determined by caller based on classification

    return {
        "has_co_first":    has_co_first,
        "num_co_first":    num_co_first_seq if has_co_first_seq else (1 if has_co_first_text else 0),
        "has_co_last":     has_co_last,
        "co_first_signal": co_first_signal,
        "co_last_signal":  co_last_signal,
        "rc_variant":      rc_variant,
    }


# ── Step 3b: 3-tier per-paper classification (EC → A/R → RC) ─────────────────

def classify_paper_author_order(authors: list, has_credit: bool = None,
                                raw_text: str = "") -> dict:
    """
    3-tier author ordering classification per the Nm-index framework:

      Tier 1 — EC  (Explicit Contribution):
        CRediT / Author Contributions section detected in paper full text.
        Contribution weight γ = 1.0  (Eqs. 4–5 of Nm-index).

      Tier 2 — A/R (Alphabetical / Random):
        Authors sorted A→Z by family name; no EC signal present.
        Contribution weight α = 1.0  (Eq. 1 of Nm-index).

      Tier 3 — RC  (Relative Contribution) — default:
        Authors NOT alphabetical and no CRediT detected.
        Contribution weight β = 1.0  (Eqs. 2–3 of Nm-index, harmonic model).

    Parameters
    ----------
    authors    : list of author dicts (Crossref format with "family", "given", "sequence")
    has_credit : bool | None  — True if CRediT section was detected in full text
    raw_text   : str          — raw paper text / abstract for co-authorship keyword scan

    Returns
    -------
    dict with:
      classification     : "EC" | "A/R" | "RC" | "Random"
      ordering_type      : human-readable label
      is_alphabetical    : bool
      confidence_score   : float [0, 1]
      alpha              : float  A/R weight (1.0 if A/R, else 0.0)
      beta               : float  RC weight  (1.0 if RC, else 0.0)
      gamma              : float  EC weight  (1.0 if EC, else 0.0)
      co_authorship      : dict from detect_co_authorship_pattern()
      rc_variant         : str | None  e.g. "RC-MultiFA", "RC-MultiFA-MultiLA"
      interpretation     : human-readable explanation
    """
    n = len(authors)
    co = detect_co_authorship_pattern(authors, raw_text)

    # ── Insufficient authors — cannot classify ────────────────────────────────
    if n < 4:
        return {
            "classification":  "Random",
            "ordering_type":   "Random / Insufficient data",
            "is_alphabetical": False,
            "confidence_score": 0.0,
            "alpha": 0.0, "beta": 0.0, "gamma": 0.0,
            "co_authorship":   co,
            "rc_variant":      None,
            "interpretation":  f"Only {n} author(s) — need ≥ 4 to classify reliably",
        }

    # ── Tier 1: EC (Explicit Contribution) ───────────────────────────────────
    # CRediT section detected → highest confidence, overrides positional analysis
    if has_credit is True:
        rc_variant = co["rc_variant"]  # EC can also have multi-FA/LA
        return {
            "classification":  "EC",
            "ordering_type":   "Explicit Contribution (EC)",
            "is_alphabetical": is_alphabetical(authors),  # informational only
            "confidence_score": 0.95,
            "alpha": 0.0, "beta": 0.0, "gamma": 1.0,
            "co_authorship":   co,
            "rc_variant":      rc_variant,
            "interpretation": (
                "CRediT / Author Contributions section found → "
                "Explicit Contribution (EC). "
                "Weights computed via CRediT taxonomy or ACI (Eqs. 4–5)."
            ),
        }

    # ── Tier 2: A/R (Alphabetical / Random) ──────────────────────────────────
    is_alpha = is_alphabetical(authors)
    false_positive_prob = chance_probability(n)

    if is_alpha:
        confidence = round(1.0 - false_positive_prob, 4)
        confidence = min(confidence, 0.999)
        return {
            "classification":  "A/R",
            "ordering_type":   "Alphabetical / Random (A/R)",
            "is_alphabetical": True,
            "confidence_score": confidence,
            "alpha": 1.0, "beta": 0.0, "gamma": 0.0,
            "co_authorship":   co,
            "rc_variant":      None,
            "interpretation": (
                f"Authors sorted A→Z (false-positive prob = 1/{n}! = {false_positive_prob:.2e}). "
                "Uniform weights applied (Eq. 1): each author gets 1/N credit."
            ),
        }

    # ── Tier 3: RC (Relative Contribution) — default ─────────────────────────
    confidence = 0.90 if n >= 6 else 0.75
    rc_variant = co["rc_variant"] if co["rc_variant"] else "RC"

    # Build RC interpretation
    if co["has_co_first"] and co["has_co_last"]:
        rc_detail = "Multiple first AND last authors detected → RC-MultiFA-MultiLA variant."
    elif co["has_co_first"]:
        rc_detail = f"Co-first authors detected ({co['co_first_signal']} signal) → RC-MultiFA variant."
    elif co["has_co_last"]:
        rc_detail = "Co-last authors detected → RC-MultiLA variant."
    else:
        rc_detail = "Single first and last author → standard RC."

    return {
        "classification":  "RC",
        "ordering_type":   f"Relative Contribution ({rc_variant})",
        "is_alphabetical": False,
        "confidence_score": confidence,
        "alpha": 0.0, "beta": 1.0, "gamma": 0.0,
        "co_authorship":   co,
        "rc_variant":      rc_variant,
        "interpretation": (
            f"NOT alphabetical, no CRediT → Relative Contribution (RC). "
            f"Harmonic positional weights (Eqs. 2–3). {rc_detail}"
        ),
    }


# ── Steps 4, 5 & 6: Journal-level aggregation & 3-layer classification ────────

def analyze_papers(papers: list, min_authors: int = 4,
                   check_fulltext: bool = False, fulltext_sample: int = 30):
    """
    Per-paper 3-tier classification and journal-level 3-layer decision.

    3-Layer Journal Decision (in priority order):
      Layer 1 — EC_rate  >= 0.30  →  Explicit Contribution (EC)
      Layer 2 — A/R_rate >= 0.75  →  Alphabetical / Random  (A/R)
      Layer 3 — A/R_rate <= 0.25  →  Relative Contribution  (RC)
      Fallback                    →  Mixed / Hybrid

    Parameters
    ----------
    papers          : list — output of fetch_papers_*()
    min_authors     : int  — minimum author count to include a paper (default: 4)
    check_fulltext  : bool — if True, sample papers and check HTML for CRediT keywords
    fulltext_sample : int  — number of papers to sample for full-text check

    Returns
    -------
    paper_results : list of per-paper dicts
    summary       : dict with journal-level statistics and 3-tier classification
    """
    paper_results = []
    total_eligible = 0

    # Per-tier counters
    ec_count  = 0
    ar_count  = 0
    rc_count  = 0

    # Co-authorship counters
    co_first_count = 0
    co_last_count  = 0

    # CRediT full-text counters
    credit_section_hits = 0
    credit_checked = 0

    # Decide which DOIs to check for full-text CRediT (Tier 1 signal)
    dois_to_check = set()
    if check_fulltext:
        eligible_dois = [
            p["doi"] for p in papers
            if len(p.get("authors", [])) >= min_authors and p.get("doi", "N/A") != "N/A"
        ]
        sample_size = min(fulltext_sample, len(eligible_dois))
        dois_to_check = set(random.sample(eligible_dois, sample_size))
        print(f"\n  Full-text CRediT check: sampling {len(dois_to_check)} papers...")

    for paper in papers:
        authors = paper.get("authors", [])
        n = len(authors)

        # Filter: too few authors → high false-positive risk, skip
        if n < min_authors:
            continue

        total_eligible += 1

        # Full-text CRediT check — only for sampled DOIs (Tier 1 signal)
        has_credit = None
        if check_fulltext and paper.get("doi", "N/A") in dois_to_check:
            credit_checked += 1
            has_credit = check_author_contributions_html(paper["doi"])
            if has_credit:
                credit_section_hits += 1
            print(
                f"  [{credit_checked}/{len(dois_to_check)}] "
                f"{paper['doi'][:35]}... → "
                f"{'CRediT found' if has_credit else 'No CRediT'}"
            )
            time.sleep(random.uniform(1.5, 3.0))  # polite delay

        # 3-tier per-paper classification (EC → A/R → RC)
        clf = classify_paper_author_order(authors, has_credit=has_credit)

        # Update tier counters
        if clf["classification"] == "EC":
            ec_count += 1
        elif clf["classification"] == "A/R":
            ar_count += 1
        elif clf["classification"] == "RC":
            rc_count += 1

        # Co-authorship counters
        co = clf["co_authorship"]
        if co["has_co_first"]:
            co_first_count += 1
        if co["has_co_last"]:
            co_last_count += 1

        paper_results.append({
            "doi":                         paper.get("doi", "N/A"),
            "title":                       paper.get("title", "N/A"),
            "journal":                     paper.get("journal", "N/A"),
            "year":                        paper.get("year"),
            "num_authors":                 n,
            "author_names":                " | ".join(a.get("family", "?") for a in authors),
            "is_alphabetical":             clf["is_alphabetical"],
            # 3-tier classification fields
            "author_order_classification": clf["classification"],
            "ordering_type":               clf["ordering_type"],
            "rc_variant":                  clf["rc_variant"] or "—",
            "author_order_confidence":     clf["confidence_score"],
            # Contribution strength scores (α, β, γ)
            "alpha":                       clf["alpha"],
            "beta":                        clf["beta"],
            "gamma":                       clf["gamma"],
            # Co-authorship signals
            "has_co_first":                co["has_co_first"],
            "has_co_last":                 co["has_co_last"],
            "co_first_signal":             co["co_first_signal"] or "—",
            "co_last_signal":              co["co_last_signal"] or "—",
            # Probability / provenance
            "chance_prob":                 round(chance_probability(n), 8),
            "source":                      paper.get("source", "N/A"),
            "has_credit_section":          has_credit,
            "interpretation":              clf["interpretation"],
        })

    # ── Rates ────────────────────────────────────────────────────────────────
    def rate(count):
        return round(count / total_eligible, 4) if total_eligible > 0 else 0.0

    ec_rate  = rate(ec_count)
    ar_rate  = rate(ar_count)
    rc_rate  = rate(rc_count)

    credit_rate = (
        round(credit_section_hits / credit_checked, 4)
        if credit_checked > 0 else None
    )

    # ── 3-Layer Journal Decision ──────────────────────────────────────────────
    if total_eligible < 20:
        conclusion = "Insufficient data"
        confidence = "Low"
    elif ec_rate >= 0.30:
        # Layer 1: EC dominant
        conclusion = "Explicit Contribution (EC)"
        confidence = "High" if total_eligible >= 100 else "Medium"
    elif ar_rate >= 0.75:
        # Layer 2: A/R dominant
        conclusion = "Alphabetical / Random (A/R)"
        confidence = "High" if total_eligible >= 100 else "Medium"
    elif ar_rate <= 0.25:
        # Layer 3: RC dominant (not enough alphabetical papers)
        conclusion = "Relative Contribution (RC)"
        confidence = "High" if total_eligible >= 100 else "Medium"
    else:
        conclusion = "Mixed / Hybrid"
        confidence = "Low"

    # Dominant α/β/γ for journal level
    journal_alpha = ar_rate
    journal_beta  = rc_rate
    journal_gamma = ec_rate

    summary = {
        "total_papers_fetched":  len(papers),
        "eligible_papers":       total_eligible,
        # Per-tier paper counts
        "ec_papers":             ec_count,
        "ar_papers":             ar_count,
        "rc_papers":             rc_count,
        # Rates
        "ec_rate":               ec_rate,
        "ar_rate":               ar_rate,
        "rc_rate":               rc_rate,
        # Journal-level contribution strength scores
        "journal_alpha":         round(journal_alpha, 4),
        "journal_beta":          round(journal_beta, 4),
        "journal_gamma":         round(journal_gamma, 4),
        # Co-authorship
        "co_first_papers":       co_first_count,
        "co_last_papers":        co_last_count,
        # Decision
        "conclusion":            conclusion,
        "confidence":            confidence,
        "min_authors_filter":    min_authors,
        # CRediT full-text check
        "credit_checked":        credit_checked,
        "credit_section_hits":   credit_section_hits,
        "credit_rate":           credit_rate,
        # Legacy (kept for backward compatibility)
        "alphabetical_papers":   ar_count,
        "contribution_based_papers": rc_count,
        "alphabetical_rate":     ar_rate,
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

    # Convenience fill for each tier
    ec_fill  = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")  # light green
    ar_fill  = PatternFill(start_color="DEEAF1", end_color="DEEAF1", fill_type="solid")  # light blue
    rc_fill  = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")  # light yellow

    def tier_fill(classification):
        if classification == "EC":
            return ec_fill
        elif classification == "A/R":
            return ar_fill
        elif classification == "RC":
            return rc_fill
        return yellow_fill

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet 1: Journal Summary
    # ─────────────────────────────────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Journal Summary"

    ws1.append(["Metric", "Value"])
    make_header_style(ws1, 1, dark_blue)

    conclusion = summary["conclusion"]
    if "EC" in conclusion:
        result_fill = green_fill
    elif "A/R" in conclusion or "Alphabetical" in conclusion:
        result_fill = blue_fill
    elif "RC" in conclusion or "Relative" in conclusion:
        result_fill = yellow_fill
    else:
        result_fill = red_fill

    # ── Section 1: 3-Tier Statistical Results ──
    ws1.append(["── 3-Tier Author Ordering Analysis ──", ""])
    make_header_style(ws1, ws1.max_row, dark_blue)

    summary_rows = [
        ("Journal / Query",                        journal_label),
        ("Min Authors Filter",                     f"≥ {summary['min_authors_filter']} authors"),
        ("Total Papers Fetched",                   summary["total_papers_fetched"]),
        ("Eligible Papers (≥ min authors)",        summary["eligible_papers"]),
        ("",                                       ""),
        ("EC  Papers (Explicit Contribution)",     summary["ec_papers"]),
        ("A/R Papers (Alphabetical / Random)",     summary["ar_papers"]),
        ("RC  Papers (Relative Contribution)",     summary["rc_papers"]),
        ("",                                       ""),
        ("EC  Rate  (γ — Tier 1 threshold ≥ 30%)", f"{summary['ec_rate']:.2%}"),
        ("A/R Rate  (α — Tier 2 threshold ≥ 75%)", f"{summary['ar_rate']:.2%}"),
        ("RC  Rate  (β — Tier 3 threshold ≤ 25%)", f"{summary['rc_rate']:.2%}"),
        ("",                                       ""),
        ("Journal α (A/R strength)",               f"{summary['journal_alpha']:.4f}"),
        ("Journal β (RC  strength)",               f"{summary['journal_beta']:.4f}"),
        ("Journal γ (EC  strength)",               f"{summary['journal_gamma']:.4f}"),
        ("",                                       ""),
        ("Co-First Author Papers",                 summary["co_first_papers"]),
        ("Co-Last  Author Papers",                 summary["co_last_papers"]),
        ("",                                       ""),
        ("JOURNAL CLASSIFICATION",                 conclusion),
        ("Confidence",                             summary["confidence"]),
    ]

    for metric, value in summary_rows:
        ws1.append([metric, value])
        row_idx = ws1.max_row
        if metric in ("JOURNAL CLASSIFICATION", "Confidence"):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = result_fill
                ws1.cell(row_idx, col).font = Font(bold=True, size=12)
        elif metric in ("EC  Rate  (γ — Tier 1 threshold ≥ 30%)",):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = ec_fill
        elif metric in ("A/R Rate  (α — Tier 2 threshold ≥ 75%)",):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = ar_fill
        elif metric in ("RC  Rate  (β — Tier 3 threshold ≤ 25%)",):
            for col in [1, 2]:
                ws1.cell(row_idx, col).fill = rc_fill
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
                "1st author = main contributor; last author may be PI/supervisor (RC or EC)"
                if "Contribution" in ft
                else "Author list likely sorted A→Z by family name (A/R)"
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

    # ── Section 3: CRediT Full-text Signal ──
    ws1.append([])
    ws1.append(["── Author Contributions (CRediT) Signal ──", ""])
    make_header_style(ws1, ws1.max_row, "70AD47")

    credit_rate = summary.get("credit_rate")
    if credit_rate is not None:
        credit_rate_display = f"{credit_rate:.2%}"
        credit_signal = (
            "EC culture confirmed (CRediT section present)"
            if credit_rate >= 0.5
            else "Likely NOT EC culture (low CRediT rate)"
        )
        credit_signal_fill = green_fill if credit_rate >= 0.5 else red_fill
    else:
        credit_rate_display = "Not checked"
        credit_signal = "Run with --check-fulltext to enable EC full-text detection"
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

    # ── 3-Tier Classification Legend ──
    ws1.append([])
    ws1.append(["Decision Layer", "Threshold", "Classification", "Nm-index Weight"])
    make_header_style(ws1, ws1.max_row, mid_blue)

    legend = [
        ("Layer 1 (EC)",  "EC_rate  ≥ 30%",  "Explicit Contribution (EC)",    "γ = 1.0  (CRediT/ACI, Eqs. 4–5)"),
        ("Layer 2 (A/R)", "A/R_rate ≥ 75%",  "Alphabetical / Random  (A/R)",  "α = 1.0  (Uniform 1/N,  Eq. 1)"),
        ("Layer 3 (RC)",  "A/R_rate ≤ 25%",  "Relative Contribution  (RC)",   "β = 1.0  (Harmonic,    Eqs. 2–3)"),
        ("Fallback",      "26% – 74%",        "Mixed / Hybrid",                "—"),
    ]
    tier_fills_legend = [ec_fill, ar_fill, rc_fill, yellow_fill]
    for row_data, tfill in zip(legend, tier_fills_legend):
        ws1.append(list(row_data))
        row_idx = ws1.max_row
        for col in range(1, 5):
            ws1.cell(row_idx, col).fill = tfill
            ws1.cell(row_idx, col).alignment = center_align

    ws1.column_dimensions["A"].width = 46
    ws1.column_dimensions["B"].width = 38
    ws1.column_dimensions["C"].width = 18
    ws1.column_dimensions["D"].width = 34

    # ─────────────────────────────────────────────────────────────────────────
    # Sheet 2: Per-Paper Results
    # ─────────────────────────────────────────────────────────────────────────
    ws2 = wb.create_sheet("Per-Paper Results")

    paper_headers = [
        "No.",                           # 1
        "DOI",                           # 2
        "Publication Title",             # 3
        "Journal",                       # 4
        "Year",                          # 5
        "# Authors",                     # 6
        "Author Family Names (in order)",# 7
        "Is Alphabetical?",              # 8
        "Classification (EC/A/R/RC)",    # 9
        "Ordering Type",                 # 10
        "RC Variant",                    # 11
        "Confidence Score",              # 12
        "α (A/R weight)",               # 13
        "β (RC  weight)",               # 14
        "γ (EC  weight)",               # 15
        "Co-First Authors?",             # 16
        "Co-Last Authors?",              # 17
        "Co-First Signal",               # 18
        "Co-Last Signal",                # 19
        "Chance Prob (1/n!)",            # 20
        "Data Source",                   # 21
        "CRediT Section?",               # 22
        "Interpretation",                # 23
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

        classification = p.get("author_order_classification", "Random")

        row_data = [
            i,                                                     # 1
            p["doi"],                                              # 2
            p["title"],                                            # 3
            p["journal"],                                          # 4
            p["year"],                                             # 5
            p["num_authors"],                                      # 6
            p["author_names"],                                     # 7
            "Yes" if p["is_alphabetical"] else "No",              # 8
            classification,                                        # 9
            p.get("ordering_type", "—"),                          # 10
            p.get("rc_variant", "—"),                             # 11
            p.get("author_order_confidence", 0.0),                 # 12
            p.get("alpha", 0.0),                                   # 13
            p.get("beta",  0.0),                                   # 14
            p.get("gamma", 0.0),                                   # 15
            "Yes" if p.get("has_co_first") else "No",             # 16
            "Yes" if p.get("has_co_last")  else "No",             # 17
            p.get("co_first_signal", "—"),                        # 18
            p.get("co_last_signal",  "—"),                        # 19
            p["chance_prob"],                                      # 20
            p.get("source", "N/A"),                               # 21
            credit_display,                                        # 22
            p.get("interpretation", ""),                          # 23
        ]
        ws2.append(row_data)
        row_idx = ws2.max_row

        # Colour-code "Is Alphabetical?" column (col 8)
        alpha_cell = ws2.cell(row_idx, 8)
        alpha_cell.fill = blue_fill if p["is_alphabetical"] else red_fill
        alpha_cell.font = Font(bold=True)
        alpha_cell.alignment = center_align

        # Colour-code "Classification" column (col 9) by tier
        class_cell = ws2.cell(row_idx, 9)
        class_cell.fill = tier_fill(classification)
        class_cell.font = Font(bold=True)
        class_cell.alignment = center_align

        # Colour-code α/β/γ columns (13–15)
        for col_idx, score_key in [(13, "alpha"), (14, "beta"), (15, "gamma")]:
            val = p.get(score_key, 0.0)
            score_cell = ws2.cell(row_idx, col_idx)
            if val == 1.0:
                score_cell.fill = green_fill
                score_cell.font = Font(bold=True)
            score_cell.alignment = center_align

        # Colour-code CRediT column (col 22)
        credit_cell = ws2.cell(row_idx, 22)
        if credit_display == "Yes":
            credit_cell.fill = green_fill
            credit_cell.font = Font(bold=True)
        elif credit_display == "No":
            credit_cell.fill = red_fill
        credit_cell.alignment = center_align

        # Co-first / co-last (cols 16–17)
        for col_idx in [16, 17]:
            cell = ws2.cell(row_idx, col_idx)
            if cell.value == "Yes":
                cell.fill = ec_fill
                cell.font = Font(bold=True)
            cell.alignment = center_align

        for col in range(1, len(paper_headers) + 1):
            ws2.cell(row_idx, col).alignment = (
                top_align if col in [3, 7, 10, 23] else center_align
            )

    col_widths = [5, 28, 52, 28, 7, 9, 55, 15, 22, 28, 18, 14, 12, 12, 12,
                  15, 14, 15, 14, 18, 14, 13, 55]
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
            "Classify journal author ordering (Alphabetical vs Contribution-based vs Random) "
            "by analysing papers via Crossref, Semantic Scholar, and/or Google Scholar APIs."
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
        choices=["crossref", "semantic", "google", "both", "all"],
        default="crossref",
        help="Data source: crossref (default) | semantic | google | both (crossref+semantic) | all (all three)"
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
    print(f"\n Field Culture Prior  : {field_culture['field_type']}")
    if field_culture["matched_keyword"]:
        print(f"   Matched keyword    : '{field_culture['matched_keyword']}'")
    print(f"   Prior confidence   : {field_culture['prior_confidence']}")

    # ── Step 1: Fetch papers ──
    papers = []

    if args.source in ("crossref", "both", "all"):
        crossref_papers = fetch_papers_crossref(
            issn=args.issn,
            journal_name=args.journal,
            max_papers=args.max,
        )
        papers.extend(crossref_papers)

    if args.source in ("semantic", "both", "all"):
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

    if args.source in ("google", "all"):
        google_max = args.max if args.source == "google" else max(50, args.max // 5)
        google_papers = fetch_papers_google_scholar(
            journal_name=journal_label,
            max_papers=google_max,
        )
        # Deduplicate by DOI before merging
        existing_dois = {p["doi"] for p in papers if p["doi"] != "N/A"}
        new_papers = [p for p in google_papers if p["doi"] not in existing_dois]
        papers.extend(new_papers)
        print(f"  Added {len(new_papers)} unique papers from Google Scholar.")

    if not papers:
        print(" No papers found. Check the ISSN or journal name.")
        return

    # ── Steps 2–6: Analyse ──
    paper_results, summary = analyze_papers(
        papers,
        min_authors=args.min_authors,
        check_fulltext=args.check_fulltext,
        fulltext_sample=args.fulltext_sample,
    )

    # ── Print 3-tier summary to console ──
    conclusion   = summary["conclusion"]
    ec_rate      = summary["ec_rate"]
    ar_rate      = summary["ar_rate"]
    rc_rate      = summary["rc_rate"]
    credit_rate  = summary.get("credit_rate")

    if "EC" in conclusion:
        tier_label = "EC  (Explicit Contribution)"
    elif "A/R" in conclusion or "Alphabetical" in conclusion:
        tier_label = "A/R (Alphabetical / Random)"
    elif "RC" in conclusion or "Relative" in conclusion:
        tier_label = "RC  (Relative Contribution)"
    else:
        tier_label = "Mixed / Hybrid"

    W = 64
    print(f"\n{'='*W}")
    print(f"  3-TIER AUTHOR ORDERING CLASSIFICATION")
    print(f"  Journal : {journal_label}")
    print(f"{'='*W}")
    print(f"  Total papers fetched              : {summary['total_papers_fetched']}")
    print(f"  Eligible papers (>= {args.min_authors} authors)    : {summary['eligible_papers']}")
    print(f"  {'─'*56}")
    print(f"  Per-paper tier breakdown:")
    print(f"    EC  papers (Explicit Contribution) : {summary['ec_papers']:4d}  [{ec_rate:.1%}]")
    print(f"    A/R papers (Alphabetical / Random) : {summary['ar_papers']:4d}  [{ar_rate:.1%}]")
    print(f"    RC  papers (Relative Contribution) : {summary['rc_papers']:4d}  [{rc_rate:.1%}]")
    print(f"  {'─'*56}")
    print(f"  Contribution strength scores (journal level):")
    print(f"    alpha (A/R) = {summary['journal_alpha']:.4f}")
    print(f"    beta  (RC)  = {summary['journal_beta']:.4f}")
    print(f"    gamma (EC)  = {summary['journal_gamma']:.4f}")
    print(f"  {'─'*56}")
    print(f"  Co-authorship patterns:")
    print(f"    Papers with co-first authors  : {summary['co_first_papers']}")
    print(f"    Papers with co-last  authors  : {summary['co_last_papers']}")
    print(f"  {'─'*56}")
    print(f"  3-Layer Decision:")
    print(f"    Layer 1 — EC_rate  >= 30% : {ec_rate:.1%}  {'<== TRIGGERED' if ec_rate >= 0.30 else ''}")
    print(f"    Layer 2 — A/R_rate >= 75% : {ar_rate:.1%}  {'<== TRIGGERED' if ar_rate >= 0.75 else ''}")
    print(f"    Layer 3 — A/R_rate <= 25% : {ar_rate:.1%}  {'<== TRIGGERED' if ar_rate <= 0.25 and ec_rate < 0.30 else ''}")
    print(f"  {'─'*56}")
    print(f"  CLASSIFICATION  : {tier_label}")
    print(f"  Confidence      : {summary['confidence']}")
    print(f"  {'─'*56}")
    print(f"  Field Culture Prior : {field_culture['field_type']}")
    print(f"  Prior Confidence    : {field_culture['prior_confidence']}")
    if args.check_fulltext and credit_rate is not None:
        print(f"  CRediT Section Rate : {credit_rate:.2%}")
    print(f"{'='*W}")

    # ── Step 7: Export ──
    save_to_excel(paper_results, summary, journal_label, field_culture=field_culture)


if __name__ == "__main__":
    main()
