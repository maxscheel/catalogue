"""
FastAPI V2 Clean - Dead code removed, cache warming kept
"""

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
from datetime import datetime

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
    title="Catalogue API V2 Clean",
    description="High-performance satellite catalogue API - clean version",
    version="2.0.0-clean",
    docs_url="/v2/docs",
    redoc_url="/v2/redoc"
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
    """Basic request logging"""
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

    # Initialize cache manager
    cache_manager = OptimizedCacheManager()
    logger.info("FastAPI V2 Clean API initialized with uvloop and optimized caching")

# =============================================================================
# CORE API ENDPOINTS - Essential functionality
# =============================================================================
@app.get("/v2/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache_active": cache_manager is not None,
        "event_loop": "uvloop" if isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy) else "default",
        "version": "clean"
    }

@app.get("/v2/catalog")
async def get_catalog_v2(
    lat: float = Query(..., description="Latitude in degrees"),
    lon: float = Query(..., description="Longitude in degrees"),
    elevation: float = Query(0.0, description="Cutoff elevation in degrees (ignore objects below this)"),
    alt: float = Query(0.0, description="Observer altitude in meters"),
    date: Optional[str] = Query(None, description="Date in ISO format")
):
    """FastAPI V2 catalog endpoint with async optimizations"""
    try:
        # Parse date
        if date:
            dt = parse_date_cached(date)
        else:
            dt = datetime.utcnow()

        # Convert lat/lon to angle objects like the Flask version
        lat_angle = angle.from_dms(lat)
        lon_angle = angle.from_dms(lon)

        # Get catalog data using optimized cache
        catalog_data = await cache_manager.get_bulk_catalog_async([dt], lat_angle, lon_angle, alt, elevation)

        if not catalog_data or not catalog_data[0]:
            raise HTTPException(status_code=404, detail="No catalog data found")

        return catalog_data[0]

    except Exception as e:
        logger.error(f"FastAPI V2 catalog error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/v2/position")
async def get_position_v2(
    lat: float = Query(..., description="Latitude in degrees"),
    lon: float = Query(..., description="Longitude in degrees"),
    elevation: float = Query(0.0, description="Cutoff elevation in degrees"),
    alt: float = Query(0.0, description="Observer altitude in meters"),
    object_name: str = Query(..., alias="object", description="Object name"),
    date: Optional[str] = Query(None, description="Date in ISO format")
):
    """FastAPI V2 position endpoint"""
    try:
        # Parse date
        if date:
            dt = parse_date_cached(date)
        else:
            dt = datetime.utcnow()

        # Convert lat/lon to angle objects like the Flask version
        lat_angle = angle.from_dms(lat)
        lon_angle = angle.from_dms(lon)

        # Get position data
        positions = cache_manager.get_cached_positions(lat_angle, lon_angle, alt, dt)

        # Find the requested object
        for pos in positions:
            if pos.get('name', '').lower() == object_name.lower():
                return pos

        raise HTTPException(status_code=404, detail=f"Object '{object_name}' not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"FastAPI V2 position error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/v2/bulk_az_el")
async def get_bulk_az_el_v2(request: BulkAzElRequest):
    """FastAPI V2 bulk azimuth/elevation endpoint with async processing"""
    try:
        # Convert lat/lon to angle objects like the Flask version
        lat_angle = angle.from_dms(request.lat)
        lon_angle = angle.from_dms(request.lon)

        # Parse dates
        dates = [parse_date_cached(ts) for ts in request.dates]

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
                await cache_manager.get_bulk_catalog_async([datetime.utcnow()], lat_angle, lon_angle, 0.0, 0.0)
                logger.info(f"Cache warmed for location: {lat}, {lon}")
            except Exception as e:
                logger.error(f"Cache warm-up failed for {lat}, {lon}: {e}")

@app.on_event("startup")
async def startup_cache_warming():
    """Start cache warming in background"""
    # Small delay to ensure cache manager is ready
    await asyncio.sleep(1)
    asyncio.create_task(warm_cache())
