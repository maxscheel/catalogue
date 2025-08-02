"""
Utility functions for FastAPI V2 Satellite Catalogue API

This module contains middleware, startup/shutdown handlers, and other utility
functions to keep the main API file clean and focused.
"""

import asyncio
import uvloop
import time
import logging
from datetime import datetime, UTC
from fastapi import Request
from tart.util import angle
from optimized_cache_manager import OptimizedCacheManager

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =============================================================================
# GLOBAL STATE
# =============================================================================
cache_manager = None

# =============================================================================
# MIDDLEWARE FUNCTIONS
# =============================================================================

async def log_requests(request: Request, call_next):
    """Log HTTP requests with timing information"""
    start_time = time.time()
    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    logger.info(f'{request.client.host} "{request.method} {request.url.path}" {response.status_code} - {process_time:.1f}ms')
    return response

# =============================================================================
# STARTUP/SHUTDOWN HANDLERS
# =============================================================================

async def startup_event():
    """Initialize the application on startup"""
    global cache_manager

    # Set uvloop as the event loop policy for better performance
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    # Initialize cache manager
    cache_manager = OptimizedCacheManager()
    logger.info("Cache manager initialized")

async def startup_cache_warming():
    """Start cache warming in background after startup"""
    # Small delay to ensure cache manager is ready
    await asyncio.sleep(1)
    asyncio.create_task(warm_cache())
    logger.info("Cache warming started")

# =============================================================================
# CACHE WARMING
# =============================================================================

async def warm_cache():
    """Background task to warm up caches with common locations"""
    if cache_manager:
        logger.info("Starting cache warm-up...")

        # Common test locations for cache warming
        test_locations = [
            (-20.259, 57.759),  # Bel Air - Mauritius
        ]

        for lat, lon in test_locations:
            try:
                lat_angle = angle.from_rad(angle.deg_to_rad(lat))
                lon_angle = angle.from_rad(angle.deg_to_rad(lon))
                await cache_manager.get_bulk_catalog_async(
                    [datetime.now(UTC)], lat_angle, lon_angle, 0.0, 0.0
                )
                logger.info(f"Cache warmed for location: {lat}, {lon}")
            except Exception as e:
                logger.error(f"Cache warm-up failed for {lat}, {lon}: {e}")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_cache_manager():
    """Get the global cache manager instance"""
    return cache_manager

def handle_date(date_string: str | None) -> datetime:
    """Handle date parsing with fallback to current time"""
    from optimized_cache_manager import parse_date_cached

    if date_string:
        dt = parse_date_cached(date_string)
    else:
        dt = datetime.now(UTC)
    return dt.replace(microsecond=0)
