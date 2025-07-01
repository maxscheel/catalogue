# Object Position Server V2 API - Optimized Version
#
# Author Tim Molteno tim@elec.ac.nz (c) 2013-2023
# Author Max Scheel max@elec.ac.nz (c) 2025 - Performance Optimisations

import asyncio
from functools import lru_cache
import time
from datetime import timedelta
import threading
import numpy as np


import tart.util.utc as utc
from tart.imaging import location

import norad_cache
from dateutil import parser
import sun_object

# ==============================
# OPTIMIZED CACHE MANAGEMENT
# ==============================

class OptimizedCacheManager:
    """Singleton cache manager with thread-safe operations and connection pooling"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._cache_lock = threading.RLock()
        self._position_cache = {}
        self._azimuth_elevation_cache = {}
        self._cache_ttl = 900  # 15 minutes TTL
        self._max_cache_size = 100000

        # Initialize caches with pre-loading
        self._init_caches()

        # Start background cache refresh
        self._start_cache_refresh_thread()

    def _init_caches(self):
        """Initialize satellite caches"""
        # Initialize caches - using same instances as V1 for consistency
        self.waas_cache = norad_cache.NORADCache()
        self.gps_cache = norad_cache.GPSCache()
        self.galileo_cache = norad_cache.GalileoCache()
        self.beidou_cache = norad_cache.BeidouCache()
        self.sun = sun_object.SunObject()

        # Pre-warm caches with current data
        current_time = utc.now()
        self._preload_cache_data(current_time)

    def _preload_cache_data(self, date):
        """Pre-load cache data for last 1 minutes and next minute at second intervals"""
        try:
            start_time = (date - timedelta(minutes=1)).replace(microsecond=0)
            end_time = (date + timedelta(minutes=1)).replace(microsecond=0)

            # Check if current time is already in cache range - skip preload if so
            cache_key = date.replace(microsecond=0).isoformat()
            with self._cache_lock:
                if cache_key in self._position_cache:
                    data, timestamp = self._position_cache[cache_key]
                    if time.time() - timestamp < self._cache_ttl:
                        print(f"Cache already contains current time {date}, skipping preload")
                        return

            # Count cache state before preload
            initial_cache_size = len(self._position_cache)
            new_entries = 0

            # Pre-calculate positions for every second in the range
            current_time = start_time
            while current_time <= end_time:
                cache_key = current_time.isoformat()

                # Only calculate if not already cached
                with self._cache_lock:
                    is_cached = cache_key in self._position_cache
                    if is_cached:
                        data, timestamp = self._position_cache[cache_key]
                        is_fresh = time.time() - timestamp < self._cache_ttl
                    else:
                        is_fresh = False

                if not is_cached or not is_fresh:
                    # Only do expensive calculations for uncached/stale entries
                    self.waas_cache.get_positions(current_time)
                    self.gps_cache.get_positions(current_time)
                    self.galileo_cache.get_positions(current_time)
                    self.beidou_cache.get_positions(current_time)
                    new_entries += 1

                current_time += timedelta(seconds=1)

            final_cache_size = len(self._position_cache)

            # Get actual cache sizes from satellite caches
            waas_size = len(getattr(self.waas_cache, 'cache', {}))
            gps_size = len(getattr(self.gps_cache, 'cache', {}))
            galileo_size = len(getattr(self.galileo_cache, 'cache', {}))
            beidou_size = len(getattr(self.beidou_cache, 'cache', {}))
            total_satellite_entries = waas_size + gps_size + galileo_size + beidou_size

            print(f"Cache preloaded for 16-minute window: {start_time} to {end_time} - {new_entries} new entries calculated")
            print(f"Satellite cache sizes: WAAS={waas_size}, GPS={gps_size}, Galileo={galileo_size}, Beidou={beidou_size}, Total={total_satellite_entries}")
        except Exception as e:
            print(f"Cache preload warning: {e}")

    def _start_cache_refresh_thread(self):
        """Start background thread to refresh cache data"""
        def refresh_worker():
            while True:
                try:
                    time.sleep(30)  # Refresh every minute
                    start = time.time()
                    current_time = utc.now()
                    self._cleanup_expired_cache()
                    self._preload_cache_data(current_time)
                    duration = time.time() - start
                    print(f"Cache refreshed in {duration:.2f} seconds")
                except Exception as e:
                    print(f"Cache refresh error: {e}")

        refresh_thread = threading.Thread(target=refresh_worker, daemon=True)
        refresh_thread.start()

    def _cleanup_expired_cache(self):
        """Clean up expired cache entries"""
        current_time = time.time()

        # Clean position cache
        with self._cache_lock:
            expired_keys = [
                key for key, (data, timestamp) in self._position_cache.items()
                if current_time - timestamp > self._cache_ttl
            ]
            for key in expired_keys:
                del self._position_cache[key]

        # Clean azimuth/elevation cache
        with self._cache_lock:
            expired_keys_az_el = [
                key for key, (data, timestamp) in self._azimuth_elevation_cache.items()
                if current_time - timestamp > self._cache_ttl
            ]
            for key in expired_keys_az_el:
                del self._azimuth_elevation_cache[key]

            # Also enforce max cache size
            evicted_keys = []
            if len(self._position_cache) > self._max_cache_size:
                # Remove oldest entries
                sorted_items = sorted(self._position_cache.items(), key=lambda x: x[1][1])
                for key, _ in sorted_items[:len(self._position_cache) - self._max_cache_size]:
                    del self._position_cache[key]
                    evicted_keys.append(key)

        if expired_keys or expired_keys_az_el or evicted_keys:
            print(f"Cache cleanup: {len(expired_keys)} expired position entries, {len(expired_keys_az_el)} expired az/el entries, {len(evicted_keys)} evicted entries")

    def get_cached_positions(self, date):
        """Get positions with caching"""
        # Round to second for cache key
        rounded_date = date.replace(microsecond=0)
        cache_key = rounded_date.isoformat()

        with self._cache_lock:
            if cache_key in self._position_cache:
                data, timestamp = self._position_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    print(f"Cache hit! for positions on {rounded_date}, for {date}")

                    return data

        # Log cache miss
        print(f"Cache miss for positions on {rounded_date}, for {date}")


        # Calculate positions
        positions = []
        positions += self.waas_cache.get_positions(date)
        positions += self.gps_cache.get_positions(date)
        positions += self.galileo_cache.get_positions(date)
        positions += self.beidou_cache.get_positions(date)

        # Cache the result
        with self._cache_lock:
            self._position_cache[cache_key] = (positions, time.time())

        return positions

    def get_cached_catalog_list(self, date, lat, lon, alt, elevation):
        """Get catalog list with caching and optimization"""
        # Round to second for cache key
        date = date.replace(microsecond=0)
        cache_key = f"{date.isoformat()}_{lat}_{lon}_{alt}_{elevation}"

        with self._cache_lock:
            if cache_key in self._azimuth_elevation_cache:
                data, timestamp = self._azimuth_elevation_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    return data

        catalog = []

        gps_eph = self.gps_cache.get_object(date)
        waas_eph = self.waas_cache.get_object(date)
        beidou_eph = self.beidou_cache.get_object(date)
        galileo_eph = self.galileo_cache.get_object(date)

        # catalog += get_az_el_optimized(gps_eph.satellites, date, lat, lon, alt, elevation, gps_eph.jansky)
        # catalog += get_az_el_optimized(waas_eph.satellites, date, lat, lon, alt, elevation, waas_eph.jansky)
        # catalog += get_az_el_optimized(beidou_eph.satellites, date, lat, lon, alt, elevation, beidou_eph.jansky)
        # catalog += get_az_el_optimized(galileo_eph.satellites, date, lat, lon, alt, elevation, galileo_eph.jansky)

        comp = galileo_eph.satellites+ waas_eph.satellites + beidou_eph.satellites + galileo_eph.satellites
        catalog += get_az_el_optimized(comp, date, lat, lon, alt, elevation, gps_eph.jansky)

        catalog += self.sun.get_az_el(date, lat, lon, alt, elevation)

        # Cache the result
        with self._cache_lock:
            self._azimuth_elevation_cache[cache_key] = (catalog, time.time())

        return catalog

    async def get_bulk_catalog_async(self, dates, lat, lon, alt, elevation):
        """Get bulk catalog data using async processing"""
        loop = asyncio.get_event_loop()

        # Create tasks for parallel processing
        tasks = []
        for date in dates:
            task = loop.run_in_executor(
                None,
                self.get_cached_catalog_list,
                date, lat, lon, alt, elevation
            )
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks)
        return results

    def get_cache_stats(self):
        """Get cache statistics"""
        with self._cache_lock:
            # Get stats from individual satellite caches
            waas_cache_size = len(getattr(self.waas_cache, 'cache', {}))
            gps_cache_size = len(getattr(self.gps_cache, 'cache', {}))
            galileo_cache_size = len(getattr(self.galileo_cache, 'cache', {}))
            beidou_cache_size = len(getattr(self.beidou_cache, 'cache', {}))

            return {
                "position_cache_size": len(self._position_cache),
                "azimuth_elevation_cache_size": len(self._azimuth_elevation_cache),
                "waas_cache_size": waas_cache_size,
                "gps_cache_size": gps_cache_size,
                "galileo_cache_size": galileo_cache_size,
                "beidou_cache_size": beidou_cache_size,
                "total_satellite_cache_entries": waas_cache_size + gps_cache_size + galileo_cache_size + beidou_cache_size,
                "cache_ttl": self._cache_ttl,
                "max_cache_size": self._max_cache_size
            }

    def clear_all_caches(self):
        """Clear all caches"""
        with self._cache_lock:
            self._position_cache.clear()
            self._azimuth_elevation_cache.clear()


# Global cache manager instance
cache_manager = OptimizedCacheManager()

# ==============================
# OPTIMIZED UTILITY FUNCTIONS
# ==============================

@lru_cache(maxsize=1000)
def parse_date_cached(date_string):
    """Cached date parsing for better performance - rounds to second"""
    try:
        if date_string == "now":
            return utc.now().replace(microsecond=0)
        else:
            dt = parser.parse(date_string.replace(' ', '+'))
            return utc.to_utc(dt).replace(microsecond=0)
    except Exception as err:
        raise Exception("Invalid Date '{}' {}".format(date_string, err))

def parse_request_date_optimized(request):
    """Optimized date parsing with validation"""
    if 'date' in request.args:
        date_string = request.args.get('date')
        d = parse_date_cached(date_string)
    else:
        d = utc.now()

    current_date = utc.now()
    if ((d - current_date).total_seconds() > 86400.0):
        raise Exception(f"Date > 24 hours in future. {current_date} {d}")
    return d

def get_required_parameter_optimized(request, param_name):
    """Optimized parameter extraction"""
    value = request.args.get(param_name)
    if value is None:
        raise Exception(f"Missing Required Parameter '{param_name}'")
    return value

def process_bulk_dates_vectorized(dates_param, lat, lon, alt, elevation):
    """Process bulk dates using vectorized operations where possible"""
    # Parse all dates at once
    dates = [parse_date_cached(ts) for ts in dates_param]

    # Use async processing for I/O bound operations
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        results = loop.run_until_complete(
            cache_manager.get_bulk_catalog_async(dates, lat, lon, alt, elevation)
        )
        return dates, results
    finally:
        loop.close()

def ecef_to_horizontal_vectorized(loc, positions_array):
    """
    Fully vectorized ECEF to horizontal coordinate transformation.
    Processes all satellite positions at once instead of individual calls.
    """
    if len(positions_array) == 0:
        return np.array([]), np.array([]), np.array([])

    # Extract coordinates
    x_coords = positions_array[:, 0]
    y_coords = positions_array[:, 1]
    z_coords = positions_array[:, 2]

    # Get location ECEF coordinates using correct method
    loc_ecef = loc.get_ecef()
    loc_x, loc_y, loc_z = loc_ecef[0], loc_ecef[1], loc_ecef[2]

    # Convert to relative coordinates
    dx = x_coords - loc_x
    dy = y_coords - loc_y
    dz = z_coords - loc_z

    # Get location parameters using correct methods
    lat_rad = np.radians(loc.latitude_deg())
    lon_rad = np.radians(loc.longitude_deg())

    # Precompute trigonometric values
    sin_lat = np.sin(lat_rad)
    cos_lat = np.cos(lat_rad)
    sin_lon = np.sin(lon_rad)
    cos_lon = np.cos(lon_rad)

    # Transform to local tangent plane (East-North-Up) - vectorized
    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    # Calculate range, elevation, azimuth - vectorized
    range_m = np.sqrt(dx*dx + dy*dy + dz*dz)
    elevation_rad = np.arcsin(np.clip(up / range_m, -1, 1))  # Clip to avoid numerical errors
    azimuth_rad = np.arctan2(east, north)

    # Convert to degrees
    elevation_deg = np.degrees(elevation_rad)
    azimuth_deg = np.degrees(azimuth_rad)

    # Ensure azimuth is 0-360
    azimuth_deg = np.where(azimuth_deg < 0, azimuth_deg + 360, azimuth_deg)

    return range_m, elevation_deg, azimuth_deg

def get_az_el_optimized(satellites, date, lat, lon, alt, elevation, jansky):
    """
    Optimized get_az_el using fully vectorized coordinate transformations.
    Eliminates the 137 individual ecef_to_horizontal calls.
    """
    if not satellites:
        return []

    # Create location object once
    loc = location.Location(lat, lon, alt)

    # Get all satellite positions in one pass
    positions = []
    names = []

    for sv in satellites:
        try:
            pos, velocity = sv.get_position(date)
            positions.append(pos)
            names.append(sv.name)
        except Exception:
            continue

    if not positions:
        return []

    # Convert to numpy array for vectorized processing
    positions_array = np.array(positions)

    # VECTORIZED coordinate transformation - key optimization!
    ranges, elevations, azimuths = ecef_to_horizontal_vectorized(loc, positions_array)

    # Vectorized rounding and filtering
    elevations_rounded = np.round(elevations, decimals=6)
    azimuths_rounded = np.round(azimuths, decimals=6)
    ranges_rounded = np.round(ranges, decimals=1)

    # Build results using vectorized filtering
    results = []
    for i, (name, r, el, az) in enumerate(zip(names, ranges_rounded, elevations_rounded, azimuths_rounded)):
        if el >= elevation:
            results.append({
                'name': name,
                'r': r,
                'el': el,
                'az': az,
                'jy': jansky
            })

    return results
