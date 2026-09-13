"""
Unit Tests and Validation for Credit & ACI System

Tests the core functionality of the author ordering classification
and credit distribution system.
"""

import unittest
from author_order_classifier import (
    normalize_family_name,
    is_alphabetical,
    chance_probability,
    calculate_aci,
    distribute_credit_contribution_based,
    distribute_credit_alphabetical,
    distribute_credit_mixed,
)


class TestNormalization(unittest.TestCase):
    """Test author name normalization."""
    
    def test_normalize_lowercase(self):
        """Test that names are converted to lowercase."""
        self.assertEqual(normalize_family_name("SMITH"), "smith")
        self.assertEqual(normalize_family_name("Smith"), "smith")
    
    def test_normalize_punctuation(self):
        """Test that special characters are removed."""
        self.assertEqual(normalize_family_name("O'Brien"), "obrien")
        self.assertEqual(normalize_family_name("Müller"), "muller")
    
    def test_normalize_whitespace(self):
        """Test that whitespace is trimmed."""
        self.assertEqual(normalize_family_name("  smith  "), "smith")
        self.assertEqual(normalize_family_name("van der plas"), "van der plas")


class TestAlphabeticalDetection(unittest.TestCase):
    """Test alphabetical ordering detection."""
    
    def test_alphabetical_order(self):
        """Test detection of alphabetically ordered authors."""
        authors = [
            {"family": "Anderson"},
            {"family": "Brown"},
            {"family": "Chen"},
            {"family": "Kumar"},
        ]
        self.assertTrue(is_alphabetical(authors))
    
    def test_non_alphabetical_order(self):
        """Test detection of non-alphabetical ordering."""
        authors = [
            {"family": "Smith"},
            {"family": "Johnson"},
            {"family": "Williams"},
            {"family": "Brown"},
        ]
        self.assertFalse(is_alphabetical(authors))
    
    def test_partially_alphabetical(self):
        """Test that partial alphabetical order is not considered alphabetical."""
        authors = [
            {"family": "Anderson"},
            {"family": "Brown"},
            {"family": "Chen"},
            {"family": "Davis"},  # Out of order
        ]
        self.assertFalse(is_alphabetical(authors))
    
    def test_missing_family_name(self):
        """Test handling of missing family names."""
        authors = [
            {"family": "Anderson"},
            {"given": "John"},  # No family name
            {"family": "Chen"},
        ]
        self.assertFalse(is_alphabetical(authors))
    
    def test_case_insensitive_alphabetical(self):
        """Test that alphabetical detection is case-insensitive."""
        authors = [
            {"family": "anderson"},
            {"family": "Brown"},
            {"family": "CHEN"},
        ]
        self.assertTrue(is_alphabetical(authors))


class TestChanceProbability(unittest.TestCase):
    """Test chance probability calculations."""
    
    def test_two_authors(self):
        """Test probability for 2 authors."""
        prob = chance_probability(2)
        self.assertAlmostEqual(prob, 0.5)  # 1/2! = 0.5
    
    def test_three_authors(self):
        """Test probability for 3 authors."""
        prob = chance_probability(3)
        self.assertAlmostEqual(prob, 1/6)  # 1/3! ≈ 0.167
    
    def test_four_authors(self):
        """Test probability for 4 authors."""
        prob = chance_probability(4)
        self.assertAlmostEqual(prob, 1/24)  # 1/4! ≈ 0.0417
    
    def test_decreasing_probability(self):
        """Test that probability decreases with more authors."""
        prob_2 = chance_probability(2)
        prob_3 = chance_probability(3)
        prob_4 = chance_probability(4)
        self.assertGreater(prob_2, prob_3)
        self.assertGreater(prob_3, prob_4)


class TestACICalculation(unittest.TestCase):
    """Test ACI (Author Contribution Index) calculations."""
    
    def test_single_author(self):
        """Test ACI for single author."""
        contributions = {"Alice": 100}
        aci = calculate_aci(contributions)
        # ACI_Alice = 100 / (100 - 100) = 100 / 0 = inf
        self.assertTrue(aci["Alice"] == float('inf'))
    
    def test_two_authors_equal(self):
        """Test ACI for two equal contributors."""
        contributions = {"Alice": 50, "Bob": 50}
        aci = calculate_aci(contributions)
        # ACI_Alice = 50 / (100 - 50) = 50 / 50 = 1.0
        self.assertAlmostEqual(aci["Alice"], 1.0)
        self.assertAlmostEqual(aci["Bob"], 1.0)
    
    def test_unequal_contributions(self):
        """Test ACI with unequal contributions."""
        contributions = {"Alice": 60, "Bob": 40}
        aci = calculate_aci(contributions)
        # ACI_Alice = 60 / (100 - 60) = 60 / 40 = 1.5
        # ACI_Bob = 40 / (100 - 40) = 40 / 60 = 0.667
        self.assertAlmostEqual(aci["Alice"], 1.5, places=3)
        self.assertAlmostEqual(aci["Bob"], 0.667, places=3)
    
    def test_zero_contribution(self):
        """Test ACI for author with zero contribution."""
        contributions = {"Alice": 100, "Bob": 0}
        aci = calculate_aci(contributions)
        self.assertEqual(aci["Bob"], 0.0)
    
    def test_four_authors_example(self):
        """Test ACI calculation from documentation example."""
        contributions = {
            "Anderson": 10,
            "Brown": 20,
            "Chen": 50,
            "Kumar": 20,
        }
        aci = calculate_aci(contributions)
        
        # Verify all ACI scores are positive
        for score in aci.values():
            self.assertGreaterEqual(score, 0)
        
        # Chen (50% contribution) should have highest ACI
        aci_scores_list = [(name, score) for name, score in aci.items()]
        chen_aci = aci["Chen"]
        max_aci = max(score for _, score in aci_scores_list)
        self.assertEqual(chen_aci, max_aci)


class TestCreditDistribution(unittest.TestCase):
    """Test credit distribution across different ordering models."""
    
    def test_contribution_based_four_authors(self):
        """Test position-weighted credit for 4 authors."""
        authors = ["Smith", "Johnson", "Williams", "Brown"]
        credit = distribute_credit_contribution_based(authors, 4)
        
        # Verify all authors are assigned credit
        self.assertEqual(len(credit), 4)
        
        # Verify total = 100%
        total = sum(credit.values())
        self.assertAlmostEqual(total, 100.0, places=1)
        
        # Verify ordering: 1st > 2nd > 3rd > 4th
        credits_list = [credit[a] for a in authors]
        self.assertGreater(credits_list[0], credits_list[1])
        self.assertGreater(credits_list[1], credits_list[2])
    
    def test_contribution_based_two_authors(self):
        """Test position-weighted credit for 2 authors."""
        authors = ["First", "Last"]
        credit = distribute_credit_contribution_based(authors, 2)
        
        # First author should get more than last
        self.assertGreater(credit["First"], credit["Last"])
        self.assertAlmostEqual(sum(credit.values()), 100.0)
    
    def test_alphabetical_equal_credit(self):
        """Test equal credit distribution for alphabetical journals (no ACI)."""
        authors = ["Anderson", "Brown", "Chen", "Kumar"]
        credit = distribute_credit_alphabetical(authors, 4, contributions=None)
        
        # All should have equal credit
        for author in authors:
            self.assertAlmostEqual(credit[author], 25.0, places=1)
    
    def test_alphabetical_with_aci(self):
        """Test ACI-based credit distribution for alphabetical journals."""
        authors = ["Anderson", "Brown", "Chen", "Kumar"]
        contributions = {
            "Anderson": 10,
            "Brown": 20,
            "Chen": 50,
            "Kumar": 20,
        }
        credit = distribute_credit_alphabetical(authors, 4, contributions)
        
        # Verify total = 100%
        total = sum(credit.values())
        self.assertAlmostEqual(total, 100.0, places=1)
        
        # Chen should get the most credit (50% contribution)
        self.assertGreater(credit["Chen"], credit["Anderson"])
        self.assertGreater(credit["Chen"], credit["Brown"])
        self.assertGreater(credit["Chen"], credit["Kumar"])
    
    def test_mixed_without_contributions(self):
        """Test mixed ordering without contribution data."""
        authors = ["Garcia", "Martinez", "Lopez", "Hernandez"]
        credit = distribute_credit_mixed(authors, 4, contributions=None)
        
        # Should default to equal credit
        for author in authors:
            self.assertAlmostEqual(credit[author], 25.0, places=1)
    
    def test_mixed_with_contributions(self):
        """Test mixed ordering with contribution data."""
        authors = ["Garcia", "Martinez", "Lopez", "Hernandez"]
        contributions = {
            "Garcia": 40,
            "Martinez": 35,
            "Lopez": 15,
            "Hernandez": 10,
        }
        credit = distribute_credit_mixed(authors, 4, contributions)
        
        # Should use ACI
        total = sum(credit.values())
        self.assertAlmostEqual(total, 100.0, places=1)
        
        # Garcia and Martinez should have higher credit
        self.assertGreater(
            credit["Garcia"] + credit["Martinez"],
            credit["Lopez"] + credit["Hernandez"]
        )


class TestIntegration(unittest.TestCase):
    """Integration tests combining multiple components."""
    
    def test_alphabetical_journal_workflow(self):
        """Test complete workflow for alphabetical journal."""
        # Alphabetically ordered authors
        authors = [
            {"family": "Anderson"},
            {"family": "Brown"},
            {"family": "Chen"},
            {"family": "Kumar"},
        ]
        
        # Should be detected as alphabetical
        self.assertTrue(is_alphabetical(authors))
        
        # Get author names
        names = [a["family"] for a in authors]
        
        # Without contributions: equal credit
        credit_equal = distribute_credit_alphabetical(names, 4, None)
        self.assertAlmostEqual(credit_equal["Chen"], 25.0)
        
        # With contributions: ACI-based
        contributions = {
            "Anderson": 10, "Brown": 20, "Chen": 50, "Kumar": 20
        }
        credit_aci = distribute_credit_alphabetical(names, 4, contributions)
        
        # Chen should get much more credit with ACI
        self.assertGreater(
            credit_aci["Chen"],
            credit_equal["Chen"]
        )
    
    def test_contribution_based_journal_workflow(self):
        """Test complete workflow for contribution-based journal."""
        # Non-alphabetical authors
        authors = [
            {"family": "Smith"},
            {"family": "Johnson"},
            {"family": "Lee"},
            {"family": "Brown"},
        ]
        
        # Should NOT be alphabetical
        self.assertFalse(is_alphabetical(authors))
        
        # Get names and calculate contribution-based credit
        names = [a["family"] for a in authors]
        credit = distribute_credit_contribution_based(names, 4)
        
        # Smith (1st) should get much more than Brown (last)
        self.assertGreater(credit["Smith"], credit["Brown"])
        self.assertGreater(credit["Smith"], 30)  # At least 30%
        self.assertLess(credit["Brown"], 20)     # At most 20%


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def test_single_author(self):
        """Test handling of single author."""
        authors = [{"family": "Smith"}]
        credit = distribute_credit_contribution_based(
            [a["family"] for a in authors], 1
        )
        self.assertAlmostEqual(credit["Smith"], 100.0)
    
    def test_many_authors(self):
        """Test handling of many authors."""
        authors = [{"family": f"Author{i}"} for i in range(20)]
        names = [a["family"] for a in authors]
        credit = distribute_credit_contribution_based(names, 20)
        
        # Should still sum to ~100%
        total = sum(credit.values())
        self.assertAlmostEqual(total, 100.0, places=0)
    
    def test_duplicate_names(self):
        """Test handling of duplicate author names."""
        contributions = {
            "Smith": 50,
            "Smith": 50,  # Overwrites previous
        }
        # Dictionary will keep only the last Smith
        self.assertEqual(len(contributions), 1)
    
    def test_empty_contributions(self):
        """Test ACI with empty contributions dict."""
        aci = calculate_aci({})
        self.assertEqual(len(aci), 0)


def run_tests():
    """Run all tests and print summary."""
    print("\n" + "="*70)
    print("  Running Unit Tests for Credit & ACI System")
    print("="*70 + "\n")
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestNormalization))
    suite.addTests(loader.loadTestsFromTestCase(TestAlphabeticalDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestChanceProbability))
    suite.addTests(loader.loadTestsFromTestCase(TestACICalculation))
    suite.addTests(loader.loadTestsFromTestCase(TestCreditDistribution))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"  Tests run: {result.testsRun}")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    print("="*70 + "\n")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
