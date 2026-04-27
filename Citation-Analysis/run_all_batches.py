#!/usr/bin/env python3
"""
Automated batch processor - runs batches sequentially and saves with correct batch numbers
Run specific batches or all batches automatically
"""

import pandas as pd
import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime

def run_batch_range(start_batch=None, end_batch=None):
    """Process batches in a specific range (or all if not specified)"""
    batch_folder = Path("batches")
    
    if not batch_folder.exists():
        print("✗ No 'batches' folder found!")
        sys.exit(1)
    
    # Get all batch files sorted
    all_batch_files = sorted(batch_folder.glob("batch_*.csv"))
    
    if not all_batch_files:
        print("✗ No batch files found in 'batches/' folder")
        sys.exit(1)
    
    # Determine which batches to process
    if start_batch is None or end_batch is None:
        # Process all batches
        batch_files_to_process = all_batch_files
        start_idx = 1
        end_idx = len(all_batch_files)
    else:
        # Process specific range
        start_idx = max(1, start_batch)
        end_idx = min(len(all_batch_files), end_batch)
        batch_files_to_process = all_batch_files[start_idx-1:end_idx]
    
    if not batch_files_to_process:
        print("✗ No batches in specified range")
        sys.exit(1)
    
    print("\n" + "="*70)
    print("AUTOMATED BATCH PROCESSOR - Sequential Processing")
    print("="*70)
    print(f"Total batches available: {len(all_batch_files)}")
    print(f"Processing batches: {start_idx} to {end_idx}")
    print(f"Batches to run: {len(batch_files_to_process)}")
    print("="*70 + "\n")
    
    all_output_files = []
    successful_batches = 0
    failed_batches = []
    total_rows = 0
    overall_start = datetime.now()
    
    for process_idx, batch_file in enumerate(batch_files_to_process, 1):
        # Extract batch number from filename
        batch_num = int(batch_file.stem.split('_')[1])
        output_file = f"output_batch_{batch_num:03d}.csv"
        
        print(f"\n{'='*70}")
        print(f"[{process_idx}/{len(batch_files_to_process)}] Processing Batch {batch_num:03d}")
        print(f"{'='*70}")
        print(f"Input:  {batch_file.name}")
        print(f"Output: {output_file}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 70)
        
        start_time = datetime.now()
        
        # Run the scraper
        try:
            result = subprocess.run(
                ["python", "openalex_scraper.py", str(batch_file), output_file],
                capture_output=False,
                timeout=None
            )
            
            if result.returncode == 0:
                elapsed = (datetime.now() - start_time).total_seconds()
                
                # Count records
                try:
                    df_output = pd.read_csv(output_file)
                    record_count = len(df_output)
                    total_rows += record_count
                    successful_batches += 1
                    all_output_files.append(output_file)
                    
                    print(f"\n✅ Batch {batch_num:03d} COMPLETE")
                    print(f"   Records generated: {record_count}")
                    print(f"   Time: {int(elapsed)} seconds ({elapsed/60:.1f} minutes)")
                    print(f"   Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception as e:
                    print(f"✗ Error reading output: {e}")
                    failed_batches.append((batch_num, str(e)))
            else:
                print(f"✗ Batch {batch_num:03d} FAILED (exit code: {result.returncode})")
                failed_batches.append((batch_num, f"Exit code: {result.returncode}"))
        
        except KeyboardInterrupt:
            print(f"\n⚠️  INTERRUPTED BY USER")
            print(f"✅ Completed: {successful_batches} batches")
            print(f"📊 Total rows: {total_rows:,}")
            break
        except Exception as e:
            print(f"✗ Error processing batch {batch_num}: {e}")
            failed_batches.append((batch_num, str(e)))
        
        # Small delay between batches
        if process_idx < len(batch_files_to_process):
            time.sleep(1)
    
    # Summary
    print("\n" + "="*70)
    print("PROCESSING COMPLETE - SUMMARY")
    print("="*70)
    overall_elapsed = (datetime.now() - overall_start).total_seconds()
    hours = int(overall_elapsed // 3600)
    minutes = int((overall_elapsed % 3600) // 60)
    seconds = int(overall_elapsed % 60)
    
    print(f"✅ Successful batches: {successful_batches}/{len(batch_files_to_process)}")
    print(f"❌ Failed batches: {len(failed_batches)}")
    print(f"📊 Total rows generated: {total_rows:,}")
    print(f"⏱️  Total time: {hours}h {minutes}m {seconds}s")
    print("="*70)
    
    if failed_batches:
        print("\n⚠️  Failed Batches:")
        for batch_num, reason in failed_batches:
            print(f"   Batch {batch_num:03d}: {reason}")
    
    # Output files kept separate - no combining
    if all_output_files:
        print("\n" + "="*70)
        print("OUTPUT FILES CREATED (KEPT SEPARATE)")
        print("="*70)
        print(f"Total output files: {len(all_output_files)}")
        for output_file in all_output_files:
            if os.path.exists(output_file):
                df = pd.read_csv(output_file)
                print(f"✓ {output_file}: {len(df):,} records")
        print("="*70 + "\n")
    
    print("\n✅ Batch processing finished!")
    print("="*70 + "\n")

def main():
    """Main entry point"""
    if len(sys.argv) > 2:
        # Command line arguments
        start_batch = int(sys.argv[1])
        end_batch = int(sys.argv[2])
        run_batch_range(start_batch, end_batch)
    else:
        # Interactive or run all
        print("\nOpenAlex Batch Runner - Automated Sequential Processing")
        print("-" * 70)
        print("\nUsage Options:")
        print("  python run_all_batches.py          (process ALL batches)")
        print("  python run_all_batches.py 1 10     (process batches 1-10)")
        print("  python run_all_batches.py 11 20    (process batches 11-20)")
        print("\nExample for friends:")
        print("  Friend 1: python run_all_batches.py 1 11    (batches 1-11)")
        print("  Friend 2: python run_all_batches.py 12 22   (batches 12-22)")
        print("  Friend 3: python run_all_batches.py 23 33   (batches 23-33)")
        print("  Friend 4: python run_all_batches.py 34 44   (batches 34-44)")
        print("  Friend 5: python run_all_batches.py 45 55   (batches 45-55)")
        print("  Friend 6: python run_all_batches.py 56 66   (batches 56-66)")
        print("\n" + "-" * 70)
        
        choice = input("\nProcess all batches? (y/n) [y]: ").lower().strip() or 'y'
        
        if choice == 'y':
            run_batch_range()
        else:
            start = int(input("Start batch (1-66): "))
            end = int(input("End batch (1-66): "))
            run_batch_range(start, end)

if __name__ == "__main__":
    main()
