import math
from typing import List, Dict, Tuple, Optional

class AuthorContributionCalculator:
    """
    A class to calculate author contributions based on different ordering norms.
    Supports Alphabetical/Random and Relative Contribution ordering.
    """
    
    def __init__(self):
        self.field_weights = {}  # Store field weights for papers
        self.author_positions = {}  # Store author positions for papers
        
    def detect_ordering_norm(self, author_list: List[str], paper_id: str) -> str:
        """
        Detect whether the author list follows alphabetical/random or relative contribution ordering.
        
        Args:
            author_list: List of author names
            paper_id: Unique identifier for the paper
            
        Returns:
            'alphabetical' or 'relative'
        """
        # For demonstration, we'll use a heuristic:
        # 1. Check if authors are sorted alphabetically
        # 2. If not, assume relative contribution
        # In practice, you might have metadata or annotations indicating the norm
        
        sorted_authors = sorted(author_list)
        
        # Check if the list matches alphabetical order (case insensitive)
        if [a.lower() for a in author_list] == [a.lower() for a in sorted_authors]:
            return 'alphabetical'
        else:
            # If not alphabetical, assume relative contribution
            # You could add more sophisticated detection here
            return 'relative'
    
    def calculate_alphabetical_weights(self, paper_id: str, field_name: str, 
                                      field_weight: float, num_authors: int) -> Dict[str, float]:
        """
        Calculate weights for alphabetical/random ordering using Equation 1:
        W_p,A/R^f = V_p^f / N_p
        
        Args:
            paper_id: Paper identifier
            field_name: Name of the field
            field_weight: Weight of the paper in this field (0 to 1)
            num_authors: Total number of authors
            
        Returns:
            Dictionary mapping author index to their contribution weight
        """
        if num_authors == 0:
            return {}
        
        # Each author gets equal share of the field weight
        contribution_per_author = field_weight / num_authors
        
        # Distribute equally to all authors
        weights = {}
        for i in range(1, num_authors + 1):
            weights[i] = contribution_per_author
            
        return weights
    
    def calculate_relative_weights(self, paper_id: str, field_name: str, 
                                  field_weight: float, num_authors: int,
                                  core_first_indices: Optional[List[int]] = None,
                                  core_last_indices: Optional[List[int]] = None) -> Dict[str, float]:
        """
        Calculate weights for relative contribution ordering using Equations 2 and 3:
        EAP_i and W_p,RC^f = (V_p^f * H_i) / sum(H_k)
        
        Args:
            paper_id: Paper identifier
            field_name: Name of the field
            field_weight: Weight of the paper in this field (0 to 1)
            num_authors: Total number of authors
            core_first_indices: List of indices for core-first authors (1-indexed)
            core_last_indices: List of indices for core-last authors (1-indexed)
            
        Returns:
            Dictionary mapping author index to their contribution weight
        """
        if num_authors == 0:
            return {}
        
        # Handle None values
        core_first = core_first_indices or []
        core_last = core_last_indices or []
        
        # Calculate Effective Author Position (EAP) using Equation 2
        eap_values = {}
        
        # For middle authors (not in core-first or core-last)
        middle_indices = set(range(1, num_authors + 1)) - set(core_first) - set(core_last)
        
        # Set EAP for different groups
        for idx in range(1, num_authors + 1):
            if idx in core_first:
                # Average position of core-first authors
                eap_values[idx] = sum(core_first) / len(core_first) if core_first else idx
            elif idx in core_last:
                # Average position of core-last authors
                eap_values[idx] = sum(core_last) / len(core_last) if core_last else idx
            else:
                # Middle author: EAP = original position
                eap_values[idx] = idx
        
        # Calculate harmonic weights (H_i = 1/EAP_i)
        harmonic_weights = {}
        for idx in range(1, num_authors + 1):
            eap = eap_values[idx]
            harmonic_weights[idx] = 1.0 / eap if eap > 0 else 0
        
        # Calculate sum of harmonic weights
        sum_harmonic = sum(harmonic_weights.values())
        
        if sum_harmonic == 0:
            return {}
        
        # Calculate contribution weights using Equation 3
        weights = {}
        for idx in range(1, num_authors + 1):
            weights[idx] = (field_weight * harmonic_weights[idx]) / sum_harmonic
            
        return weights
    
    def calculate_total_author_contributions(self, paper_id: str, author_list: List[str], 
                                            fields_data: Dict[str, float],
                                            core_first_indices: Optional[List[int]] = None,
                                            core_last_indices: Optional[List[int]] = None) -> Dict[str, Dict]:
        """
        Calculate total contributions for all authors across all fields.
        
        Args:
            paper_id: Paper identifier
            author_list: List of author names
            fields_data: Dictionary mapping field names to their weights (sum should be 1.0)
            core_first_indices: List of indices for core-first authors
            core_last_indices: List of indices for core-last authors
            
        Returns:
            Dictionary containing:
            - 'ordering_norm': Detected ordering norm
            - 'field_weights': Input field weights
            - 'author_contributions': Dictionary mapping author names to their total contribution
            - 'detailed_contributions': Detailed breakdown by field and author position
        """
        num_authors = len(author_list)
        
        # Validate field weights sum to 1
        total_field_weight = sum(fields_data.values())
        if abs(total_field_weight - 1.0) > 1e-6:
            print(f"Warning: Field weights sum to {total_field_weight}, should be 1.0")
        
        # Detect ordering norm
        ordering_norm = self.detect_ordering_norm(author_list, paper_id)
        
        # Initialize contribution tracking
        author_contributions = {author: 0.0 for author in author_list}
        detailed_contributions = {}
        
        # Calculate contributions for each field
        for field_name, field_weight in fields_data.items():
            if field_weight == 0:
                continue
                
            if ordering_norm == 'alphabetical':
                # Use Equation 1
                weights = self.calculate_alphabetical_weights(
                    paper_id, field_name, field_weight, num_authors
                )
            else:  # relative
                # Use Equations 2 and 3
                weights = self.calculate_relative_weights(
                    paper_id, field_name, field_weight, num_authors,
                    core_first_indices, core_last_indices
                )
            
            # Store detailed field contributions
            detailed_contributions[field_name] = {}
            for idx, weight in weights.items():
                author_name = author_list[idx - 1]  # Convert 1-indexed to 0-indexed
                detailed_contributions[field_name][author_name] = weight
                author_contributions[author_name] += weight
        
        # Prepare result
        result = {
            'ordering_norm': ordering_norm,
            'field_weights': fields_data,
            'author_contributions': author_contributions,
            'detailed_contributions': detailed_contributions,
            'total_weight': sum(author_contributions.values())
        }
        
        return result
    
    def print_contribution_summary(self, result: Dict) -> None:
        """
        Pretty print the contribution summary.
        """
        print("=" * 70)
        print(f"ORDERING NORM DETECTED: {result['ordering_norm'].upper()}")
        print("=" * 70)
        print("\nField Weights:")
        for field, weight in result['field_weights'].items():
            print(f"  {field}: {weight:.3f}")
        
        print("\n" + "-" * 70)
        print("AUTHOR CONTRIBUTIONS (Total per author):")
        print("-" * 70)
        
        # Sort by contribution (descending)
        sorted_authors = sorted(result['author_contributions'].items(), 
                              key=lambda x: x[1], reverse=True)
        for author, contribution in sorted_authors:
            print(f"  {author}: {contribution:.4f} ({contribution*100:.2f}%)")
        
        print("\n" + "-" * 70)
        print("DETAILED BREAKDOWN BY FIELD:")
        print("-" * 70)
        
        for field, contributions in result['detailed_contributions'].items():
            print(f"\n  Field: {field}")
            sorted_contrib = sorted(contributions.items(), key=lambda x: x[1], reverse=True)
            for author, weight in sorted_contrib:
                print(f"    {author}: {weight:.4f} ({weight*100:.2f}% of field)")
        
        print("\n" + "=" * 70)
        print(f"Total sum of all contributions: {result['total_weight']:.4f} (should be 1.0)")
        print("=" * 70)


# Example usage
def run_examples():
    """
    Run example calculations for both alphabetical and relative ordering norms.
    """
    calculator = AuthorContributionCalculator()
    
    # Example 1: Alphabetical ordering
    print("\n" + "="*80)
    print("EXAMPLE 1: ALPHABETICAL/RANDOM ORDERING")
    print("="*80)
    
    authors_alpha = ['Adams, J.', 'Brown, M.', 'Chen, L.', 'Davis, R.', 'Evans, S.']
    fields_alpha = {
        'Networks': 0.30,
        'Cyber Security': 0.50,
        'Science': 0.20
    }
    
    result_alpha = calculator.calculate_total_author_contributions(
        paper_id='P001',
        author_list=authors_alpha,
        fields_data=fields_alpha
    )
    calculator.print_contribution_summary(result_alpha)
    
    # Example 2: Relative contribution ordering (with core authors)
    print("\n" + "="*80)
    print("EXAMPLE 2: RELATIVE CONTRIBUTION ORDERING")
    print("="*80)
    
    authors_rel = ['Smith, J.', 'Johnson, M.', 'Williams, K.', 'Brown, R.', 'Jones, P.']
    fields_rel = {
        'Networks': 0.30,
        'Cyber Security': 0.50,
        'Science': 0.20
    }
    
    # Suppose authors at positions 1, 2 are core-first, position 5 is core-last
    result_rel = calculator.calculate_total_author_contributions(
        paper_id='P002',
        author_list=authors_rel,
        fields_data=fields_rel,
        core_first_indices=[1, 2],
        core_last_indices=[5]
    )
    calculator.print_contribution_summary(result_rel)
    
    # Example 3: Relative contribution without core authors (standard harmonic)
    print("\n" + "="*80)
    print("EXAMPLE 3: RELATIVE CONTRIBUTION (STANDARD HARMONIC, NO CORE)")
    print("="*80)
    
    authors_std = ['Anderson, A.', 'Baker, B.', 'Clark, C.', 'Diaz, D.', 'Edwards, E.']
    fields_std = {
        'Computer Science': 1.0
    }
    
    result_std = calculator.calculate_total_author_contributions(
        paper_id='P003',
        author_list=authors_std,
        fields_data=fields_std,
        core_first_indices=None,
        core_last_indices=None
    )
    calculator.print_contribution_summary(result_std)
    
    # Example 4: Compare the two norms for the same paper
    print("\n" + "="*80)
    print("EXAMPLE 4: COMPARISON - SAME PAPER, DIFFERENT NORMS")
    print("="*80)
    
    # Same author list (not alphabetically sorted, so detected as relative)
    authors_same = ['Wang, H.', 'Li, M.', 'Zhang, Y.', 'Liu, S.', 'Chen, W.']
    fields_same = {
        'Machine Learning': 0.60,
        'Data Science': 0.40
    }
    
    # Case A: Forced alphabetical (simulate by making it sorted)
    authors_sorted = sorted(authors_same)
    print("\nCase A: Alphabetical order (authors sorted)")
    result_comp_alpha = calculator.calculate_total_author_contributions(
        paper_id='P004A',
        author_list=authors_sorted,
        fields_data=fields_same
    )
    calculator.print_contribution_summary(result_comp_alpha)
    
    print("\nCase B: Relative contribution (original order)")
    result_comp_rel = calculator.calculate_total_author_contributions(
        paper_id='P004B',
        author_list=authors_same,
        fields_data=fields_same
    )
    calculator.print_contribution_summary(result_comp_rel)


if __name__ == "__main__":
    run_examples()