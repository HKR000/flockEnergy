# Engineering Reflection: Urja Meter Ops Gateway

*Written candidly as part of the Flock Energy Software Assignment submission.*

---

### 1. What assumptions did you make?

* **Read-Heavy vs. Write-Heavy Profile:**  
  I assumed that in a real utility operations setting, field staff and analytics teams look up meter details, run geospatial queries, and check status thousands of times a day, whereas physical meter installations, nameplate attributes, and network hierarchy changes happen on batch schedules (e.g., overnight syncs or weekly commissioning). Building a high-throughput, in-memory local query layer that hydrates via bulk export is infinitely more practical than proxying every read live to a fragile, legacy government portal.

* **Coordinate System & Earth Curvature (Haversine Accuracy):**  
  I assumed meter coordinates are standard WGS-84 decimal latitude/longitude without elevation. For spatial proximity queries (`/api/v1/meters/nearby`), I chose the Haversine formula assuming a spherical Earth with radius $R = 6,371\text{ km}$. Within the geographic span of a single electricity distribution zone (e.g., Jaipur and surrounding circles, roughly 50–100 km across), ellipsoidal distortion error is under 0.3%—completely negligible for dispatching field technicians or grouping meters around distribution transformers.

* **Energy Register Semantics:**  
  Looking at `/portal/meters/{meterId}/energy`, I observed that `kwh` and `kvah` values increase monotonically over time (e.g., `48438.74`, `48439.16`, `48439.58`). I assumed these are cumulative register index counters rather than interval deltas. Therefore, net energy consumed in a 15-minute interval must be computed as $(kwh_{t} - kwh_{t-1})$.

* **Hierarchy Robustness & Data Messiness:**  
  I assumed that not every meter in legacy utility databases has a pristine 7-level hierarchy. Some meters could have missing feeder codes or orphaned DT references. I made parent hierarchy fields optional in the schema to ensure the parser never crashes on corrupted or partially filled legacy records.

---

### 2. Which part was the most difficult, and how did you get unstuck?

The most difficult hurdle was **unlocking the bulk export endpoint (`/portal/export`)**.

When exploring the portal UI, I saw an export option. But when I attempted to call `GET /portal/export` via Python with an authenticated session cookie, the server returned `401 Unauthorized` with an error indicating missing signature headers.

**How I got unstuck:**
1. I opened Chrome DevTools, went to the **Sources** and **Network** tabs, and triggered the export button in the UI.
2. I inspected the outgoing headers and noticed two custom headers: `x-timestamp` and `x-signature`.
3. I searched the client-side JavaScript chunk files for `/portal/export` and located the source in bundle `4.2Bgc2kUI.js`.
4. Reading the minified code, I found a call to `/portal/keys` which returned `{ data: { signingSecret: "..." } }`.
5. Right beneath it was the signature generator: it built a canonical string by joining the HTTP method, request path, query parameters, and epoch timestamp with newline characters (`\n`):
   $$\text{stringToSign} = \text{"GET\n/portal/export\npage=1\n"} + \text{timestamp}$$
   It then hashed this string using HMAC-SHA256 with the secret key and hex-encoded the result.
6. I replicated this logic in Python using the `hmac` and `hashlib` standard libraries. As soon as I fired the signed request, the portal immediately returned all 403 meters with complete hierarchies and coordinates in a single ~400ms payload. 

That was the turning point of the project: it meant I didn't need to write a fragile, slow scraper that hammered the utility's server with hundreds of sequential requests.

---

### 3. If you had another day, what would you improve?

1. **Spatial Indexing via SQLite/Spatialite or PostGIS:**  
   The current Haversine implementation scans the list of 403 cached meters in memory. It takes under 0.5 milliseconds for 403 items. However, if this utility had 500,000 smart meters across Rajasthan, a linear list scan would choke the CPU. With an extra day, I would back the cache with an embedded SQLite database using R-Tree spatial indexing (`rtree`) or PostgreSQL with PostGIS (`ST_DWithin`), providing logarithmic spatial lookup times.

2. **Automated Anomaly & Outage Detection:**  
   Utility operators care deeply about identifying dead meters. I would add background analytical heuristics to flag:
   * **Zero-consumption meters:** Meters showing identical kWh registers over 48+ hours.
   * **Low-voltage alerts:** Meters reporting phase voltage below 200V or sudden spikes above 250V.
   * **DT Overload risk:** Transformers where the aggregate connected meter load exceeds their rated capacity (kVA).

3. **Incremental Change Detection (ETags / Hashes):**  
   Instead of refreshing the entire export periodically, compute an MD5 hash of each meter's attributes to emit clean change events (`METER_STATUS_CHANGED`, `METER_REPLACED`) onto a message stream.

---

### 4. What mistake did you make while solving this?

**Mistake 1: The RESTful Assumption Trap.**  
Early on, after seeing `/portal/meters/search`, I assumed the portal had standard REST conventions and tried calling `GET /portal/meters/{meterId}` to retrieve single meter details. It returned `404 Not Found`. I spent 20 minutes double-checking URLs and authentication headers, wondering why the browser could render the meter page while my script received a 404.

It turned out Urja Meter Ops is a SvelteKit single-page application. When you navigate to a meter page, SvelteKit doesn't hit a `/portal/meters/{id}` API route; it fetches a serialized SSR payload at `/meters/{id}/__data.json` and renders it client-side. Realizing this prevented me from barking up the wrong tree, and pushed me to find the clean `/portal/export` endpoint instead.

**Mistake 2: Calling FastAPI Route Functions Directly in Unit Tests.**  
When writing unit tests for the routers, I initially called the router functions directly (e.g. `await list_meters(service=srv)`). In FastAPI, default parameter decorators like `Query(1)` and `Query(20)` remain instances of `fastapi.params.Query` if called directly without FastAPI's dependency injection container, leading to unexpected `TypeError: unsupported operand type for +: 'int' and 'Query'`. I fixed this by implementing defensive type normalization inside the service layer so functions operate cleanly both inside FastAPI and in isolated unit tests.

---

### 5. If you were reviewing your own submission, what would you criticise?

* **"Appropriately Sized" vs. "Over-Engineered":**  
  A critic might ask: *"Why didn't you use a database like PostgreSQL or Redis?"*  
  My defense: For 403 meters, adding Docker, PostgreSQL, and Redis containers would have been textbook over-engineering. An in-memory cache with zero external dependencies boots in 0.2 seconds, uses less than 20MB of RAM, and makes evaluation frictionless for any reviewer. But I acknowledge the architectural boundary: the moment data grows beyond ~50,000 meters, an external indexed database is mandatory.

* **On-Demand Telemetry Scraping:**  
  While meter summaries, hierarchies, and coordinates are bulk-cached, the 15-minute interval energy readings (`/api/v1/meters/{id}/consumption`) are still retrieved on-demand from `/portal/meters/{id}/energy` because the bulk export does not include time-series historical intervals. If a user requested consumption for all 403 meters concurrently, the legacy portal would be hit with 403 calls. In production, I would schedule a background queue (e.g., Celery or asyncio worker pool) to stagger historical interval telemetry ingestion.
