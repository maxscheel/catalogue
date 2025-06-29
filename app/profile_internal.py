#!/usr/bin/env python3
# Internal API Profiling - Server-side performance measurement
# Quick profiling to identify bottlenecks in API functions

import cProfile
import pstats
import io
import time
from functools import wraps
import json

# Simple timing decorator
def time_it(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__}: {(end-start)*1000:.2f}ms")
        return result
    return wrapper

def profile_catalog_request():
    """Profile a single catalog request internally"""
    import restful_api
    from flask import Flask
    from tart.util import angle
    import tart.util.utc as utc
    
    print("=== Profiling Catalog Request ===")
    
    # Mock request data
    date = utc.now()
    lat = angle.from_dms(-45.85)
    lon = angle.from_dms(170.54)
    alt = 0.0
    elevation = 0.0
    
    pr = cProfile.Profile()
    pr.enable()
    
    # Profile the main function
    start_time = time.time()
    catalog = restful_api.get_catalog_list(date, lat, lon, alt, elevation)
    end_time = time.time()
    
    pr.disable()
    
    print(f"Total time: {(end_time - start_time)*1000:.2f}ms")
    print(f"Results count: {len(catalog)}")
    
    # Print top time consumers
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
    ps.print_stats(15)
    print("\nTop time consumers:")
    print(s.getvalue())

def profile_cache_operations():
    """Profile V2 cache operations"""
    try:
        from restful_api_v2 import cache_manager
        import tart.util.utc as utc
        from tart.util import angle
        
        print("\n=== Profiling V2 Cache Operations ===")
        
        date = utc.now()
        lat = angle.from_dms(-45.85)
        lon = angle.from_dms(170.54)
        alt = 0.0
        elevation = 0.0
        
        # First call (cache miss)
        start = time.time()
        result1 = cache_manager.get_cached_catalog_list(date, lat, lon, alt, elevation)
        miss_time = time.time() - start
        
        # Second call (cache hit)
        start = time.time()
        result2 = cache_manager.get_cached_catalog_list(date, lat, lon, alt, elevation)
        hit_time = time.time() - start
        
        print(f"Cache miss: {miss_time*1000:.2f}ms")
        print(f"Cache hit: {hit_time*1000:.2f}ms")
        print(f"Cache speedup: {miss_time/hit_time:.1f}x")
        
    except ImportError as e:
        print(f"V2 profiling failed: {e}")

def profile_bulk_processing():
    """Profile bulk request processing"""
    import restful_api
    from datetime import datetime, timedelta
    from tart.util import angle
    import tart.util.utc as utc
    
    print("\n=== Profiling Bulk Processing ===")
    
    # Create test data
    dates = [utc.now() + timedelta(seconds=i) for i in range(10)]
    lat = angle.from_dms(-45.85)
    lon = angle.from_dms(170.54)
    alt = 0.0
    elevation = 0.0
    
    pr = cProfile.Profile()
    pr.enable()
    
    start_time = time.time()
    
    # Sequential processing (V1 style)
    results = []
    for date in dates:
        catalog = restful_api.get_catalog_list(date, lat, lon, alt, elevation)
        results.append(catalog)
    
    end_time = time.time()
    pr.disable()
    
    print(f"Sequential bulk (V1): {(end_time - start_time)*1000:.2f}ms for {len(dates)} dates")
    print(f"Per request: {(end_time - start_time)*1000/len(dates):.2f}ms")
    
    # Show bottlenecks
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
    ps.print_stats(10)
    print("\nBulk processing bottlenecks:")
    print(s.getvalue())

def profile_individual_caches():
    """Profile individual satellite cache performance"""
    import norad_cache
    import tart.util.utc as utc
    from tart.util import angle
    
    print("\n=== Profiling Individual Caches ===")
    
    date = utc.now()
    lat = angle.from_dms(-45.85)
    lon = angle.from_dms(170.54)
    alt = 0.0
    elevation = 0.0
    
    caches = {
        'WAAS': norad_cache.NORADCache(),
        'GPS': norad_cache.GPSCache(),
        'Galileo': norad_cache.GalileoCache(),
        'Beidou': norad_cache.BeidouCache()
    }
    
    for name, cache in caches.items():
        try:
            start = time.time()
            result = cache.get_az_el(date, lat, lon, alt, elevation)
            end = time.time()
            print(f"{name:8}: {(end-start)*1000:6.2f}ms ({len(result)} satellites)")
        except Exception as e:
            print(f"{name:8}: ERROR - {e}")

def run_full_profile():
    """Run complete profiling suite"""
    print("🔍 INTERNAL API PROFILING")
    print("=" * 50)
    
    profile_individual_caches()
    profile_catalog_request()
    profile_cache_operations()
    profile_bulk_processing()
    
    print("\n" + "=" * 50)
    print("Profiling complete!")

if __name__ == '__main__':
    run_full_profile()