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
├── main.py              # Basic version of the scraper
├── main_improved.py     # Enhanced version with anti-detection & CAPTCHA handling
├── .env                 # API keys (ScraperAPI, Scopus)
├── .gitignore           # Git ignore rules
├── requirements.txt     # Python dependencies
└── README.md            # This file
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

## License

This project is for **educational and research purposes only**. Please respect Google Scholar's terms of service.
