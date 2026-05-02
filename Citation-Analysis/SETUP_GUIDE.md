# OpenAlex Batch Processing - Friend Setup Guide

## Overview
You will run **citation analysis on assigned author batches** automatically. Each batch contains ~1,000 authors. The process is fully automated - just run one command!

---

## What You Will Receive

Your instructor will provide you with a folder containing:

1. **openalex_scraper.py** - The main scraper script
2. **run_all_batches.py** - Automation script to run batches
3. **batches/ folder** - Your assigned batch files (e.g., batch_022.csv, batch_023.csv, etc.)
4. **requirements.txt** - Python dependencies

Example folder structure:
```
your_work_folder/
├── openalex_scraper.py
├── run_all_batches.py
├── requirements.txt
└── batches/
    ├── batch_022_1000authors.csv
    ├── batch_023_1000authors.csv
    ├── batch_024_1000authors.csv
    ... (your assigned batches)
```

---

## Setup Instructions

### Step 1: Install Python
Make sure you have **Python 3.7 or higher** installed.

Check if Python is installed:
```bash
python --version
```

If not installed, download from: https://www.python.org/downloads/

### Step 2: Install Required Libraries

Navigate to your work folder in terminal/command prompt:

```bash
cd path_to_your_work_folder
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

This installs:
- `pandas` - For CSV processing
- `requests` - For API calls

---

## Running Your Batches

### What Are Your Assigned Batches?

Your instructor will tell you which batch numbers to process. For example:
- **Friend 1**: Batches 1-11
- **Friend 2**: Batches 12-22
- **Friend 3**: Batches 23-33
- etc.

### Run the Command

Open terminal/command prompt in your work folder and run:

```bash
python run_all_batches.py START_BATCH END_BATCH
```

**Replace START_BATCH and END_BATCH with your assigned numbers**

#### Example 1: If assigned batches 1-11
```bash
python run_all_batches.py 1 11
```

#### Example 2: If assigned batches 12-22
```bash
python run_all_batches.py 12 22
```

#### Example 3: If assigned batches 23-33
```bash
python run_all_batches.py 23 33
```

---

## What Happens During Processing

When you run the command, you will see:

```
======================================================================
AUTOMATED BATCH PROCESSOR - Sequential Processing
======================================================================
Total batches available: 12
Processing batches: 1 to 11
Batches to run: 11
======================================================================

======================================================================
[1/11] Processing Batch 001
======================================================================
Input:  batch_001_1000authors.csv
Output: output_batch_001.csv
Started: 2026-04-25 10:30:45
------================================================================

  Searching: John Smith
    [FOUND] John Smith (145 works)
    Fetching publications...
    ✓ Found 100 publication(s)
    Searching for citing papers...
    ✓ Found 95 citing paper(s)

[Batch 1 processes all 1,000 authors and generates output...]

✅ Batch 001 COMPLETE
   Records generated: 95,000
   Time: 3600 seconds (60 minutes)
   Ended: 2026-04-25 11:30:45

```

The script will automatically:
- Process each batch sequentially (one after another)
- Show progress for each author
- Save results immediately as it processes
- Display completion time and total records

---

## Output Files

After running `python run_all_batches.py 1 11`, you will have:

```
output_batch_001.csv  ← Results from Batch 1 (1,000 authors)
output_batch_002.csv  ← Results from Batch 2 (1,000 authors)
output_batch_003.csv  ← Results from Batch 3 (1,000 authors)
...
output_batch_011.csv  ← Results from Batch 11 (1,000 authors)
```

Each file contains citation data for ~1,000 authors with columns:
- Author name
- Publication info
- Citing paper info
- Author overlap analysis

---

## How Long Will It Take?

**Approximate timing:**
- Each batch (1,000 authors): **3-6 hours** depending on network speed
- 11 batches: **33-66 hours** (about 2-3 days continuous)

**Tips to speed up:**
- Use a fast, stable internet connection
- Keep your device awake (disable sleep mode)
- Close other bandwidth-heavy programs

---

## If Connection Drops

**Don't worry!** The script is designed to handle network interruptions:

- It will detect connection loss
- Display: `⚠️ CONNECTION LOST - Waiting for connection...`
- Automatically resume when connection returns
- All data processed so far is **saved**

You can also manually restart:
```bash
python run_all_batches.py 1 11
```

The script will continue from where it stopped (it checks which batches are already done).

---

## Troubleshooting

### Error: "batch_XXX_*.csv not found"
Make sure you have the correct batch files in the `batches/` folder.

### Error: "ModuleNotFoundError: No module named 'pandas'"
Install dependencies:
```bash
pip install -r requirements.txt
```

### Script stops mid-processing
Check your internet connection. The script will attempt to resume automatically.

### Python not recognized
You may need to use `python3` instead:
```bash
python3 run_all_batches.py 1 11
```

---

## Sending Results Back

Once processing is complete:

1. **Collect all output files** (output_batch_001.csv through output_batch_011.csv)
2. **Compress them** into a ZIP file or folder
3. **Upload to shared location** (Google Drive, OneDrive, FTP, etc.)
4. **Notify instructor** that results are ready

Example: If your name is Ahmad and assigned batches 1-11:
```
Ahmad_Batches_1-11.zip
├── output_batch_001.csv
├── output_batch_002.csv
...
└── output_batch_011.csv
```

---

## Important Notes

✅ **You need:** Python 3.x, stable internet, ~50GB storage (if running all batches)

✅ **Automatic features:**
- Saves each row immediately (no data loss if interrupted)
- Retries failed API calls automatically
- Shows real-time progress
- Handles network disconnections

⚠️ **Do NOT:** 
- Manually edit the batch files
- Close the terminal while processing
- Run multiple instances simultaneously

---

## Quick Checklist

- [ ] Python 3.x installed
- [ ] Files received (openalex_scraper.py, run_all_batches.py, batches/)
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Know your assigned batch numbers (e.g., 1-11)
- [ ] Stable internet connection active
- [ ] Sufficient disk space (~50GB)
- [ ] Run: `python run_all_batches.py START END`
- [ ] Wait for completion
- [ ] Send results to instructor

---

## Questions?

If you have issues or questions, contact your instructor.

Good luck! 🚀

