import requests
import json
import re
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime


class CrossRefAPI:
    """Class to fetch publication details from CrossRef API."""
    
    BASE_URL = "https://api.crossref.org/works"
    
    def __init__(self, email: Optional[str] = None):
        """
        Initialize the CrossRef API client.
        
        Args:
            email: Your email for polite pool (faster rate limits)
        """
        self.headers = {
            "User-Agent": "PythonCrossRefClient/1.0"
        }
        if email:
            self.headers["User-Agent"] += f" (mailto:{email})"

    def _normalize_text(self, value: str) -> str:
        """Normalize text for reliable comparisons."""
        return " ".join(re.sub(r"[^a-z0-9\s]", " ", value.lower()).split())

    def _tokens_are_compatible(self, left_token: str, right_token: str) -> bool:
        """Return True when two name tokens are equal or one is the initial of the other."""
        if left_token == right_token:
            return True

        if len(left_token) == 1 and right_token.startswith(left_token):
            return True

        if len(right_token) == 1 and left_token.startswith(right_token):
            return True

        return False

    def _given_names_match(self, requested_parts: List[str], author_parts: List[str]) -> bool:
        """Compare given-name tokens, allowing exact and initial-based matches."""
        requested_given = requested_parts[:-1]
        author_given = author_parts[:-1]

        if not requested_given or not author_given:
            return False

        requested_index = 0
        author_index = 0

        while requested_index < len(requested_given) and author_index < len(author_given):
            if self._tokens_are_compatible(requested_given[requested_index], author_given[author_index]):
                requested_index += 1
                author_index += 1
            elif len(requested_given[requested_index]) == 1:
                requested_index += 1
            elif len(author_given[author_index]) == 1:
                author_index += 1
            else:
                return False

        while requested_index < len(requested_given):
            if len(requested_given[requested_index]) != 1:
                return False
            requested_index += 1

        while author_index < len(author_given):
            if len(author_given[author_index]) != 1:
                return False
            author_index += 1

        return True

    def _author_matches(self, requested_name: str, authors: List[Dict[str, Any]]) -> bool:
        """Return True if any result author matches the requested name, including initials."""
        normalized_requested = self._normalize_text(requested_name)
        requested_parts = normalized_requested.split()

        if len(requested_parts) < 2:
            return False

        for author in authors:
            normalized_author = self._normalize_text(author.get("name", ""))
            if normalized_author == normalized_requested:
                return True

            author_parts = normalized_author.split()
            if len(author_parts) < 2:
                continue

            if requested_parts[-1] != author_parts[-1]:
                continue

            if self._given_names_match(requested_parts, author_parts):
                return True

        return False

    def _filter_results_by_author_name(
        self,
        requested_name: str,
        results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Keep only papers whose author list contains the requested full author name."""
        return [
            result for result in results
            if self._author_matches(requested_name, result.get("authors", []))
        ]
    
    def search_by_title(self, title: str, rows: int = 5) -> List[Dict[str, Any]]:
        """
        Search for publications by title.
        
        Args:
            title: The title to search for
            rows: Number of results to return (default: 5)
            
        Returns:
            List of publication details
        """
        params = {
            "query.title": title,
            "rows": rows
        }
        
        response = requests.get(self.BASE_URL, params=params, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            return self._parse_results(data.get("message", {}).get("items", []))
        else:
            print(f"Error: {response.status_code}")
            return []
    
    def search_by_author(self, author_name: str, rows: int = 10) -> List[Dict[str, Any]]:
        """
        Search for publications by author name.
        
        Args:
            author_name: The author name to search for
            rows: Number of results to return (default: 10)
            
        Returns:
            List of publication details
        """
        params = {
            "query.author": author_name,
            "rows": rows
        }
        
        response = requests.get(self.BASE_URL, params=params, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            parsed_results = self._parse_results(data.get("message", {}).get("items", []))
            return self._filter_results_by_author_name(author_name, parsed_results)
        else:
            print(f"Error: {response.status_code}")
            return []
    
    def get_all_papers_by_author(self, author_name: str, max_results: int = 1000) -> List[Dict[str, Any]]:
        """
        Get ALL papers by an author using pagination.
        
        Args:
            author_name: The author name to search for
            max_results: Maximum number of results to fetch (default: 1000)
            
        Returns:
            List of all publication details
        """
        all_results = []
        offset = 0
        rows_per_request = 100  # CrossRef allows up to 1000, but 100 is more reliable
        
        print(f"\nFetching all papers for author: '{author_name}'...")
        
        while offset < max_results:
            params = {
                "query.author": author_name,
                "rows": min(rows_per_request, max_results - offset),
                "offset": offset
            }
            
            response = requests.get(self.BASE_URL, params=params, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("message", {}).get("items", [])
                
                if not items:
                    break  # No more results
                
                parsed = self._parse_results(items)
                filtered = self._filter_results_by_author_name(author_name, parsed)
                all_results.extend(filtered)
                
                total_results = data.get("message", {}).get("total-results", 0)
                print(f"  Fetched {len(all_results)} of {min(total_results, max_results)} papers...")
                
                offset += rows_per_request
                
                # Stop if we've fetched all available results
                if offset >= total_results:
                    break
                    
            else:
                print(f"Error: {response.status_code}")
                break
        
        print(f"✓ Total papers fetched: {len(all_results)}")
        return all_results
    
    def search_by_author_and_title(self, author_name: str, title: str, rows: int = 5) -> List[Dict[str, Any]]:
        """
        Search for publications by both author name and title.
        
        Args:
            author_name: The author name to search for
            title: The title to search for
            rows: Number of results to return (default: 5)
            
        Returns:
            List of publication details
        """
        params = {
            "query.author": author_name,
            "query.title": title,
            "rows": rows
        }
        
        response = requests.get(self.BASE_URL, params=params, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            parsed_results = self._parse_results(data.get("message", {}).get("items", []))
            return self._filter_results_by_author_name(author_name, parsed_results)
        else:
            print(f"Error: {response.status_code}")
            return []
    
    def get_by_doi(self, doi: str) -> Optional[Dict[str, Any]]:
        """
        Get publication details by DOI.
        
        Args:
            doi: The DOI of the publication
            
        Returns:
            Publication details or None if not found
        """
        url = f"{self.BASE_URL}/{doi}"
        
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            data = response.json()
            results = self._parse_results([data.get("message", {})])
            return results[0] if results else None
        else:
            print(f"Error: {response.status_code}")
            return None
    
    def _parse_results(self, items: List[Dict]) -> List[Dict[str, Any]]:
        """
        Parse CrossRef API results into a cleaner format.
        
        Args:
            items: Raw items from CrossRef API
            
        Returns:
            List of parsed publication details
        """
        results = []
        
        for item in items:
            # Extract DOI
            doi = item.get("DOI", "N/A")
            
            # Extract Title
            title_list = item.get("title", [])
            title = title_list[0] if title_list else "N/A"
            
            # Extract Abstract
            abstract = item.get("abstract", "N/A")
            # Clean up HTML tags from abstract if present
            if abstract != "N/A":
                abstract = re.sub(r'<[^>]+>', '', abstract)
            
            # Extract Journal/Container Title
            container_title_list = item.get("container-title", [])
            journal = container_title_list[0] if container_title_list else "N/A"
            
            # Extract Year
            published_date = item.get("published-print") or item.get("published-online") or item.get("created")
            year = "N/A"
            if published_date and "date-parts" in published_date:
                date_parts = published_date["date-parts"]
                if date_parts and date_parts[0]:
                    year = date_parts[0][0]
            
            # Extract Authors
            authors_list = item.get("author", [])
            authors = []
            for author in authors_list:
                given_name = author.get("given", "")
                family_name = author.get("family", "")
                full_name = f"{given_name} {family_name}".strip()
                if full_name:
                    authors.append({
                        "name": full_name,
                        "affiliation": author.get("affiliation", []),
                        "orcid": author.get("ORCID", "N/A")
                    })
            
            # Extract additional useful information
            publication_type = item.get("type", "N/A")
            issn = item.get("ISSN", [])
            url = item.get("URL", "N/A")
            references_count = item.get("references-count", 0)
            is_referenced_by_count = item.get("is-referenced-by-count", 0)
            
            results.append({
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "journal": journal,
                "year": year,
                "authors": authors,
                "publication_type": publication_type,
                "issn": issn,
                "url": url,
                "references_count": references_count,
                "citations_count": is_referenced_by_count
            })
        
        return results
    
    def print_result(self, result: Dict[str, Any]):
        """
        Print a single result in a formatted way.
        
        Args:
            result: A parsed publication result
        """
        print("=" * 80)
        print(f"DOI: {result['doi']}")
        print(f"Title: {result['title']}")
        print(f"Journal: {result['journal']}")
        print(f"Year: {result['year']}")
        print(f"Publication Type: {result['publication_type']}")
        print(f"Citations: {result['citations_count']}")
        print(f"URL: {result['url']}")
        print("\nAuthors:")
        for i, author in enumerate(result['authors'], 1):
            print(f"  {i}. {author['name']}")
            if author['orcid'] != "N/A":
                print(f"     ORCID: {author['orcid']}")
        print(f"\nAbstract: {result['abstract'][:500]}..." if len(result['abstract']) > 500 else f"\nAbstract: {result['abstract']}")
        print("=" * 80)
    
    def save_to_excel(self, results: List[Dict[str, Any]], filename: Optional[str] = None) -> str:
        """
        Save the results to an Excel file.
        
        Args:
            results: List of parsed publication results
            filename: Optional filename (without extension). If not provided, auto-generates one.
            
        Returns:
            The path to the saved Excel file
        """
        if not results:
            print("No results to save.")
            return ""
        
        # Prepare data for DataFrame
        excel_data = []
        for result in results:
            # Convert authors list to a formatted string
            authors_str = "; ".join([author['name'] for author in result['authors']])
            authors_orcid = "; ".join([
                f"{author['name']} ({author['orcid']})" 
                for author in result['authors'] 
                if author['orcid'] != "N/A"
            ])
            
            # Convert ISSN list to string
            issn_str = "; ".join(result.get('issn', [])) if result.get('issn') else "N/A"
            
            excel_data.append({
                "DOI": result['doi'],
                "Title": result['title'],
                "Abstract": result['abstract'],
                "Journal": result['journal'],
                "Year": result['year'],
                "Authors": authors_str,
                "Authors with ORCID": authors_orcid if authors_orcid else "N/A",
                "Number of Authors": len(result['authors']),
                "Publication Type": result['publication_type'],
                "ISSN": issn_str,
                "URL": result['url'],
                "References Count": result['references_count'],
                "Citations Count": result['citations_count']
            })
        
        # Create DataFrame
        df = pd.DataFrame(excel_data)
        
        # Generate filename if not provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crossref_results_{timestamp}"
        
        # Ensure .xlsx extension
        if not filename.endswith('.xlsx'):
            filename = f"{filename}.xlsx"
        
        # Save to Excel with formatting
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Publications')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Publications']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                # Limit column width to 50 for readability
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[chr(65 + idx) if idx < 26 else f"{chr(65 + idx // 26 - 1)}{chr(65 + idx % 26)}"].width = adjusted_width
        
        print(f"\n✓ Results saved to: {filename}")
        return filename


def main():
    """Main function to fetch publication data and save to Excel."""
    
    # Initialize the API client
    api = CrossRefAPI(email="your_email@example.com")
    
    print("\n" + "=" * 80)
    print("CrossRef API - Publication Search & Save to Excel")
    print("=" * 80)
    
    print("\nHow would you like to search?")
    print("1. Search by Title")
    print("2. Search by Author Name (limited results)")
    print("3. Get ALL papers by Author (fetches all available)")
    print("4. Search by Author and Title")
    print("5. Get by DOI")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    results = []
    
    if choice == "1":
        title = input("Enter the title to search: ").strip()
        rows = input("Number of results to fetch (default 10): ").strip()
        rows = int(rows) if rows.isdigit() else 10
        if title:
            print(f"\nSearching for title: '{title}'...")
            results = api.search_by_title(title, rows=rows)
    
    elif choice == "2":
        author = input("Enter the author name to search: ").strip()
        rows = input("Number of results to fetch (default 10): ").strip()
        rows = int(rows) if rows.isdigit() else 10
        if author:
            print(f"\nSearching for author: '{author}'...")
            results = api.search_by_author(author, rows=rows)
    
    elif choice == "3":
        author = input("Enter the author name: ").strip()
        max_results = input("Maximum papers to fetch (default 500, enter 'all' for unlimited): ").strip()
        if max_results.lower() == 'all':
            max_results = 10000
        else:
            max_results = int(max_results) if max_results.isdigit() else 500
        if author:
            results = api.get_all_papers_by_author(author, max_results=max_results)
    
    elif choice == "4":
        author = input("Enter the author name: ").strip()
        title = input("Enter the title: ").strip()
        rows = input("Number of results to fetch (default 10): ").strip()
        rows = int(rows) if rows.isdigit() else 10
        if author and title:
            print(f"\nSearching for author: '{author}' and title: '{title}'...")
            results = api.search_by_author_and_title(author, title, rows=rows)
    
    elif choice == "5":
        doi = input("Enter the DOI: ").strip()
        if doi:
            print(f"\nFetching DOI: '{doi}'...")
            result = api.get_by_doi(doi)
            if result:
                results = [result]
    
    else:
        print("Invalid choice.")
        return
    
    # Display and save results
    if results:
        print(f"\n✓ Found {len(results)} result(s):\n")
        
        # Ask if user wants to see all results (can be many)
        if len(results) > 5:
            show_all = input(f"Show all {len(results)} results on screen? (y/n, default: n): ").strip().lower()
            if show_all == 'y':
                for result in results:
                    api.print_result(result)
            else:
                print("Showing first 3 results...")
                for result in results[:3]:
                    api.print_result(result)
        else:
            for result in results:
                api.print_result(result)
        
        # Save to Excel automatically
        filename = input("\nEnter filename for Excel (press Enter for auto-generated name): ").strip()
        api.save_to_excel(results, filename if filename else None)
        print("\nDone!")
    else:
        print("\nNo results found.")


# Example usage for quick testing
def example_usage():
    """Example usage of the CrossRef API client."""
    
    api = CrossRefAPI()
    
    # Example 1: Search by title
    print("\n--- Search by Title ---")
    results = api.search_by_title("machine learning", rows=2)
    for result in results:
        api.print_result(result)
    
    # Example 2: Search by author
    print("\n--- Search by Author ---")
    results = api.search_by_author("John Smith", rows=2)
    for result in results:
        api.print_result(result)
    
    # Example 3: Get by DOI
    print("\n--- Get by DOI ---")
    result = api.get_by_doi("10.1038/nature12373")
    if result:
        api.print_result(result)


if __name__ == "__main__":
    main()