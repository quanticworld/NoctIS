#!/usr/bin/env python3
"""
Aggregate all breach files from /mnt/osint/CompilationOfManyBreaches
Handles ':' separator intelligently (email can't contain ':', but passwords can)
Outputs to /home/quantic/NoctIS/breaches/ready/
"""
import os
import re
from pathlib import Path
from datetime import datetime
import hashlib

# Configuration
SOURCE_DIR = Path('/mnt/osint/CompilationOfManyBreaches')
OUTPUT_DIR = Path('/home/quantic/NoctIS/breaches/ready')
OUTPUT_FILE = OUTPUT_DIR / f'aggregated_all_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

# Statistics
stats = {
    'files_processed': 0,
    'total_lines': 0,
    'valid_lines': 0,
    'skipped_lines': 0,
    'duplicates': 0,
    'errors': 0
}

# Email regex for validation
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Track duplicates (using hash to save memory)
seen_hashes = set()

def parse_line(line):
    """
    Parse a line with ':' separator
    Format: email:password or email:hash or email:username:password

    Strategy: email is always first part (can't contain ':')
             everything after first ':' is considered password/data
    """
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    # Split only on first ':'
    parts = line.split(':', 1)

    if len(parts) < 2:
        return None  # No separator found

    email = parts[0].strip()
    data = parts[1].strip()  # Can contain ':' (e.g., hash:salt or time:12:00:00)

    # Validate email
    if not EMAIL_REGEX.match(email):
        return None

    # Rebuild normalized line
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
            except UnicodeDecodeError:
                continue

        stats['files_processed'] += 1

        valid_lines = []
        for line in lines:
            stats['total_lines'] += 1

            parsed = parse_line(line)
            if parsed:
                # Check for duplicates using hash (memory efficient)
                line_hash = hashlib.md5(parsed.encode()).hexdigest()
                if line_hash in seen_hashes:
                    stats['duplicates'] += 1
                    continue

                seen_hashes.add(line_hash)
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
    """Find all text files recursively"""
    extensions = ['.txt', '.csv', '.sql', '.dump', '']
    files = []

    for ext in extensions:
        files.extend(directory.rglob(f'*{ext}'))

    # Filter only regular files
    return [f for f in files if f.is_file()]

def main():
    """Main aggregation function"""
    print(f"🔍 Scanning {SOURCE_DIR} for breach files...")

    if not SOURCE_DIR.exists():
        print(f"❌ Source directory not found: {SOURCE_DIR}")
        return

    # Find all files
    files = find_files(SOURCE_DIR)
    print(f"📁 Found {len(files)} files to process\n")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Open output file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{len(files)}] ", end='')

            valid_lines = process_file(file_path)

            # Write to output
            for line in valid_lines:
                out_f.write(line + '\n')

            # Progress
            if stats['files_processed'] % 10 == 0:
                print(f"\n📊 Progress: {stats['valid_lines']:,} valid lines so far\n")

    # Final statistics
    file_size_mb = OUTPUT_FILE.stat().st_size / (1024 * 1024)

    print("\n" + "="*60)
    print("✅ AGGREGATION COMPLETE!")
    print("="*60)
    print(f"Output file: {OUTPUT_FILE}")
    print(f"File size:   {file_size_mb:,.1f} MB")
    print(f"\nStatistics:")
    print(f"  Files processed:  {stats['files_processed']:,}")
    print(f"  Total lines read: {stats['total_lines']:,}")
    print(f"  Valid lines:      {stats['valid_lines']:,}")
    print(f"  Skipped (invalid):{stats['skipped_lines']:,}")
    print(f"  Duplicates:       {stats['duplicates']:,}")
    print(f"  Errors:           {stats['errors']:,}")
    print(f"\nImport command:")
    print(f"  Use NoctIS to import: {OUTPUT_FILE}")
    print(f"  Delimiter: ':'")
    print(f"  Mapping: col_0=email, col_1=password (or hash)")
    print("="*60)

if __name__ == '__main__':
    main()
