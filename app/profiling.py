# Performance Profiling and Measurement Tools
# (c) 2023 Performance Optimization
#
# This module provides profiling tools to measure and track API performance

import time
import functools
import json
import threading
from collections import defaultdict, deque
from datetime import datetime
import psutil
import os
import traceback
import cProfile
import pstats
import io
from contextlib import contextmanager


class PerformanceMetrics:
    """Thread-safe performance metrics collector"""
    
    def __init__(self, max_samples=1000):
        self.max_samples = max_samples
        self.metrics = defaultdict(lambda: {
            'times': deque(maxlen=max_samples),
            'memory_usage': deque(maxlen=max_samples),
            'cpu_percent': deque(maxlen=max_samples),
            'request_count': 0,
            'error_count': 0,
            'total_time': 0.0
        })
        self.lock = threading.Lock()
        self.process = psutil.Process(os.getpid())
    
    def record_request(self, endpoint, duration, memory_mb=None, cpu_percent=None, error=False):
        """Record metrics for a request"""
        with self.lock:
            metric = self.metrics[endpoint]
            metric['times'].append(duration)
            metric['request_count'] += 1
            metric['total_time'] += duration
            
            if error:
                metric['error_count'] += 1
            
            if memory_mb is not None:
                metric['memory_usage'].append(memory_mb)
            
            if cpu_percent is not None:
                metric['cpu_percent'].append(cpu_percent)
    
    def get_stats(self, endpoint=None):
        """Get performance statistics"""
        with self.lock:
            if endpoint:
                return self._calculate_stats(endpoint, self.metrics[endpoint])
            else:
                return {ep: self._calculate_stats(ep, data) 
                       for ep, data in self.metrics.items()}
    
    def _calculate_stats(self, endpoint, data):
        """Calculate statistics for an endpoint"""
        times = list(data['times'])
        if not times:
            return {
                'endpoint': endpoint,
                'request_count': 0,
                'avg_time': 0,
                'min_time': 0,
                'max_time': 0,
                'p95_time': 0,
                'p99_time': 0,
                'error_rate': 0,
                'requests_per_second': 0
            }
        
        times.sort()
        count = len(times)
        
        stats = {
            'endpoint': endpoint,
            'request_count': data['request_count'],
            'error_count': data['error_count'],
            'avg_time': sum(times) / count,
            'min_time': times[0],
            'max_time': times[-1],
            'p95_time': times[int(count * 0.95)] if count > 0 else 0,
            'p99_time': times[int(count * 0.99)] if count > 0 else 0,
            'error_rate': data['error_count'] / data['request_count'] if data['request_count'] > 0 else 0
        }
        
        # Calculate requests per second over total time
        if data['total_time'] > 0:
            stats['requests_per_second'] = data['request_count'] / data['total_time']
        else:
            stats['requests_per_second'] = 0
        
        # Add memory and CPU stats if available
        if data['memory_usage']:
            memory_list = list(data['memory_usage'])
            stats['avg_memory_mb'] = sum(memory_list) / len(memory_list)
            stats['max_memory_mb'] = max(memory_list)
        
        if data['cpu_percent']:
            cpu_list = list(data['cpu_percent'])
            stats['avg_cpu_percent'] = sum(cpu_list) / len(cpu_list)
            stats['max_cpu_percent'] = max(cpu_list)
        
        return stats
    
    def reset(self):
        """Reset all metrics"""
        with self.lock:
            self.metrics.clear()


# Global metrics instance
metrics = PerformanceMetrics()


def profile_endpoint(include_system_metrics=True, profile_code=False):
    """Decorator to profile endpoint performance"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            endpoint_name = func.__name__
            start_time = time.time()
            error = False
            
            # Get initial system metrics
            memory_before = None
            cpu_before = None
            
            if include_system_metrics:
                try:
                    memory_before = metrics.process.memory_info().rss / 1024 / 1024  # MB
                    cpu_before = metrics.process.cpu_percent()
                except:
                    pass
            
            # Profile code execution if requested
            profiler = None
            if profile_code:
                profiler = cProfile.Profile()
                profiler.enable()
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                error = True
                raise
            finally:
                # Calculate execution time
                duration = time.time() - start_time
                
                # Get final system metrics
                memory_after = None
                cpu_after = None
                
                if include_system_metrics:
                    try:
                        memory_after = metrics.process.memory_info().rss / 1024 / 1024  # MB
                        cpu_after = metrics.process.cpu_percent()
                    except:
                        pass
                
                # Disable profiler if used
                if profiler:
                    profiler.disable()
                    # Store profiler results (you could save to file or analyze)
                    # For now, we'll just store the top functions
                    pass
                
                # Record metrics
                metrics.record_request(
                    endpoint_name, 
                    duration, 
                    memory_mb=memory_after,
                    cpu_percent=cpu_after,
                    error=error
                )
        
        return wrapper
    return decorator


@contextmanager
def profile_block(block_name):
    """Context manager to profile a block of code"""
    start_time = time.time()
    error = False
    
    try:
        yield
    except Exception as e:
        error = True
        raise
    finally:
        duration = time.time() - start_time
        metrics.record_request(block_name, duration, error=error)


class BenchmarkRunner:
    """Run benchmarks against API endpoints"""
    
    def __init__(self, base_url="http://localhost:8876"):
        self.base_url = base_url
        self.results = []
    
    def run_single_request_benchmark(self, endpoint, params, num_requests=100, concurrent=False):
        """Benchmark single requests"""
        import requests
        import concurrent.futures
        
        url = f"{self.base_url}{endpoint}"
        
        def make_request():
            start_time = time.time()
            try:
                response = requests.get(url, params=params, timeout=30)
                duration = time.time() - start_time
                return {
                    'success': response.status_code == 200,
                    'duration': duration,
                    'status_code': response.status_code,
                    'response_size': len(response.content) if response.content else 0
                }
            except Exception as e:
                duration = time.time() - start_time
                return {
                    'success': False,
                    'duration': duration,
                    'error': str(e),
                    'status_code': None,
                    'response_size': 0
                }
        
        results = []
        
        if concurrent:
            # Run concurrent requests
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(make_request) for _ in range(num_requests)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
        else:
            # Run sequential requests
            for _ in range(num_requests):
                results.append(make_request())
        
        return self._analyze_benchmark_results(endpoint, results)
    
    def run_bulk_request_benchmark(self, endpoint, json_data, num_requests=10):
        """Benchmark bulk requests"""
        import requests
        
        url = f"{self.base_url}{endpoint}"
        results = []
        
        for _ in range(num_requests):
            start_time = time.time()
            try:
                response = requests.post(url, json=json_data, timeout=60)
                duration = time.time() - start_time
                results.append({
                    'success': response.status_code == 200,
                    'duration': duration,
                    'status_code': response.status_code,
                    'response_size': len(response.content) if response.content else 0
                })
            except Exception as e:
                duration = time.time() - start_time
                results.append({
                    'success': False,
                    'duration': duration,
                    'error': str(e),
                    'status_code': None,
                    'response_size': 0
                })
        
        return self._analyze_benchmark_results(endpoint, results)
    
    def _analyze_benchmark_results(self, endpoint, results):
        """Analyze benchmark results"""
        successful_results = [r for r in results if r['success']]
        failed_results = [r for r in results if not r['success']]
        
        if not successful_results:
            return {
                'endpoint': endpoint,
                'total_requests': len(results),
                'successful_requests': 0,
                'failed_requests': len(failed_results),
                'success_rate': 0.0,
                'avg_duration': 0,
                'min_duration': 0,
                'max_duration': 0,
                'p95_duration': 0,
                'p99_duration': 0,
                'requests_per_second': 0
            }
        
        durations = [r['duration'] for r in successful_results]
        durations.sort()
        
        total_time = sum(durations)
        
        return {
            'endpoint': endpoint,
            'total_requests': len(results),
            'successful_requests': len(successful_results),
            'failed_requests': len(failed_results),
            'success_rate': len(successful_results) / len(results),
            'avg_duration': sum(durations) / len(durations),
            'min_duration': min(durations),
            'max_duration': max(durations),
            'p95_duration': durations[int(len(durations) * 0.95)],
            'p99_duration': durations[int(len(durations) * 0.99)],
            'requests_per_second': len(successful_results) / total_time if total_time > 0 else 0,
            'avg_response_size_kb': sum(r['response_size'] for r in successful_results) / len(successful_results) / 1024
        }


def generate_performance_report():
    """Generate a comprehensive performance report"""
    stats = metrics.get_stats()
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'endpoints': stats,
        'summary': {
            'total_endpoints': len(stats),
            'total_requests': sum(s['request_count'] for s in stats.values()),
            'total_errors': sum(s['error_count'] for s in stats.values()),
            'overall_error_rate': 0
        }
    }
    
    # Calculate overall error rate
    total_requests = report['summary']['total_requests']
    total_errors = report['summary']['total_errors']
    if total_requests > 0:
        report['summary']['overall_error_rate'] = total_errors / total_requests
    
    return report


def save_performance_report(filename=None):
    """Save performance report to file"""
    if filename is None:
        filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report = generate_performance_report()
    
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    return filename


# Middleware for Flask to automatically profile all requests
class ProfilingMiddleware:
    def __init__(self, app):
        self.app = app
        self.wrap_wsgi_app()
    
    def wrap_wsgi_app(self):
        original_wsgi_app = self.app.wsgi_app
        
        def profiling_wsgi_app(environ, start_response):
            start_time = time.time()
            
            def new_start_response(status, response_headers, exc_info=None):
                duration = time.time() - start_time
                endpoint = environ.get('PATH_INFO', 'unknown')
                method = environ.get('REQUEST_METHOD', 'GET')
                endpoint_name = f"{method} {endpoint}"
                
                # Record the request
                error = status.startswith('4') or status.startswith('5')
                metrics.record_request(endpoint_name, duration, error=error)
                
                return start_response(status, response_headers, exc_info)
            
            return original_wsgi_app(environ, new_start_response)
        
        self.app.wsgi_app = profiling_wsgi_app