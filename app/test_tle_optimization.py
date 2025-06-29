#!/usr/bin/env python3
# Simple TLE Optimization Test
# Test TLE caching integration with existing norad_cache code

import time
import threading
from functools import lru_cache
from sgp4.earth_gravity import wgs84
from sgp4.io import twoline2rv

# Simple TLE cache using LRU
@lru_cache(maxsize=1000)
def cached_twoline2rv(line1, line2):
    """Cached version of twoline2rv"""
    return twoline2rv(line1, line2, wgs84)

# Monkey patch the original function
original_twoline2rv = twoline2rv

def patch_tle_parsing():
    """Replace twoline2rv with cached version"""
    import sgp4.io
    sgp4.io.twoline2rv = cached_twoline2rv

def unpatch_tle_parsing():
    """Restore original twoline2rv"""
    import sgp4.io
    sgp4.io.twoline2rv = original_twoline2rv

def test_tle_caching_performance():
    """Test TLE caching performance impact"""
    import norad_cache
    import tart.util.utc as utc
    from tart.util import angle
    
    print("=== TLE CACHING PERFORMANCE TEST ===")
    
    date = utc.now()
    lat = angle.from_dms(-45.85)
    lon = angle.from_dms(170.54)
    
    # Test without caching
    print("\n🐌 WITHOUT TLE Caching:")
    unpatch_tle_parsing()
    
    times_uncached = []
    for i in range(3):
        start = time.time()
        gps_cache = norad_cache.GPSCache()
        result = gps_cache.get_az_el(date, lat, lon, 0, 0)
        duration = time.time() - start
        times_uncached.append(duration)
        print(f"  Run {i+1}: {duration*1000:.2f}ms ({len(result)} sats)")
    
    avg_uncached = sum(times_uncached) / len(times_uncached)
    
    # Test with caching
    print("\n🚀 WITH TLE Caching:")
    patch_tle_parsing()
    
    times_cached = []
    for i in range(3):
        start = time.time()
        gps_cache = norad_cache.GPSCache()
        result = gps_cache.get_az_el(date, lat, lon, 0, 0)
        duration = time.time() - start
        times_cached.append(duration)
        print(f"  Run {i+1}: {duration*1000:.2f}ms ({len(result)} sats)")
    
    avg_cached = sum(times_cached) / len(times_cached)
    
    # Results
    speedup = avg_uncached / avg_cached
    improvement = (avg_uncached - avg_cached) / avg_uncached * 100
    time_saved = (avg_uncached - avg_cached) * 1000
    
    print(f"\n📊 RESULTS:")
    print(f"  Average uncached: {avg_uncached*1000:.2f}ms")
    print(f"  Average cached:   {avg_cached*1000:.2f}ms")
    print(f"  Speedup:         {speedup:.1f}x")
    print(f"  Improvement:     {improvement:.1f}%")
    print(f"  Time saved:      {time_saved:.2f}ms")
    
    # Test cache effectiveness
    cache_info = cached_twoline2rv.cache_info()
    print(f"\n💾 CACHE STATS:")
    print(f"  Cache hits:   {cache_info.hits}")
    print(f"  Cache misses: {cache_info.misses}")
    print(f"  Cache size:   {cache_info.currsize}")
    if cache_info.hits + cache_info.misses > 0:
        hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses)
        print(f"  Hit rate:     {hit_rate:.1%}")
    
    return {
        'avg_uncached_ms': avg_uncached * 1000,
        'avg_cached_ms': avg_cached * 1000,
        'speedup': speedup,
        'improvement_pct': improvement,
        'cache_info': cache_info
    }

def test_bulk_request_improvement():
    """Test improvement on bulk requests (our main target)"""
    import norad_cache
    import tart.util.utc as utc
    from tart.util import angle
    from datetime import timedelta
    
    print("\n=== BULK REQUEST OPTIMIZATION TEST ===")
    
    base_date = utc.now()
    dates = [base_date + timedelta(seconds=i) for i in range(10)]
    lat = angle.from_dms(-45.85)
    lon = angle.from_dms(170.54)
    
    # Without caching
    print("\n🐌 Bulk WITHOUT TLE Caching:")
    unpatch_tle_parsing()
    
    start = time.time()
    results_uncached = []
    for date in dates:
        gps_cache = norad_cache.GPSCache()
        result = gps_cache.get_az_el(date, lat, lon, 0, 0)
        results_uncached.append(result)
    bulk_uncached_time = time.time() - start
    
    total_sats_uncached = sum(len(r) for r in results_uncached)
    print(f"  Time: {bulk_uncached_time*1000:.2f}ms")
    print(f"  Total calculations: {total_sats_uncached}")
    print(f"  Per calculation: {bulk_uncached_time*1000/total_sats_uncached:.2f}ms")
    
    # With caching
    print("\n🚀 Bulk WITH TLE Caching:")
    patch_tle_parsing()
    
    start = time.time()
    results_cached = []
    for date in dates:
        gps_cache = norad_cache.GPSCache()
        result = gps_cache.get_az_el(date, lat, lon, 0, 0)
        results_cached.append(result)
    bulk_cached_time = time.time() - start
    
    total_sats_cached = sum(len(r) for r in results_cached)
    print(f"  Time: {bulk_cached_time*1000:.2f}ms")
    print(f"  Total calculations: {total_sats_cached}")
    print(f"  Per calculation: {bulk_cached_time*1000/total_sats_cached:.2f}ms")
    
    # Bulk results
    bulk_speedup = bulk_uncached_time / bulk_cached_time
    bulk_improvement = (bulk_uncached_time - bulk_cached_time) / bulk_uncached_time * 100
    bulk_time_saved = (bulk_uncached_time - bulk_cached_time) * 1000
    
    print(f"\n📊 BULK IMPROVEMENT:")
    print(f"  Speedup:     {bulk_speedup:.1f}x")
    print(f"  Improvement: {bulk_improvement:.1f}%")
    print(f"  Time saved:  {bulk_time_saved:.2f}ms")
    
    return {
        'bulk_uncached_ms': bulk_uncached_time * 1000,
        'bulk_cached_ms': bulk_cached_time * 1000,
        'bulk_speedup': bulk_speedup,
        'bulk_improvement_pct': bulk_improvement
    }

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🔍 TLE OPTIMIZATION COMPREHENSIVE TEST")
    print("=" * 50)
    
    # Single request test
    single_results = test_tle_caching_performance()
    
    # Bulk request test  
    bulk_results = test_bulk_request_improvement()
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 SUMMARY")
    print("=" * 50)
    print(f"Single requests:")
    print(f"  Improvement: {single_results['improvement_pct']:.1f}%")
    print(f"  Speedup: {single_results['speedup']:.1f}x")
    print(f"  Time saved: {single_results['avg_uncached_ms'] - single_results['avg_cached_ms']:.1f}ms")
    
    print(f"\nBulk requests (10 dates):")  
    print(f"  Improvement: {bulk_results['bulk_improvement_pct']:.1f}%")
    print(f"  Speedup: {bulk_results['bulk_speedup']:.1f}x")
    print(f"  Time saved: {bulk_results['bulk_uncached_ms'] - bulk_results['bulk_cached_ms']:.1f}ms")
    
    cache_info = single_results['cache_info']
    if cache_info.hits + cache_info.misses > 0:
        hit_rate = cache_info.hits / (cache_info.hits + cache_info.misses)
        print(f"\nTLE Cache effectiveness:")
        print(f"  Hit rate: {hit_rate:.1%}")
        print(f"  Cache size: {cache_info.currsize} satellites")
    
    # Recommendation
    if single_results['improvement_pct'] > 20:
        print(f"\n✅ RECOMMENDATION: Deploy TLE caching!")
        print(f"   Expected improvement: {single_results['improvement_pct']:.0f}% for single requests")
        print(f"   Expected improvement: {bulk_results['bulk_improvement_pct']:.0f}% for bulk requests")
    else:
        print(f"\n❌ RECOMMENDATION: TLE caching shows minimal benefit")
    
    return single_results, bulk_results

if __name__ == "__main__":
    run_comprehensive_test()