"""Scheduler for running scrapers on cron schedules"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import logging
from typing import Dict

from .scraper_db import scraper_db
from .scraper_executor import scraper_executor

logger = logging.getLogger(__name__)


class ScraperScheduler:
    """Manage cron-based scraper execution"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.job_ids: Dict[str, str] = {}  # scraper_id -> job_id

    def start(self):
        """Start the scheduler"""
        logger.info("Starting scraper scheduler...")
        self.scheduler.start()
        self.reload_schedules()
        logger.info("Scraper scheduler started")

    def stop(self):
        """Stop the scheduler"""
        logger.info("Stopping scraper scheduler...")
        self.scheduler.shutdown()
        logger.info("Scraper scheduler stopped")

    def reload_schedules(self):
        """Reload all enabled scrapers with cron"""
        logger.info("Reloading scraper schedules...")

        # Clear existing jobs
        for job_id in list(self.job_ids.values()):
            try:
                self.scheduler.remove_job(job_id)
            except:
                pass
        self.job_ids.clear()

        # Load enabled scrapers with cron
        scrapers = scraper_db.list_scrapers(enabled_only=True)

        for scraper in scrapers:
            if scraper.get('cron_expression'):
                self.schedule_scraper(scraper['id'], scraper['cron_expression'])

        logger.info(f"Loaded {len(self.job_ids)} scheduled scrapers")

    def schedule_scraper(self, scraper_id: str, cron_expression: str):
        """Schedule a scraper with cron expression"""
        try:
            # Parse cron expression (minute hour day month day_of_week)
            parts = cron_expression.split()
            if len(parts) != 5:
                logger.error(f"Invalid cron expression for scraper {scraper_id}: {cron_expression}")
                return

            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4]
            )

            job = self.scheduler.add_job(
                self._execute_scraper,
                trigger=trigger,
                args=[scraper_id],
                id=f"scraper_{scraper_id}",
                name=f"Scraper {scraper_id}",
                replace_existing=True
            )

            self.job_ids[scraper_id] = job.id

            # Update next run time
            next_run = job.next_run_time
            if next_run:
                scraper_db.update_scraper(
                    scraper_id,
                    next_run_at=int(next_run.timestamp())
                )

            logger.info(f"Scheduled scraper {scraper_id} with cron '{cron_expression}'")

        except Exception as e:
            logger.error(f"Failed to schedule scraper {scraper_id}: {e}")

    def unschedule_scraper(self, scraper_id: str):
        """Remove scraper from schedule"""
        job_id = self.job_ids.get(scraper_id)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                del self.job_ids[scraper_id]
                logger.info(f"Unscheduled scraper {scraper_id}")
            except Exception as e:
                logger.error(f"Failed to unschedule scraper {scraper_id}: {e}")

        # Clear next run time
        scraper_db.update_scraper(scraper_id, next_run_at=None)

    async def _execute_scraper(self, scraper_id: str):
        """Execute scraper (called by scheduler)"""
        logger.info(f"Scheduler executing scraper {scraper_id}")
        try:
            execution_id = await scraper_executor.execute_scraper(scraper_id)
            logger.info(f"Scraper {scraper_id} execution started: {execution_id}")
        except Exception as e:
            logger.error(f"Failed to execute scraper {scraper_id}: {e}")


# Singleton
scraper_scheduler = ScraperScheduler()
