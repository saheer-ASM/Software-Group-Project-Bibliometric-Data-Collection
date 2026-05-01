"""
Batch runner for author_order_classifier.py
Runs the classifier for all 100 top journals (h5-index list).
Usage:
    python run_all_journals.py
    python run_all_journals.py --max 300 --sample 100 --start 1
    python run_all_journals.py --max 200 --sample 80 --start 6  # resume from journal #6
"""

import subprocess
import sys
import time
import argparse
from datetime import datetime

JOURNALS = [
    "Nature",
    "IEEE/CVF Conference on Computer Vision and Pattern Recognition",
    "The New England Journal of Medicine",
    "Science",
    "Nature Communications",
    "The Lancet",
    "Neural Information Processing Systems",
    "International Conference on Learning Representations",
    "Advanced Materials",
    "Cell",
    "Science of The Total Environment",
    "JAMA",
    "Journal of Cleaner Production",
    "Angewandte Chemie International Edition",
    "IEEE Access",
    "Chemical Reviews",
    "Nature Medicine",
    "International Journal of Molecular Sciences",
    "International Conference on Machine Learning",
    "Proceedings of the National Academy of Sciences",
    "Advanced Functional Materials",
    "European Conference on Computer Vision",
    "Chemical Society Reviews",
    "International Journal of Environmental Research and Public Health",
    "IEEE/CVF International Conference on Computer Vision",
    "Sustainability",
    "Chemical engineering journal",
    "PLOS ONE",
    "Renewable and Sustainable Energy Reviews",
    "Science Advances",
    "Journal of Business Research",
    "Advanced Energy Materials",
    "Journal of the American Chemical Society",
    "Meeting of the Association for Computational Linguistics (ACL)",
    "Scientific Reports",
    "AAAI Conference on Artificial Intelligence",
    "ACS Nano",
    "Journal of Hazardous Materials",
    "BMJ",
    "Frontiers in Immunology",
    "Nucleic Acids Research",
    "Journal of Clinical Oncology",
    "Energy & Environmental Science",
    "Signal Transduction and Targeted Therapy",
    "Conference on Empirical Methods in Natural Language Processing (EMNLP)",
    "IEEE Transactions on Pattern Analysis and Machine Intelligence",
    "Nutrients",
    "Applied Catalysis B: Environmental",
    "Circulation",
    "Sensors",
    "Technological Forecasting and Social Change",
    "Frontiers in Psychology",
    "Chemosphere",
    "Morbidity and Mortality Weekly Report",
    "The Lancet Oncology",
    "Molecules",
    "Physical Review Letters",
    "Environmental Science & Technology",
    "IEEE Internet of Things Journal",
    "Applied Energy",
    "Nature Materials",
    "Advanced Science",
    "Environmental Science and Pollution Research",
    "Nature Biotechnology",
    "JAMA Network Open",
    "Applied Sciences",
    "The Lancet Infectious Diseases",
    "Nano Energy",
    "ACM Computing Surveys",
    "Journal of Environmental Management",
    "Expert Systems with Applications",
    "Journal of the American College of Cardiology",
    "Nature Energy",
    "Energy",
    "ACS Catalysis",
    "Renewable Energy",
    "Journal of Materials Chemistry A",
    "Trends in Food Science & Technology",
    "Construction and Building Materials",
    "Clinical Infectious Diseases",
    "Nature Genetics",
    "Gastroenterology",
    "European Heart Journal",
    "IEEE Transactions on Industrial Informatics",
    "Cells",
    "Water Research",
    "International Journal of Biological Macromolecules",
    "Joule",
    "Journal of Medical Internet Research",
    "Bioresource Technology",
    "Coordination Chemistry Reviews",
    "Nature Nanotechnology",
    "International Journal of Hydrogen Energy",
    "Environmental Pollution",
    "Small",
    "ACS Applied Materials & Interfaces",
    "Energy Storage Materials",
    "The Astrophysical Journal",
    "ACS Energy Letters",
    "Journal of Retailing and Consumer Services",
]

def main():
    parser = argparse.ArgumentParser(description="Batch runner for author_order_classifier.py")
    parser.add_argument("--max",    type=int, default=300, help="Max papers to fetch per journal (default: 300)")
    parser.add_argument("--sample", type=int, default=100, help="Full-text sample size per journal (default: 100)")
    parser.add_argument("--start",  type=int, default=1,   help="Start from journal number (1-indexed, default: 1)")
    args = parser.parse_args()

    start_idx = args.start - 1  # convert to 0-indexed
    total = len(JOURNALS)
    to_run = JOURNALS[start_idx:]

    print("=" * 70)
    print(f"  Batch Author Order Classifier")
    print(f"  Total journals : {total}")
    print(f"  Starting from  : #{args.start} ({JOURNALS[start_idx]})")
    print(f"  Remaining      : {len(to_run)}")
    print(f"  --max {args.max}  --sample {args.sample}")
    print("=" * 70)

    results = []
    failed  = []

    for i, journal in enumerate(to_run, start=args.start):
        print(f"\n[{i}/{total}] Processing: {journal}")
        print("-" * 60)

        cmd = [
            sys.executable, "author_order_classifier.py",
            "--journal", journal,
            "--max",    str(args.max),
            "--sample", str(args.sample),
        ]

        start_time = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=False, text=True)
            elapsed = time.time() - start_time
            if proc.returncode == 0:
                results.append((i, journal, "OK", f"{elapsed:.0f}s"))
                print(f"  ✅ Done in {elapsed:.0f}s")
            else:
                results.append((i, journal, "ERROR", f"{elapsed:.0f}s"))
                failed.append((i, journal))
                print(f"  ❌ Exited with code {proc.returncode}")
        except Exception as e:
            elapsed = time.time() - start_time
            results.append((i, journal, f"EXCEPTION: {e}", f"{elapsed:.0f}s"))
            failed.append((i, journal))
            print(f"  ❌ Exception: {e}")

        # Brief pause between journals to be polite to APIs
        if i < total:
            time.sleep(3)

    # Summary
    print("\n" + "=" * 70)
    print("  BATCH COMPLETE — SUMMARY")
    print("=" * 70)
    for num, journal, status, elapsed in results:
        icon = "✅" if status == "OK" else "❌"
        print(f"  {icon} #{num:3d}  {journal[:50]:<50}  {status}  ({elapsed})")

    if failed:
        print(f"\n  {len(failed)} journal(s) failed:")
        for num, journal in failed:
            print(f"    #{num}: {journal}")
        print("\n  Re-run failed journals with:")
        for num, journal in failed:
            print(f'    python author_order_classifier.py --journal "{journal}" --max {args.max} --sample {args.sample}')

    print("\n  All output files saved in current directory.")
    print("=" * 70)

if __name__ == "__main__":
    main()
