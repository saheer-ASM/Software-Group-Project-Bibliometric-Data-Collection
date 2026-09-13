"""
DEMONSTRATION: Credit & ACI Author Ordering System
(No external dependencies - shows examples directly)
"""

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def normalize_family_name(name: str) -> str:
    """Normalise an author family name for comparison."""
    name = name.lower()
    # Remove non-alphabetic characters
    name = "".join(c for c in name if c.isalpha() or c == ' ')
    return name.strip()


def is_alphabetical(authors: list) -> bool:
    """Check if author list is in alphabetical order."""
    family_names = []
    for author in authors:
        family = author.get("family", "").strip()
        if not family:
            return False
        family_names.append(normalize_family_name(family))
    
    return family_names == sorted(family_names)


def calculate_aci(contributions: dict) -> dict:
    """Calculate ACI scores from contributions."""
    total = sum(contributions.values())
    if total == 0:
        return {k: 0.0 for k in contributions}
    
    aci_scores = {}
    for author, contrib in contributions.items():
        if contrib == 0:
            aci_scores[author] = 0.0
        else:
            numerator = contrib
            denominator = total - contrib
            if denominator == 0:
                aci_scores[author] = float('inf')
            else:
                aci_scores[author] = round(numerator / denominator, 4)
    
    return aci_scores


def distribute_credit_contribution_based(authors: list, n_authors: int) -> dict:
    """Distribute credit using position-weighted scheme."""
    if n_authors == 1:
        return {authors[0]: 100.0}
    elif n_authors == 2:
        return {authors[0]: 60.0, authors[1]: 40.0}
    elif n_authors == 3:
        return {authors[0]: 50.0, authors[1]: 25.0, authors[2]: 25.0}
    else:
        credit_dist = {}
        weights = [0.40, 0.25, 0.15]
        
        for i, author in enumerate(authors):
            if i < 3:
                credit_dist[author] = weights[i] * 100
            else:
                remaining_credit = 20.0 / (n_authors - 3)
                credit_dist[author] = remaining_credit
        
        total = sum(credit_dist.values())
        if total > 0:
            credit_dist = {k: round(v * 100 / total, 2) for k, v in credit_dist.items()}
        
        return credit_dist


def distribute_credit_alphabetical(authors: list, n_authors: int, 
                                   contributions: dict = None) -> dict:
    """Distribute credit for alphabetical ordering."""
    equal_share = 100.0 / n_authors
    
    if contributions is None or len(contributions) == 0:
        return {author: equal_share for author in authors}
    
    aci_scores = calculate_aci(contributions)
    total_aci = sum(aci_scores.values())
    
    if total_aci == 0:
        return {author: equal_share for author in authors}
    
    aci_dist = {}
    for author in authors:
        if author in aci_scores:
            aci_dist[author] = round((aci_scores[author] / total_aci) * 100, 2)
        else:
            aci_dist[author] = equal_share
    
    return aci_dist


# ============================================================================
# DEMONSTRATIONS
# ============================================================================

def demo_1():
    print_section("DEMO 1: Contribution-Based Ordering (Nature paper)")
    
    authors = ["Smith", "Johnson", "Williams", "Brown"]
    n = len(authors)
    
    credit = distribute_credit_contribution_based(authors, n)
    
    print(f"\nJournal: Nature (Contribution-Based)")
    print(f"Authors: {', '.join(authors)}")
    print(f"Ordering: Non-alphabetical")
    print(f"\nCredit Distribution (Position-Weighted):")
    
    for i, author in enumerate(authors, 1):
        c = credit[author]
        position = ['1st (Main contributor)', '2nd (Contributor)', 
                    '3rd (Contributor)', 'Last (Supervisor)'][i-1]
        bar = '█' * int(c / 2) + '░' * (50 - int(c / 2))
        print(f"  {author:12} │{bar}│ {c:6.1f}%  ({position})")


def demo_2():
    print_section("DEMO 2: Alphabetical Ordering (Math paper - NO ACI)")
    
    authors = ["Anderson", "Brown", "Chen", "Kumar"]
    n = len(authors)
    
    credit = distribute_credit_alphabetical(authors, n, contributions=None)
    
    print(f"\nJournal: Mathematics (Alphabetical)")
    print(f"Authors: {', '.join(authors)}")
    print(f"Ordering: ALPHABETICAL (A < B < C < K)")
    print(f"Contributions: NOT DECLARED")
    print(f"\nCredit Distribution (Equal - No information from order):")
    
    for author in authors:
        c = credit[author]
        bar = '█' * int(c / 2) + '░' * (50 - int(c / 2))
        print(f"  {author:12} │{bar}│ {c:6.1f}%")


def demo_3():
    print_section("DEMO 3: Alphabetical Ordering (Economics paper - WITH ACI)")
    
    authors = ["Anderson", "Brown", "Chen", "Kumar"]
    contributions = {
        "Anderson": 10,   # Minimal
        "Brown": 20,      # Moderate
        "Chen": 50,       # Main contributor
        "Kumar": 20,      # Moderate
    }
    
    # Calculate ACI
    aci = calculate_aci(contributions)
    
    # Calculate credit
    credit = distribute_credit_alphabetical(authors, len(authors), contributions)
    
    print(f"\nJournal: Economics (Alphabetical + Contributions)")
    print(f"Authors: {', '.join(authors)}")
    print(f"Ordering: ALPHABETICAL (A < B < C < K)")
    print(f"Contributions: DECLARED")
    
    print(f"\nDeclared Contributions:")
    for author in authors:
        print(f"  {author:12} : {contributions[author]:3d}%")
    
    print(f"\nACI Scores (ACI_i = C_i / (ΣC_j - C_i)):")
    for author in authors:
        print(f"  {author:12} : {aci[author]:8.4f}")
    
    print(f"\nACI-Corrected Credit Distribution:")
    for author in authors:
        c = credit[author]
        bar = '█' * int(c / 2) + '░' * (50 - int(c / 2))
        print(f"  {author:12} │{bar}│ {c:6.1f}%")
    
    print(f"\n🔍 INSIGHT:")
    print(f"   Chen is 3rd alphabetically, but gets {credit['Chen']:.1f}% credit")
    print(f"   Anderson is 1st alphabetically, but gets {credit['Anderson']:.1f}% credit")
    print(f"   ACI successfully corrects alphabetical bias!")


def demo_4():
    print_section("DEMO 4: Detailed ACI Calculation Walkthrough")
    
    print(f"\nPaper: 'Machine Learning Framework'")
    print(f"Authors: Alice, Bob, Charlie, Diana")
    
    contributions = {
        "Alice": 50,
        "Bob": 30,
        "Charlie": 15,
        "Diana": 5,
    }
    
    total = sum(contributions.values())
    
    print(f"\nStep 1: Declared Contributions")
    print(f"  Alice   : 50%")
    print(f"  Bob     : 30%")
    print(f"  Charlie : 15%")
    print(f"  Diana   :  5%")
    print(f"  TOTAL   : {total}%")
    
    print(f"\nStep 2: Calculate ACI for each author")
    print(f"  Formula: ACI_i = C_i / (ΣC_j - C_i)")
    
    aci = calculate_aci(contributions)
    
    for author in ["Alice", "Bob", "Charlie", "Diana"]:
        c_i = contributions[author]
        denominator = total - c_i
        aci_val = aci[author]
        print(f"\n  ACI_{author:7} = {c_i} / ({total} - {c_i}) = {c_i} / {denominator} = {aci_val:.4f}")
    
    print(f"\nStep 3: Interpret ACI Scores")
    print(f"  Alice   : {aci['Alice']:.4f}  ← Main contributor (1.0 = half of others combined)")
    print(f"  Bob     : {aci['Bob']:.4f}  ← Significant contributor")
    print(f"  Charlie : {aci['Charlie']:.4f}  ← Partial contributor")
    print(f"  Diana   : {aci['Diana']:.4f}  ← Minimal contributor")


def demo_5():
    print_section("DEMO 5: Real-World Decision Tree")
    
    print("""
SCENARIO 1: You analyzed Nature (150 papers)
  Alphabetical papers: 18/150 = 12%
  Decision: CONTRIBUTION-BASED (12% < 25%)
  Credit Model: Position-weighted
  Confidence: HIGH (150 papers > 100)
  ✅ Use position-weighted model

SCENARIO 2: You analyzed Mathematics journal (120 papers)
  Alphabetical papers: 115/120 = 95.8%
  Decision: ALPHABETICAL (95.8% > 75%)
  Credit Model: Equal (or ACI if available)
  Confidence: HIGH (120 papers > 100)
  ✅ Use equal credit (1/N) OR ACI if contributors declared

SCENARIO 3: You analyzed emerging journal (45 papers)
  Alphabetical papers: 18/45 = 40%
  Decision: MIXED/UNCLEAR (26% < 40% < 74%)
  Credit Model: Prefer ACI
  Confidence: LOW (45 papers < 100)
  ✅ Use ACI if available, else equal credit
  ⚠️  Need more papers for high confidence

SCENARIO 4: Math paper with alphabetical authors but ACI data
  Authors: Anderson, Brown, Chen, Kumar (alphabetical)
  Without ACI: Anderson (1st) gets 25%, Chen (3rd) gets 25%
  With ACI: Anderson gets 5%, Chen gets 53% (fair!)
  ✅ ACI corrects alphabetical bias
    """)


def demo_6():
    print_section("DEMO 6: Summary Table")
    
    print("""
┌──────────────────────────────────────────────────────────────────────┐
│                    JOURNAL CLASSIFICATION TABLE                      │
├──────────────┬─────────────────┬────────────┬──────────────────────┤
│   Range      │   Type          │Confidence  │   Credit Model       │
├──────────────┼─────────────────┼────────────┼──────────────────────┤
│ ≥ 75%        │ ALPHABETICAL    │ High*      │ Equal or ACI-based  │
│ 26% - 74%    │ MIXED/UNCLEAR   │ Low        │ Prefer ACI          │
│ ≤ 25%        │ CONTRIBUTION    │ High*      │ Position-weighted   │
└──────────────┴─────────────────┴────────────┴──────────────────────┘
  * High confidence requires ≥ 100 papers analyzed


┌──────────────────────────────────────────────────────────────────────┐
│            CREDIT DISTRIBUTION FORMULAS AT A GLANCE                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ CONTRIBUTION-BASED (Position-weighted):                              │
│   1st author: 40-50%                                                 │
│   2nd:        20-25%                                                 │
│   3rd:        10-15%                                                 │
│   Others:     Remaining % (divided equally)                         │
│                                                                      │
│ ALPHABETICAL (No ACI):                                               │
│   Each author: 100% / N                                              │
│                                                                      │
│ ALPHABETICAL (With ACI):                                             │
│   Author_i: (ACI_i / Σ ACI_j) × 100%                                │
│                                                                      │
│ ACI FORMULA:                                                         │
│   ACI_i = C_i / (ΣC_j - C_i)                                         │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
    """)


# Run all demonstrations
if __name__ == "__main__":
    print("\n")
    print("╔" + "═"*68 + "╗")
    print("║" + " "*68 + "║")
    print("║" + "  Credit & ACI Author Ordering System - DEMONSTRATIONS".center(68) + "║")
    print("║" + " "*68 + "║")
    print("╚" + "═"*68 + "╝")
    
    demo_1()
    demo_2()
    demo_3()
    demo_4()
    demo_5()
    demo_6()
    
    print(f"\n{'='*70}")
    print("  ✅ All demonstrations completed!")
    print(f"{'='*70}\n")
    print("📚 For more information:")
    print("  • See CREDIT_ACI_README.md for full documentation")
    print("  • Run: python3 credit_aci_examples.py (requires requests, openpyxl)")
    print("  • Run: python3 test_credit_aci.py (unit tests)")
    print("  • Run: python3 author_order_classifier.py (classify journals)")
    print()
