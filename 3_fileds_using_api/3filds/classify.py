# import os
# import csv
# import time
# from dotenv import load_dotenv
# from openai import OpenAI

# # -----------------------------
# # Load environment variables
# # -----------------------------
# load_dotenv()

# client = OpenAI(
#     api_key=os.environ.get("DEEPSEEK_API_KEY"),
#     base_url="https://api.deepseek.com"
# )

# MODEL_NAME = "deepseek-chat"

# MAIN_FIELDS = [
#     "Multidisciplinary",
#     "General Agricultural and Biological Sciences",
#     "Agricultural and Biological Sciences (miscellaneous)",
#     "Agronomy and Crop Science",
#     "Animal Science and Zoology",
#     "Aquatic Science",
#     "Ecology, Evolution, Behavior and Systematics",
#     "Food Science",
#     "Forestry",
#     "Horticulture",
#     "Insect Science",
#     "Plant Science",
#     "Soil Science",
#     "General Arts and Humanities",
#     "Arts and Humanities (miscellaneous)",
#     "History",
#     "Language and Linguistics",
#     "Archeology (arts and humanities)",
#     "Classics",
#     "Conservation",
#     "History and Philosophy of Science",
#     "Literature and Literary Theory",
#     "Museology",
#     "Music",
#     "Philosophy",
#     "Religious Studies",
#     "Visual Arts and Performing Arts",
#     "General Biochemistry, Genetics and Molecular Biology",
#     "Biochemistry, Genetics and Molecular Biology (miscellaneous)",
#     "Aging",
#     "Biochemistry",
#     "Biophysics",
#     "Biotechnology",
#     "Cancer Research",
#     "Cell Biology",
#     "Clinical Biochemistry",
#     "Developmental Biology",
#     "Endocrinology",
#     "Genetics",
#     "Molecular Biology",
#     "Molecular Medicine",
#     "Physiology",
#     "Structural Biology",
#     "General Business, Management and Accounting",
#     "Business, Management and Accounting ",
#     "Accounting",
#     "Business and International Management",
#     "Management Information Systems",
#     "Management of Technology and Innovation",
#     "Marketing",
#     "Organizational Behavior and Human Resource Management",
#     "Strategy and Management",
#     "Tourism, Leisure and Hospitality Management",
#     "Industrial Relations",
#     "General Chemical Engineering",
#     "Chemical Engineering",
#     "Bioengineering",
#     "Catalysis",
#     "Chemical Health and Safety",
#     "Colloid and Surface Chemistry",
#     "Filtration and Separation",
#     "Fluid Flow and Transfer Processes",
#     "Process Chemistry and Technology",
#     "General Chemistry",
#     "Chemistry (miscellaneous)",
#     "Analytical Chemistry",
#     "Electrochemistry",
#     "Inorganic Chemistry",
#     "Organic Chemistry",
#     "Physical and Theoretical Chemistry",
#     "Spectroscopy",
#     "General Computer Science",
#     "Computer Science",
#     "Artificial Intelligence",
#     "Computational Theory and Mathematics",
#     "Computer Graphics and Computer-Aided Design",
#     "Computer Networks and Communications",
#     "Computer Science Applications",
#     "Computer Vision and Pattern Recognition",
#     "Hardware and Architecture",
#     "Human-Computer Interaction",
#     "Information Systems",
#     "Signal Processing",
#     "Software",
#     "General Decision Sciences",
#     "Decision Sciences (miscellaneous)",
#     "Information Systems and Management",
#     "Management Science and Operations Research",
#     "Statistics, Probability and Uncertainty",
#     "General Earth and Planetary Sciences",
#     "Earth and Planetary Sciences ",
#     "Atmospheric Science",
#     "Computers in Earth Sciences",
#     "Earth-Surface Processes",
#     "Economic Geology",
#     "Geochemistry and Petrology",
#     "Geology",
#     "Geophysics",
#     "Geotechnical Engineering and Engineering Geology",
#     "Oceanography",
#     "Paleontology",
#     "Space and Planetary Science",
#     "Stratigraphy",
#     "General Economics, Econometrics and Finance",
#     "Economics, Econometrics and Finance",
#     "Economics and Econometrics",
#     "Finance",
#     "General Energy",
#     "Energy",
#     "Energy Engineering and Power Technology",
#     "Fuel Technology",
#     "Nuclear Energy and Engineering",
#     "Renewable Energy, Sustainability and the Environment",
#     "General Engineering",
#     "Engineering (miscellaneous)",
#     "Aerospace Engineering",
#     "Automotive Engineering",
#     "Biomedical Engineering",
#     "Civil and Structural Engineering",
#     "Computational Mechanics",
#     "Control and Systems Engineering",
#     "Electrical and Electronic Engineering",
#     "Industrial and Manufacturing Engineering",
#     "Mechanical Engineering",
#     "Mechanics of Materials",
#     "Ocean Engineering",
#     "Safety, Risk, Reliability and Quality",
#     "Media Technology",
#     "Building and Construction",
#     "Architecture",
#     "General Environmental Science",
#     "Environmental Science (miscellaneous)",
#     "Ecological Modeling",
#     "Ecology",
#     "Environmental Chemistry",
#     "Environmental  Engineering",
#     "Global and Planetary Change",
#     "Health, Toxicology and Mutagenesis",
#     "Management, Monitoring, Policy and Law",
#     "Nature and Landscape Conservation",
#     "Pollution",
#     "Waste Management and Disposal",
#     "Water Science and Technology",
#     "General Immunology and Microbiology",
#     "Immunology and Microbiology ",
#     "Applied Microbiology and Biotechnology",
#     "Immunology",
#     "Microbiology",
#     "Parasitology",
#     "Virology",
#     "General Materials Science",
#     "Materials Science",
#     "Biomaterials",
#     "Ceramics and Composites",
#     "Electronic, Optical and Magnetic Materials",
#     "Materials Chemistry",
#     "Metals and Alloys",
#     "Polymers and Plastics",
#     "Surfaces, Coatings and Films",
#     "General Mathematics",
#     "Mathematics (miscellaneous)",
#     "Algebra and Number Theory",
#     "Analysis",
#     "Applied Mathematics",
#     "Computational Mathematics",
#     "Control and Optimization",
#     "Discrete Mathematics and Combinatorics",
#     "Geometry and Topology",
#     "Logic",
#     "Mathematical Physics",
#     "Modeling and Simulation",
#     "Numerical Analysis",
#     "Statistics and Probability",
#     "Theoretical Computer Science",
#     "General Medicine",
#     "Medicine (miscellaneous)",
#     "Anatomy",
#     "Anesthesiology and Pain Medicine",
#     "Biochemistry (medical)",
#     "Cardiology and Cardiovascular Medicine",
#     "Critical Care and Intensive Care Medicine",
#     "Complementary and Alternative Medicine",
#     "Dermatology",
#     "Drug Guides",
#     "Embryology",
#     "Emergency Medicine",
#     "Endocrinology, Diabetes and Metabolism",
#     "Epidemiology",
#     "Family Practice",
#     "Gastroenterology",
#     "Genetics (clinical)",
#     "Geriatrics and Gerontology",
#     "Health Informatics",
#     "Health Policy",
#     "Hematology",
#     "Hepatology",
#     "Histology",
#     "Immunology and Allergy",
#     "Internal Medicine",
#     "Infectious Diseases",
#     "Microbiology (medical)",
#     "Nephrology",
#     "Neurology (clinical)",
#     "Obstetrics and Gynecology",
#     "Oncology",
#     "Ophthalmology",
#     "Orthopedics and Sports Medicine",
#     "Otorhinolaryngology",
#     "Pathology and Forensic Medicine",
#     "Pediatrics, Perinatology and Child Health",
#     "Pharmacology (medical)",
#     "Physiology (medical)",
#     "Psychiatry and Mental Health",
#     "Public Health, Environmental and Occupational Health",
#     "Pulmonary and Respiratory Medicine",
#     "Radiology, Nuclear Medicine and Imaging",
#     "Rehabilitation",
#     "Reproductive Medicine",
#     "Reviews and References (medical)",
#     "Rheumatology",
#     "Surgery",
#     "Transplantation",
#     "Urology",
#     "General Neuroscience",
#     "Neuroscience (miscellaneous)",
#     "Behavioral Neuroscience",
#     "Biological Psychiatry",
#     "Cellular and Molecular Neuroscience",
#     "Cognitive Neuroscience",
#     "Developmental Neuroscience",
#     "Endocrine and Autonomic Systems",
#     "Neurology",
#     "Sensory Systems",
#     "General Nursing",
#     "Nursing (miscellaneous)",
#     "Assessment and Diagnosis",
#     "Care Planning",
#     "Community and Home Care",
#     "Critical Care Nursing",
#     "Emergency Nursing",
#     "Fundamentals and Skills",
#     "Gerontology",
#     "Іssues, Ethics and Legal Aspects",
#     "Leadership and Management",
#     "LPN and LVN",
#     "Maternity and Midwifery",
#     "Medical and Surgical Nursing",
#     "Nurse Assisting",
#     "Nutrition and Dietetics",
#     "Oncology (nursing)",
#     "Pathophysiology",
#     "Pediatrics",
#     "Pharmacology (nursing)",
#     "Psychiatric Mental Health",
#     "Research and Theory",
#     "Review and Exam Preparation",
#     "General Pharmacology, Toxicology and Pharmaceutics",
#     "Pharmacology, Toxicology and Pharmaceutics (miscellaneous)",
#     "Drug Discovery",
#     "Pharmaceutical Science",
#     "Pharmacology",
#     "Toxicology",
#     "General Physics and Astronomy",
#     "Physics and Astronomy (miscellaneous)",
#     "Acoustics and Ultrasonics",
#     "Astronomy and Astrophysics",
#     "Condensed Matter Physics",
#     "Instrumentation",
#     "Nuclear and High Energy Physics",
#     "Atomic and Molecular Physics, and Optics",
#     "Radiation",
#     "Statistical and Nonlinear Physics",
#     "Surfaces and Interfaces",
#     "General Psychology",
#     "Psychology (miscellaneous)",
#     "Applied Psychology",
#     "Clinical Psychology",
#     "Developmental and Educational Psychology",
#     "Experimental and Cognitive Psychology",
#     "Neuropsychology and Physiological Psychology",
#     "Social Psychology",
#     "General Social Sciences",
#     "Social Sciences (miscellaneous)",
#     "Archeology",
#     "Development",
#     "Education",
#     "Geography, Planning and Development",
#     "Health (social science)",
#     "Human Factors and Ergonomics",
#     "Law",
#     "Library and Information Sciences",
#     "Linguistics and Language",
#     "Safety Research",
#     "Sociology and Political Science",
#     "Transportation",
#     "Anthropology",
#     "Communication",
#     "Cultural Studies",
#     "Demography",
#     "Gender Studies",
#     "Life-span and Life-course Studies",
#     "Political Science and International Relations",
#     "Public Administration",
#     "Urban Studies",
#     "General Veterinary",
#     "Veterinary (miscellaneous)",
#     "Equine",
#     "Food Animals",
#     "Small Animals",
#     "General Dentistry",
#     "Dentistry (miscellaneous)",
#     "Dental Assisting",
#     "Dental Hygiene",
#     "Oral Surgery",
#     "Orthodontics",
#     "Periodontics",
#     "General Health Professions",
#     "Health Professions (miscellaneous)",
#     "Chiropractics",
#     "Complementary and Manual Therapy",
#     "Emergency Medical Services",
#     "Health Information Management",
#     "Medical Assisting and Transcription",
#     "Medical Laboratory Technology",
#     "Medical Terminology",
#     "Occupational Therapy",
#     "Optometry",
#     "Pharmacy",
#     "Physical Therapy, Sports Therapy and Rehabilitation",
#     "Podiatry",
#     "Radiological and Ultrasound Technology",
#     "Respiratory Care",
#     "Speech and Hearing"
# ]

# # -----------------------------
# # Parse model output
# # -----------------------------
# def parse_top3_fields_confidence(text, fields):
#     results = []
#     for line in text.splitlines():
#         if "Confidence" in line:
#             try:
#                 parts = line.split(",")
#                 field = parts[0].split(":")[1].strip()
#                 conf = float(parts[1].split(":")[1].replace("%", "").strip())
#                 if field in fields:
#                     results.append((field, conf))
#             except:
#                 pass

#     # Ensure exactly 3 outputs
#     while len(results) < 3:
#         results.append(("", 0.0))

#     return results[:3]

# # -----------------------------
# # Classify a single paper
# # -----------------------------
# def classify_paper(title, abstract, fields):
# #     prompt = f"""
# # Classify the following paper into the top 3 most relevant fields from this list:

# # {', '.join(fields)}

# # Title:
# # {title}

# # Abstract:
# # {abstract}

# # Respond ONLY in this format:
# # Field 1: <name>, Confidence: <percent>%
# # Field 2: <name>, Confidence: <percent>%
# # Field 3: <name>, Confidence: <percent>%

# # The confidence percentages MUST sum to 100%.'
# # Don'T include any explanations or extra text, just the 3 fields and their confidence scores.
# # """


#     prompt = (
#         f"Classify the following paper into the top 3 most relevant fields from this list: {', '.join(fields)}.\n"
#         f"Title: {title}\nAbstract: {abstract}\n"
#         "Respond with the 3 fields and their confidence percentages, such that the sum of the confidences is 100%. Format: Field 1: <name>, Confidence: <percent>%. Field 2: <name>, Confidence: <percent>%. Field 3: <name>, Confidence: <percent>%."
#     )

#     max_retries = 5
#     delay = 5

#     for attempt in range(1, max_retries + 1):
#         try:
#             response = client.chat.completions.create(
#                 model=MODEL_NAME,
#                 messages=[
#                     {"role": "system", "content": "You are an academic paper classification assistant."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 temperature=0.2
#             )

#             content = response.choices[0].message.content
#             top_fields = parse_top3_fields_confidence(content, fields)
#             return top_fields, content

#         except Exception as e:
#             if attempt < max_retries:
#                 print(f"API error: {e}. Retrying in {delay}s...")
#                 time.sleep(delay)
#                 delay *= 2
#             else:
#                 return [("ERROR", 0), ("", 0), ("", 0)], str(e)

# # -----------------------------
# # Classify CSV file
# # -----------------------------
# def classify_csv(input_csv, output_csv):
#     with open(input_csv, newline='', encoding='utf-8', errors='replace') as infile, \
#          open(output_csv, 'w', newline='', encoding='utf-8') as outfile:

#         reader = list(csv.DictReader(infile))
#         writer = csv.DictWriter(
#             outfile,
#             fieldnames=[
#                 'title', 'abstract',
#                 'field_1_na', 'field_1_co',
#                 'field_2_na', 'field_2_co',
#                 'field_3_na', 'field_3_co'
#             ]
#         )
#         writer.writeheader()

#         total = len(reader)

#         for idx, row in enumerate(reader, 1):
#             title = row.get('title') or row.get('Title') or row.get('TITLE') or ''
#             abstract = row.get('abstract') or row.get('Abstract') or row.get('ABSTRACT') or ''

#             print(f"Processing {idx}/{total}: {title[:60]}")

#             fields_conf, _ = classify_paper(title, abstract, MAIN_FIELDS)

#             writer.writerow({
#                 'title': title,
#                 'abstract': abstract,
#                 'field_1_na': fields_conf[0][0],
#                 'field_1_co': f"{fields_conf[0][1]:.2f}%",
#                 'field_2_na': fields_conf[1][0],
#                 'field_2_co': f"{fields_conf[1][1]:.2f}%",
#                 'field_3_na': fields_conf[2][0],
#                 'field_3_co': f"{fields_conf[2][1]:.2f}%"
#             })

#             outfile.flush()
#             time.sleep(1.5)  # avoid rate limits

#         print("✅ Classification completed:", output_csv)

# # -----------------------------
# # Run
# # -----------------------------
# if __name__ == "__main__":
#     classify_csv("input.csv", "output.csv")


import os
import csv
import time
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()

import os
import csv
import time
from openai import OpenAI  # Assuming you have the DeepSeek OpenAI-compatible SDK

# --- Helper function ---
def parse_top3_fields_confidence(text, fields):
    import re
    # Find all field/confidence pairs
    pattern = re.compile(
        r"Field\s*\d+\s*[:=]\s*([\w\s\-\(\)&,]+),?\s*Confidence\s*[:=]\s*(\d{1,3})%", 
        re.IGNORECASE
    )
    matches = pattern.findall(text)
    results = []
    for i, (field, conf) in enumerate(matches):
        field = field.strip()
        # Try to match to known fields if possible
        for f in fields:
            if f.lower() in field.lower():
                field = f
                break
        try:
            conf = float(conf)
        except:
            conf = 0.0
        results.append((field, conf))
    # If less than 3, pad with empty/0
    while len(results) < 3:
        results.append(("", 0.0))
    return results[:3]

# --- Client Setup ---
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

MODEL_NAME = "deepseek-reasoner"

MAIN_FIELDS = [
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
    "Business, Management and Accounting ",
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
    "Earth and Planetary Sciences ",
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
    "Environmental  Engineering",
    "Global and Planetary Change",
    "Health, Toxicology and Mutagenesis",
    "Management, Monitoring, Policy and Law",
    "Nature and Landscape Conservation",
    "Pollution",
    "Waste Management and Disposal",
    "Water Science and Technology",
    "General Immunology and Microbiology",
    "Immunology and Microbiology ",
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
    "Speech and Hearing","Genetics"
]
# --- Paper classification ---
def classify_paper(title, abstract, fields):
    prompt = (
        f"Classify the following paper into the top 3 most relevant fields from this list: {', '.join(fields)}.\n"
        f"Title: {title}\nAbstract: {abstract}\n"
        "Respond with the 3 fields and their confidence percentages, such that the sum of the confidences is 100%.Do not include any explanations or extra text and you must give the fileds from above list only."
        "Format: Field 1: <name>, Confidence: <percent>%. "
        "Field 2: <name>, Confidence: <percent>%. "
        "Field 3: <name>, Confidence: <percent>%."
    )

    max_retries = 5
    delay = 5  # seconds
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            # Extract text from response
            content = response.choices[0].message.content
            top_fields = parse_top3_fields_confidence(content, fields)
            return top_fields, content
        except Exception as e:
            if 'connection' in str(e).lower() or 'timeout' in str(e).lower() or 'network' in str(e).lower():
                if attempt < max_retries:
                    print(f"Connection error: {e}. Retrying in {delay} seconds (attempt {attempt}/{max_retries})...")
                    time.sleep(delay)
                    delay *= 2
                    continue
            return [("ERROR", 0), ("", 0), ("", 0)], str(e)

# --- CSV Processing ---
def classify_csv(input_csv, output_csv):
    with open(input_csv, newline='', encoding='utf-8') as infile, \
         open(output_csv, 'w', newline='', encoding='utf-8') as outfile:
        reader = list(csv.DictReader(infile))
        total = len(reader)
        fieldnames = ['title', 'abstract']
        for i in range(1, 4):
            fieldnames += [f'field_{i}_na', f'field_{i}_co']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for idx, row in enumerate(reader, 1):
            title = row.get('Title') or (list(row.values())[0] if row else '')
            abstract = row.get('Abstract', '')
            print(f"Processing {idx}/{total}: {str(title)[:50]}...", flush=True)

            fields_conf, _ = classify_paper(title, abstract, MAIN_FIELDS)

            out_row = {'title': title, 'abstract': abstract}
            for i, (fname, fconf) in enumerate(fields_conf, 1):
                out_row[f'field_{i}_na'] = fname
                out_row[f'field_{i}_co'] = f"{fconf:.2f}%"
            writer.writerow(out_row)
            outfile.flush()
            time.sleep(1.5)  # rate limit safety
        print("Processing complete. Output saved to", output_csv)

if __name__ == "__main__":
    classify_csv('input4_1.csv', 'output4_1.csv')