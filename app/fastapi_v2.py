# =============================================================================
# CORE IMPORTS - Required for basic functionality
# =============================================================================
import asyncio
import uvloop
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import time
import logging
from datetime import datetime, UTC

# =============================================================================
# PROJECT IMPORTS - Core dependencies
# =============================================================================
from tart.util import angle
from optimized_cache_manager import OptimizedCacheManager, parse_date_cached

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# PYDANTIC MODELS - Core API models only
# =============================================================================
class BulkAzElRequest(BaseModel):
    """Request model for bulk azimuth/elevation calculations"""
    lat: float
    lon: float
    elevation: Optional[float] = 0.0  # Cutoff elevation in degrees
    alt: Optional[float] = 0.0  # Observer altitude in meters
    dates: List[str]

# =============================================================================
# GLOBAL STATE - Core application state
# =============================================================================
cache_manager = None

# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================
app = FastAPI(
    title="Catalogue API V2",
    description="Satellite catalogue API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - Required for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# CORE MIDDLEWARE - Basic request logging
# =============================================================================
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(f'{request.client.host} "{request.method} {request.url.path}" {response.status_code} - {process_time:.1f}ms')
    return response

# =============================================================================
# STARTUP EVENTS - Core initialization
# =============================================================================
@app.on_event("startup")
async def startup_event():
    """Initialize the optimized cache manager on startup"""
    global cache_manager

    # Set uvloop as the event loop policy
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    cache_manager = OptimizedCacheManager()

# =============================================================================
# CORE API ENDPOINTS - Essential functionality
# =============================================================================
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "cache_active": cache_manager is not None,
        "event_loop": "uvloop" if isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy) else "default",
        "version": "clean"
    }

@app.get("/catalog")
async def get_catalog(
    lat: float = Query(..., description="Latitude in degrees"),
    lon: float = Query(..., description="Longitude in degrees"),
    date: Optional[str] = Query(None, description="Date in ISO format [Second] precision"),
    alt: float = Query(0.0, description="Observer altitude in meters"),
    elevation: float = Query(0.0, description="Cutoff elevation in degrees (ignore objects below this)"),
):
    dt = handleDate(date)

    # Convert lat/lon to angle objects like the Flask version
    lat_angle = angle.from_dms(lat)
    lon_angle = angle.from_dms(lon)

    # Get catalog data using optimized cache
    catalog_data = await cache_manager.get_bulk_catalog_async([dt], lat_angle, lon_angle, alt, elevation)

    if not catalog_data or not catalog_data[0]:
        raise HTTPException(status_code=404, detail="No catalog data found")

    return catalog_data[0]


def handleDate(date: str|None) -> datetime:
    if date:
        dt = parse_date_cached(date)
    else:
        dt = datetime.now(UTC)
    return dt.replace(microsecond=0)

@app.get("/position/")
async def get_position(
    date: Optional[str] = Query(None, description="Date in ISO format")
):
    dt = handleDate(date)
    positions = cache_manager.get_cached_positions(dt)
    return positions

@app.post("/bulk_az_el")
async def get_bulk_az_el(request: BulkAzElRequest):
    """FastAPI V2 bulk azimuth/elevation endpoint with async processing"""
    try:
        # Convert lat/lon to angle objects like the Flask version
        lat_angle = angle.from_dms(request.lat)
        lon_angle = angle.from_dms(request.lon)

        # Parse dates
        dates = [handleDate(ts) for ts in request.dates]

        # Get bulk catalog data asynchronously
        catalog_data = await cache_manager.get_bulk_catalog_async(
            dates, lat_angle, lon_angle, request.alt, request.elevation
        )

        # Return V1-compatible format
        result = {
            'lat': request.lat,
            'lon': request.lon,
            'alt': request.alt,
            'dates': request.dates,
            'az_el': catalog_data
        }

        return result

    except Exception as e:
        logger.error(f"FastAPI V2 bulk az/el error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# CACHE WARMING - Background task for performance
# =============================================================================
async def warm_cache():
    """Background task to warm up caches"""
    if cache_manager:
        logger.info("Starting cache warm-up...")
        # Warm up with common locations
        test_locations = [
            (-45.85, 170.54),  # Christchurch
            (40.7128, -74.0060),  # New York
            (51.5074, -0.1278),   # London
        ]

        for lat, lon in test_locations:
            try:
                lat_angle = angle.from_dms(lat)
                lon_angle = angle.from_dms(lon)
                await cache_manager.get_bulk_catalog_async([datetime.now(UTC)], lat_angle, lon_angle, 0.0, 0.0)
                logger.info(f"Cache warmed for location: {lat}, {lon}")
            except Exception as e:
                logger.error(f"Cache warm-up failed for {lat}, {lon}: {e}")

@app.on_event("startup")
async def startup_cache_warming():
    """Start cache warming in background"""
    # Small delay to ensure cache manager is ready
    await asyncio.sleep(1)
    asyncio.create_task(warm_cache())
