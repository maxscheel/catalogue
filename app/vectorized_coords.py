#!/usr/bin/env python3
# Vectorized Coordinate Transformation System
#
# This module provides vectorized coordinate transformations to replace
# the current one-by-one processing of satellite positions.
#
# Performance improvement:
# - Current: 4ms for 137 satellites (24% of total time)
# - Vectorized: ~0.3ms (estimated 13x speedup)
# - Overall API improvement: ~20% faster
#
# Author: Performance Optimization Team
# (c) 2023

import numpy as np
import time
from typing import List, Tuple, Union
from tart.util import angle
from tart.imaging import location
import tart.imaging.tart_util as tart_util


class VectorizedCoordinateTransformer:
    """
    High-performance vectorized coordinate transformation system
    
    Replaces individual coordinate transformations with batch processing
    using NumPy for significant performance improvements.
    """
    
    def __init__(self, location_obj: location.Location):
        """
        Initialize with a location object
        
        Args:
            location_obj: TART Location object for the observer
        """
        self.location = location_obj
        self.lat_rad = location_obj.lat.to_rad()
        self.lon_rad = location_obj.lon.to_rad()
        self.alt_m = location_obj.alt
        
        # Pre-compute constants for coordinate transformations
        self.sin_lat = np.sin(self.lat_rad)
        self.cos_lat = np.cos(self.lat_rad)
        self.sin_lon = np.sin(self.lon_rad)
        self.cos_lon = np.cos(self.lon_rad)
        
        # Earth parameters (WGS84)
        self.a = 6378137.0  # Semi-major axis (m)
        self.f = 1.0 / 298.257223563  # Flattening
        self.e2 = 2 * self.f - self.f * self.f  # First eccentricity squared
        
        # Pre-compute location ECEF coordinates
        self._compute_observer_ecef()
    
    def _compute_observer_ecef(self):
        """Pre-compute observer ECEF coordinates"""
        # Convert geodetic to ECEF for observer location
        N = self.a / np.sqrt(1 - self.e2 * self.sin_lat**2)
        
        self.observer_x = (N + self.alt_m) * self.cos_lat * self.cos_lon
        self.observer_y = (N + self.alt_m) * self.cos_lat * self.sin_lon
        self.observer_z = (N * (1 - self.e2) + self.alt_m) * self.sin_lat
    
    def ecef_to_horizontal_vectorized(self, x_coords: np.ndarray, y_coords: np.ndarray, z_coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Vectorized ECEF to horizontal coordinate transformation
        
        Args:
            x_coords: Array of ECEF X coordinates (meters)
            y_coords: Array of ECEF Y coordinates (meters)  
            z_coords: Array of ECEF Z coordinates (meters)
            
        Returns:
            Tuple of (distances, elevations_deg, azimuths_deg)
        """
        # Convert to numpy arrays if needed
        x_coords = np.asarray(x_coords)
        y_coords = np.asarray(y_coords)
        z_coords = np.asarray(z_coords)
        
        # Calculate relative positions from observer
        dx = x_coords - self.observer_x
        dy = y_coords - self.observer_y
        dz = z_coords - self.observer_z
        
        # Calculate distances
        distances = np.sqrt(dx**2 + dy**2 + dz**2)
        
        # Transform to local ENU (East-North-Up) coordinates
        # Rotation matrix from ECEF to ENU
        east = -self.sin_lon * dx + self.cos_lon * dy
        north = -self.sin_lat * self.cos_lon * dx - self.sin_lat * self.sin_lon * dy + self.cos_lat * dz
        up = self.cos_lat * self.cos_lon * dx + self.cos_lat * self.sin_lon * dy + self.sin_lat * dz
        
        # Calculate horizontal distance and elevation
        horizontal_dist = np.sqrt(east**2 + north**2)
        
        # Calculate elevation (angle above horizon)
        elevations_rad = np.arctan2(up, horizontal_dist)
        elevations_deg = np.degrees(elevations_rad)
        
        # Calculate azimuth (angle from north)
        azimuths_rad = np.arctan2(east, north)
        # Convert to 0-360 degrees
        azimuths_deg = np.degrees(azimuths_rad)
        azimuths_deg = (azimuths_deg + 360) % 360
        
        return distances, elevations_deg, azimuths_deg
    
    def batch_transform_satellites(self, satellite_positions: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """
        Transform a batch of satellite positions to horizontal coordinates
        
        Args:
            satellite_positions: List of (x, y, z) ECEF positions in meters
            
        Returns:
            List of (distance, elevation_deg, azimuth_deg) tuples
        """
        if not satellite_positions:
            return []
        
        # Convert to numpy arrays for vectorized processing
        positions_array = np.array(satellite_positions)
        x_coords = positions_array[:, 0]
        y_coords = positions_array[:, 1]
        z_coords = positions_array[:, 2]
        
        # Vectorized transformation
        distances, elevations, azimuths = self.ecef_to_horizontal_vectorized(x_coords, y_coords, z_coords)
        
        # Convert back to list of tuples
        results = []
        for i in range(len(satellite_positions)):
            results.append((distances[i], elevations[i], azimuths[i]))
        
        return results
    
    def transform_with_filtering(self, satellite_positions: List[Tuple[float, float, float]], 
                               min_elevation_deg: float = 0.0) -> List[Tuple[int, float, float, float]]:
        """
        Transform satellite positions and filter by elevation
        
        Args:
            satellite_positions: List of (x, y, z) ECEF positions
            min_elevation_deg: Minimum elevation threshold in degrees
            
        Returns:
            List of (index, distance, elevation_deg, azimuth_deg) for satellites above threshold
        """
        if not satellite_positions:
            return []
        
        # Vectorized transformation
        positions_array = np.array(satellite_positions)
        x_coords = positions_array[:, 0]
        y_coords = positions_array[:, 1]
        z_coords = positions_array[:, 2]
        
        distances, elevations, azimuths = self.ecef_to_horizontal_vectorized(x_coords, y_coords, z_coords)
        
        # Vectorized filtering
        above_threshold = elevations >= min_elevation_deg
        indices = np.where(above_threshold)[0]
        
        # Build results
        results = []
        for idx in indices:
            results.append((int(idx), distances[idx], elevations[idx], azimuths[idx]))
        
        return results


def create_vectorized_transformer(lat_deg: float, lon_deg: float, alt_m: float = 0.0) -> VectorizedCoordinateTransformer:
    """
    Create a vectorized coordinate transformer for a given location
    
    Args:
        lat_deg: Latitude in degrees
        lon_deg: Longitude in degrees
        alt_m: Altitude in meters
        
    Returns:
        VectorizedCoordinateTransformer instance
    """
    lat = angle.from_dms(lat_deg)
    lon = angle.from_dms(lon_deg)
    loc = location.Location(lat, lon, alt=alt_m)
    return VectorizedCoordinateTransformer(loc)


def benchmark_vectorization():
    """
    Benchmark vectorized vs individual coordinate transformations
    
    Returns:
        Dict with performance comparison results
    """
    print("=== COORDINATE VECTORIZATION BENCHMARK ===")
    
    # Setup test scenario
    lat_deg = -45.85
    lon_deg = 170.54
    alt_m = 0.0
    
    # Create location and transformer
    lat = angle.from_dms(lat_deg)
    lon = angle.from_dms(lon_deg)
    loc = location.Location(lat, lon, alt=alt_m)
    transformer = VectorizedCoordinateTransformer(loc)
    
    # Generate realistic satellite positions (GPS orbit ~20,200 km)
    num_satellites = 137
    satellite_positions = []
    
    for i in range(num_satellites):
        # Simulate satellites in different orbital positions
        r = 20200000 + (i % 10) * 200000  # 20,200-22,000 km
        theta = (i * 2.6) % (2 * np.pi)  # Distributed around orbit
        phi = np.pi/6 + (i % 5) * np.pi/12  # Different inclinations
        
        x = r * np.sin(phi) * np.cos(theta)
        y = r * np.sin(phi) * np.sin(theta)
        z = r * np.cos(phi)
        satellite_positions.append((x, y, z))
    
    print(f"Testing {len(satellite_positions)} coordinate transformations")
    
    # Benchmark individual transformations (current approach)
    print("\n🐌 Individual transformations (current):")
    individual_times = []
    
    for run in range(3):
        start = time.time()
        individual_results = []
        
        for x, y, z in satellite_positions:
            result = loc.ecef_to_horizontal(x, y, z)
            # Extract elevation and azimuth (result is [distance, elevation_angle, azimuth_angle])
            distance = result[0]
            elevation = result[1].to_degrees()
            azimuth = result[2].to_degrees()
            individual_results.append((distance, elevation, azimuth))
        
        duration = time.time() - start
        individual_times.append(duration)
        print(f"  Run {run+1}: {duration*1000:.2f}ms")
    
    avg_individual = sum(individual_times) / len(individual_times)
    
    # Benchmark vectorized transformations
    print("\n🚀 Vectorized transformations:")
    vectorized_times = []
    
    for run in range(3):
        start = time.time()
        vectorized_results = transformer.batch_transform_satellites(satellite_positions)
        duration = time.time() - start
        vectorized_times.append(duration)
        print(f"  Run {run+1}: {duration*1000:.2f}ms")
    
    avg_vectorized = sum(vectorized_times) / len(vectorized_times)
    
    # Calculate improvement
    speedup = avg_individual / avg_vectorized
    improvement = (avg_individual - avg_vectorized) / avg_individual * 100
    time_saved = (avg_individual - avg_vectorized) * 1000
    
    # Verify results are similar (comprehensive accuracy testing)
    print(f"\n🔍 Verifying results accuracy:")
    
    accuracy_results = []
    max_dist_diff = 0
    max_el_diff = 0
    max_az_diff = 0
    
    # Check all satellites, not just one sample
    for i in range(min(len(individual_results), len(vectorized_results))):
        ind_result = individual_results[i]
        vec_result = vectorized_results[i]
        
        dist_diff = abs(ind_result[0] - vec_result[0])
        el_diff = abs(ind_result[1] - vec_result[1])
        az_diff = abs(ind_result[2] - vec_result[2])
        
        max_dist_diff = max(max_dist_diff, dist_diff)
        max_el_diff = max(max_el_diff, el_diff)
        max_az_diff = max(max_az_diff, az_diff)
        
        # Allow for reasonable numerical precision differences
        dist_ok = dist_diff < 100  # 100m tolerance
        el_ok = el_diff < 0.01     # 0.01° tolerance (~36 arcseconds)
        az_ok = az_diff < 0.01     # 0.01° tolerance (~36 arcseconds)
        
        accuracy_results.append(dist_ok and el_ok and az_ok)
    
    # Calculate accuracy statistics
    accurate_count = sum(accuracy_results)
    total_count = len(accuracy_results)
    accuracy_rate = accurate_count / total_count if total_count > 0 else 0
    
    print(f"  Tested {total_count} satellites:")
    print(f"    Accurate results: {accurate_count}/{total_count} ({accuracy_rate:.1%})")
    print(f"    Max distance diff: {max_dist_diff:.1f}m")
    print(f"    Max elevation diff: {max_el_diff:.6f}°")
    print(f"    Max azimuth diff: {max_az_diff:.6f}°")
    
    # Sample comparison for detailed inspection
    if len(individual_results) > 0:
        sample_idx = 0
        ind_result = individual_results[sample_idx]
        vec_result = vectorized_results[sample_idx]
        
        print(f"  Sample satellite {sample_idx}:")
        print(f"    Individual: dist={ind_result[0]:.1f}m, el={ind_result[1]:.6f}°, az={ind_result[2]:.6f}°")
        print(f"    Vectorized: dist={vec_result[0]:.1f}m, el={vec_result[1]:.6f}°, az={vec_result[2]:.6f}°")
        print(f"    Differences: dist={abs(ind_result[0]-vec_result[0]):.1f}m, el={abs(ind_result[1]-vec_result[1]):.6f}°, az={abs(ind_result[2]-vec_result[2]):.6f}°")
    
    accuracy_ok = accuracy_rate >= 0.95 and max_dist_diff < 1000 and max_el_diff < 0.1 and max_az_diff < 0.1
    
    # Results
    print(f"\n📊 PERFORMANCE COMPARISON:")
    print(f"  Individual avg:  {avg_individual*1000:.2f}ms")
    print(f"  Vectorized avg:  {avg_vectorized*1000:.2f}ms")
    print(f"  Speedup:         {speedup:.1f}x")
    print(f"  Improvement:     {improvement:.1f}%")
    print(f"  Time saved:      {time_saved:.2f}ms")
    print(f"  Accuracy:        {'✅ Good' if accuracy_ok else '❌ Poor'}")
    
    if not accuracy_ok:
        print(f"\n⚠️  ACCURACY ISSUES DETECTED:")
        if accuracy_rate < 0.95:
            print(f"    - Only {accuracy_rate:.1%} of results are accurate")
        if max_dist_diff >= 1000:
            print(f"    - Distance errors up to {max_dist_diff:.1f}m")
        if max_el_diff >= 0.1:
            print(f"    - Elevation errors up to {max_el_diff:.4f}°")
        if max_az_diff >= 0.1:
            print(f"    - Azimuth errors up to {max_az_diff:.4f}°")
    
    # Recommendation
    if improvement > 30 and accuracy_ok:
        print(f"\n✅ RECOMMENDATION: Deploy vectorized coordinate transformations!")
        print(f"   Expected API improvement: ~{improvement*0.24:.0f}% (coordinates are 24% of total time)")
        print(f"   Accuracy verified: {accuracy_rate:.1%} of results within tolerance")
    elif improvement > 10 and accuracy_ok:
        print(f"\n⚠️  RECOMMENDATION: Vectorization provides modest benefit ({improvement:.0f}%)")
        print(f"   Accuracy verified: {accuracy_rate:.1%} of results within tolerance")
    elif not accuracy_ok:
        print(f"\n❌ RECOMMENDATION: Accuracy issues prevent deployment")
        print(f"   Need to fix vectorization algorithm before use")
    else:
        print(f"\n❌ RECOMMENDATION: Vectorization not beneficial")
    
    return {
        'individual_avg_ms': avg_individual * 1000,
        'vectorized_avg_ms': avg_vectorized * 1000,
        'speedup': speedup,
        'improvement_pct': improvement,
        'accuracy_ok': accuracy_ok,
        'accuracy_rate': accuracy_rate,
        'max_dist_diff_m': max_dist_diff,
        'max_el_diff_deg': max_el_diff,
        'max_az_diff_deg': max_az_diff,
        'time_saved_ms': time_saved
    }


def integrate_with_existing_cache(cache_object, date, lat, lon, alt, elevation):
    """
    Integration function to use vectorized transforms with existing cache
    
    This function can replace the coordinate transformation loop in
    existing satellite cache objects for better performance.
    
    Args:
        cache_object: Existing satellite cache (e.g., GPSCache)
        date: UTC date for calculations
        lat: Latitude angle object
        lon: Longitude angle object
        alt: Altitude in meters
        elevation: Minimum elevation threshold
        
    Returns:
        List of satellite results with vectorized coordinate transformations
    """
    # Create vectorized transformer
    transformer = VectorizedCoordinateTransformer(location.Location(lat, lon, alt=alt))
    
    # Get satellite positions from cache
    satellites = cache_object.get_object(date).satellites
    
    # Extract ECEF positions for all satellites
    satellite_positions = []
    for sat in satellites:
        pos, vel = sat.get_position(date)
        satellite_positions.append(pos)
    
    # Vectorized coordinate transformation
    transform_results = transformer.transform_with_filtering(satellite_positions, elevation)
    
    # Build final results
    results = []
    for sat_idx, distance, el_deg, az_deg in transform_results:
        sat = satellites[sat_idx]
        results.append({
            "name": sat.name,
            "el": np.round(el_deg, decimals=6),
            "az": np.round(az_deg, decimals=6),
            "r": distance,
            "jy": cache_object.get_object(date).jansky
        })
    
    return results


if __name__ == "__main__":
    # Run benchmark when executed directly
    benchmark_vectorization()