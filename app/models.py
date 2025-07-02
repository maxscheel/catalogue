"""
Pydantic Models for Satellite Catalogue API V2

This module contains all the Pydantic models used for request/response validation
and API documentation generation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# =============================================================================
# REQUEST MODELS
# =============================================================================

class BulkAzElRequest(BaseModel):
    """Request model for bulk azimuth/elevation calculations"""
    lat: float = Field(..., description="Observer latitude in degrees", example=-45.85, ge=-90, le=90)
    lon: float = Field(..., description="Observer longitude in degrees", example=170.54, ge=-180, le=180)
    elevation: Optional[float] = Field(0.0, description="Minimum elevation cutoff in degrees (satellites below this are filtered out)", example=10.0, ge=0, le=90)
    alt: Optional[float] = Field(0.0, description="Observer altitude above sea level in meters", example=100.0, ge=0)
    dates: List[str] = Field(..., description="List of ISO format datetime strings", example=["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"])

    class Config:
        json_schema_extra = {
            "example": {
                "lat": -45.85,
                "lon": 170.54,
                "elevation": 10.0,
                "alt": 100.0,
                "dates": [
                    "2024-01-15T12:00:00Z",
                    "2024-01-15T12:01:00Z",
                    "2024-01-15T12:02:00Z"
                ]
            }
        }

# =============================================================================
# SATELLITE DATA MODELS
# =============================================================================

class SatelliteInfo(BaseModel):
    """Individual satellite information"""
    name: str = Field(..., description="Satellite name or identifier", example="GPS BIIR-2")
    az: float = Field(..., description="Azimuth angle in degrees (0=North, 90=East)", example=125.5, ge=0, lt=360)
    el: float = Field(..., description="Elevation angle in degrees above horizon", example=45.2, ge=0, le=90)
    r: float = Field(..., description="Range/distance to satellite in meters", example=20234567.8)
    jy: Optional[float] = Field(None, description="Flux density in Jansky for radio astronomy", example=1e-4)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "GPS BIIR-2",
                "az": 125.5,
                "el": 45.2,
                "r": 20234567.8,
                "jy": 1e-4
            }
        }


class PositionInfo(BaseModel):
    """Individual satellite position information from cache"""
    name: str = Field(..., description="Satellite name or identifier", example="GPS BIIR-2")
    ecef: List[float] = Field(..., description="ECEF position coordinates [x, y, z] in meters", example=[12345678.9, -23456789.1, 34567890.2])
    ecef_dot: List[float] = Field(..., description="ECEF velocity vector [vx, vy, vz] in m/s", example=[1234.5, -2345.6, 3456.7])
    jy: float = Field(..., description="Flux density in Jansky for radio astronomy", example=1e-4)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "GPS BIIR-2",
                "ecef": [12345678.9, -23456789.1, 34567890.2],
                "ecef_dot": [1234.5, -2345.6, 3456.7],
                "jy": 1e-4
            }
        }

# =============================================================================
# RESPONSE MODELS
# =============================================================================

class BulkAzElResponse(BaseModel):
    """Response model for bulk azimuth/elevation calculations"""
    lat: float = Field(..., description="Observer latitude used", example=-45.85)
    lon: float = Field(..., description="Observer longitude used", example=170.54)
    alt: float = Field(..., description="Observer altitude used", example=100.0)
    dates: List[str] = Field(..., description="Input timestamps", example=["2024-01-15T12:00:00Z"])
    az_el: list[List[SatelliteInfo]] = Field(..., description="Catalog data for each timestamp - array of satellite arrays")

    class Config:
        json_schema_extra = {
            "example": {
                "lat": -45.85,
                "lon": 170.54,
                "alt": 100.0,
                "dates": ["2024-01-15T12:00:00Z", "2024-01-15T12:01:00Z"],
                "az_el": [
                    [
                        {
                            "name": "GPS BIIR-2",
                            "az": 125.5,
                            "el": 45.2,
                            "r": 20234567.8,
                            "jy": 1e-4
                        }
                    ],
                    [
                        {
                            "name": "GPS BIIR-3",
                            "az": 130.0,
                            "el": 50.0,
                            "r": 20100000.0,
                            "jy": 1e-4
                        }
                    ]
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str = Field(..., description="Error description", example="No catalog data found")

    class Config:
        json_schema_extra = {
            "example": {"detail": "No catalog data found"}
        }

# =============================================================================
# TYPE ALIASES
# =============================================================================

# Type aliases for cleaner endpoint definitions
CatalogResponse = List[SatelliteInfo]
PositionsResponse = List[PositionInfo]
