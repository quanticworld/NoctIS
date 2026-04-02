#!/usr/bin/env python3
"""
Simple aggregation - just concat all files without dedup
Fast and memory efficient
"""
import re
from pathlib import Path
from datetime import datetime

SOURCE_DIR = Path('/mnt/osint/CompilationOfManyBreaches')
OUTPUT_DIR = Path('/home/quantic/NoctIS/breaches/ready')
OUTPUT_FILE = OUTPUT_DIR / f'aggregated_simple_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

stats = {'files': 0, 'lines': 0, 'valid': 0, 'skipped': 0}

def parse_line(line):
    """Validate and normalize line"""
    line = line.strip()
    if not line or line.startswith('#'):
        return None

    parts = line.split(':', 1)
    if len(parts) < 2:
        return None

    email = parts[0].strip()
    if not EMAIL_REGEX.match(email):
        return None

    return f"{email}:{parts[1].strip()}"

def find_files():
    """Find all files"""
    exts = ['.txt', '.csv', '.sql', '.dump', '']
    files = []
    for ext in exts:
        files.extend(SOURCE_DIR.rglob(f'*{ext}'))
    return [f for f in files if f.is_file()]

def main():
    print(f"🔍 Scanning {SOURCE_DIR}...")
    files = find_files()
    print(f"📁 {len(files)} files found\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, 'w', encoding='utf-8', buffering=1024*1024*100) as out:  # 100MB buffer
        for i, fp in enumerate(files, 1):
            print(f"[{i}/{len(files)}] {fp.name[:60]}")

            try:
                for enc in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(fp, 'r', encoding=enc, errors='ignore') as f:
                            for line in f:
                                stats['lines'] += 1
                                parsed = parse_line(line)
                                if parsed:
                                    out.write(parsed + '\n')
                                    stats['valid'] += 1
                                else:
                                    stats['skipped'] += 1
                        stats['files'] += 1
                        break
                    except:
                        continue
            except Exception as e:
                print(f"  ❌ {e}")

            if i % 100 == 0:
                print(f"\n📊 {stats['valid']:,} lines written\n")

    size_gb = OUTPUT_FILE.stat().st_size / (1024**3)

    print("\n" + "="*60)
    print("✅ DONE!")
    print("="*60)
    print(f"File:  {OUTPUT_FILE}")
    print(f"Size:  {size_gb:.2f} GB")
    print(f"Lines: {stats['valid']:,}")
    print(f"\nStats:")
    print(f"  Files:   {stats['files']:,}")
    print(f"  Read:    {stats['lines']:,}")
    print(f"  Written: {stats['valid']:,}")
    print(f"  Skipped: {stats['skipped']:,}")
    print("="*60)

if __name__ == '__main__':
    main()
