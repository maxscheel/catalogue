#!/usr/bin/env python3
# Comprehensive Benchmark Suite for Catalogue API
# (c) 2023 Performance Optimization
#
# This script provides benchmarking tools to measure API performance
# and compare different implementations

import requests
import time
import json
import sys
import argparse
import statistics
import concurrent.futures
from datetime import datetime, timedelta
import numpy as np
from typing import List, Dict, Any


class BenchmarkConfig:
    """Configuration for benchmark runs"""
    def __init__(self):
        self.base_url = "http://localhost:8876"
        self.warmup_requests = 5
        self.benchmark_requests = 100
        self.bulk_requests = 10
        self.concurrent_workers = 10
        self.timeout = 30
        self.bulk_timeout = 60
        self.output_file = None


class BenchmarkResult:
    """Container for benchmark results"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.durations: List[float] = []
        self.success_count = 0
        self.error_count = 0
        self.errors: List[str] = []
        self.response_sizes: List[int] = []
        self.start_time = None
        self.end_time = None
    
    def add_result(self, duration: float, success: bool, error: str = None, response_size: int = 0):
        """Add a single request result"""
        self.durations.append(duration)
        self.response_sizes.append(response_size)
        
        if success:
            self.success_count += 1
        else:
            self.error_count += 1
            if error:
                self.errors.append(error)
    
    def get_stats(self) -> Dict[str, Any]:
        """Calculate statistics from results"""
        if not self.durations:
            return {
                'test_name': self.test_name,
                'total_requests': 0,
                'success_rate': 0,
                'avg_duration': 0,
                'median_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'p95_duration': 0,
                'p99_duration': 0,
                'std_deviation': 0,
                'requests_per_second': 0,
                'avg_response_size_kb': 0,
                'total_time': 0
            }
        
        total_time = (self.end_time - self.start_time).total_seconds() if self.start_time and self.end_time else sum(self.durations)
        successful_durations = self.durations[:self.success_count] if self.success_count > 0 else []
        
        stats = {
            'test_name': self.test_name,
            'total_requests': len(self.durations),
            'successful_requests': self.success_count,
            'failed_requests': self.error_count,
            'success_rate': self.success_count / len(self.durations) if self.durations else 0,
            'total_time': total_time,
            'errors': self.errors[:10]  # Limit to first 10 errors
        }
        
        if successful_durations:
            stats.update({
                'avg_duration': statistics.mean(successful_durations),
                'median_duration': statistics.median(successful_durations),
                'min_duration': min(successful_durations),
                'max_duration': max(successful_durations),
                'p95_duration': np.percentile(successful_durations, 95),
                'p99_duration': np.percentile(successful_durations, 99),
                'std_deviation': statistics.stdev(successful_durations) if len(successful_durations) > 1 else 0,
                'requests_per_second': self.success_count / total_time if total_time > 0 else 0
            })
        else:
            stats.update({
                'avg_duration': 0,
                'median_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'p95_duration': 0,
                'p99_duration': 0,
                'std_deviation': 0,
                'requests_per_second': 0
            })
        
        # Response size stats
        if self.response_sizes:
            stats['avg_response_size_kb'] = statistics.mean(self.response_sizes) / 1024
            stats['total_data_transferred_mb'] = sum(self.response_sizes) / 1024 / 1024
        else:
            stats['avg_response_size_kb'] = 0
            stats['total_data_transferred_mb'] = 0
        
        return stats


class CatalogueBenchmark:
    """Main benchmark class for the catalogue API"""
    
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.session = requests.Session()
        self.results: List[BenchmarkResult] = []
    
    def run_all_benchmarks(self):
        """Run all benchmark tests"""
        print(f"Starting benchmark suite against {self.config.base_url}")
        print("=" * 60)
        
        # Test basic connectivity
        if not self._test_connectivity():
            print("ERROR: Could not connect to API. Please ensure it's running.")
            return False
        
        print("✓ API connectivity confirmed")
        print()
        
        # Run individual benchmarks
        benchmarks = [
            ("Single Catalog Requests (Sequential)", self._benchmark_single_catalog_sequential),
            ("Single Catalog Requests (Concurrent)", self._benchmark_single_catalog_concurrent),
            ("Position Requests (Sequential)", self._benchmark_position_sequential),
            ("Position Requests (Concurrent)", self._benchmark_position_concurrent),
            ("Bulk Az/El Requests (Small)", self._benchmark_bulk_small),
            ("Bulk Az/El Requests (Medium)", self._benchmark_bulk_medium),
            ("Bulk Az/El Requests (Large)", self._benchmark_bulk_large),
            ("Stress Test (High Concurrency)", self._benchmark_stress_test),
        ]
        
        for test_name, benchmark_func in benchmarks:
            print(f"Running: {test_name}")
            result = benchmark_func()
            self.results.append(result)
            self._print_result_summary(result)
            print()
        
        # Generate final report
        self._generate_report()
        return True
    
    def _test_connectivity(self) -> bool:
        """Test if the API is reachable"""
        try:
            response = self.session.get(
                f"{self.config.base_url}/catalog",
                params={'lat': -45.85, 'lon': 170.54},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def _benchmark_single_catalog_sequential(self) -> BenchmarkResult:
        """Benchmark sequential catalog requests"""
        result = BenchmarkResult("Single Catalog Requests (Sequential)")
        result.start_time = datetime.now()
        
        # Warmup
        self._warmup_catalog_requests()
        
        # Actual benchmark
        for i in range(self.config.benchmark_requests):
            duration, success, error, response_size = self._make_catalog_request(
                lat=-45.85 + (i % 10) * 0.1,  # Vary location slightly
                lon=170.54 + (i % 10) * 0.1
            )
            result.add_result(duration, success, error, response_size)
        
        result.end_time = datetime.now()
        return result
    
    def _benchmark_single_catalog_concurrent(self) -> BenchmarkResult:
        """Benchmark concurrent catalog requests"""
        result = BenchmarkResult("Single Catalog Requests (Concurrent)")
        result.start_time = datetime.now()
        
        # Warmup
        self._warmup_catalog_requests()
        
        # Concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_workers) as executor:
            futures = []
            for i in range(self.config.benchmark_requests):
                future = executor.submit(
                    self._make_catalog_request,
                    lat=-45.85 + (i % 10) * 0.1,
                    lon=170.54 + (i % 10) * 0.1
                )
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures):
                duration, success, error, response_size = future.result()
                result.add_result(duration, success, error, response_size)
        
        result.end_time = datetime.now()
        return result
    
    def _benchmark_position_sequential(self) -> BenchmarkResult:
        """Benchmark sequential position requests"""
        result = BenchmarkResult("Position Requests (Sequential)")
        result.start_time = datetime.now()
        
        for i in range(self.config.benchmark_requests):
            duration, success, error, response_size = self._make_position_request()
            result.add_result(duration, success, error, response_size)
        
        result.end_time = datetime.now()
        return result
    
    def _benchmark_position_concurrent(self) -> BenchmarkResult:
        """Benchmark concurrent position requests"""
        result = BenchmarkResult("Position Requests (Concurrent)")
        result.start_time = datetime.now()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_workers) as executor:
            futures = [executor.submit(self._make_position_request) for _ in range(self.config.benchmark_requests)]
            
            for future in concurrent.futures.as_completed(futures):
                duration, success, error, response_size = future.result()
                result.add_result(duration, success, error, response_size)
        
        result.end_time = datetime.now()
        return result
    
    def _benchmark_bulk_small(self) -> BenchmarkResult:
        """Benchmark small bulk requests (10 timestamps)"""
        return self._benchmark_bulk_requests("Bulk Az/El Requests (Small)", 10)
    
    def _benchmark_bulk_medium(self) -> BenchmarkResult:
        """Benchmark medium bulk requests (100 timestamps)"""
        return self._benchmark_bulk_requests("Bulk Az/El Requests (Medium)", 100)
    
    def _benchmark_bulk_large(self) -> BenchmarkResult:
        """Benchmark large bulk requests (1000 timestamps)"""
        return self._benchmark_bulk_requests("Bulk Az/El Requests (Large)", 1000)
    
    def _benchmark_bulk_requests(self, test_name: str, num_timestamps: int) -> BenchmarkResult:
        """Benchmark bulk requests with specified number of timestamps"""
        result = BenchmarkResult(test_name)
        result.start_time = datetime.now()
        
        # Generate timestamps
        base_time = datetime.now()
        timestamps = [
            (base_time + timedelta(seconds=i)).isoformat()
            for i in range(num_timestamps)
        ]
        
        bulk_data = {
            'lat': -45.85,
            'lon': 170.54,
            'alt': 0,
            'dates': timestamps
        }
        
        for i in range(self.config.bulk_requests):
            duration, success, error, response_size = self._make_bulk_request(bulk_data)
            result.add_result(duration, success, error, response_size)
        
        result.end_time = datetime.now()
        return result
    
    def _benchmark_stress_test(self) -> BenchmarkResult:
        """Stress test with high concurrency"""
        result = BenchmarkResult("Stress Test (High Concurrency)")
        result.start_time = datetime.now()
        
        # Use higher concurrency for stress test
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            # Mix of different request types
            for i in range(self.config.benchmark_requests):
                if i % 3 == 0:
                    future = executor.submit(self._make_catalog_request, -45.85, 170.54)
                elif i % 3 == 1:
                    future = executor.submit(self._make_position_request)
                else:
                    # Small bulk request
                    timestamps = [(datetime.now() + timedelta(seconds=j)).isoformat() for j in range(5)]
                    bulk_data = {'lat': -45.85, 'lon': 170.54, 'alt': 0, 'dates': timestamps}
                    future = executor.submit(self._make_bulk_request, bulk_data)
                
                futures.append(future)
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    duration, success, error, response_size = future.result()
                    result.add_result(duration, success, error, response_size)
                except Exception as e:
                    result.add_result(0, False, str(e), 0)
        
        result.end_time = datetime.now()
        return result
    
    def _warmup_catalog_requests(self):
        """Warmup the API with a few requests"""
        for i in range(self.config.warmup_requests):
            self._make_catalog_request(-45.85, 170.54)
            time.sleep(0.1)
    
    def _make_catalog_request(self, lat: float, lon: float) -> tuple:
        """Make a single catalog request"""
        start_time = time.time()
        try:
            response = self.session.get(
                f"{self.config.base_url}/catalog",
                params={'lat': lat, 'lon': lon},
                timeout=self.config.timeout
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                return duration, True, None, len(response.content)
            else:
                return duration, False, f"HTTP {response.status_code}", len(response.content)
        
        except Exception as e:
            duration = time.time() - start_time
            return duration, False, str(e), 0
    
    def _make_position_request(self) -> tuple:
        """Make a single position request"""
        start_time = time.time()
        try:
            response = self.session.get(
                f"{self.config.base_url}/position",
                timeout=self.config.timeout
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                return duration, True, None, len(response.content)
            else:
                return duration, False, f"HTTP {response.status_code}", len(response.content)
        
        except Exception as e:
            duration = time.time() - start_time
            return duration, False, str(e), 0
    
    def _make_bulk_request(self, data: dict) -> tuple:
        """Make a bulk request"""
        start_time = time.time()
        try:
            response = self.session.post(
                f"{self.config.base_url}/bulk_az_el",
                json=data,
                timeout=self.config.bulk_timeout
            )
            duration = time.time() - start_time
            
            if response.status_code == 200:
                return duration, True, None, len(response.content)
            else:
                return duration, False, f"HTTP {response.status_code}", len(response.content)
        
        except Exception as e:
            duration = time.time() - start_time
            return duration, False, str(e), 0
    
    def _print_result_summary(self, result: BenchmarkResult):
        """Print a summary of benchmark results"""
        stats = result.get_stats()
        
        print(f"  Total Requests: {stats['total_requests']}")
        print(f"  Success Rate: {stats['success_rate']:.1%}")
        print(f"  Avg Duration: {stats['avg_duration']:.3f}s")
        print(f"  P95 Duration: {stats['p95_duration']:.3f}s")
        print(f"  P99 Duration: {stats['p99_duration']:.3f}s")
        print(f"  Requests/sec: {stats['requests_per_second']:.1f}")
        print(f"  Avg Response: {stats['avg_response_size_kb']:.1f} KB")
        
        if stats['failed_requests'] > 0:
            print(f"  ⚠️  Failed Requests: {stats['failed_requests']}")
            if stats['errors']:
                print(f"  Sample Errors: {stats['errors'][:3]}")
    
    def _generate_report(self):
        """Generate comprehensive benchmark report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'config': {
                'base_url': self.config.base_url,
                'benchmark_requests': self.config.benchmark_requests,
                'bulk_requests': self.config.bulk_requests,
                'concurrent_workers': self.config.concurrent_workers
            },
            'results': [result.get_stats() for result in self.results]
        }
        
        # Print summary table
        print("=" * 80)
        print("BENCHMARK SUMMARY")
        print("=" * 80)
        print(f"{'Test Name':<40} {'Success%':<10} {'Avg(ms)':<10} {'P95(ms)':<10} {'RPS':<10}")
        print("-" * 80)
        
        for result in self.results:
            stats = result.get_stats()
            print(f"{stats['test_name']:<40} "
                  f"{stats['success_rate']*100:>7.1f}%  "
                  f"{stats['avg_duration']*1000:>7.0f}ms  "
                  f"{stats['p95_duration']*1000:>7.0f}ms  "
                  f"{stats['requests_per_second']:>7.1f}")
        
        # Save detailed report if requested
        if self.config.output_file:
            with open(self.config.output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nDetailed report saved to: {self.config.output_file}")
        
        return report


def main():
    """Main benchmark runner"""
    parser = argparse.ArgumentParser(description="Catalogue API Benchmark Suite")
    parser.add_argument('--url', default='http://localhost:8876', 
                       help='Base URL of the API (default: http://localhost:8876)')
    parser.add_argument('--requests', type=int, default=100,
                       help='Number of requests per benchmark (default: 100)')
    parser.add_argument('--bulk-requests', type=int, default=10,
                       help='Number of bulk requests (default: 10)')
    parser.add_argument('--workers', type=int, default=10,
                       help='Number of concurrent workers (default: 10)')
    parser.add_argument('--output', help='Output file for detailed results (JSON)')
    parser.add_argument('--quick', action='store_true',
                       help='Run a quick benchmark with fewer requests')
    
    args = parser.parse_args()
    
    # Create configuration
    config = BenchmarkConfig()
    config.base_url = args.url
    config.benchmark_requests = 20 if args.quick else args.requests
    config.bulk_requests = 3 if args.quick else args.bulk_requests
    config.concurrent_workers = args.workers
    config.output_file = args.output
    
    # Run benchmarks
    benchmark = CatalogueBenchmark(config)
    success = benchmark.run_all_benchmarks()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()