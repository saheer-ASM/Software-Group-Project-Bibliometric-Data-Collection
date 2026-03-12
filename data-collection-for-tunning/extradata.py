import requests
import pandas as pd
import time
import ssl
import re
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
import os
from dotenv import load_dotenv

# ==== CONFIGURE THIS ====
load_dotenv()  

API_KEY = os.getenv("SEMANTIC_SCHOLAR_API_KEY")

if not API_KEY:
    raise ValueError("SEMANTIC_SCHOLAR_API_KEY not found. Check your .env file.")

KEYWORDS = [
    "Applied Microbiology and Biotechnology",
    "Biochemistry in medical",
    "Biological Psychiatry",
    "Care Planning",
    "Clinical Biochemistry",
    "Computer Science Applications",
    "Drug Guides",
    "Endocrine and Autonomic Systems",
    "Endocrinology, Diabetes and Metabolism",
    "Fundamentals and Skills",
    "Clinical Genetics",
    "Geography, Planning and Development",
    "Gerontology",
    "History and Philosophy of Science",
    "Information Systems and Management",
    "LPN and LVN",
    "Medical Assisting and Transcription",
    "Microbiology and medical",
    "Nature and Landscape Conservation",
    "Neurology",
    "Neuropsychology and Physiological Psychology",
    "Nuclear Energy and Engineering",
    "Numerical Analysis",
    "Nurse Assisting",
    "Obstetrics and Gynecology",
    "Oncology and nursing",
    "Oral Surgery",
    "Pathophysiology",
    "Physiology and medical",
    "Radiological and Ultrasound Technology",
    "Radiology, Nuclear Medicine and Imaging",
    "Renewable Energy, Sustainability and the Environment",
    "Respiratory Care",
    "Review and Exam Preparation",
    "Reviews and References and medical",
    "Stratigraphy"
]


PAPERS_PER_FIELD = 100  # max papers per field with abstracts
BATCH_SIZE = 150     # max papers per request
OUTPUT_FILE = "papers_by_field_with_only_abstract_extra.xlsx"

BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
HEADERS = {"x-api-key": API_KEY}

# ==== SSL-safe session ====
class TLSAdapter(HTTPAdapter):
    """Force TLS 1.2+ for requests session."""
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1  # disable old TLS
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=ctx)

session = requests.Session()
session.mount("https://", TLSAdapter())

# ==== Helper to clean text for Excel ====
def clean_text(text):
    """Remove illegal characters for Excel."""
    if not text:
        return ""
    # Remove control characters except newline, tab, carriage return
    return re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", text)

# ==== Fetch papers ====
all_papers = []

for keyword in KEYWORDS:
    print(f"\nFetching papers for keywords: {keyword}")
    offset = 0
    papers_collected = 0

    while papers_collected < PAPERS_PER_FIELD:
        limit = min(BATCH_SIZE, PAPERS_PER_FIELD - papers_collected)
        params = {
            "query": keyword,
            "limit": limit,
            "offset": offset,
            "fields": "title,abstract"
        }

        try:
            response = session.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching papers: {e}")
            print(f"Skipping remaining papers for '{keyword}' and moving to next keyword.")
            break

        batch = response.json().get("data", [])
        if not batch:
            print(f"No more papers returned for '{keyword}'. Collected {papers_collected} papers with abstracts.")
            break

        for paper in batch:
            abstract = paper.get("abstract", "")
            if not abstract:  # skip papers without abstract
                continue
            all_papers.append({
                "Field": keywords,
                "Title": clean_text(paper.get("title", "")),
                "Abstract": clean_text(abstract)
            })
            papers_collected += 1  # only count papers with abstract

        offset += len(batch)
        print(f"Collected {papers_collected}/{PAPERS_PER_FIELD} papers with abstracts for '{keyword}'...")

        # Respect API rate limit
        time.sleep(1)

# ==== Save to Excel ====
df = pd.DataFrame(all_papers)
df.to_excel(OUTPUT_FILE, index=False)
print(f"\nDone! Saved {len(df)} papers with abstracts to {OUTPUT_FILE}")
