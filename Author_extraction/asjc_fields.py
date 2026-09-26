"""ASJC / Scopus subject-area names used as the field axis of the sample.

Originally copied verbatim from `data-collection-for-tunning/main.py` (333
entries). Reconciled against the fine-tuned classifier's label space in
`feildclassification/training_output/final_model/label_mapping.json` (305
labels): 37 fields with no training coverage there were removed, and 20 more
were renamed to that file's punctuation (commas stripped) to match exactly.
296 fields remain.
"""

ASJC_FIELDS = [
    #replace the list with shaith provide for you here like below
    #Example list is given need to replace with your list of fileds

    "Multidisciplinary",
    "General Agricultural and Biological Sciences",
    "Agricultural and Biological Sciences (miscellaneous)",
    "Agronomy and Crop Science",
    
]

# Removed (present in the original 333 but absent from label_mapping.json,
# meaning the classifier has zero training examples for them):
#   History and Philosophy of Science, Clinical Biochemistry,
#   Computer Science Applications, Information Systems and Management,
#   Stratigraphy, Nuclear Energy and Engineering,
#   Renewable Energy, Sustainability and the Environment,
#   Nature and Landscape Conservation, Applied Microbiology and Biotechnology,
#   Numerical Analysis, Biochemistry (medical), Drug Guides,
#   Endocrinology, Diabetes and Metabolism, Genetics (clinical),
#   Microbiology (medical), Obstetrics and Gynecology, Physiology (medical),
#   Radiology, Nuclear Medicine and Imaging, Reviews and References (medical),
#   Biological Psychiatry, Endocrine and Autonomic Systems, Neurology,
#   Care Planning, Fundamentals and Skills, Gerontology, LPN and LVN,
#   Nurse Assisting, Oncology (nursing), Pathophysiology,
#   Review and Exam Preparation, Nuclear and High Energy Physics,
#   Neuropsychology and Physiological Psychology,
#   Geography, Planning and Development, Oral Surgery,
#   Medical Assisting and Transcription, Radiological and Ultrasound
#   Technology, Respiratory Care.
#
# Renamed to label_mapping.json's punctuation (commas stripped):
#   Ecology, Evolution, Behavior and Systematics; General Biochemistry,
#   Genetics and Molecular Biology; Biochemistry, Genetics and Molecular
#   Biology (miscellaneous); General Business, Management and Accounting;
#   Business, Management and Accounting; Tourism, Leisure and Hospitality
#   Management; Statistics, Probability and Uncertainty; General Economics,
#   Econometrics and Finance; Economics, Econometrics and Finance; Safety,
#   Risk, Reliability and Quality; Health, Toxicology and Mutagenesis;
#   Management, Monitoring, Policy and Law; Electronic, Optical and Magnetic
#   Materials; Surfaces, Coatings and Films; Pediatrics, Perinatology and
#   Child Health; Public Health, Environmental and Occupational Health;
#   Issues, Ethics and Legal Aspects; General Pharmacology, Toxicology and
#   Pharmaceutics; Pharmacology, Toxicology and Pharmaceutics
#   (miscellaneous); Atomic and Molecular Physics, and Optics.

assert len(ASJC_FIELDS) == len(set(ASJC_FIELDS)), "duplicate field name"
assert all(ord(c) < 128 for f in ASJC_FIELDS for c in f), (
    "non-ASCII in a field name -- look for lookalike Cyrillic letters")
