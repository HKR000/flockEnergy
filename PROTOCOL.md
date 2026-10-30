# Urja Meter Ops: Protocol & Reverse-Engineering Analysis

This document provides a technical breakdown of how the **Urja Meter Ops** legacy portal (`https://urja-ops.flockenergy.tech`) actually functions under the hood, how its internal data was discovered and reverse-engineered, and the design decisions made to build a clean, resilient API service in front of it.

---

## 1. Architectural Overview

The Urja Meter Ops portal is built with **SvelteKit** and serves field operators looking up smart meter installations, distribution network structures, and 15-minute interval energy telemetry. 

While the web UI presents human-friendly tables and detail pages, the system has **no official public API**. All programmatic consumption requires reverse-engineering its internal endpoints, session mechanics, and client-side JavaScript bundles.

---

## 2. Authentication & Session Management

### 2.1 Login Mechanism
* **Endpoint:** `POST https://urja-ops.flockenergy.tech/login`
* **Content-Type:** `application/x-www-form-urlencoded`
* **Credentials:**
  * `email`: `operator@urja.local`
  * `password`: `urja-ops-2026`
* **Session Transport:**
  * Upon successful authentication (`302 Redirect` or `200 OK`), the server sets a session cookie (e.g. `urja_session` or standard session cookie).
  * Subsequent requests must carry this cookie along with standard browser headers (`User-Agent`, `Referer`, `Origin`).
  * Authentication sessions have a finite lifetime; our integration client automatically re-authenticates upon detecting `401 Unauthorized` or redirect to `/login`.

---

## 3. Discovered Endpoints & Protocols

Through network trace analysis and static analysis of the client bundles (e.g. `4.2Bgc2kUI.js`, `6.l777LXKL.js`), the following internal endpoints were identified:

### 3.1 Meter Search (`GET /portal/meters/search`)
* **URL:** `/portal/meters/search?q={query}&page={page}`
* **Returns:** Basic paginated meter summaries (403 total meters across the utility).
* **Payload Structure:**
  ```json
  {
    "total": 403,
    "page": 1,
    "pageSize": 20,
    "data": [
      {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Installed",
        "dtCode": "DT-001"
      }
    ]
  }
  ```
* **Limitation:** The search query parameter `q` only filters against `meterId` and `serialNo`. It is impossible on the legacy portal to filter by manufacturer (`make`), phase (`single`/`three`), operational status, or feeder code.

---

### 3.2 Distribution Transformers (`GET /portal/dts`)
* **URL:** `/portal/dts?page={page}`
* **Returns:** Paginated list of Distribution Transformers (40 total DTs).
* **Payload Structure:**
  ```json
  {
    "total": 40,
    "page": 1,
    "pageSize": 20,
    "data": [
      {
        "code": "DT-001",
        "name": "Malviya Nagar DT 1",
        "feederCode": "F-001",
        "capacityKva": 100
      }
    ]
  }
  ```

---

### 3.3 Signing Secret Key (`GET /portal/keys`)
* **URL:** `/portal/keys`
* **Authentication:** Authenticated session cookie required.
* **Returns:** The dynamic signing secret used by client scripts to authenticate export requests:
  ```json
  {
    "data": {
      "signingSecret": "I3dZPPf5CgTp7JyGNMI8i6z8LFR7TmSR"
    }
  }
  ```

---

### 3.4 Cryptographic Bulk Export (`GET /portal/export`)
* **URL:** `/portal/export?page={page}`
* **Authentication:** Session cookie **AND** HMAC-SHA256 signature headers.
* **Signature Algorithm (Discovered in `4.2Bgc2kUI.js`):**
  1. Retrieve `signingSecret` from `/portal/keys`.
  2. Compute current UTC UNIX epoch timestamp (seconds): `ts = str(int(time.time()))`.
  3. Form canonical string to sign:
     $$\text{string\_to\_sign} = \text{"GET"} + \text{"\textbackslash n"} + \text{path} + \text{"\textbackslash n"} + \text{query} + \text{"\textbackslash n"} + \text{ts}$$
     Example: `GET\n/portal/export\npage=1\n1793340000`
  4. Generate HMAC-SHA256 digest in lowercase hexadecimal.
  5. Send request with headers:
     * `x-timestamp`: `{ts}`
     * `x-signature`: `{hex_digest}`
* **Payload:**
  Returns full dumps of all 403 meters containing:
  * Complete meter attributes (`meterId`, `serialNo`, `make`, `phaseType`, `installStatus`, `installType`, `build`).
  * 7-Level Network Hierarchy (`zone`, `circle`, `division`, `subdivision`, `substation`, `feeder`, `dt`).
  * Precise coordinates (`geo.lat`, `geo.lng`).

---

### 3.5 Individual Telemetry & Detail Endpoints

1. **Geolocation:** `GET /portal/meters/{meterId}/geo`
   * Returns: `{"data": {"latitude": "26.9389...", "longitude": "75.8309..."}}`
   * *Quirk:* Coordinates are string representations of floats.

2. **Energy Interval Telemetry:** `GET /portal/meters/{meterId}/energy`
   * Returns interval readings (up to ~337 interval rows per meter):
     ```json
     [
       {
         "timestamp": "23/06/2026 23:30",
         "kwh": "48438.74",
         "kvah": "52313.84",
         "voltR": "226"
       }
     ]
     ```
   * *Quirks:* Timestamps use Indian format `DD/MM/YYYY HH:MM`. All numeric telemetry fields (`kwh`, `kvah`, `voltR`) are passed as strings. Cumulative kilowatt-hour values require delta calculation to extract periodic consumption.

3. **Meter Detail 404 Quirk:**
   * Calling `GET /portal/meters/{meterId}` returns a `404 Not Found`.
   * The web application uses SvelteKit SSR JSON serialization located at:
     `GET /meters/{meterId}/__data.json`
   * However, using `/portal/export` eliminates the need to scrape individual SvelteKit serialization buffers because `/portal/export` provides the complete normalized dataset in a single cryptographic call.

---

## 4. Integration Strategy & Architecture

| Problem in Legacy Portal | Solution in Gateway API |
| :--- | :--- |
| **No multi-attribute filtering** | Local indexed query engine allowing filtering by `make`, `phase`, `status`, `build`, `feeder`, and `dt`. |
| **No spatial queries** | Built-in geospatial indexing with Haversine spherical distance calculation (`/api/v1/meters/nearby`). |
| **No clean hierarchy tree** | Reconstructed hierarchical graph (`Zone -> Circle -> Division -> SubDivision -> SubStation -> Feeder -> DT -> Meters`). |
| **Rate limits / fragile upstream** | Bulk export hydration cached in memory with TTL freshness monitoring and background refresh. |
| **String-typed messy metrics** | Pydantic data normalization with strict typing, ISO-8601 timestamps, and energy deltas. |
