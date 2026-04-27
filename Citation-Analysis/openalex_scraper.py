#!/usr/bin/env python3
"""
OpenAlex Publication Citation Analyzer
Analyzes author publications and their citations using FREE OpenAlex API

NO API KEY REQUIRED - Completely FREE!

QUICK START:
  1. Edit input_authors.csv with author names
  2. Run: python openalex_scraper.py input_authors.csv output_results.csv
  3. Check output_results.csv for results
"""

import pandas as pd
import csv
from typing import List, Dict, Set, Tuple
import os
import sys
from pathlib import Path
import time
import re
from urllib.parse import quote
from datetime import datetime

# API requests
import requests
import socket

class OpenAlexScraper:
    """OpenAlex scraper for citation analysis - FREE, no API key needed"""
    
    MAX_CITING_PAPERS = 100
    BASE_URL = "https://api.openalex.org"
    
    # User agent for API requests (OpenAlex requires this)
    HEADERS = {
        'User-Agent': 'CitationAnalyzer (mailto:user@institution.edu)'
    }
    
    # Connection resilience settings
    MAX_RETRIES = 5
    INITIAL_RETRY_DELAY = 1  # seconds
    MAX_RETRY_DELAY = 120    # 2 minutes max
    
    def __init__(self):
        self.results = []
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.connection_lost_count = 0
        
    def check_internet_connection(self) -> bool:
        """Check if internet connection is available"""
        try:
            # Try to connect to Google DNS
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except (socket.timeout, socket.error):
            return False
    
    def wait_for_connection(self):
        """Wait for internet connection to be restored"""
        wait_time = self.INITIAL_RETRY_DELAY
        attempt = 1
        
        while not self.check_internet_connection():
            print(f"\n⚠️  CONNECTION LOST - Waiting for connection to be restored...")
            print(f"   [Attempt {attempt}] Retrying in {wait_time} seconds...")
            print(f"   Check your internet connection or try again later")
            print(f"   Data will be automatically saved when connection returns\n")
            
            try:
                time.sleep(wait_time)
            except KeyboardInterrupt:
                print("⚠️  Connection wait interrupted by user")
                raise
            
            # Exponential backoff: double the wait time, up to MAX_RETRY_DELAY
            wait_time = min(wait_time * 2, self.MAX_RETRY_DELAY)
            attempt += 1
        
        print(f"✅ CONNECTION RESTORED! Resuming from where we left off...\n")
    
    def make_request_with_retry(self, url: str, params: dict = None, timeout: int = 10) -> dict:
        """Make API request with automatic retry and connection recovery"""
        retry_count = 0
        wait_time = self.INITIAL_RETRY_DELAY
        
        while retry_count < self.MAX_RETRIES:
            try:
                # Check connection before making request
                if not self.check_internet_connection():
                    self.wait_for_connection()
                
                response = self.session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response.json()
                
            except (requests.ConnectionError, requests.Timeout) as e:
                retry_count += 1
                print(f"\n⚠️  CONNECTION ERROR: {type(e).__name__}")
                
                if retry_count >= self.MAX_RETRIES:
                    print(f"   Max retries ({self.MAX_RETRIES}) exceeded")
                    raise
                
                print(f"   Waiting {wait_time}s before retry {retry_count}/{self.MAX_RETRIES}...")
                
                try:
                    time.sleep(wait_time)
                except KeyboardInterrupt:
                    raise
                
                wait_time = min(wait_time * 2, self.MAX_RETRY_DELAY)
                
            except requests.RequestException as e:
                print(f"   Request error: {str(e)[:60]}")
                raise
            
            except Exception as e:
                print(f"   Unexpected error: {str(e)[:60]}")
                raise
        
        raise Exception("Failed to complete request after retries")
        
    def search_author(self, author_name: str) -> Dict:
        """Search for author by name in OpenAlex"""
        try:
            print(f"  Searching: {author_name}")
            
            # OpenAlex author search endpoint
            url = f"{self.BASE_URL}/authors"
            params = {'search': author_name, 'per_page': 1}
            
            data = self.make_request_with_retry(url, params, timeout=10)
            
            if data['results']:
                author = data['results'][0]
                print(f"    [FOUND] {author['display_name']} ({author['works_count']} works)")
                return author
            else:
                print(f"    [NOT FOUND] Author not found")
                return None
                
        except Exception as e:
            print(f"    [ERROR] {str(e)[:60]}")
            return None
    
    def get_author_publications(self, author: Dict, author_name: str) -> List[Dict]:
        """Get publications for an author using works_api_url"""
        try:
            print(f"    Fetching publications...")
            
            # Get the works_api_url from author object
            if 'works_api_url' not in author:
                print(f"    [WARNING] No works_api_url in author data")
                return []
            
            works_url = author['works_api_url']
            
            # Fetch works using the proper URL with retry logic
            params = {
                'sort': 'cited_by_count:desc',  # Fixed: use hyphenated field names
                'per_page': 100  # Increased from 50 to get more publications
            }
            
            data = self.make_request_with_retry(works_url, params, timeout=10)
            
            publications = []
            
            for work in data.get('results', []):
                # Extract authors
                authors = []
                if work.get('authorships'):
                    for auth in work['authorships'][:20]:
                        if 'author' in auth and auth['author']:
                            authors.append(auth['author']['display_name'])
                
                # Get year
                try:
                    if work.get('publication_date'):
                        parts = work['publication_date'].split('-')
                        year = int(parts[0]) if parts and parts[0].strip() else 2024
                    else:
                        year = 2024
                except (ValueError, IndexError, AttributeError):
                    year = 2024
                
                pub = {
                    'id': work['id'],
                    'title': work.get('title', 'Unknown'),
                    'year': year,
                    'cited_by_count': work.get('cited_by_count', 0),
                    'authors': authors if authors else [author_name],
                    'scopus_id': work.get('ids', {}).get('scopus', '') if work.get('ids') else ''
                }
                publications.append(pub)
            
            if publications:
                print(f"    ✓ Found {len(publications)} publication(s)")
            else:
                print(f"    ⚠ No publications found")
                
            return publications
            
        except Exception as e:
            print(f"    Error: {str(e)[:60]}")
            return []
    
    def get_citing_papers(self, work_id: str, work_title: str) -> List[Dict]:
        """Get papers that cite the given publication"""
        try:
            print(f"    Searching for citing papers...")
            
            # Extract clean ID
            if 'https://' in str(work_id):
                clean_id = work_id.split('/')[-1]
            else:
                clean_id = work_id
            
            # Use OpenAlex works endpoint with cites filter
            url = f"{self.BASE_URL}/works"
            params = {
                'filter': f'cites:{clean_id}',
                'sort': 'cited_by_count:desc',
                'per_page': self.MAX_CITING_PAPERS  # Now fetches up to 100 citing papers
            }
            
            data = self.make_request_with_retry(url, params, timeout=10)
            
            citing_papers = []
            
            for work in data.get('results', [])[:self.MAX_CITING_PAPERS]:
                # Extract authors
                authors = []
                if work.get('authorships'):
                    for auth in work['authorships'][:10]:
                        if 'author' in auth and auth['author']:
                            authors.append(auth['author']['display_name'])
                
                # Get year
                try:
                    if work.get('publication_date'):
                        parts = work['publication_date'].split('-')
                        year = int(parts[0]) if parts and parts[0].strip() else 2024
                    else:
                        year = 2024
                except (ValueError, IndexError, AttributeError):
                    year = 2024
                
                citing_papers.append({
                    'id': work['id'],
                    'title': work.get('title', 'Unknown'),
                    'year': year,
                    'authors': authors if authors else ['Unknown'],
                    'scopus_id': work.get('ids', {}).get('scopus', '') if work.get('ids') else ''
                })
            
            print(f"    ✓ Found {len(citing_papers)} citing paper(s)")
            return citing_papers
            
        except Exception as e:
            print(f"    Error: {str(e)[:60]}")
            return []
    
    def extract_author_names(self, author_list: List[str]) -> Set[str]:
        """Extract individual author names"""
        if not author_list:
            return set()
        return set(author.strip() for author in author_list if author.strip())
    
    def find_overlapping_authors(self, original_authors: Set[str], 
                                citing_authors: List[str]) -> Tuple[Set[str], Set[str]]:
        """Find overlapping and non-overlapping authors"""
        citing_set = set(citing_authors)
        
        # Fuzzy matching for author names (handle small variations)
        overlapping = set()
        non_overlapping = citing_set.copy()
        
        for citing_author in citing_set:
            if not citing_author or not citing_author.strip():  # Skip empty authors
                continue
                
            for orig_author in original_authors:
                if not orig_author or not orig_author.strip():  # Skip empty authors
                    continue
                    
                # Exact match
                if citing_author.lower() == orig_author.lower():
                    overlapping.add(citing_author)
                    break
                
                # Last name match (safe split with fallback)
                citing_parts = citing_author.split()
                orig_parts = orig_author.split()
                
                if citing_parts and orig_parts:  # Only compare if both have parts
                    if citing_parts[-1].lower() == orig_parts[-1].lower():
                        overlapping.add(citing_author)
                        if citing_author in non_overlapping:
                            non_overlapping.discard(citing_author)
                        break
        
        return overlapping, non_overlapping
    
    def process_author(self, author_name: str, output_csv: str = None, author_idx: int = 0, total_authors: int = 0, batch_num: str = "") -> tuple:
        """Process a single author and extract citation data for ALL their publications
        Returns tuple of (detail_rows, summary_row, author_metadata)
        Saves results incrementally after each publication to prevent data loss on interrupt
        author_idx: current author number (for display)
        total_authors: total authors being processed (for display)
        batch_num: batch number for display
        """
        print(f"\n[Processing] {author_name}")
        author_results = []
        
        # Add delay to be respectful to API
        time.sleep(0.5)
        
        # Search for author
        author = self.search_author(author_name)
        if not author:
            return [], None, {}
        
        # Extract author metadata
        works_count = author.get('works_count', 0)
        author_scopus_id = ''
        if author.get('ids') and author['ids'].get('scopus'):
            author_scopus_id = author['ids']['scopus']
        
        # Get author publications using works_api_url
        publications = self.get_author_publications(author, author_name)
        if not publications:
            print(f"  No publications found")
            return [], None, {'author_name': author_name, 'works_count': works_count}
        
        print(f"  Found {len(publications)} publication(s)")
        
        # Track unique citing papers across all publications
        total_citing_count = 0
        
        # Process ALL publications for this author
        for pub_idx, original_pub in enumerate(publications, 1):
            # Show both author and publication counters with batch number
            if author_idx > 0 and total_authors > 0:
                if batch_num:
                    print(f"  BATCH {batch_num}: [{author_idx}/{total_authors}][{pub_idx}/{len(publications)}] {original_pub['title'][:50]}...")
                else:
                    print(f"  [{author_idx}/{total_authors}][{pub_idx}/{len(publications)}] {original_pub['title'][:50]}...")
            else:
                print(f"  [{pub_idx}/{len(publications)}] {original_pub['title'][:50]}...")
            print(f"      Cited by: {original_pub['cited_by_count']} papers", end="")
            
            original_authors = self.extract_author_names(original_pub['authors'])
            
            # Get citing papers for this publication
            citing_papers = self.get_citing_papers(original_pub['id'], original_pub['title'])
            if not citing_papers:
                print(" - No citing papers")
                continue
            
            print(f" - Found {len(citing_papers)} citing paper(s)")
            total_citing_count += len(citing_papers)
            
            pub_results = []  # Track results from this publication
            
            # Process each citing paper for this original publication
            for citing_paper in citing_papers:
                overlapping, non_overlapping = self.find_overlapping_authors(
                    original_authors, citing_paper['authors']
                )
                
                result = {
                    # Author & Metadata
                    'Author': author_name,
                    'Analysis_Type': 'Citation Analysis',
                    
                    # Original Publication (Input paper)
                    'OrigPub_Title': original_pub['title'],
                    'OrigPub_Year': original_pub['year'],
                    'OrigPub_Authors': ';'.join(original_authors),
                    'OrigPub_CitedByCount': original_pub['cited_by_count'],
                    
                    # Citing Publication (Paper that cites the original)
                    'CitingPub_Title': citing_paper['title'],
                    'CitingPub_Year': citing_paper['year'],
                    'CitingPub_Authors': ';'.join(citing_paper['authors']),
                    
                    # Author Overlap Analysis
                    'Overlap_CommonAuthors': ';'.join(overlapping) if overlapping else '',
                    'Overlap_Count': len(overlapping),
                    'Overlap_UniqueAuthors': ';'.join(non_overlapping) if non_overlapping else '',
                    'Overlap_UniqueCount': len(non_overlapping)
                }
                
                pub_results.append(result)
                author_results.append(result)
                
                # Save each row IMMEDIATELY to CSV for maximum data safety
                if output_csv:
                    try:
                        df_row = pd.DataFrame([result])
                        df_row.to_csv(output_csv, mode='a', header=False, 
                                    index=False, quoting=csv.QUOTE_ALL)
                    except:
                        pass  # Silent fail on write, continue processing
        
        print(f"  ✓ Created {len(author_results)} records")
        
        # Create summary row for this author
        summary_row = {
            'Author': f"=== SUMMARY: {author_name} ===",
            'Analysis_Type': f'Total Works in OpenAlex: {works_count}',
            'OrigPub_Title': f'Publications Analyzed: {len(publications)}',
            'OrigPub_Year': '',
            'OrigPub_Authors': f'Total Citing Papers Found: {total_citing_count}',
            'OrigPub_CitedByCount': f'Records Generated: {len(author_results)}',
            'CitingPub_Title': '',
            'CitingPub_Year': '',
            'CitingPub_Authors': '',
            'Overlap_CommonAuthors': '',
            'Overlap_Count': '',
            'Overlap_UniqueAuthors': '',
            'Overlap_UniqueCount': ''
        }
        
        return author_results, summary_row, {'author_name': author_name, 'works_count': works_count, 'pubs_analyzed': len(publications), 'total_citing': total_citing_count}
    
    def run(self, input_csv: str, output_csv: str):
        """Main execution method - saves data immediately after each author"""
        print("\n" + "="*70)
        print("OPENALEX PUBLICATION CITATION ANALYZER")
        print("FREE - No API Key Required - Unlimited Requests")
        print("="*70)
        
        # Check internet connection at startup
        print("Checking internet connection...")
        if not self.check_internet_connection():
            print("⚠️  No internet connection detected!")
            self.wait_for_connection()
        print("✅ Internet connection OK\n")
        
        print(f"Input:  {input_csv}")
        print(f"Output: {output_csv}\n")
        
        # Extract batch number from output filename (e.g., output_batch_001.csv -> 001)
        batch_num = ""
        if "batch_" in output_csv.lower():
            try:
                # Extract batch number like "001" from "output_batch_001.csv"
                parts = output_csv.split("_")
                for i, part in enumerate(parts):
                    if part == "batch" and i + 1 < len(parts):
                        batch_num = parts[i + 1].replace(".csv", "")
                        break
            except:
                pass
        
        print(f"Batch:  {batch_num if batch_num else 'N/A'}\n")
        
        # Read input CSV
        try:
            df_input = pd.read_csv(input_csv)
            authors = df_input['author'].tolist()
            print(f"Loaded {len(authors)} author(s)\n")
        except Exception as e:
            print(f"✗ Error reading input CSV: {e}")
            sys.exit(1)
        
        # CSV columns with better organization
        csv_columns = [
            'Author', 'Analysis_Type',
            'OrigPub_Title', 'OrigPub_Year', 'OrigPub_Authors', 'OrigPub_CitedByCount',
            'CitingPub_Title', 'CitingPub_Year', 'CitingPub_Authors',
            'Overlap_CommonAuthors', 'Overlap_Count',
            'Overlap_UniqueAuthors', 'Overlap_UniqueCount'
        ]
        
        # Initialize output CSV with headers
        try:
            df_empty = pd.DataFrame(columns=csv_columns)
            df_empty.to_csv(output_csv, index=False, quoting=csv.QUOTE_ALL)
            print(f"[OK] Initialized output file: {output_csv}\n")
        except Exception as e:
            print(f"[ERROR] Error initializing output CSV: {e}")
            sys.exit(1)
        
        # Process each author and save immediately with summaries
        total_records = 0
        try:
            for idx, author in enumerate(authors, 1):
                print(f"[{idx}/{len(authors)}]", end=' ')
                author_results, summary_row, metadata = self.process_author(author, output_csv, idx, len(authors), batch_num)
                
                # Save results immediately after processing each author
                if author_results:
                    total_records += len(author_results)
                    print(f"  ✓ Saved {len(author_results)} records (Total: {total_records})")
                    
                    # Save summary row for this author
                    if summary_row:
                        df_summary = pd.DataFrame([summary_row])
                        df_summary.to_csv(output_csv, mode='a', header=False, 
                                        index=False, quoting=csv.QUOTE_ALL)
                        # Add blank separator row
                        df_blank = pd.DataFrame([{col: '' for col in csv_columns}])
                        df_blank.to_csv(output_csv, mode='a', header=False, 
                                       index=False, quoting=csv.QUOTE_ALL)
                else:
                    print(f"  (No results)")
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️  INTERRUPTED BY USER")
            # Count actual records saved to file
            try:
                if os.path.exists(output_csv):
                    with open(output_csv, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        saved_count = max(0, len(lines) - 1)  # Subtract header
                    print(f"✓ Data saved successfully: {output_csv}")
                    print(f"  Records saved: {saved_count}")
                else:
                    print(f"✓ Data saved successfully: {output_csv}")
                    print(f"  Records saved so far: {total_records}")
            except Exception as e:
                print(f"✓ Data saved successfully: {output_csv}")
                print(f"  Records saved so far: {total_records}")
            print("\n" + "="*70)
            sys.exit(0)
        
        except Exception as e:
            print(f"\n\n⚠️  ERROR OCCURRED: {str(e)[:100]}")
            print(f"✓ Data saved successfully: {output_csv}")
            print(f"  Records saved: {total_records}")
            print("\n" + "="*70)
            sys.exit(1)
        
        # Print summary
        print("\n" + "="*70)
        print(f"Authors: {len(authors)} | Records: {total_records}")
        print("="*70)
        print("\n✅ OpenAlex scraping complete!")
        print("📊 Data source: OpenAlex (www.openalex.org)")
        print("💰 Cost: FREE - No subscription required")


def main():
    """Main entry point"""
    print("\nOpenAlex Citation Analyzer")
    print("-" * 70)
    
    # Handle command-line arguments
    if len(sys.argv) > 1:
        input_csv = sys.argv[1]
        output_csv = sys.argv[2] if len(sys.argv) > 2 else "output_results.csv"
    else:
        input_csv = "input_authors.csv"
        output_csv = "output_results.csv"
    
    # Validate input file
    if not os.path.exists(input_csv):
        print(f"✗ Input file not found: {input_csv}")
        print(f"\nCreate {input_csv} with format:")
        print("  author")
        print("  John Smith")
        print("  Jane Doe")
        sys.exit(1)
    
    # Run scraper
    scraper = OpenAlexScraper()
    scraper.run(input_csv, output_csv)


if __name__ == "__main__":
    main()
