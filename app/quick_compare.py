#!/usr/bin/env python3
# Quick V1 vs V2 Performance Comparison
# (c) 2023 Performance Optimization
# Test comment to verify build caching works

import requests
import time
import json
import statistics
from datetime import datetime, timedelta

def time_request(func, *args, **kwargs):
    """Time a request and return duration and result"""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        return duration, True, result.status_code, len(result.content)
    except Exception as e:
        duration = time.time() - start_time
        return duration, False, 0, 0

def run_comparison(base_url="http://localhost:8876", num_requests=20):
    """Run quick comparison between V1 and V2 endpoints"""
    
    print("🚀 Quick V1 vs V2 Performance Comparison")
    print("=" * 50)
    
    session = requests.Session()
    
    # Test parameters
    catalog_params = {'lat': -45.85, 'lon': 170.54, 'elevation': 0.0}
    
    # Small bulk request (10 timestamps)
    timestamps = [(datetime.now() + timedelta(seconds=i)).isoformat() for i in range(10)]
    bulk_data = {
        'lat': -45.85,
        'lon': 170.54,
        'alt': 0,
        'dates': timestamps
    }
    
    results = {}
    
    # 1. Catalog Endpoint Comparison
    print("\n📊 Testing Catalog Endpoints...")
    
    # V1 Catalog
    v1_catalog_times = []
    for i in range(num_requests):
        duration, success, status, size = time_request(
            session.get, f"{base_url}/catalog", params=catalog_params, timeout=10
        )
        if success:
            v1_catalog_times.append(duration)
    
    # V2 Catalog
    v2_catalog_times = []
    for i in range(num_requests):
        duration, success, status, size = time_request(
            session.get, f"{base_url}/v2/catalog", params=catalog_params, timeout=10
        )
        if success:
            v2_catalog_times.append(duration)
    
    # 2. Position Endpoint Comparison
    print("📊 Testing Position Endpoints...")
    
    # V1 Position
    v1_position_times = []
    for i in range(num_requests):
        duration, success, status, size = time_request(
            session.get, f"{base_url}/position", timeout=10
        )
        if success:
            v1_position_times.append(duration)
    
    # V2 Position
    v2_position_times = []
    for i in range(num_requests):
        duration, success, status, size = time_request(
            session.get, f"{base_url}/v2/position", timeout=10
        )
        if success:
            v2_position_times.append(duration)
    
    # 3. Small Bulk Request Comparison
    print("📊 Testing Small Bulk Requests...")
    
    # V1 Bulk
    v1_bulk_times = []
    for i in range(5):  # Fewer bulk requests
        duration, success, status, size = time_request(
            session.post, f"{base_url}/bulk_az_el", json=bulk_data, timeout=30
        )
        if success:
            v1_bulk_times.append(duration)
    
    # V2 Bulk
    v2_bulk_times = []
    for i in range(5):  # Fewer bulk requests
        duration, success, status, size = time_request(
            session.post, f"{base_url}/v2/bulk_az_el", json=bulk_data, timeout=30
        )
        if success:
            v2_bulk_times.append(duration)
    
    # Calculate and display results
    print("\n" + "=" * 60)
    print("📈 PERFORMANCE COMPARISON RESULTS")
    print("=" * 60)
    
    def calc_stats(times):
        if not times:
            return {'avg': 0, 'min': 0, 'max': 0, 'p95': 0, 'count': 0}
        return {
            'avg': statistics.mean(times),
            'min': min(times),
            'max': max(times),
            'p95': sorted(times)[int(len(times) * 0.95)] if len(times) > 1 else times[0],
            'count': len(times)
        }
    
    def print_comparison(test_name, v1_times, v2_times):
        v1_stats = calc_stats(v1_times)
        v2_stats = calc_stats(v2_times)
        
        improvement = 0
        if v1_stats['avg'] > 0 and v2_stats['avg'] > 0:
            improvement = ((v1_stats['avg'] - v2_stats['avg']) / v1_stats['avg']) * 100
        
        print(f"\n{test_name}")
        print("-" * len(test_name))
        print(f"V1: {v1_stats['avg']*1000:.1f}ms avg, {v1_stats['p95']*1000:.1f}ms p95 ({v1_stats['count']} requests)")
        print(f"V2: {v2_stats['avg']*1000:.1f}ms avg, {v2_stats['p95']*1000:.1f}ms p95 ({v2_stats['count']} requests)")
        
        if improvement > 0:
            print(f"✅ V2 is {improvement:.1f}% faster")
        elif improvement < 0:
            print(f"❌ V2 is {abs(improvement):.1f}% slower")
        else:
            print("⚖️  Similar performance")
        
        if v1_stats['avg'] > 0 and v2_stats['avg'] > 0:
            speedup = v1_stats['avg'] / v2_stats['avg']
            print(f"📊 Speedup ratio: {speedup:.2f}x")
    
    print_comparison("Catalog Requests", v1_catalog_times, v2_catalog_times)
    print_comparison("Position Requests", v1_position_times, v2_position_times)
    print_comparison("Small Bulk Requests", v1_bulk_times, v2_bulk_times)
    
    # Overall summary
    all_v1_times = v1_catalog_times + v1_position_times + v1_bulk_times
    all_v2_times = v2_catalog_times + v2_position_times + v2_bulk_times
    
    if all_v1_times and all_v2_times:
        overall_improvement = ((statistics.mean(all_v1_times) - statistics.mean(all_v2_times)) / statistics.mean(all_v1_times)) * 100
        
        print(f"\n🎯 OVERALL PERFORMANCE")
        print("-" * 20)
        print(f"V1 Average: {statistics.mean(all_v1_times)*1000:.1f}ms")
        print(f"V2 Average: {statistics.mean(all_v2_times)*1000:.1f}ms")
        
        if overall_improvement > 0:
            print(f"✅ Overall V2 improvement: {overall_improvement:.1f}%")
        else:
            print(f"❌ Overall V2 regression: {abs(overall_improvement):.1f}%")
    
    print(f"\n⏱️  Total benchmark time: {time.time() - start_time:.1f}s")
    
    return {
        'catalog': {'v1': v1_catalog_times, 'v2': v2_catalog_times},
        'position': {'v1': v1_position_times, 'v2': v2_position_times},
        'bulk': {'v1': v1_bulk_times, 'v2': v2_bulk_times}
    }

if __name__ == '__main__':
    import sys
    
    # Quick test first
    try:
        response = requests.get("http://localhost:8876/catalog?lat=-45.85&lon=170.54", timeout=5)
        if response.status_code != 200:
            print("❌ API not responding correctly")
            sys.exit(1)
    except:
        print("❌ Cannot connect to API at http://localhost:8876")
        sys.exit(1)
    
    start_time = time.time()
    results = run_comparison()