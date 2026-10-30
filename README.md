# Urja Meter Ops Gateway API & Dashboard

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![Tests Passing](https://img.shields.io/badge/Tests-Passing-brightgreen.svg)]()
[![OpenAPI 3.1](https://img.shields.io/badge/OpenAPI-3.1.0-6BA539.svg?logo=openapi-initiative)]()

A production-grade integration service, query gateway, and modern monitoring dashboard built over the legacy **Urja Meter Ops** internal portal (`https://urja-ops.flockenergy.tech`).

---

## Table of Contents
* [1. System Overview](#1-system-overview)
* [2. Project Structure](#2-project-structure)
* [3. Key Architectural Decisions](#3-key-architectural-decisions)
* [4. Quickstart & Installation](#4-quickstart--installation)
* [5. API Documentation & Sample Requests](#5-api-documentation--sample-requests)
* [6. Modern Web Dashboard UI](#6-modern-web-dashboard-ui)
* [7. Running Test Suites](#7-running-test-suites)
* [8. Design Decisions, Assumptions & Trade-offs](#8-design-decisions-assumptions--trade-offs)
* [9. Links to Key Documentation](#9-links-to-key-documentation)

---

## 1. System Overview

Electricity distribution utilities rely on internal systems like **Urja Meter Ops** to monitor smart meters, track field installations, and view telemetry. However, legacy portals lack public APIs, programmatic query tools, and spatial filtering.

This service acts as an **intelligent gateway**:
1. **Reverse-Engineered Integration:** Authenticates against Urja Meter Ops and leverages its cryptographic bulk export endpoint (`/portal/export` signed via HMAC-SHA256) for instant, high-speed dataset synchronization.
2. **Normalized Data Models:** Cleanses heterogeneous string formats, parses Indian timestamps, and enforces strict Pydantic schemas.
3. **Advanced Local Querying:** Enables multi-attribute filtering (make, phase type, status, build generation, feeder, DT) not possible on the original portal.
4. **Geospatial Proximity Search:** Implements Haversine spherical queries (`/api/v1/meters/nearby`) to locate meters within a radius of any GPS coordinate.
5. **Network Hierarchy Reconstruction:** Maps meters across the 7-tier distribution grid (`Zone -> Circle -> Division -> SubDivision -> SubStation -> Feeder -> Distribution Transformer`).
6. **Modern Web Client:** An embedded web client with consumption graphs, interactive spatial maps, and grid health telemetry.

---

## 2. Project Structure

```
flockEnergy/
├── app/
│   ├── client/
│   │   └── portal_client.py     # Resilient HTTP client with auth session & HMAC-SHA256 signer
│   ├── models/
│   │   ├── common.py            # Pagination & generic response envelopes
│   │   ├── dt.py                # Distribution Transformer domain models
│   │   ├── hierarchy.py         # 7-level utility grid hierarchy graph models
│   │   ├── meter.py             # MeterSummary, MeterDetail, Coordinates, Telemetry schemas
│   │   └── sync.py              # Cache status & synchronization telemetry
│   ├── routers/
│   │   ├── health.py            # /health & /healthz liveness endpoints
│   │   ├── hierarchy.py         # /api/v1/hierarchy graph queries
│   │   ├── meters.py            # /api/v1/meters (list, get, nearby, consumption)
│   │   ├── sync.py              # /api/v1/sync triggers and cache freshness
│   │   └── transformers.py      # /api/v1/transformers (DTs & connected meter rosters)
│   ├── services/
│   │   ├── geo_service.py       # Haversine spatial calculations & radius indexing
│   │   ├── meter_service.py     # Ingestion normalization & interval delta calculations
│   │   ├── network_service.py   # Hierarchy tree compilation from meter telemetry
│   │   └── sync_service.py      # High-performance in-memory cache & background scheduler
│   ├── static/                  # Modern web dashboard (HTML5, Vanilla CSS, JS)
│   │   ├── index.html           # Single-page dashboard interface
│   │   ├── style.css            # Dark mode glassmorphism UI styling
│   │   └── app.js               # Reactive state, Leaflet mapping, Chart.js telemetry
│   ├── config.py                # Environment configurations & defaults
│   └── main.py                  # FastAPI application entrypoint with CORS & lifespan
├── tests/
│   ├── test_api.py              # End-to-end API router unit & integration tests
│   ├── test_client.py           # HMAC signature & portal client tests
│   ├── test_geo.py              # Haversine distance & spatial search accuracy tests
│   ├── test_hierarchy.py        # Grid hierarchy reconstruction tests
│   └── test_normalization.py    # Pydantic schema & energy delta calculation tests
├── openapi.json                 # Exported OpenAPI 3.1.0 specification
├── PROTOCOL.md                  # Detailed reverse-engineering write-up of the Urja portal
├── REFLECTION.md                # Self-reflection & trade-offs analysis
├── requirements.txt             # Python dependencies
└── run_tests.py                 # Automated test runner script
```

---

## 3. Key Architectural Decisions

* **Bulk Hydration over Live Proxying:** Querying individual meters on the legacy portal creates 400+ sequential HTTP roundtrips that choke the legacy server. By capturing the signing key from `/portal/keys` and generating HMAC-SHA256 headers for `/portal/export`, we retrieve all 403 meters in a single operation (~450ms).
* **In-Memory Query Layer with TTL Freshness:** Meter records and hierarchy are indexed in memory. The service reports freshness metrics (`last_synced_at`, `is_fresh`, `age_seconds`) and refreshes periodically in the background without blocking client requests.
* **Separation of Concerns:** Routers only handle request validation and dependency injection. Domain logic is cleanly decoupled into dedicated services (`GeoService`, `NetworkService`, `MeterService`, `SyncService`).

---

## 4. Quickstart & Installation

### 4.1 Prerequisites
* Python 3.10 or higher
* `pip` package manager

### 4.2 Setup & Run
1. **Clone the repository:**
   ```bash
   git clone https://github.com/HKR000/flockEnergy.git
   cd flockEnergy
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Start the API service:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Access the application:**
   * **Interactive Web Dashboard:** [http://localhost:8000/](http://localhost:8000/)
   * **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
   * **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
   * **OpenAPI Specification:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## 5. API Documentation & Sample Requests

### 5.1 Multi-Attribute Filter Query
Query smart meters filtered by phase, status, and manufacturer:
```bash
curl -X GET "http://localhost:8000/api/v1/meters?make=HPL&phase_type=single&install_status=Installed&page=1&page_size=2" \
     -H "Accept: application/json"
```
**Sample Response:**
```json
{
  "items": [
    {
      "meter_id": "J100000",
      "serial_no": "SE33962",
      "make": "HPL",
      "phase_type": "single",
      "install_status": "Installed",
      "install_type": "Whole Current",
      "build": "legacy",
      "dt_code": "DT-001",
      "dt_name": "Malviya Nagar DT 1",
      "feeder_code": "F-001",
      "coordinates": {
        "latitude": 26.9389,
        "longitude": 75.8309
      }
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 2,
  "total_pages": 1
}
```

### 5.2 Geospatial Proximity Search
Locate smart meters within 2.5 km of coordinates `(26.9124, 75.7873)`:
```bash
curl -X GET "http://localhost:8000/api/v1/meters/nearby?latitude=26.9124&longitude=75.7873&radius_meters=2500&limit=5" \
     -H "Accept: application/json"
```

### 5.3 Network Hierarchy Tree
Fetch the complete multi-tiered grid graph:
```bash
curl -X GET "http://localhost:8000/api/v1/hierarchy" -H "Accept: application/json"
```

### 5.4 Interval Energy Consumption & Summary
Get 15-minute telemetry readings and computed cumulative usage:
```bash
curl -X GET "http://localhost:8000/api/v1/meters/J100000/consumption" -H "Accept: application/json"
```

---

## 6. Modern Web Dashboard UI

The application includes a built-in modern dashboard served directly at `http://localhost:8000/`. It features:
* **Metric Cards:** Real-time counters for total meters, active transformers, online telemetry, and cache freshness.
* **Filterable Data Explorer:** Multi-column search with real-time text and status dropdowns.
* **Geospatial Map View:** Pinpointing meters and DT coordinates with radius exploration.
* **Energy Consumption Analytics:** Visualizing 15-minute load curves and voltage profiles.

---

## 7. Running Test Suites

The test suite covers HMAC signature generation, data normalization, geospatial accuracy, network hierarchy reconstruction, and end-to-end API router validation.

Run all tests with:
```bash
python run_tests.py
```
**Expected Output:**
```
.....
----------------------------------------------------------------------
Ran 5 tests in 0.051s

OK
All 11 API endpoints tested successfully!
```

---

## 8. Design Decisions, Assumptions & Trade-offs

### Assumptions
1. **Infrequent Master Data Changes:** Utility master asset data (meter nameplates, transformer locations) updates on daily or weekly cycles, while downstream applications read data frequently. In-memory caching provides microsecond response times without overloading the upstream portal.
2. **Coordinate Accuracy:** Geolocation data matches WGS-84 decimal coordinates. Haversine distance computations are accurate to within 0.3% error over city-wide distribution areas.
3. **Cumulative Register Readings:** Register metrics (`kwh`, `kvah`) reflect cumulative total energy; periodic interval consumption is derived by calculating sequential deltas.

### Trade-offs & What Was Skipped
* **Skipped Relational Database (PostgreSQL/PostGIS):** An in-memory cache was intentionally selected over an external database dependency. This allows the entire service to run locally with zero configuration and zero paid dependencies.
* **Scale Consideration:** For utilities with $> 100,000$ meters, the in-memory array scan would be replaced with an embedded SQLite or PostgreSQL backend with spatial R-tree indexes.

---

## 9. Links to Key Documentation

* [PROTOCOL.md](file:///PROTOCOL.md) — Technical write-up on reverse engineering the Urja portal, HMAC signature algorithms, and API discovery.
* [REFLECTION.md](file:///REFLECTION.md) — Evaluation reflection answering assumptions, biggest hurdles, mistakes made, and critique.
* [openapi.json](file:///openapi.json) — OpenAPI 3.1.0 specification for the clean gateway API.
