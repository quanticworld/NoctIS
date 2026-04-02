"""Scrapers API endpoints"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging

from app.models.scraper import (
    ScraperCreate, ScraperUpdate, ScraperResponse,
    ExecutionResponse, FindingResponse
)
from app.services.scraper_db import scraper_db
from app.services.scraper_executor import scraper_executor
from app.services.scraper_scheduler import scraper_scheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


# SCRAPERS CRUD
@router.post("", response_model=ScraperResponse)
async def create_scraper(scraper: ScraperCreate):
    """Create a new scraper"""
    try:
        scraper_id = scraper_db.create_scraper(
            name=scraper.name,
            description=scraper.description,
            code=scraper.code,
            language=scraper.language,
            cron_expression=scraper.cron_expression,
            enabled=scraper.enabled,
            keywords=scraper.keywords,
            auto_import=scraper.auto_import
        )

        # Schedule if enabled and has cron
        if scraper.enabled and scraper.cron_expression:
            scraper_scheduler.schedule_scraper(scraper_id, scraper.cron_expression)

        result = scraper_db.get_scraper(scraper_id)
        return result

    except Exception as e:
        logger.error(f"Failed to create scraper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ScraperResponse])
async def list_scrapers(enabled_only: bool = Query(False)):
    """List all scrapers"""
    try:
        scrapers = scraper_db.list_scrapers(enabled_only=enabled_only)
        return scrapers
    except Exception as e:
        logger.error(f"Failed to list scrapers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scraper_id}", response_model=ScraperResponse)
async def get_scraper(scraper_id: str):
    """Get scraper by ID"""
    scraper = scraper_db.get_scraper(scraper_id)
    if not scraper:
        raise HTTPException(status_code=404, detail="Scraper not found")
    return scraper


@router.put("/{scraper_id}", response_model=ScraperResponse)
async def update_scraper(scraper_id: str, updates: ScraperUpdate):
    """Update scraper"""
    # Check exists
    existing = scraper_db.get_scraper(scraper_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Scraper not found")

    # Prepare updates
    update_dict = {k: v for k, v in updates.dict(exclude_unset=True).items() if v is not None}

    if not update_dict:
        return existing

    # Update database
    success = scraper_db.update_scraper(scraper_id, **update_dict)
    if not success:
        raise HTTPException(status_code=500, detail="Update failed")

    # Handle scheduling changes
    updated = scraper_db.get_scraper(scraper_id)

    # Reschedule if cron or enabled changed
    if 'cron_expression' in update_dict or 'enabled' in update_dict:
        scraper_scheduler.unschedule_scraper(scraper_id)

        if updated['enabled'] and updated.get('cron_expression'):
            scraper_scheduler.schedule_scraper(scraper_id, updated['cron_expression'])

    return updated


@router.delete("/{scraper_id}")
async def delete_scraper(scraper_id: str):
    """Delete scraper"""
    # Unschedule first
    scraper_scheduler.unschedule_scraper(scraper_id)

    # Delete
    success = scraper_db.delete_scraper(scraper_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scraper not found")

    return {"message": "Scraper deleted"}


# EXECUTION
@router.post("/{scraper_id}/execute", response_model=dict)
async def execute_scraper(scraper_id: str):
    """Execute scraper manually"""
    try:
        execution_id = await scraper_executor.execute_scraper(scraper_id)
        return {
            "message": "Scraper execution started",
            "execution_id": execution_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to execute scraper: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scraper_id}/executions", response_model=List[ExecutionResponse])
async def list_executions(
    scraper_id: str,
    limit: int = Query(100, ge=1, le=1000)
):
    """List executions for a scraper"""
    executions = scraper_db.list_executions(scraper_id=scraper_id, limit=limit)
    return executions


@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: str):
    """Get execution details"""
    execution = scraper_db.get_execution(execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    return execution


# FINDINGS
@router.get("/{scraper_id}/findings", response_model=List[FindingResponse])
async def list_findings(
    scraper_id: str,
    execution_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000)
):
    """List findings for a scraper"""
    findings = scraper_db.list_findings(
        scraper_id=scraper_id,
        execution_id=execution_id,
        limit=limit
    )
    return findings


# TEMPLATES
@router.get("/templates/list", response_model=List[dict])
async def list_templates():
    """Get available scraper templates"""
    templates = [
        {
            "id": "pastebin_recent",
            "name": "Pastebin Recent Monitor",
            "description": "Monitor recent Pastebin pastes for keywords",
            "language": "python",
            "keywords": ["password", "leak", "database"]
        },
        {
            "id": "paste_ee",
            "name": "Paste.ee Monitor",
            "description": "Monitor paste.ee for recent pastes",
            "language": "python",
            "keywords": ["combo", "combolist"]
        },
        {
            "id": "ghostbin",
            "name": "Ghostbin Monitor",
            "description": "Monitor Ghostbin for recent pastes",
            "language": "python",
            "keywords": ["breach", "leaked"]
        }
    ]
    return templates


@router.get("/templates/{template_id}/code")
async def get_template_code(template_id: str):
    """Get template code"""
    templates = {
        "pastebin_recent": PASTEBIN_TEMPLATE,
        "paste_ee": PASTE_EE_TEMPLATE,
        "ghostbin": GHOSTBIN_TEMPLATE
    }

    code = templates.get(template_id)
    if not code:
        raise HTTPException(status_code=404, detail="Template not found")

    return {"code": code}


# TEMPLATES CODE
PASTEBIN_TEMPLATE = """#!/usr/bin/env python3
'''
Pastebin Recent Monitor
Scrapes recent public pastes and searches for keywords
Outputs JSON lines with findings
'''
import requests
import json
import time
from datetime import datetime

# Configuration
KEYWORDS = ['password', 'leak', 'database', 'combo']  # Customize this!
API_KEY = None  # Get free API key at pastebin.com/doc_api
CHECK_LIMIT = 100  # Number of recent pastes to check

def get_recent_pastes():
    '''Get recent public pastes'''
    url = 'https://scrape.pastebin.com/api_scraping.php'
    params = {'limit': CHECK_LIMIT}

    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching pastes: {e}", file=sys.stderr)

    return []

def check_paste(paste):
    '''Check if paste contains keywords'''
    key = paste.get('key')
    title = paste.get('title', '').lower()

    # Check title for keywords
    matched_keywords = []
    for keyword in KEYWORDS:
        if keyword.lower() in title:
            matched_keywords.append(keyword)

    if not matched_keywords:
        return None

    # Found keyword! Get full content
    try:
        content_url = f"https://scrape.pastebin.com/api_scrape_item.php?i={key}"
        resp = requests.get(content_url, timeout=10)
        content = resp.text if resp.status_code == 200 else ""
    except:
        content = ""

    # Output JSON finding
    return {
        'url': f'https://pastebin.com/{key}',
        'title': paste.get('title'),
        'author': paste.get('user'),
        'date': paste.get('date'),
        'matched_keywords': matched_keywords,
        'preview': content[:500] if content else title,
        'scraper': 'pastebin_recent'
    }

def main():
    pastes = get_recent_pastes()

    for paste in pastes:
        finding = check_paste(paste)
        if finding:
            # Output as JSON line (scraper executor will parse this)
            print(json.dumps(finding))

    print(f"Checked {len(pastes)} pastes", file=sys.stderr)

if __name__ == '__main__':
    import sys
    main()
"""

PASTE_EE_TEMPLATE = """#!/usr/bin/env python3
'''
Paste.ee Recent Monitor
'''
import requests
import json

KEYWORDS = ['combo', 'combolist', 'leak']

def main():
    # Paste.ee doesn't have public API for recent pastes
    # This is a placeholder - would need reverse engineering
    print("Paste.ee monitoring not implemented yet", file=sys.stderr)

if __name__ == '__main__':
    import sys
    main()
"""

GHOSTBIN_TEMPLATE = """#!/usr/bin/env python3
'''
Ghostbin Recent Monitor
'''
import requests
import json

KEYWORDS = ['breach', 'leaked', 'database']

def main():
    # Ghostbin monitoring placeholder
    print("Ghostbin monitoring not implemented yet", file=sys.stderr)

if __name__ == '__main__':
    import sys
    main()
"""
