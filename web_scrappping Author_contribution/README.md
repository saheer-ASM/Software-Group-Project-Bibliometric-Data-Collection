# Google Scholar Web Scraper

A Python tool that scrapes publication details from Google Scholar for a given author name — including **title**, **abstract**, **citation count**, and **publication year** — and exports everything to a formatted Excel file.

## Features

- 🔍 Search Google Scholar by author name
- 📄 Extract all publications from an author's profile
- 📝 Scrape abstracts from individual publication pages
- 📊 Capture citation counts and publication years
- 💾 Export results to a styled `.xlsx` Excel file
- 🛡️ Anti-detection measures (user-agent rotation, human-like delays, stealth scripts)
- 🔗 Optional Scopus API enrichment (DOI, Scopus ID, EID)

## Project Structure

```
├── main.py                     # Basic Google Scholar scraper
├── main_improved.py            # Enhanced scraper with anti-detection & CAPTCHA handling
├── author_order_classifier.py  # Classifies journals: alphabetical vs contribution-based
├── .env                        # API keys (ScraperAPI, Scopus, contact email)
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Scripts

### `main.py` — Basic Scraper

A straightforward Google Scholar scraper using Playwright:

- Searches for the author profile on Google Scholar
- Loads all publications by clicking "Show more"
- Opens each publication page to extract the abstract
- Saves results to Excel

### `main_improved.py` — Enhanced Scraper

An improved version with robust anti-detection:

- **User-agent rotation** across multiple browser signatures
- **Human-like behaviour** — random delays, gradual scrolling, mouse movements, character-by-character typing
- **Stealth scripts** — hides `navigator.webdriver`, spoofs plugins and languages
- **CAPTCHA handling** — detects CAPTCHAs and pauses for manual solving (30 s window)
- **Fresh browser contexts** per request with randomised fingerprints
- Accepts both an **author name** or a **direct profile URL** as input

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Shaith-Ahamed/Web_scrapping.git
cd Web_scrapping
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers

```bash
python -m playwright install chromium
```

### 4. Set up environment variables

Create a `.env` file in the project root:

```
key=your_scraperapi_key
scopus_key=your_scopus_api_key   # optional
```

## Usage

### Run the basic scraper

```bash
python main.py
```

### Run the improved scraper

```bash
python main_improved.py
```

You can also pass the author name directly:

```bash
python main_improved.py "Author Name"
```

### Interactive prompt

```
Enter author name: Thilina Weerasinghe
```

The scraper will:

1. Search Google Scholar for the author
2. Open the author's profile
3. Load all publications
4. Extract title, year, citations, and abstract for each paper
5. Save everything to `publications_<AuthorName>_<timestamp>.xlsx`

## Output

An Excel file with the following columns:

| Column | Description |
|---|---|
| No. | Row number |
| Author Name | Searched author |
| Scopus Author ID | Scopus ID (if available) |
| Publication Title | Full title |
| Abstract | Extracted abstract text |
| Publication Year (Scholar) | Year from Google Scholar |
| Publication Year (Scopus) | Year from Scopus (if available) |
| Citations (Scholar) | Citation count |
| Scopus Document ID | Scopus doc ID (if available) |
| Scopus EID | Scopus EID (if available) |
| DOI | Digital Object Identifier (if available) |

## Requirements

- Python 3.8+
- Playwright
- openpyxl
- python-dotenv
- requests

See `requirements.txt` for full list.

## Notes

- A **Chromium browser window** will open during scraping (non-headless) so you can monitor progress and solve CAPTCHAs if needed.
- Google Scholar may rate-limit or show CAPTCHAs with heavy use. The improved version handles this with delays and manual-solve pauses.
- Scopus enrichment is **optional** — works without a Scopus API key.

---

## `author_order_classifier.py` — Author Ordering Classifier

Determines whether a journal uses **alphabetical** or **contribution-based** author ordering
by fetching and analysing a large sample of papers from the [Crossref API](https://api.crossref.org).

### How it works

| Step | Action | Detail |
|---|---|---|
| 1 | Fetch paper metadata | Crossref API — filter by ISSN or journal name |
| 2 | Normalize author names | Lowercase family name, remove punctuation |
| 3 | Check alphabetical order | Compare actual order vs sorted order |
| 4 | Filter by author count | Only papers with ≥ 4 authors (reduces false positives) |
| 5 | Compute AlphabeticalRate | `alphabetical_papers / eligible_papers` |
| 6 | Classify journal | Apply threshold rules below |
| 7 | Export to Excel | Per-paper results + summary sheet |

### Classification thresholds

| AlphabeticalRate | Classification | Confidence |
|---|---|---|
| ≥ 75% | Alphabetical-dominant | High (if ≥ 100 papers) |
| 26% – 74% | Mixed / Unclear | Low |
| ≤ 25% | Contribution-based | High (if ≥ 100 papers) |

### Why filter by ≥ 4 authors?

| # Authors | Chance of random alphabetical (1/n!) | Use for evidence? |
|---|---|---|
| 2 | 50.0% | No — exclude |
| 3 | 16.7% | Marginal |
| 4 | 4.2% | Yes — include |
| 5 | 0.8% | Strong evidence |
| 6+ | < 0.1% | Very strong evidence |

### Usage

```bash
# By ISSN
python author_order_classifier.py --issn 1476-4687 --max 500

# By journal name
python author_order_classifier.py --journal "IEEE Transactions on Networking" --max 300

# Interactive prompt
python author_order_classifier.py
```

### Optional `.env` setting

Add your email for Crossref's polite pool (faster responses):
```
contact_email=your@email.com
```

### Output

An Excel file `author_order_<journal>_<timestamp>.xlsx` with:
- **Sheet 1 — Journal Summary**: AlphabeticalRate, Conclusion, Confidence, classification legend
- **Sheet 2 — Per-Paper Results**: one row per paper with DOI, title, authors, alphabetical flag, chance probability

---

## License

This project is for **educational and research purposes only**. Please respect Google Scholar's terms of service.
