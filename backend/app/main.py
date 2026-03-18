"""FastAPI main application"""
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .config import settings
from .models import StatsRequest, StatsResponse, ConfigResponse, RegexTemplate
from .services.stats import StatsService
from .services.typesense_service import typesense_service
from .websocket import websocket_endpoint
from .routers import files, search, import_router, mdm
import logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Initializing Typesense collections...")
    try:
        results = await typesense_service.initialize_collections()
        logger.info(f"Typesense collections initialized: {results}")
    except Exception as e:
        logger.error(f"Failed to initialize Typesense: {e}")

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="OSINT Red Team Toolbox - Professional search interface with Typesense indexing",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(files.router, prefix=settings.api_prefix)
app.include_router(search.router, prefix=settings.api_prefix)
app.include_router(import_router.router, prefix=settings.api_prefix)
app.include_router(mdm.router, prefix=settings.api_prefix)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
