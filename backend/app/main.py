"""FastAPI main application"""
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .models import StatsRequest, StatsResponse, ConfigResponse, RegexTemplate
from .services.stats import StatsService
from .services.clickhouse_service import clickhouse_service
from .websocket import websocket_endpoint
from .websocket_scrapers import websocket_scraper_logs
from .routers import files, search, import_router, mdm, scrapers, operations
from .services.scraper_scheduler import scraper_scheduler
from .services.background_import_service import background_import_service
from .services.import_executor import import_executor
import logging
import asyncio

logger = logging.getLogger(__name__)


async def _initialize_clickhouse_background():
    """Background task to initialize ClickHouse without blocking startup"""
    max_retries = 30  # 30 attempts (ClickHouse starts faster)
    retry_delay = 2   # 2 seconds between each
    clickhouse_ready = False

    # Update status
    clickhouse_service._initialization_status = "checking"
    clickhouse_service._initialization_message = "Checking ClickHouse connection..."

    for attempt in range(1, max_retries + 1):
        try:
            # Update progress during health checks
            clickhouse_service._initialization_progress = min(int((attempt / max_retries) * 10), 10)

            health = await clickhouse_service.health_check()
            if health.get('status') == 'healthy':
                logger.info(f"✅ ClickHouse is healthy (attempt {attempt}/{max_retries})")
                clickhouse_service._initialization_message = "ClickHouse is healthy"
                clickhouse_ready = True
                break
            else:
                logger.warning(f"⚠️  ClickHouse health check returned: {health}")
                clickhouse_service._initialization_message = f"Waiting for ClickHouse... (attempt {attempt}/{max_retries})"
                if attempt < max_retries:
                    await asyncio.sleep(retry_delay)
        except Exception as e:
            logger.info(f"⏳ ClickHouse not ready yet (attempt {attempt}/{max_retries}), retrying in {retry_delay}s...")
            logger.debug(f"   Error: {e}")
            clickhouse_service._initialization_message = f"Connecting to ClickHouse... ({attempt}/{max_retries})"

            if attempt >= max_retries:
                logger.error(f"❌ ClickHouse failed to start after {max_retries * retry_delay}s ({max_retries} attempts)")
                logger.error(f"   Last error: {e}")
                clickhouse_service._initialization_status = "error"
                clickhouse_service._initialization_message = f"ClickHouse connection failed: {str(e)}"
            else:
                await asyncio.sleep(retry_delay)

    if not clickhouse_ready:
        clickhouse_service._initialization_status = "error"
        clickhouse_service._initialization_message = "ClickHouse is not ready"
        logger.error("❌ ClickHouse is not ready - ClickHouse features will be unavailable")
    else:
        # Initialize tables
        logger.info("📦 Verifying ClickHouse tables...")
        try:
            results = await clickhouse_service.initialize_collections()
            logger.info(f"✅ Tables verified: {results}")

            # Get table statistics
            for table_name in ['silver_records', 'master_records', 'conflicts']:
                try:
                    stats = await clickhouse_service.get_collection_stats(table_name)
                    if stats:
                        num_docs = stats.get('num_documents', 0)
                        logger.info(f"   📊 {table_name}: {num_docs:,} documents")
                except Exception as e:
                    logger.debug(f"   Could not get stats for {table_name}: {e}")

            logger.info("=" * 60)
            logger.info("🎯 NoctIS ClickHouse is fully initialized!")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"❌ Failed to verify ClickHouse tables: {e}")
            clickhouse_service._initialization_status = "error"
            clickhouse_service._initialization_message = f"Failed to verify tables: {str(e)}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Starting NoctIS - OSINT Red Team Toolbox")
    logger.info("=" * 60)
    logger.info("⚡ Backend starting immediately - ClickHouse initialization in background")

    # Launch ClickHouse initialization in background
    asyncio.create_task(_initialize_clickhouse_background())

    # Start scraper scheduler
    logger.info("🕒 Starting scraper scheduler...")
    scraper_scheduler.start()

    # Resume interrupted import jobs
    logger.info("🔄 Checking for interrupted import jobs...")
    resumable_jobs = background_import_service.get_resumable_jobs()
    if resumable_jobs:
        logger.info(f"📦 Found {len(resumable_jobs)} interrupted job(s) to resume:")
        for job_id, job in resumable_jobs.items():
            logger.info(f"   - {job_id}: {job.breach_name} ({job.processed_lines:,} lines processed)")
            # Re-submit the job for execution with resume flag
            task = asyncio.create_task(import_executor.execute_job(job_id, resume=True))
            job.task = task
            logger.info(f"   ✅ Resumed job {job_id}")
    else:
        logger.info("   No interrupted jobs to resume")

    logger.info("=" * 60)
    logger.info("🎯 NoctIS backend is ready to serve requests!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("=" * 60)
    logger.info("👋 Shutting down NoctIS...")
    logger.info("=" * 60)

    # Stop scraper scheduler
    logger.info("🕒 Stopping scraper scheduler...")
    scraper_scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="OSINT Red Team Toolbox - Professional search interface with Meilisearch indexing",
    lifespan=lifespan
)

# Configure CORS - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when allow_origins is ["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(import_router.router, prefix=settings.api_prefix)
app.include_router(mdm.router, prefix=settings.api_prefix)
app.include_router(scrapers.router, prefix=settings.api_prefix)
app.include_router(operations.router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "online",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get(f"{settings.api_prefix}/config", response_model=ConfigResponse)
async def get_config():
    """Get current configuration"""
    templates = [
        {
            "id": RegexTemplate.NAME_SEARCH.value,
            "name": "Name Search",
            "description": "Search for first name and last name in any order",
            "pattern": "(FIRST.*LAST|LAST.*FIRST)",
            "fields": ["first_name", "last_name"],
        },
        {
            "id": RegexTemplate.EMAIL.value,
            "name": "Email Address",
            "description": "Match standard email addresses",
            "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "fields": [],
        },
        {
            "id": RegexTemplate.PHONE_FR.value,
            "name": "Phone Number (FR)",
            "description": "Match French phone numbers (0X XX XX XX XX)",
            "pattern": r"0[1-9][\s.-]?(?:\d{2}[\s.-]?){4}",
            "fields": [],
        },
        {
            "id": RegexTemplate.IP_ADDRESS.value,
            "name": "IP Address",
            "description": "Match IPv4 addresses",
            "pattern": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
            "fields": [],
        },
        {
            "id": RegexTemplate.CUSTOM.value,
            "name": "Custom Regex",
            "description": "Enter your own regex pattern",
            "pattern": "",
            "fields": ["pattern"],
        },
    ]

    return ConfigResponse(
        search_path=settings.default_search_path,
        threads=settings.default_threads,
        max_filesize=settings.default_max_filesize,
        available_templates=templates,
    )


@app.post(f"{settings.api_prefix}/stats", response_model=StatsResponse)
async def calculate_stats(request: StatsRequest):
    """Calculate statistics for a given path"""
    try:
        stats = await StatsService.calculate_stats(request.path)
        return stats
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate stats: {str(e)}")


@app.websocket("/ws/search")
async def websocket_search(websocket: WebSocket):
    """WebSocket endpoint for real-time search"""
    await websocket_endpoint(websocket)


@app.websocket("/ws/scrapers/{execution_id}")
async def websocket_scraper_execution(websocket: WebSocket, execution_id: str):
    """WebSocket endpoint for real-time scraper execution logs"""
    await websocket_scraper_logs(websocket, execution_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
