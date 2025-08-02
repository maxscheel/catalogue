"""
API Response Examples for Satellite Catalogue API V2

This module contains all the example data used in FastAPI endpoint documentation
to keep the main API file clean and maintainable.
"""

# =============================================================================
# SATELLITE DATA EXAMPLES
# =============================================================================

SATELLITE_INFO_EXAMPLES = {
    "gps_example": {
        "name": "GPS BIIR-2",
        "az": 125.5,
        "el": 45.2,
        "r": 20234567.8,
        "jy": 1e-4,
    },
    "galileo_example": {
        "name": "GALILEO-22",
        "az": 280.1,
        "el": 35.7,
        "r": 23456789.1,
        "jy": 1e-4,
    },
    "beidou_example": {
        "name": "BEIDOU-3 M14",
        "az": 91.5,
        "el": 75.8,
        "r": 21677345.2,
        "jy": 1e-4,
    },
    "sun_example": {
        "name": "Sun",
        "az": 180.0,
        "el": 30.0,
        "r": 149597870700.0,
        "jy": 1000000.0,
    },
}

POSITION_INFO_EXAMPLES = {
    "gps_position": {
        "name": "GPS BIIR-2",
        "ecef": [12345678.9, -23456789.1, 34567890.2],
        "ecef_dot": [1234.5, -2345.6, 3456.7],
        "jy": 1e-4,
    },
    "galileo_position": {
        "name": "GALILEO-FM2",
        "ecef": [9876543.2, 8765432.1, -7654321.0],
        "ecef_dot": [-987.6, 876.5, 765.4],
        "jy": 1e-4,
    },
}

# =============================================================================
# CATALOG RESPONSE EXAMPLES
# =============================================================================

CATALOG_EXAMPLES = {
    "christchurch_location": {
        "summary": "Christchurch, New Zealand example",
        "value": [
            SATELLITE_INFO_EXAMPLES["gps_example"],
            SATELLITE_INFO_EXAMPLES["galileo_example"],
            SATELLITE_INFO_EXAMPLES["sun_example"],
        ],
    },
    "high_elevation_filter": {
        "summary": "High elevation filter example",
        "value": [
            SATELLITE_INFO_EXAMPLES["beidou_example"],
            {**SATELLITE_INFO_EXAMPLES["sun_example"], "el": 45.0},
        ],
    },
}

POSITIONS_EXAMPLES = {
    "cached_positions": {
        "summary": "Cached satellite positions",
        "value": [
            POSITION_INFO_EXAMPLES["gps_position"],
            POSITION_INFO_EXAMPLES["galileo_position"],
        ],
    },
}

# =============================================================================
# BULK RESPONSE EXAMPLES
# =============================================================================

BULK_AZ_EL_EXAMPLES = {
    "bulk_processing": {
        "summary": "Bulk processing example with multiple timestamps",
        "value": {
            "lat": -45.85,
            "lon": 170.54,
            "alt": 100.0,
            "dates": ["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"],
            "az_el": [
                [
                    SATELLITE_INFO_EXAMPLES["gps_example"],
                ],
                [
                    {
                        **SATELLITE_INFO_EXAMPLES["gps_example"],
                        "az": 130.0,
                        "el": 50.0,
                        "r": 20100000.0,
                    },
                ],
            ],
        },
    },
}

# =============================================================================
# HEALTH CHECK EXAMPLES
# =============================================================================

HEALTH_EXAMPLES = {
    "healthy_service": {
        "summary": "Healthy service response",
        "value": {
            "status": "healthy",
            "timestamp": "2024-01-15T12:00:00.123456Z",
            "cache_active": True,
            "event_loop": "uvloop",
            "version": "clean",
        },
    },
}

# =============================================================================
# REQUEST EXAMPLES
# =============================================================================

BULK_REQUEST_EXAMPLES = {
    "time_series_analysis": {
        "summary": "Time series analysis over 3 minutes",
        "value": {
            "lat": -45.85,
            "lon": 170.54,
            "elevation": 10.0,
            "alt": 100.0,
            "dates": [
                "2024-01-15T12:00:00Z",
                "2024-01-15T12:01:00Z",
                "2024-01-15T12:02:00Z",
            ],
        },
    },
    "radio_telescope": {
        "summary": "Radio telescope pointing schedule",
        "value": {
            "lat": -43.53,
            "lon": 172.64,
            "elevation": 20.0,
            "alt": 50.0,
            "dates": [
                "2024-01-15T12:00:00Z",
                "2024-01-15T12:05:00Z",
                "2024-01-15T12:10:00Z",
            ],
        },
    },
}

# =============================================================================
# ERROR EXAMPLES
# =============================================================================

ERROR_EXAMPLES = {
    "no_data_found": {
        "summary": "No catalog data available",
        "value": {"detail": "No catalog data found"},
    },
    "invalid_coordinates": {
        "summary": "Invalid latitude/longitude",
        "value": {"detail": "Latitude must be between -90 and 90 degrees"},
    },
    "internal_error": {
        "summary": "Internal server error",
        "value": {"detail": "Cache manager initialization failed"},
    },
}
