"""
Credit and ACI (Author Contribution Index) Calculation Examples

This script demonstrates how to use the Credit and ACI framework
to fairly distribute authorship credit based on:
1. Contribution-based ordering (typical in STEM fields)
2. Alphabetical ordering (typical in Math/CS theory)
3. Mixed/unknown ordering

Usage:
    python credit_aci_examples.py
"""

from author_order_classifier import (
    calculate_aci,
    distribute_credit_contribution_based,
    distribute_credit_alphabetical,
    distribute_credit_mixed,
)


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def example_1_contribution_based_ordering():
    """
    Example 1: Contribution-Based Ordering (Common in Biology, Medicine, CS)
    
    Field: Biology paper with 4 authors
    Ordering: Authors contribute in different amounts
    Expected: 1st author highest credit, decreasing through middle, 
              last author (supervisor) gets supervision credit
    """
    print_section("EXAMPLE 1: Contribution-Based Ordering")
    
    authors = ["Smith", "Johnson", "Williams", "Brown"]
    n_authors = len(authors)
    
    credit_dist = distribute_credit_contribution_based(authors, n_authors)
    
    print(f"\nField: Biology (Contribution-based)")
    print(f"Authors: {', '.join(authors)}")
    print(f"\nCredit Distribution (position-weighted):")
    for author, credit in credit_dist.items():
        print(f"  {author:12} : {credit:6.1f}%")
    
    print(f"\nInterpretation:")
    print(f"  • 1st author (Smith):      {credit_dist['Smith']:.1f}% - Main contributor")
    print(f"  • 2nd author (Johnson):    {credit_dist['Johnson']:.1f}% - Partial contributor")
    print(f"  • 3rd author (Williams):   {credit_dist['Williams']:.1f}% - Partial contributor")
    print(f"  • Last author (Brown):     {credit_dist['Brown']:.1f}% - Supervisor/Lab head")


def example_2_alphabetical_ordering_no_aci():
    """
    Example 2: Alphabetical Ordering with NO declared contributions (ACI unavailable)
    
    Field: Mathematics or Theoretical CS paper
    Authors listed alphabetically by surname
    Expected: Equal credit to all authors (ordering doesn't reflect contribution)
    """
    print_section("EXAMPLE 2: Alphabetical Ordering (NO ACI Available)")
    
    authors = ["Anderson", "Brown", "Chen", "Kumar"]
    n_authors = len(authors)
    
    # No contributions declared
    credit_dist = distribute_credit_alphabetical(authors, n_authors, contributions=None)
    
    print(f"\nField: Mathematics (Alphabetical ordering)")
    print(f"Authors: {', '.join(authors)} (ordered alphabetically)")
    print(f"\nCredit Distribution (Equal credit, no ACI):")
    for author, credit in credit_dist.items():
        print(f"  {author:12} : {credit:6.1f}%")
    
    print(f"\nInterpretation:")
    print(f"  • All authors get equal credit (1/N = 1/4 = 25%)")
    print(f"  • Alphabetical order does NOT reflect contribution")
    print(f"  • This is standard in Math and Theoretical CS")


def example_3_alphabetical_ordering_with_aci():
    """
    Example 3: Alphabetical Ordering WITH declared contributions (ACI available)
    
    Field: Economics paper with alphabetically ordered authors
    BUT the authors declare their actual contributions
    Expected: ACI corrects for alphabetical bias
    """
    print_section("EXAMPLE 3: Alphabetical Ordering (WITH ACI Available)")
    
    authors = ["Anderson", "Brown", "Chen", "Kumar"]
    n_authors = len(authors)
    
    # Declared contributions (these are the actual author efforts)
    contributions = {
        "Anderson": 10,   # Minimal contribution
        "Brown":    20,   # Moderate contribution
        "Chen":     50,   # Main contributor
        "Kumar":    20,   # Moderate contribution
    }
    
    # Calculate ACI scores
    aci_scores = calculate_aci(contributions)
    
    print(f"\nField: Economics (Alphabetical ordering WITH contributions)")
    print(f"Authors: {', '.join(authors)}")
    print(f"\nDeclared Contributions:")
    for author, contrib in contributions.items():
        print(f"  {author:12} : {contrib:3d}%")
    
    print(f"\nACI Scores (ACI_i = C_i / (ΣC_j - C_i)):")
    for author, aci in aci_scores.items():
        print(f"  {author:12} : {aci:6.4f}")
    
    # Now distribute credit based on ACI
    credit_dist = distribute_credit_alphabetical(authors, n_authors, contributions)
    
    print(f"\nCredit Distribution (using ACI to correct bias):")
    for author, credit in credit_dist.items():
        print(f"  {author:12} : {credit:6.1f}%")
    
    print(f"\nInterpretation:")
    print(f"  • Even though Chen is 3rd alphabetically, they get {credit_dist['Chen']:.1f}% credit")
    print(f"  • This is their fair share based on actual contribution")
    print(f"  • ACI successfully corrects the alphabetical ordering bias")


def example_4_mixed_ordering():
    """
    Example 4: Mixed/Unknown Ordering
    
    Cases where ordering may or may not reflect contribution.
    Strategy: Use ACI if available, otherwise use equal credit.
    """
    print_section("EXAMPLE 4: Mixed/Unknown Ordering")
    
    authors = ["Garcia", "Martinez", "Lopez", "Hernandez"]
    n_authors = len(authors)
    
    # Case A: No contributions declared
    print(f"\nCase A: Mixed ordering with NO declared contributions")
    credit_dist_a = distribute_credit_mixed(authors, n_authors, contributions=None)
    for author, credit in credit_dist_a.items():
        print(f"  {author:12} : {credit:6.1f}%")
    print(f"  → Default to equal credit (1/N)")
    
    # Case B: Contributions declared
    print(f"\nCase B: Mixed ordering WITH declared contributions")
    contributions = {
        "Garcia": 40,
        "Martinez": 35,
        "Lopez": 15,
        "Hernandez": 10,
    }
    
    print(f"Declared Contributions:")
    for author, contrib in contributions.items():
        print(f"  {author:12} : {contrib:3d}%")
    
    credit_dist_b = distribute_credit_mixed(authors, n_authors, contributions)
    print(f"\nCredit Distribution (using ACI):")
    for author, credit in credit_dist_b.items():
        print(f"  {author:12} : {credit:6.1f}%")
    print(f"  → Uses declared contributions to calculate fair credit")


def example_5_aci_detailed_calculation():
    """
    Example 5: Detailed ACI Calculation Walkthrough
    
    Shows step-by-step how ACI is calculated from raw contributions.
    """
    print_section("EXAMPLE 5: Detailed ACI Calculation Walkthrough")
    
    authors = ["Alice", "Bob", "Charlie"]
    contributions = {
        "Alice":   50,
        "Bob":     30,
        "Charlie": 20,
    }
    
    print(f"\nAuthors and their contributions:")
    for author, contrib in contributions.items():
        print(f"  {author:10} : {contrib}%")
    
    total_contrib = sum(contributions.values())
    print(f"  Total      : {total_contrib}%")
    
    print(f"\nACI Calculation (Formula: ACI_i = C_i / (ΣC_j - C_i)):")
    print(f"  Where C_i = contribution of author i")
    print(f"        ΣC_j = sum of all contributions")
    
    aci_scores = calculate_aci(contributions)
    
    for author in ["Alice", "Bob", "Charlie"]:
        c_i = contributions[author]
        sum_cj = total_contrib
        denominator = sum_cj - c_i
        if denominator > 0:
            aci_val = c_i / denominator
            print(f"\n  ACI_{author} = {c_i} / ({sum_cj} - {c_i})")
            print(f"            = {c_i} / {denominator}")
            print(f"            = {aci_val:.4f}")
    
    print(f"\nFinal ACI Scores:")
    for author, aci in aci_scores.items():
        print(f"  {author:10} : {aci:.4f}")


def example_6_real_world_application():
    """
    Example 6: Real-world Application
    
    How to determine ordering type and apply appropriate credit model
    in a real bibliometric system.
    """
    print_section("EXAMPLE 6: Real-World Application Workflow")
    
    print("""
WORKFLOW FOR YOUR JOURNAL CLASSIFICATION SYSTEM:

Step 1: Classify the Journal
  └─ Analyze alphabetical rate from papers
     • AlphabeticalRate ≥ 75%  → ALPHABETICAL
     • AlphabeticalRate ≤ 25%  → CONTRIBUTION-BASED
     • Else                     → MIXED

Step 2: Select Credit Model
  ┌─ CONTRIBUTION-BASED
  │  └─ Credit Rule: Position-weighted
  │     ├─ 1st author gets 40-50%
  │     ├─ Middle authors get decreasing shares
  │     └─ Last gets 10-20% (supervision)
  │
  ├─ ALPHABETICAL
  │  └─ Credit Rule: Equal OR ACI
  │     ├─ If no ACI: Each author gets 1/N
  │     └─ If ACI available: Use declared contributions
  │
  └─ MIXED
     └─ Credit Rule: Prefer ACI
        ├─ If contributions available: Use ACI
        └─ Else: Use equal credit

Step 3: Export Results
  └─ Include in Excel output:
     ├─ Classification (journal type)
     ├─ AlphabeticalRate
     ├─ Confidence level
     ├─ Per-paper credit distribution
     └─ ACI scores (if applicable)

EXAMPLE:
  Journal: Nature (contribution-based)
  └─ Paper with authors [Smith, Johnson, Lee, Brown]
     ├─ Alphabetical? No
     ├─ Credit Distribution:
     │  ├─ Smith    : 45.0% (1st - main contributor)
     │  ├─ Johnson  : 25.0% (2nd - partial)
     │  ├─ Lee      : 15.0% (3rd - partial)
     │  └─ Brown    : 15.0% (4th - supervisor)
     └─ Interpretation: Fair distribution based on ordering
    """)


if __name__ == "__main__":
    example_1_contribution_based_ordering()
    example_2_alphabetical_ordering_no_aci()
    example_3_alphabetical_ordering_with_aci()
    example_4_mixed_ordering()
    example_5_aci_detailed_calculation()
    example_6_real_world_application()
    
    print(f"\n{'='*70}")
    print("✅ Examples completed!")
    print(f"{'='*70}\n")
