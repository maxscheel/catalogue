# Object Position Server

FastAPI-based satellite position server providing real-time GNSS and space object tracking data.

## Quick Start

### Docker (Recommended)
```bash
docker compose up --build
```
API available at http://localhost:8876

### Local Development
```bash
# Install dependencies
uv sync --dev

# Run server
uv run uvicorn main:app --host 0.0.0.0 --port 8876 --reload
```

## Development

### Linting & Type Checking
```bash
make lint      # Run ruff with auto-fix
make typecheck # Run ty type checker
```

### Testing
```bash
make test-client  # Run API tests
curl "http://localhost:8876/catalog?lat=-45.85&lon=170.54&elevation=10"
```

## API Endpoints

- `GET /catalog` - Satellite positions with az/el
- `GET /position/` - Raw ECEF coordinates
- `POST /bulk_az_el` - Bulk processing for multiple timestamps

Documentation: http://localhost:8876/docs

## Example Usage

### Basic Request
```bash
wget -qO- "http://localhost:8876/catalog?lat=-45.85&lon=170.54&elevation=10"
```

### Bulk Processing
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"lat": -45.85, "lon": 170.54, "dates": ["2024-01-15T12:00:00Z"]}' \
  "http://localhost:8876/bulk_az_el"
```

## More Accurate Power Estimates

Steigenberger, Peter, Steffen Thoelert, and Oliver Montenbruck. "GNSS satellite transmit power and its impact on orbit determination." Journal of Geodesy 92.6 (2018): 609-624.

Author: Tim Molteno (tim@elec.ac.nz), Max Scheel (max@elec.ac.nz)
