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

FIELDS = [
    "Multidisciplinary",
    "General Agricultural and Biological Sciences",
    "Agricultural and Biological Sciences (miscellaneous)",
    "Agronomy and Crop Science",
    "Animal Science and Zoology",
    "Aquatic Science",
    "Ecology, Evolution, Behavior and Systematics",
    "Food Science",
    "Forestry",
    "Horticulture",
    "Insect Science",
    "Plant Science",
    "Soil Science",
    "General Arts and Humanities",
    "Arts and Humanities (miscellaneous)",
    "History",
    "Language and Linguistics",
    "Archeology (arts and humanities)",
    "Classics",
    "Conservation",
    "History and Philosophy of Science",
    "Literature and Literary Theory",
    "Museology",
    "Music",
    "Philosophy",
    "Religious Studies",
    "Visual Arts and Performing Arts",
    "General Biochemistry, Genetics and Molecular Biology",
    "Biochemistry, Genetics and Molecular Biology (miscellaneous)",
    "Aging",
    "Biochemistry",
    "Biophysics",
    "Biotechnology",
    "Cancer Research",
    "Cell Biology",
    "Clinical Biochemistry",
    "Developmental Biology",
    "Endocrinology",
    "Genetics",
    "Molecular Biology",
    "Molecular Medicine",
    "Physiology",
    "Structural Biology",
    "General Business, Management and Accounting",
    "Business, Management and Accounting",
    "Accounting",
    "Business and International Management",
    "Management Information Systems",
    "Management of Technology and Innovation",
    "Marketing",
    "Organizational Behavior and Human Resource Management",
    "Strategy and Management",
    "Tourism, Leisure and Hospitality Management",
    "Industrial Relations",
    "General Chemical Engineering",
    "Chemical Engineering",
    "Bioengineering",
    "Catalysis",
    "Chemical Health and Safety",
    "Colloid and Surface Chemistry",
    "Filtration and Separation",
    "Fluid Flow and Transfer Processes",
    "Process Chemistry and Technology",
    "General Chemistry",
    "Chemistry (miscellaneous)",
    "Analytical Chemistry",
    "Electrochemistry",
    "Inorganic Chemistry",
    "Organic Chemistry",
    "Physical and Theoretical Chemistry",
    "Spectroscopy",
    "General Computer Science",
    "Computer Science",
    "Artificial Intelligence",
    "Computational Theory and Mathematics",
    "Computer Graphics and Computer-Aided Design",
    "Computer Networks and Communications",
    "Computer Science Applications",
    "Computer Vision and Pattern Recognition",
    "Hardware and Architecture",
    "Human-Computer Interaction",
    "Information Systems",
    "Signal Processing",
    "Software",
    "General Decision Sciences",
    "Decision Sciences (miscellaneous)",
    "Information Systems and Management",
    "Management Science and Operations Research",
    "Statistics, Probability and Uncertainty",
    "General Earth and Planetary Sciences",
    "Earth and Planetary Sciences",
    "Atmospheric Science",
    "Computers in Earth Sciences",
    "Earth-Surface Processes",
    "Economic Geology",
    "Geochemistry and Petrology",
    "Geology",
    "Geophysics",
    "Geotechnical Engineering and Engineering Geology",
    "Oceanography",
    "Paleontology",
    "Space and Planetary Science",
    "Stratigraphy",
    "General Economics, Econometrics and Finance",
    "Economics, Econometrics and Finance",
    "Economics and Econometrics",
    "Finance",
    "General Energy",
    "Energy",
    "Energy Engineering and Power Technology",
    "Fuel Technology",
    "Nuclear Energy and Engineering",
    "Renewable Energy, Sustainability and the Environment",
    "General Engineering",
    "Engineering (miscellaneous)",
    "Aerospace Engineering",
    "Automotive Engineering",
    "Biomedical Engineering",
    "Civil and Structural Engineering",
    "Computational Mechanics",
    "Control and Systems Engineering",
    "Electrical and Electronic Engineering",
    "Industrial and Manufacturing Engineering",
    "Mechanical Engineering",
    "Mechanics of Materials",
    "Ocean Engineering",
    "Safety, Risk, Reliability and Quality",
    "Media Technology",
    "Building and Construction",
    "Architecture",
    "General Environmental Science",
    "Environmental Science (miscellaneous)",
    "Ecological Modeling",
    "Ecology",
    "Environmental Chemistry",
    "Environmental Engineering",
    "Global and Planetary Change",
    "Health, Toxicology and Mutagenesis",
    "Management, Monitoring, Policy and Law",
    "Nature and Landscape Conservation",
    "Pollution",
    "Waste Management and Disposal",
    "Water Science and Technology",
    "General Immunology and Microbiology",
    "Immunology and Microbiology",
    "Applied Microbiology and Biotechnology",
    "Immunology",
    "Microbiology",
    "Parasitology",
    "Virology",
    "General Materials Science",
    "Materials Science",
    "Biomaterials",
    "Ceramics and Composites",
    "Electronic, Optical and Magnetic Materials",
    "Materials Chemistry",
    "Metals and Alloys",
    "Polymers and Plastics",
    "Surfaces, Coatings and Films",
    "General Mathematics",
    "Mathematics (miscellaneous)",
    "Algebra and Number Theory",
    "Analysis",
    "Applied Mathematics",
    "Computational Mathematics",
    "Control and Optimization",
    "Discrete Mathematics and Combinatorics",
    "Geometry and Topology",
    "Logic",
    "Mathematical Physics",
    "Modeling and Simulation",
    "Numerical Analysis",
    "Statistics and Probability",
    "Theoretical Computer Science",
    "General Medicine",
    "Medicine (miscellaneous)",
    "Anatomy",
    "Anesthesiology and Pain Medicine",
    "Biochemistry (medical)",
    "Cardiology and Cardiovascular Medicine",
    "Critical Care and Intensive Care Medicine",
    "Complementary and Alternative Medicine",
    "Dermatology",
    "Drug Guides",
    "Embryology",
    "Emergency Medicine",
    "Endocrinology, Diabetes and Metabolism",
    "Epidemiology",
    "Family Practice",
    "Gastroenterology",
    "Genetics (clinical)",
    "Geriatrics and Gerontology",
    "Health Informatics",
    "Health Policy",
    "Hematology",
    "Hepatology",
    "Histology",
    "Immunology and Allergy",
    "Internal Medicine",
    "Infectious Diseases",
    "Microbiology (medical)",
    "Nephrology",
    "Neurology (clinical)",
    "Obstetrics and Gynecology",
    "Oncology",
    "Ophthalmology",
    "Orthopedics and Sports Medicine",
    "Otorhinolaryngology",
    "Pathology and Forensic Medicine",
    "Pediatrics, Perinatology and Child Health",
    "Pharmacology (medical)",
    "Physiology (medical)",
    "Psychiatry and Mental Health",
    "Public Health, Environmental and Occupational Health",
    "Pulmonary and Respiratory Medicine",
    "Radiology, Nuclear Medicine and Imaging",
    "Rehabilitation",
    "Reproductive Medicine",
    "Reviews and References (medical)",
    "Rheumatology",
    "Surgery",
    "Transplantation",
    "Urology",
    "General Neuroscience",
    "Neuroscience (miscellaneous)",
    "Behavioral Neuroscience",
    "Biological Psychiatry",
    "Cellular and Molecular Neuroscience",
    "Cognitive Neuroscience",
    "Developmental Neuroscience",
    "Endocrine and Autonomic Systems",
    "Neurology",
    "Sensory Systems",
    "General Nursing",
    "Nursing (miscellaneous)",
    "Assessment and Diagnosis",
    "Care Planning",
    "Community and Home Care",
    "Critical Care Nursing",
    "Emergency Nursing",
    "Fundamentals and Skills",
    "Gerontology",
    "Іssues, Ethics and Legal Aspects",
    "Leadership and Management",
    "LPN and LVN",
    "Maternity and Midwifery",
    "Medical and Surgical Nursing",
    "Nurse Assisting",
    "Nutrition and Dietetics",
    "Oncology (nursing)",
    "Pathophysiology",
    "Pediatrics",
    "Pharmacology (nursing)",
    "Psychiatric Mental Health",
    "Research and Theory",
    "Review and Exam Preparation",
    "General Pharmacology, Toxicology and Pharmaceutics",
    "Pharmacology, Toxicology and Pharmaceutics (miscellaneous)",
    "Drug Discovery",
    "Pharmaceutical Science",
    "Pharmacology",
    "Toxicology",
    "General Physics and Astronomy",
    "Physics and Astronomy (miscellaneous)",
    "Acoustics and Ultrasonics",
    "Astronomy and Astrophysics",
    "Condensed Matter Physics",
    "Instrumentation",
    "Nuclear and High Energy Physics",
    "Atomic and Molecular Physics, and Optics",
    "Radiation",
    "Statistical and Nonlinear Physics",
    "Surfaces and Interfaces",
    "General Psychology",
    "Psychology (miscellaneous)",
    "Applied Psychology",
    "Clinical Psychology",
    "Developmental and Educational Psychology",
    "Experimental and Cognitive Psychology",
    "Neuropsychology and Physiological Psychology",
    "Social Psychology",
    "General Social Sciences",
    "Social Sciences (miscellaneous)",
    "Archeology",
    "Development",
    "Education",
    "Geography, Planning and Development",
    "Health (social science)",
    "Human Factors and Ergonomics",
    "Law",
    "Library and Information Sciences",
    "Linguistics and Language",
    "Safety Research",
    "Sociology and Political Science",
    "Transportation",
    "Anthropology",
    "Communication",
    "Cultural Studies",
    "Demography",
    "Gender Studies",
    "Life-span and Life-course Studies",
    "Political Science and International Relations",
    "Public Administration",
    "Urban Studies",
    "General Veterinary",
    "Veterinary (miscellaneous)",
    "Equine",
    "Food Animals",
    "Small Animals",
    "General Dentistry",
    "Dentistry (miscellaneous)",
    "Dental Assisting",
    "Dental Hygiene",
    "Oral Surgery",
    "Orthodontics",
    "Periodontics",
    "General Health Professions",
    "Health Professions (miscellaneous)",
    "Chiropractics",
    "Complementary and Manual Therapy",
    "Emergency Medical Services",
    "Health Information Management",
    "Medical Assisting and Transcription",
    "Medical Laboratory Technology",
    "Medical Terminology",
    "Occupational Therapy",
    "Optometry",
    "Pharmacy",
    "Physical Therapy, Sports Therapy and Rehabilitation",
    "Podiatry",
    "Radiological and Ultrasound Technology",
    "Respiratory Care",
    "Speech and Hearing"
]


PAPERS_PER_FIELD = 100  # max papers per field with abstracts
BATCH_SIZE = 150     # max papers per request
OUTPUT_FILE = "papers_by_field_with_only_abstract.xlsx"

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

for field in FIELDS:
    print(f"\nFetching papers for field: {field}")
    offset = 0
    papers_collected = 0

    while papers_collected < PAPERS_PER_FIELD:
        limit = min(BATCH_SIZE, PAPERS_PER_FIELD - papers_collected)
        params = {
            "query": field,
            "limit": limit,
            "offset": offset,
            "fields": "title,abstract"
        }

        try:
            response = session.get(BASE_URL, headers=HEADERS, params=params, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching papers: {e}")
            print(f"Skipping remaining papers for '{field}' and moving to next field.")
            break

        batch = response.json().get("data", [])
        if not batch:
            print(f"No more papers returned for '{field}'. Collected {papers_collected} papers with abstracts.")
            break

        for paper in batch:
            abstract = paper.get("abstract", "")
            if not abstract:  # skip papers without abstract
                continue
            all_papers.append({
                "Field": field,
                "Title": clean_text(paper.get("title", "")),
                "Abstract": clean_text(abstract)
            })
            papers_collected += 1  # only count papers with abstract

        offset += len(batch)
        print(f"Collected {papers_collected}/{PAPERS_PER_FIELD} papers with abstracts for '{field}'...")

        # Respect API rate limit
        time.sleep(1)

# ==== Save to Excel ====
df = pd.DataFrame(all_papers)
df.to_excel(OUTPUT_FILE, index=False)
print(f"\nDone! Saved {len(df)} papers with abstracts to {OUTPUT_FILE}")
