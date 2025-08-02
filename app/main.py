# =============================================================================
# CORE IMPORTS - Required for basic functionality
# =============================================================================
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import List, Optional

from examples import BULK_AZ_EL_EXAMPLES, CATALOG_EXAMPLES, POSITIONS_EXAMPLES
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

# =============================================================================
# PROJECT IMPORTS - Core dependencies
# =============================================================================
from models import (
    BulkAzElRequest,
    BulkAzElResponse,
    CatalogResponse,
    ErrorResponse,
    PositionInfo,
    PositionsResponse,
    SatelliteInfo,
)
from utils import (
    get_cache_manager,
    handle_date,
    log_requests,
    startup_cache_warming,
    startup_event,
)


# =============================================================================
# LIFESPAN EVENT HANDLER
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup events
    await startup_event()
    await startup_cache_warming()
    yield
    # Shutdown events (if needed)
    pass

# =============================================================================
# FASTAPI APPLICATION SETUP
# =============================================================================
app = FastAPI(
    lifespan=lifespan,
    title="Satellite Catalogue API V2",
    description="""
    ## Satellite Catalogue API for GNSS and Space Object Tracking

    Get real-time satellite position data for GPS, GLONASS, Galileo, and BeiDou constellations.

    ### Features:
    - Real-time satellite positions with azimuth/elevation calculations
    - Bulk processing for multiple timestamps
    - Flexible filtering by elevation cutoff and location
    - Support for radio astronomy applications
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
    ],
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
# MIDDLEWARE
# =============================================================================
app.middleware("http")(log_requests)

# =============================================================================
# CORE API ENDPOINTS - Essential functionality
# =============================================================================


@app.get(
    "/catalog",
    response_model=list[SatelliteInfo],
    tags=["catalog"],
    summary="Get Satellite Catalog",
    description="""
    Get satellite positions visible from a specific location and time.

    Returns azimuth, elevation, and range for all visible satellites.
    Satellites below the elevation cutoff are filtered out.
    """,
    responses={
        200: {
            "description": "Successful catalog retrieval",
            "content": {
                "application/json": {
                    "examples": CATALOG_EXAMPLES,
                },
            },
        },
        404: {
            "description": "No catalog data found",
            "model": ErrorResponse,
        },
        422: {
            "description": "Invalid input parameters",
            "model": ErrorResponse,
        },
    },
)
async def get_catalog(
    lat: float = Query(
        ...,
        description="Observer latitude in decimal degrees",
        example=-45.85,
        ge=-90,
        le=90,
    ),
    lon: float = Query(
        ...,
        description="Observer longitude in decimal degrees",
        example=170.54,
        ge=-180,
        le=180,
    ),
    date: str | None = Query(
        None,
        description="ISO format timestamp (YYYY-MM-DDTHH:MM:SSZ). Defaults to current time.",
        example="2024-01-15T12:00:00Z",
    ),
    alt: float = Query(
        0.0,
        description="Observer altitude above sea level in meters",
        example=100.0,
        ge=0,
    ),
    elevation: float = Query(
        0.0,
        description="Minimum elevation cutoff in degrees. Satellites below this angle are filtered out.",
        example=10.0,
        ge=0,
        le=90,
    ),
) -> list[SatelliteInfo]:
    dt = handle_date(date)
    # Get catalog data using cache manager
    cache_manager = get_cache_manager()
    catalog_data = await cache_manager.get_bulk_catalog_async(
        [dt], lat, lon, alt, elevation
    )

    if not catalog_data or not catalog_data[0]:
        raise HTTPException(status_code=404, detail="No catalog data found")

    return catalog_data[0]


@app.get(
    "/position/",
    response_model=PositionsResponse,
    tags=["catalog"],
    summary="Get Satellite Positions",
    description="""
    Get raw satellite position data in ECEF coordinates for a specific timestamp.
    """,
    responses={
        200: {
            "description": "Cached position data retrieved successfully",
            "content": {
                "application/json": {
                    "examples": POSITIONS_EXAMPLES,
                },
            },
        },
    },
)
async def get_position(
    date: str | None = Query(
        None,
        description="ISO format timestamp (YYYY-MM-DDTHH:MM:SSZ). Defaults to current time.",
        example="2024-01-15T12:00:00Z",
    ),
) -> list[PositionInfo]:
    """Get satellite position data in ECEF coordinates"""
    dt = handle_date(date)
    cache_manager = get_cache_manager()
    return cache_manager.get_cached_positions(dt)


@app.post(
    "/bulk_az_el",
    response_model=BulkAzElResponse,
    tags=["bulk"],
    summary="Bulk Azimuth/Elevation Calculation",
    description="""
    Calculate satellite positions for multiple timestamps in a single request.

    Useful for time series analysis and batch processing.
    """,
    responses={
        200: {
            "description": "Bulk calculation completed successfully",
            "content": {
                "application/json": {
                    "examples": BULK_AZ_EL_EXAMPLES,
                },
            },
        },
        400: {
            "description": "Invalid request parameters",
            "model": ErrorResponse,
        },
        500: {
            "description": "Internal server error during processing",
            "model": ErrorResponse,
        },
    },
)
async def get_bulk_az_el(request: BulkAzElRequest) -> BulkAzElResponse:
    """Calculate satellite positions for multiple timestamps efficiently."""
    try:
        # Parse dates
        dates = [handle_date(ts) for ts in request.dates]

        # Get bulk catalog data asynchronously
        cache_manager = get_cache_manager()
        catalog_data = await cache_manager.get_bulk_catalog_async(
            dates,
            request.lat,
            request.lon,
            request.alt,
            request.elevation,
        )

        return {
            "lat": request.lat,
            "lon": request.lon,
            "alt": request.alt,
            "dates": request.dates,
            "az_el": catalog_data,
        }
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"FastAPI V2 bulk az/el error: {e!s}")
        raise HTTPException(status_code=500, detail=str(e))
