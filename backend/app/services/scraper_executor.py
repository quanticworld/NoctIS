"""Scraper execution engine with sandboxing"""
import asyncio
import subprocess
import tempfile
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging
import json

from .scraper_db import scraper_db

logger = logging.getLogger(__name__)


class ScraperExecutor:
    """Execute scrapers in sandboxed environment"""

    def __init__(self):
        self.running_executions: Dict[str, asyncio.Task] = {}

    async def execute_scraper(self, scraper_id: str) -> str:
        """Execute a scraper"""
        scraper = scraper_db.get_scraper(scraper_id)
        if not scraper:
            raise ValueError(f"Scraper {scraper_id} not found")

        # Create execution record
        execution_id = scraper_db.create_execution(scraper_id)

        # Run async (don't block)
        task = asyncio.create_task(self._run_scraper(scraper, execution_id))
        self.running_executions[execution_id] = task

        # Update scraper last run
        scraper_db.update_scraper(
            scraper_id,
            last_run_at=int(datetime.now().timestamp()),
            last_run_status='running'
        )

        return execution_id

    async def _run_scraper(self, scraper: Dict[str, Any], execution_id: str):
        """Run scraper in subprocess"""
        started_at = datetime.now()
        stdout_lines = []
        stderr_lines = []
        findings_count = 0

        try:
            # Create temp file for scraper code
            suffix = '.py' if scraper['language'] == 'python' else '.sh'
            with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False) as f:
                temp_file = f.name
                f.write(scraper['code'])

            # Make executable if bash
            if scraper['language'] == 'bash':
                os.chmod(temp_file, 0o755)

            # Prepare command
            if scraper['language'] == 'python':
                cmd = ['python3', temp_file]
            else:
                cmd = ['bash', temp_file]

            # Execute with timeout (30 minutes max)
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tempfile.gettempdir()
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=1800  # 30 minutes
                )

                stdout_text = stdout.decode('utf-8', errors='ignore')
                stderr_text = stderr.decode('utf-8', errors='ignore')

                stdout_lines = stdout_text.split('\n')
                stderr_lines = stderr_text.split('\n')

                # Parse findings from stdout (expect JSON lines)
                findings = self._parse_findings(stdout_text, scraper)
                findings_count = len(findings)

                # Store findings
                for finding_data in findings:
                    matched_keywords = self._match_keywords(
                        finding_data,
                        scraper.get('keywords', [])
                    )
                    scraper_db.create_finding(
                        scraper['id'],
                        execution_id,
                        finding_data,
                        matched_keywords
                    )

                # Auto-import to Typesense if enabled
                if scraper.get('auto_import') and findings:
                    await self._import_to_typesense(findings, scraper)

                # Success
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()

                scraper_db.update_execution(
                    execution_id,
                    status='success',
                    finished_at=int(finished_at.timestamp()),
                    duration_seconds=duration,
                    stdout=stdout_text[:10000],  # Limit storage
                    stderr=stderr_text[:10000],
                    findings_count=findings_count
                )

                scraper_db.update_scraper(
                    scraper['id'],
                    last_run_status='success'
                )

            except asyncio.TimeoutError:
                process.kill()
                raise Exception("Scraper execution timeout (30 minutes)")

            finally:
                # Clean up temp file
                try:
                    os.unlink(temp_file)
                except:
                    pass

        except Exception as e:
            logger.error(f"Scraper execution failed: {e}")

            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()

            scraper_db.update_execution(
                execution_id,
                status='error',
                finished_at=int(finished_at.timestamp()),
                duration_seconds=duration,
                stdout='\n'.join(stdout_lines)[:10000],
                stderr='\n'.join(stderr_lines)[:10000],
                error_message=str(e),
                findings_count=findings_count
            )

            scraper_db.update_scraper(
                scraper['id'],
                last_run_status='error'
            )

        finally:
            # Remove from running executions
            if execution_id in self.running_executions:
                del self.running_executions[execution_id]

    def _parse_findings(self, stdout: str, scraper: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse findings from stdout
        Expects JSON lines or structured output

        Format:
        {"email": "test@example.com", "password": "123", "source": "pastebin"}
        {"email": "foo@bar.com", "password": "abc"}
        """
        findings = []

        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue

            # Try to parse as JSON
            try:
                data = json.loads(line)
                if isinstance(data, dict):
                    findings.append(data)
            except json.JSONDecodeError:
                # Not JSON, try to parse as email:password
                if ':' in line and '@' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        findings.append({
                            'email': parts[0].strip(),
                            'password': parts[1].strip(),
                            'scraper': scraper['name']
                        })

        return findings

    def _match_keywords(self, data: Dict[str, Any], keywords: List[str]) -> List[str]:
        """Match keywords in finding data"""
        if not keywords:
            return []

        data_str = json.dumps(data).lower()
        matched = []

        for keyword in keywords:
            if keyword.lower() in data_str:
                matched.append(keyword)

        return matched

    async def _import_to_typesense(self, findings: List[Dict[str, Any]], scraper: Dict[str, Any]):
        """Auto-import findings to Typesense"""
        try:
            # Import to silver_records
            from .mdm_service import mdm_service

            documents = []
            for finding in findings:
                doc = {
                    'email': finding.get('email'),
                    'password': finding.get('password'),
                    'breach_name': f"Scraper_{scraper['name']}",
                    'source_file': f"scraper_{scraper['id']}"
                }
                # Remove None values
                doc = {k: v for k, v in doc.items() if v is not None}
                if doc:
                    documents.append(doc)

            if documents:
                result = await mdm_service.import_to_silver(
                    documents,
                    breach_name=f"Scraper_{scraper['name']}",
                    source_file=f"scraper_{scraper['id']}"
                )
                logger.info(f"Auto-imported {result.get('imported', 0)} findings to Typesense")

        except Exception as e:
            logger.error(f"Failed to auto-import to Typesense: {e}")

    def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get execution status"""
        return scraper_db.get_execution(execution_id)

    def is_running(self, execution_id: str) -> bool:
        """Check if execution is running"""
        return execution_id in self.running_executions


# Singleton
scraper_executor = ScraperExecutor()
