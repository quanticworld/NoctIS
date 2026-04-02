#!/usr/bin/env python3
"""
Optimized aggregation with Bloom Filter for memory efficiency
Can handle billions of lines without RAM issues
"""
import os
import re
from pathlib import Path
from datetime import datetime
from pybloom_live import BloomFilter

# Configuration
SOURCE_DIR = Path('/mnt/osint/CompilationOfManyBreaches')
OUTPUT_DIR = Path('/home/quantic/NoctIS/breaches/ready')
OUTPUT_FILE = OUTPUT_DIR / f'aggregated_optimized_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

# Bloom Filter config (for ~1 billion items, 0.1% false positive rate)
EXPECTED_ITEMS = 1_000_000_000  # 1 billion
FALSE_POSITIVE_RATE = 0.001  # 0.1%

# Statistics
stats = {
    'files_processed': 0,
    'total_lines': 0,
    'valid_lines': 0,
    'skipped_lines': 0,
    'duplicates': 0,
    'errors': 0
}

# Email regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Bloom filter for duplicate detection (memory efficient!)
print(f"🔧 Initializing Bloom Filter for {EXPECTED_ITEMS:,} items...")
bloom = BloomFilter(capacity=EXPECTED_ITEMS, error_rate=FALSE_POSITIVE_RATE)
print(f"   Bloom Filter size: ~{bloom.num_bits / 8 / 1024 / 1024:.0f} MB in RAM")
print()

def parse_line(line):
    """Parse email:password line"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    parts = line.split(':', 1)
    if len(parts) < 2:
        return None

    email = parts[0].strip()
    data = parts[1].strip()

    if not EMAIL_REGEX.match(email):
        return None

    return f"{email}:{data}"

def process_file(file_path):
    """Process a single file"""
    global stats

    print(f"Processing: {file_path.relative_to(SOURCE_DIR)}")

    try:
        # Try multiple encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    lines = f.readlines()
                break
            except:
                continue

        stats['files_processed'] += 1
        valid_lines = []

        for line in lines:
            stats['total_lines'] += 1

            parsed = parse_line(line)
            if parsed:
                # Check Bloom filter (fast!)
                if parsed in bloom:
                    stats['duplicates'] += 1
                    continue

                # Add to Bloom filter
                bloom.add(parsed)
                valid_lines.append(parsed)
                stats['valid_lines'] += 1
            else:
                stats['skipped_lines'] += 1

        return valid_lines

    except Exception as e:
        print(f"  ❌ Error: {e}")
        stats['errors'] += 1
        return []

def find_files(directory):
    """Find all files recursively"""
    extensions = ['.txt', '.csv', '.sql', '.dump', '']
    files = []

    for ext in extensions:
        files.extend(directory.rglob(f'*{ext}'))

    return [f for f in files if f.is_file()]

def main():
    """Main aggregation"""
    print(f"🔍 Scanning {SOURCE_DIR}...")

    if not SOURCE_DIR.exists():
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return

    files = find_files(SOURCE_DIR)
    print(f"📁 Found {len(files)} files to process\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Process files
    with open(OUTPUT_FILE, 'w', encoding='utf-8', buffering=1024*1024*10) as out_f:  # 10MB buffer
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] ", end='')

            valid_lines = process_file(file_path)

            # Write to output
            for line in valid_lines:
                out_f.write(line + '\n')

            # Progress every 100 files
            if stats['files_processed'] % 100 == 0:
                print(f"\n📊 Progress: {stats['valid_lines']:,} valid lines, {stats['duplicates']:,} duplicates skipped\n")

    # Final stats
    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)

    print("\n" + "="*60)
    print("✅ AGGREGATION COMPLETE!")
    print("="*60)
    print(f"Output: {OUTPUT_FILE}")
    print(f"Size:   {file_size_mb:,.1f} MB")
    print(f"\nStatistics:")
    print(f"  Files processed:  {stats['files_processed']:,}")
    print(f"  Total lines:      {stats['total_lines']:,}")
    print(f"  Valid lines:      {stats['valid_lines']:,}")
    print(f"  Duplicates:       {stats['duplicates']:,}")
    print(f"  Skipped:          {stats['skipped_lines']:,}")
    print(f"  Errors:           {stats['errors']:,}")
    print(f"\nDeduplication rate: {(stats['duplicates'] / stats['total_lines'] * 100):.1f}%")
    print("="*60)

if __name__ == '__main__':
    main()
