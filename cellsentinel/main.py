"""
CellSentinel - FastAPI Application Entrypoint.
Production-grade Lost Device Recovery & Cell-Tower Telemetry Engine.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from cellsentinel.config import settings
from cellsentinel.database import init_database, get_db_connection
from cellsentinel.routers import devices, telemetry, resolver, dashboard


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle startup and shutdown hooks."""
    # 1. Initialize SQLite schema
    init_database()

    # 2. Check if database has any devices, if not auto-seed demo
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM devices;")
        count = cursor.fetchone()[0]

    if count == 0:
        # Seed realistic demo lost device and trajectory
        await dashboard.seed_demo()

    yield


app = FastAPI(
    title="CellSentinel",
    description="Production-grade Lost Device Recovery & Cell-Tower Telemetry Engine",
    version=settings.APP_VERSION,
    lifespan=lifespan
)

# Enable CORS for cross-origin integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets
static_dir = settings.BASE_DIR / "cellsentinel" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include Routers
app.include_router(devices.router)
app.include_router(telemetry.router)
app.include_router(resolver.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["Health"])
def health_check():
    """System health check and telecom engine status."""
    return {
        "status": "HEALTHY",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "ONLINE",
        "engine": "OPERATIONAL"
    }


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard_page():
    """Serve the primary Live Incident & Map Dashboard."""
    template_path = settings.BASE_DIR / "cellsentinel" / "templates" / "index.html"
    if template_path.exists():
        return FileResponse(template_path)
    return HTMLResponse("<h2>CellSentinel Dashboard Template Initializing...</h2>")
