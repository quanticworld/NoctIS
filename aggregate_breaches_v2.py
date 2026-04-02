#!/usr/bin/env python3
"""
Memory-optimized aggregation without external dependencies
Uses batched deduplication to avoid RAM overflow
"""
import os
import re
from pathlib import Path
from datetime import datetime
import tempfile
import subprocess

# Configuration
SOURCE_DIR = Path('/mnt/osint/CompilationOfManyBreaches')
OUTPUT_DIR = Path('/home/quantic/NoctIS/breaches/ready')
OUTPUT_FILE = OUTPUT_DIR / f'aggregated_v2_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

# Batching config
BATCH_SIZE = 50_000_000  # 50M lines per batch
DEDUP_MEMORY_LIMIT = 5_000_000  # Keep only 5M hashes in RAM at once

# Statistics
stats = {
    'files_processed': 0,
    'total_lines': 0,
    'valid_lines': 0,
    'duplicates_local': 0,
    'skipped_lines': 0,
    'errors': 0
}

# Email regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

def parse_line(line):
    """Parse email:password"""
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

def process_file_streaming(file_path, output_file, seen_recent):
    """Process file with streaming write and rolling dedup window"""
    global stats

    try:
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                    for line in f:
                        stats['total_lines'] += 1

                        parsed = parse_line(line)
                        if parsed:
                            # Check only recent hashes (rolling window)
                            line_hash = hash(parsed)

                            if line_hash in seen_recent:
                                stats['duplicates_local'] += 1
                                continue

                            # Add to rolling window
                            seen_recent.add(line_hash)

                            # Limit rolling window size (keep only last N)
                            if len(seen_recent) > DEDUP_MEMORY_LIMIT:
                                # Remove oldest 20%
                                to_remove = len(seen_recent) // 5
                                for _ in range(to_remove):
                                    seen_recent.pop()

                            # Write immediately
                            output_file.write(parsed + '\n')
                            stats['valid_lines'] += 1
                        else:
                            stats['skipped_lines'] += 1

                stats['files_processed'] += 1
                break

            except Exception as e:
                if encoding == 'cp1252':  # Last encoding
                    raise e
                continue

    except Exception as e:
        print(f"  ❌ Error: {e}")
        stats['errors'] += 1

def find_files(directory):
    """Find all files"""
    extensions = ['.txt', '.csv', '.sql', '.dump', '']
    files = []

    for ext in extensions:
        files.extend(directory.rglob(f'*{ext}'))

    return [f for f in files if f.is_file()]

def main():
    """Main aggregation with streaming"""
    print(f"🔍 Scanning {SOURCE_DIR}...")

    if not SOURCE_DIR.exists():
        print(f"❌ Not found: {SOURCE_DIR}")
        return

    files = find_files(SOURCE_DIR)
    print(f"📁 Found {len(files)} files")
    print(f"💾 Using rolling dedup window: {DEDUP_MEMORY_LIMIT:,} hashes (~400 MB RAM)\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Rolling hash window (set with limited size)
    seen_recent = set()

    # Stream processing
    with open(OUTPUT_FILE, 'w', encoding='utf-8', buffering=1024*1024*50) as out_f:  # 50MB buffer
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {file_path.name[:50]}")

            process_file_streaming(file_path, out_f, seen_recent)

            # Progress
            if i % 100 == 0:
                print(f"\n📊 {stats['valid_lines']:,} lines written, {stats['duplicates_local']:,} local dupes\n")

    # Final deduplication with sort -u (disk-based, unlimited size!)
    print("\n🔄 Final deduplication with sort -u (may take 10-15 min)...")
    temp_sorted = OUTPUT_FILE.with_suffix('.sorted.txt')

    try:
        # Use system sort -u (very efficient, disk-based)
        subprocess.run(
            ['sort', '-u', '-o', str(temp_sorted), str(OUTPUT_FILE)],
            check=True
        )

        # Replace original with sorted
        temp_sorted.replace(OUTPUT_FILE)
        print("✅ Final deduplication complete!")

    except Exception as e:
        print(f"⚠️  Sort failed: {e}")
        print("   Keeping file with local deduplication only")
        if temp_sorted.exists():
            temp_sorted.unlink()

    # Stats
    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)
    final_lines = int(subprocess.check_output(['wc', '-l', str(OUTPUT_FILE)]).split()[0])

    print("\n" + "="*60)
    print("✅ COMPLETE!")
    print("="*60)
    print(f"Output: {OUTPUT_FILE}")
    print(f"Size:   {file_size_mb:,.1f} MB")
    print(f"Lines:  {final_lines:,}")
    print(f"\nStats:")
    print(f"  Files:            {stats['files_processed']:,}")
    print(f"  Lines processed:  {stats['total_lines']:,}")
    print(f"  Valid written:    {stats['valid_lines']:,}")
    print(f"  Local dupes:      {stats['duplicates_local']:,}")
    print(f"  Final dupes:      {stats['valid_lines'] - final_lines:,}")
    print(f"  Skipped:          {stats['skipped_lines']:,}")
    print("="*60)

if __name__ == '__main__':
    main()
