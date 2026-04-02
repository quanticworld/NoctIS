#!/usr/bin/env python3
"""
Pastebin LinkedIn Leak Monitor
Monitors recent Pastebin pastes for LinkedIn-related leaks
Outputs JSON lines with findings
"""
import requests
import json
import time
import re
from datetime import datetime
import sys

# Configuration
KEYWORDS = [
    'linkedin',
    'linkedin.com',
    'linkedin leak',
    'linkedin database',
    'linkedin dump',
    'linkedin breach',
    'linkedin combo',
    'linkedin credentials',
    'li.com',
    'email:pass',
    '@linkedin',
    'linkedIn data'
]

# Pastebin scraping API endpoint
SCRAPING_API_URL = 'https://scrape.pastebin.com/api_scraping.php'

# Rate limiting
REQUEST_DELAY = 2  # seconds between requests
CHECK_LIMIT = 100  # Number of recent pastes to check per run

# Stats
stats = {
    'pastes_checked': 0,
    'matches_found': 0,
    'errors': 0
}


def log(message, level='INFO'):
    """Print log message to stderr"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] [{level}] {message}", file=sys.stderr)


def get_recent_pastes():
    """Get recent public pastes from Pastebin scraping API"""
    try:
        params = {'limit': CHECK_LIMIT}
        response = requests.get(SCRAPING_API_URL, params=params, timeout=10)

        if response.status_code == 200:
            pastes = response.json()
            log(f"Retrieved {len(pastes)} recent pastes")
            return pastes
        else:
            log(f"Failed to get pastes: HTTP {response.status_code}", 'ERROR')
            return []

    except Exception as e:
        log(f"Error fetching pastes: {e}", 'ERROR')
        stats['errors'] += 1
        return []


def get_paste_content(paste_key):
    """Get full content of a paste"""
    try:
        url = f"https://scrape.pastebin.com/api_scrape_item.php?i={paste_key}"
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.text
        else:
            log(f"Failed to get paste content {paste_key}: HTTP {response.status_code}", 'WARNING')
            return None

    except Exception as e:
        log(f"Error fetching paste content {paste_key}: {e}", 'ERROR')
        stats['errors'] += 1
        return None


def analyze_content(content):
    """Analyze paste content for sensitive data patterns"""
    analysis = {
        'has_emails': False,
        'has_passwords': False,
        'has_linkedin_pattern': False,
        'email_count': 0,
        'credential_pairs': 0
    }

    if not content:
        return analysis

    # Email pattern
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, content)
    analysis['email_count'] = len(emails)
    analysis['has_emails'] = len(emails) > 0

    # LinkedIn email pattern
    linkedin_emails = [e for e in emails if 'linkedin.com' in e.lower()]
    analysis['has_linkedin_pattern'] = len(linkedin_emails) > 0

    # Credential pair patterns (email:password or email:hash)
    credential_pattern = r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}[:;|]\S+'
    credentials = re.findall(credential_pattern, content)
    analysis['credential_pairs'] = len(credentials)
    analysis['has_passwords'] = len(credentials) > 0

    return analysis


def check_paste(paste):
    """Check if paste contains LinkedIn-related keywords and analyze content"""
    paste_key = paste.get('key')
    title = paste.get('title', '').lower()
    syntax = paste.get('syntax', '').lower()

    stats['pastes_checked'] += 1

    # Quick title/metadata check first
    matched_keywords = []
    for keyword in KEYWORDS:
        if keyword.lower() in title:
            matched_keywords.append(keyword)

    # If no match in title, skip (avoid fetching content for every paste)
    if not matched_keywords:
        return None

    log(f"Potential match in paste {paste_key}: {title}")

    # Get full content for deeper analysis
    time.sleep(REQUEST_DELAY)  # Rate limiting
    content = get_paste_content(paste_key)

    if not content:
        return None

    # Analyze content
    analysis = analyze_content(content)

    # Only report if it has actual credential data
    if not (analysis['has_emails'] or analysis['has_passwords']):
        log(f"Paste {paste_key} has keywords but no credential data", 'WARNING')
        return None

    # Extract sample data (first 500 chars)
    preview = content[:500] if len(content) > 500 else content

    # Build finding
    finding = {
        'url': f'https://pastebin.com/{paste_key}',
        'paste_key': paste_key,
        'title': paste.get('title', 'Untitled'),
        'author': paste.get('user') or 'Anonymous',
        'date': paste.get('date'),
        'size': paste.get('size', 0),
        'syntax': syntax,
        'matched_keywords': matched_keywords,
        'analysis': analysis,
        'preview': preview,
        'scraper': 'pastebin_linkedin_monitor',
        'timestamp': int(time.time()),
        'severity': 'high' if analysis['credential_pairs'] > 10 else 'medium'
    }

    stats['matches_found'] += 1
    log(f"✓ MATCH FOUND: {paste_key} - {analysis['email_count']} emails, {analysis['credential_pairs']} credential pairs")

    return finding


def main():
    """Main execution"""
    log("Starting Pastebin LinkedIn Monitor")
    log(f"Monitoring keywords: {', '.join(KEYWORDS)}")

    # Get recent pastes
    pastes = get_recent_pastes()

    if not pastes:
        log("No pastes retrieved, exiting", 'WARNING')
        return

    # Check each paste
    for i, paste in enumerate(pastes):
        finding = check_paste(paste)

        if finding:
            # Output as JSON line (scraper executor will parse this)
            print(json.dumps(finding))
            sys.stdout.flush()  # Ensure immediate output

        # Progress logging every 10 pastes
        if (i + 1) % 10 == 0:
            log(f"Progress: {i + 1}/{len(pastes)} pastes checked")

    # Final stats
    log("=" * 60)
    log("SCAN COMPLETE")
    log(f"Pastes checked: {stats['pastes_checked']}")
    log(f"Matches found: {stats['matches_found']}")
    log(f"Errors: {stats['errors']}")
    log("=" * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        log("Interrupted by user", 'WARNING')
        sys.exit(0)
    except Exception as e:
        log(f"Fatal error: {e}", 'ERROR')
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
