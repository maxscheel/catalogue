# =============================================================================
# CORE IMPORTS - Required for basic functionality
# =============================================================================
import asyncio
import uvloop
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, RootModel
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
    lat: float = Field(..., description="Observer latitude in degrees", example=-45.85, ge=-90, le=90)
    lon: float = Field(..., description="Observer longitude in degrees", example=170.54, ge=-180, le=180)
    elevation: Optional[float] = Field(0.0, description="Minimum elevation cutoff in degrees (satellites below this are filtered out)", example=10.0, ge=0, le=90)
    alt: Optional[float] = Field(0.0, description="Observer altitude above sea level in meters", example=100.0, ge=0)
    dates: List[str] = Field(..., description="List of ISO format datetime strings", example=["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"])

    class Config:
        schema_extra = {
            "example": {
                "lat": -45.85,
                "lon": 170.54,
                "elevation": 10.0,
                "alt": 100.0,
                "dates": ["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z", "2024-01-15T12:02:00Z"]
            }
        }


class SatelliteInfo(BaseModel):
    """Individual satellite information"""
    name: str = Field(..., description="Satellite name or identifier", example="GPS BIIR-2")
    az: float = Field(..., description="Azimuth angle in degrees (0=North, 90=East)", example=125.5, ge=0, lt=360)
    el: float = Field(..., description="Elevation angle in degrees above horizon", example=45.2, ge=0, le=90)
    r: float = Field(..., description="Range/distance to satellite in meters", example=20234567.8)
    jy: Optional[float] = Field(None, description="Flux density in Jansky for radio astronomy", example=1e-4)

    class Config:
        schema_extra = {
            "example": {
                "name": "GPS BIIR-2",
                "az": 125.5,
                "el": 45.2,
                "r": 20234567.8,
                "jy": 1e-4
            }
        }


# Type alias for catalog response - just a list of satellites

class BulkAzElResponse(BaseModel):
    """Response model for bulk azimuth/elevation calculations"""
    lat: float = Field(..., description="Observer latitude used", example=-45.85)
    lon: float = Field(..., description="Observer longitude used", example=170.54)
    alt: float = Field(..., description="Observer altitude used", example=100.0)
    dates: List[str] = Field(..., description="Input timestamps", example=["2024-01-15T12:00:00Z"])
    az_el: List[SatelliteInfo] = Field(..., description="Catalog data for each timestamp - array of satellite arrays")

    class Config:
        schema_extra = {
            "example": {
                "lat": -45.85,
                "lon": 170.54,
                "alt": 100.0,
                "dates": ["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"],
                "az_el": [
                    [
                        {
                            "name": "GPS BIIR-2",
                            "az": 125.5,
                            "el": 45.2,
                            "r": 20234567.8,
                            "jy": 1e-4
                        }
                    ],
                    [
                        {
                            "name": "GPS BIIR-3",
                            "az": 130.0,
                            "el": 50.0,
                            "r": 20100000.0,
                            "jy": 1e-4
                        }
                    ]
                ]
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service health status", example="healthy")
    timestamp: str = Field(..., description="Current server timestamp", example="2024-01-15T12:00:00Z")
    cache_active: bool = Field(..., description="Whether cache manager is active", example=True)
    event_loop: str = Field(..., description="Active event loop type", example="uvloop")
    version: str = Field(..., description="Service version", example="clean")

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T12:00:00.123456Z",
                "cache_active": True,
                "event_loop": "uvloop",
                "version": "clean"
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str = Field(..., description="Error description", example="No catalog data found")

# =============================================================================
# GLOBAL STATE - Core application state
# =============================================================================
cache_manager = None

# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================
app = FastAPI(
    title="Satellite Catalogue API V2",
    description="""
    ## High-performance satellite catalogue API for GNSS and space object tracking

    This API provides real-time satellite position data for GPS, GLONASS, Galileo, and BeiDou constellations.

    ### Features:
    - **Real-time satellite positions** with azimuth/elevation calculations
    - **Bulk processing** for multiple timestamps
    - **Optimized caching** for high-performance queries
    - **Async processing** with uvloop for maximum throughput
    - **Flexible filtering** by elevation cutoff and location

    ### Use Cases:
    - GNSS receiver simulation and testing
    - Radio telescope pointing calculations
    - Satellite visibility analysis
    - Space situational awareness

    ### Performance:
    - Cached position calculations for sub-millisecond response times
    - Async bulk processing for large datasets
    - Optimized for radio astronomy and GNSS applications
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={
        "name": "TART Team",
        "url": "https://tart.elec.ac.nz",
        "email": "tim@elec.ac.nz",
    },
    license_info={
        "name": "GPL v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.html",
    },
    tags_metadata=[
        {
            "name": "catalog",
            "description": "Satellite catalog and position data",
        },
        {
            "name": "bulk",
            "description": "Bulk processing endpoints for multiple timestamps",
        },
        {
            "name": "cache",
            "description": "Cache management and position data",
        },
    ]
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
@app.get(
    "/health",
    response_model=HealthResponse,
    include_in_schema=False
)
async def health_check():
    """Health check endpoint for monitoring service status"""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "cache_active": cache_manager is not None,
        "event_loop": "uvloop" if isinstance(asyncio.get_event_loop_policy(), uvloop.EventLoopPolicy) else "default",
        "version": "clean"
    }

@app.get(
    "/catalog",
    response_model=List[SatelliteInfo],
    tags=["catalog"],
    summary="Get Satellite Catalog",
    description="""
    Get real-time satellite catalog data for a specific location and time.

    This endpoint calculates the azimuth, elevation, and range for all visible satellites
    from the specified observer location. Satellites below the elevation cutoff are filtered out.

    ### Parameters:
    - **lat**: Observer latitude in decimal degrees (-90 to 90)
    - **lon**: Observer longitude in decimal degrees (-180 to 180)
    - **date**: Optional timestamp (defaults to current time)
    - **alt**: Observer altitude above sea level in meters
    - **elevation**: Minimum elevation cutoff in degrees (0-90)

    ### Returns:
    Complete satellite visibility data including position vectors and metadata.

    ### Example Usage:
    ```
    GET /catalog?lat=-45.85&lon=170.54&elevation=10.0&alt=100.0
    ```
    """,
    operation_id="get_satellite_catalog",
    responses={
        200: {
            "description": "Successful catalog retrieval",
            "content": {
                "application/json": {
                    "examples": {
                        "christchurch_location": {
                            "summary": "Christchurch, New Zealand example",
                            "value": [
                                {
                                    "name": "GPS BIIR-2",
                                    "az": 125.5,
                                    "el": 45.2,
                                    "r": 20234567.8,
                                    "jy": 1e-4
                                },
                                {
                                    "name": "GALILEO-22",
                                    "az": 280.1,
                                    "el": 35.7,
                                    "r": 23456789.1,
                                    "jy": 1e-4
                                },
                                {
                                    "name": "Sun",
                                    "az": 180.0,
                                    "el": 30.0,
                                    "r": 149597870700.0,
                                    "jy": 1000000.0
                                }
                            ]
                        },
                        "high_elevation_filter": {
                            "summary": "High elevation filter example",
                            "value": [
                                {
                                    "name": "BEIDOU-3 M14",
                                    "az": 91.5,
                                    "el": 75.8,
                                    "r": 21677345.2,
                                    "jy": 1e-4
                                },
                                {
                                    "name": "Sun",
                                    "az": 180.0,
                                    "el": 45.0,
                                    "r": 149597870700.0,
                                    "jy": 1000000.0
                                }
                            ]
                        }
                    }
                }
            }
        },
        404: {
            "description": "No catalog data found",
            "model": ErrorResponse
        },
        422: {
            "description": "Invalid input parameters",
            "model": ErrorResponse
        }
    }
)
async def get_catalog(
    lat: float = Query(..., description="Observer latitude in decimal degrees", example=-45.85, ge=-90, le=90),
    lon: float = Query(..., description="Observer longitude in decimal degrees", example=170.54, ge=-180, le=180),
    date: Optional[str] = Query(None, description="ISO format timestamp (YYYY-MM-DDTHH:MM:SSZ). Defaults to current time.", example="2024-01-15T12:00:00Z"),
    alt: float = Query(0.0, description="Observer altitude above sea level in meters", example=100.0, ge=0),
    elevation: float = Query(0.0, description="Minimum elevation cutoff in degrees. Satellites below this angle are filtered out.", example=10.0, ge=0, le=90),
):
    dt = handleDate(date)

    # Convert lat/lon to angle objects like the Flask version
    lat_angle = angle.from_dms(lat)
    lon_angle = angle.from_dms(lon)

    # Get catalog data using optimized cache
    catalog_data = await cache_manager.get_bulk_catalog_async([dt], lat_angle, lon_angle, alt, elevation)

    if not catalog_data or not catalog_data[0]:
        raise HTTPException(status_code=404, detail="No catalog data found")

    return catalog_data


def handleDate(date: str|None) -> datetime:
    if date:
        dt = parse_date_cached(date)
    else:
        dt = datetime.now(UTC)
    return dt.replace(microsecond=0)

@app.get(
    "/position/",
    tags=["cache"],
    summary="Get Cached Satellite Positions",
    description="""
    Retrieve raw satellite position data from the cache for a specific timestamp.

    This endpoint returns the underlying cached position data used for catalog calculations.
    Useful for debugging and accessing raw satellite state vectors.

    ### Parameters:
    - **date**: Optional timestamp (defaults to current time)

    ### Returns:
    Raw cached position data for all tracked satellites.
    """,
    operation_id="get_cached_positions",
    responses={
        200: {
            "description": "Cached position data retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "name": "GPS BIIR-2",
                            "az": 125.5,
                            "el": 45.2,
                            "r": 20234567.8,
                            "jy": 1e-4
                        },
                        {
                            "name": "GALILEO-FM2",
                            "az": 210.3,
                            "el": 65.1,
                            "r": 23456789.0,
                            "jy": 1e-4
                        }
                    ]
                }
            }
        }
    }
)
async def get_position(
    date: Optional[str] = Query(None, description="ISO format timestamp (YYYY-MM-DDTHH:MM:SSZ). Defaults to current time.", example="2024-01-15T12:00:00Z")
):
    """Get cached satellite position data for debugging and analysis"""
    dt = handleDate(date)
    positions = cache_manager.get_cached_positions(dt)
    return positions

@app.post(
    "/bulk_az_el",
    response_model=BulkAzElResponse,
    tags=["bulk"],
    summary="Bulk Azimuth/Elevation Calculation",
    description="""
    Calculate satellite azimuth and elevation data for multiple timestamps in a single request.

    This endpoint is optimized for bulk processing and uses async caching for high performance.
    Ideal for simulation, analysis, and batch processing of satellite visibility data.

    ### Use Cases:
    - Time series analysis of satellite visibility
    - GNSS receiver simulation over time periods
    - Batch processing for research and analysis
    - Radio telescope pointing schedule generation

    ### Performance:
    - Async processing for optimal throughput
    - Intelligent caching reduces computation time
    - Supports hundreds of timestamps per request

    ### Request Body:
    JSON object with observer location, timestamps, and filtering parameters.
    """,
    operation_id="bulk_azimuth_elevation",
    responses={
        200: {
            "description": "Bulk calculation completed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "lat": -45.85,
                        "lon": 170.54,
                        "alt": 100.0,
                        "dates": ["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"],
                        "az_el": [
                            [
                                {
                                    "name": "GPS BIIR-2",
                                    "az": 125.5,
                                    "el": 45.2,
                                    "r": 20234567.8,
                                    "jy": 1e-4
                                }
                            ],
                            [
                                {
                                    "name": "GPS BIIR-3",
                                    "az": 130.0,
                                    "el": 50.0,
                                    "r": 20100000.0,
                                    "jy": 1e-4
                                }
                            ]
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error during processing",
            "model": ErrorResponse
        }
    }
)
async def get_bulk_az_el(request: BulkAzElRequest):
    """
    Process bulk azimuth/elevation calculations with async optimization.

    Efficiently calculates satellite positions for multiple timestamps using
    optimized caching and async processing for maximum performance.
    """
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
