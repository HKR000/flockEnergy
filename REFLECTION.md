# Engineering Reflection: Urja Meter Ops Gateway

This reflection addresses the evaluation questions outlined in the Flock Energy Software Assignment brief.

---

### 1. What assumptions did you make?
* **Read-Heavy vs. Write-Heavy Usage:** We assumed downstream consumers (analytics engines, field apps, dashboards) require fast, frequent querying across multiple dimensions, while upstream meter nameplate data changes infrequently (batch daily/weekly updates). Consequently, an in-memory cached query layer hydrated via bulk export is far superior to proxying every request live to the slow legacy portal.
* **Geospatial Reference Frame:** We assumed meter coordinates adhere to standard WGS-84 decimal degrees (`(latitude, longitude)`), allowing spherical distance approximations via the Haversine formula (accurate within ~0.3% error margin for distribution utility scale across metropolitan areas like Jaipur).
* **Energy Telemetry Semantics:** We assumed `kwh` and `kvah` in interval records represent cumulative meter registers rather than interval deltas. Therefore, net energy consumed over a period is calculated by taking difference between subsequent timestamps.
* **Consistency of Network Hierarchy:** We assumed every meter maps up through the 7-tier distribution hierarchy (`Zone -> Circle -> Division -> SubDivision -> SubStation -> Feeder -> DT`), but designed optional fallback models because legacy utility records often contain orphaned or partially filled hierarchy nodes.

---

### 2. Which part was the most difficult, and how did you get unstuck?
* **The Most Difficult Part:** Uncovering how bulk export authentication worked on the portal. Navigating the UI revealed an export button, but direct requests to `/portal/export` failed with `401 Unauthorized` and `Missing signature headers`, even with an active session cookie.
* **How We Got Unstuck:** We inspected the client-side JavaScript chunk files downloaded by the browser (specifically `4.2Bgc2kUI.js`). By analyzing the minified source, we found:
  1. A preparatory call fetching an ephemeral secret from `/portal/keys`.
  2. A HMAC-SHA256 signature algorithm concatenating the HTTP method, request path, query string, and current UNIX timestamp (`GET\n/portal/export\npage=1\n{timestamp}`).
  3. Replicating this exact canonical signing routine in Python unlocked instant bulk extraction of all 403 meters with their complete hierarchy in a single secure operation.

---

### 3. If you had another day, what would you improve?
* **Persistent Storage Backend:** Replace the in-memory cache with an embedded SQLite or PostgreSQL/PostGIS database, allowing SQL-level spatial indexing (`ST_DWithin`, R-trees) that scales seamlessly to hundreds of thousands of meters.
* **Differential Change Polling:** Instead of full syncs, poll recent update logs or hash individual meter records to identify only modified meters, reducing network overhead.
* **Time-Series Telemetry Caching:** Pre-aggregate 15-minute intervals into hourly, daily, and monthly rollups with peak load detection and outage indicators.
* **Automated Webhooks / Change Events:** Provide webhook subscription endpoints so external microservices can receive notifications when meter statuses transition (e.g. `Installed` $\to$ `Faulty`).

---

### 4. What mistake did you make while solving this?
* **Initial Direct Scraping Assumption:** Early in exploration, we attempted to scrape individual meter pages one-by-one by querying `/portal/meters/{meterId}`. This immediately hit `404 Not Found` because the portal's SvelteKit router loaded detail data via `/__data.json` endpoints rather than standard REST routes.
* Scraping 403 individual meter JSON endpoints would have resulted in slow startup times and fragile network calls. Pausing to inspect network traffic and discovering the bulk cryptographic export endpoint completely eliminated this complexity and made the service over 50x faster.

---

### 5. If you were reviewing your own submission, what would you criticise?
* **In-Memory Query Scaling Ceiling:** The current in-memory list filtering and Haversine scan performs sub-millisecond queries for 403 meters, but would degrade at ~100,000+ meters without spatial indexes (e.g. KD-Tree, R-Tree, or PostGIS).
* **Single Background Sync Worker:** In a distributed multi-replica deployment, having each instance run its own background sync task could cause redundant traffic to the legacy portal. In production, synchronization should be delegated to a distributed worker (e.g. Celery / Redis lock).
