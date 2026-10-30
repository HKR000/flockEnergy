// State
let currentPage = 1;
let totalPages = 1;
let searchDebounceTimer = null;
let leafletMap = null;
let mapMarkers = [];
let consumptionChartInstance = null;
let overviewStatusChartInstance = null;
let overviewMakeChartInstance = null;

// Tab Switching
function switchTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active-tab"));
  const activeBtn = document.getElementById(`tab-${tabName}`);
  if (activeBtn) activeBtn.classList.add("active-tab");

  ["overview", "meters", "map", "hierarchy", "transformers"].forEach(name => {
    const el = document.getElementById(`view-${name}`);
    if (el) {
      if (name === tabName) {
        el.classList.remove("hidden");
      } else {
        el.classList.add("hidden");
      }
    }
  });

  if (tabName === "map") {
    setTimeout(initMap, 200);
  } else if (tabName === "hierarchy") {
    loadHierarchy();
  } else if (tabName === "transformers") {
    loadTransformers();
  }
}

// Initial Load
document.addEventListener("DOMContentLoaded", async () => {
  await loadOverviewStats();
  await loadMeters(1);
});

// Overview Stats & Charts
async function loadOverviewStats() {
  try {
    const res = await fetch("/api/v1/sync/status");
    const syncStatus = await res.json();

    document.getElementById("stat-total").innerText = syncStatus.total_meters_cached;
    document.getElementById("stat-dts").innerText = syncStatus.total_transformers_cached;

    const cacheEl = document.getElementById("stat-cache");
    cacheEl.innerText = syncStatus.is_fresh ? "Fresh (TTL OK)" : "Stale / Refreshing";
    cacheEl.className = syncStatus.is_fresh ? "text-sm font-bold text-emerald-600 mt-2" : "text-sm font-bold text-amber-600 mt-2";

    if (syncStatus.last_synced_at) {
      const dt = new Date(syncStatus.last_synced_at);
      document.getElementById("stat-synced-at").innerText = `Last sync: ${dt.toLocaleTimeString()}`;
    }

    // Load meter aggregations
    const metersRes = await fetch("/api/v1/meters?page=1&page_size=500");
    const metersData = await metersRes.json();
    const items = metersData.items;

    let installed = 0, faulty = 0, decomm = 0;
    const makeCounts = {};

    items.forEach(m => {
      if (m.install_status === "Installed") installed++;
      else if (m.install_status === "Faulty") faulty++;
      else if (m.install_status === "Decommissioned") decomm++;

      makeCounts[m.make] = (makeCounts[m.make] || 0) + 1;
    });

    document.getElementById("stat-installed").innerText = installed;
    document.getElementById("stat-faulty").innerText = faulty;
    document.getElementById("stat-decomm").innerText = decomm;

    renderOverviewCharts(installed, faulty, decomm, makeCounts);
  } catch (err) {
    console.error("Failed to load overview stats:", err);
  }
}

function renderOverviewCharts(installed, faulty, decomm, makeCounts) {
  // Status chart
  const statusCtx = document.getElementById("overviewStatusChart");
  if (statusCtx) {
    if (overviewStatusChartInstance) overviewStatusChartInstance.destroy();
    overviewStatusChartInstance = new Chart(statusCtx, {
      type: "doughnut",
      data: {
        labels: ["Installed", "Faulty", "Decommissioned"],
        datasets: [{
          data: [installed, faulty, decomm],
          backgroundColor: ["#10b981", "#f43f5e", "#f59e0b"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom" } }
      }
    });
  }

  // Make chart
  const makeCtx = document.getElementById("overviewMakeChart");
  if (makeCtx) {
    if (overviewMakeChartInstance) overviewMakeChartInstance.destroy();
    overviewMakeChartInstance = new Chart(makeCtx, {
      type: "bar",
      data: {
        labels: Object.keys(makeCounts),
        datasets: [{
          label: "Meters Count",
          data: Object.values(makeCounts),
          backgroundColor: "#3b82f6"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } }
      }
    });
  }
}

// Meters Explorer
function debounceMeters() {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => loadMeters(1), 250);
}

async function loadMeters(page = 1) {
  currentPage = page;
  const q = document.getElementById("filter-search").value.trim();
  const status = document.getElementById("filter-status").value;
  const phase = document.getElementById("filter-phase").value;
  const make = document.getElementById("filter-make").value;
  const build = document.getElementById("filter-build").value;

  const params = new URLSearchParams({ page, page_size: 20 });
  if (q) params.append("q", q);
  if (status) params.append("install_status", status);
  if (phase) params.append("phase_type", phase);
  if (make) params.append("make", make);
  if (build) params.append("build", build);

  const tbody = document.getElementById("meters-table-body");
  tbody.innerHTML = `<tr><td colspan="9" class="px-4 py-8 text-center text-slate-400">Loading meters...</td></tr>`;

  try {
    const res = await fetch(`/api/v1/meters?${params.toString()}`);
    const data = await res.json();
    totalPages = data.total_pages;

    document.getElementById("page-total").innerText = data.total;
    document.getElementById("page-start").innerText = data.total > 0 ? (page - 1) * 20 + 1 : 0;
    document.getElementById("page-end").innerText = Math.min(page * 20, data.total);
    document.getElementById("page-indicator").innerText = `Page ${data.page} of ${Math.max(1, data.total_pages)}`;

    document.getElementById("btn-prev").disabled = page <= 1;
    document.getElementById("btn-next").disabled = page >= data.total_pages;

    if (data.items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="px-4 py-8 text-center text-slate-400">No meters found matching criteria.</td></tr>`;
      return;
    }

    tbody.innerHTML = data.items.map(m => {
      let badgeClass = "badge-installed";
      if (m.install_status === "Faulty") badgeClass = "badge-faulty";
      if (m.install_status === "Decommissioned") badgeClass = "badge-decommissioned";

      return `
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="px-4 py-3 font-semibold text-slate-900">${m.meter_id}</td>
          <td class="px-4 py-3 text-slate-600 font-mono text-xs">${m.serial_no}</td>
          <td class="px-4 py-3 text-slate-700 font-medium">${m.make}</td>
          <td class="px-4 py-3 text-slate-600">${m.phase_type}</td>
          <td class="px-4 py-3"><span class="badge ${badgeClass}">${m.install_status}</span></td>
          <td class="px-4 py-3 text-slate-600 font-mono text-xs">${m.dt_code || "—"}</td>
          <td class="px-4 py-3 text-slate-600 font-mono text-xs">${m.feeder_code || "—"}</td>
          <td class="px-4 py-3"><span class="px-2 py-0.5 text-[10px] rounded font-mono ${m.build === 'v2' ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-600'}">${m.build || 'legacy'}</span></td>
          <td class="px-4 py-3 text-right">
            <button onclick="openMeterModal('${m.meter_id}')" class="text-xs bg-slate-900 hover:bg-slate-800 text-white px-2.5 py-1 rounded-md transition-colors font-medium">Inspect</button>
          </td>
        </tr>
      `;
    }).join("");
  } catch (err) {
    console.error("Failed to load meters:", err);
    tbody.innerHTML = `<tr><td colspan="9" class="px-4 py-8 text-center text-rose-500">Failed to load meters.</td></tr>`;
  }
}

function prevPage() {
  if (currentPage > 1) loadMeters(currentPage - 1);
}

function nextPage() {
  if (currentPage < totalPages) loadMeters(currentPage + 1);
}

// Live Map
async function initMap() {
  const container = document.getElementById("map-container");
  if (!leafletMap) {
    // Center roughly around Jaipur coordinates from dataset (26.91, 75.8)
    leafletMap = L.map("map-container").setView([26.9124, 75.7873], 12);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap contributors"
    }).addTo(leafletMap);
  } else {
    leafletMap.invalidateSize();
  }

  // Clear existing markers
  mapMarkers.forEach(m => leafletMap.removeLayer(m));
  mapMarkers = [];

  try {
    const res = await fetch("/api/v1/meters?page=1&page_size=500");
    const data = await res.json();
    const bounds = [];

    data.items.forEach(m => {
      if (!m.coordinates) return;
      const lat = m.coordinates.latitude;
      const lng = m.coordinates.longitude;
      bounds.push([lat, lng]);

      let color = "#10b981"; // green
      if (m.install_status === "Faulty") color = "#f43f5e"; // red
      if (m.install_status === "Decommissioned") color = "#f59e0b"; // amber

      const marker = L.circleMarker([lat, lng], {
        radius: 6,
        fillColor: color,
        color: "#ffffff",
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.85
      }).addTo(leafletMap);

      marker.bindPopup(`
        <div class="font-sans text-xs space-y-1">
          <p class="font-bold text-sm text-slate-900">${m.meter_id} (${m.make})</p>
          <p><span class="text-slate-500">Serial:</span> ${m.serial_no}</p>
          <p><span class="text-slate-500">Status:</span> ${m.install_status}</p>
          <p><span class="text-slate-500">DT:</span> ${m.dt_code || '—'}</p>
          <button onclick="openMeterModal('${m.meter_id}')" class="mt-2 w-full text-center bg-slate-900 text-white py-1 px-2 rounded font-medium text-xs">Inspect Details</button>
        </div>
      `);

      mapMarkers.push(marker);
    });

    if (bounds.length > 0) {
      leafletMap.fitBounds(bounds, { padding: [30, 30] });
    }
  } catch (err) {
    console.error("Failed to load map markers:", err);
  }
}

// Hierarchy Explorer
async function loadHierarchy() {
  const container = document.getElementById("hierarchy-tree-container");
  container.innerHTML = "Loading network topology tree...";

  try {
    const res = await fetch("/api/v1/hierarchy");
    const data = await res.json();

    function renderNode(node) {
      const hasChildren = node.children && node.children.length > 0;
      const levelColors = {
        zone: "text-purple-600 font-bold",
        circle: "text-indigo-600 font-bold",
        division: "text-blue-600 font-semibold",
        subdivision: "text-sky-600",
        substation: "text-teal-600",
        feeder: "text-emerald-600",
        dt: "text-amber-600 font-bold"
      };

      const colorClass = levelColors[node.level] || "text-slate-700";

      return `
        <div class="tree-node">
          <div class="tree-header">
            <span>${hasChildren ? "▾" : "•"}</span>
            <span class="uppercase text-[10px] bg-slate-100 text-slate-500 px-1 py-0.5 rounded font-mono">${node.level}</span>
            <span class="${colorClass}">${node.name} (${node.code})</span>
            <span class="text-[11px] text-slate-400 bg-slate-50 px-1.5 py-0.5 rounded-full border border-slate-200">${node.meter_count} meters</span>
          </div>
          ${hasChildren ? node.children.map(renderNode).join("") : ""}
        </div>
      `;
    }

    container.innerHTML = `
      <div class="font-sans text-xs mb-3 font-semibold text-slate-600">
        Utility: ${data.utility_name} — Total Categorized Meters: ${data.total_meters}
      </div>
      ${data.zones.map(renderNode).join("")}
    `;
  } catch (err) {
    container.innerHTML = `<span class="text-rose-500">Failed to load hierarchy: ${err}</span>`;
  }
}

// Transformers
async function loadTransformers() {
  const tbody = document.getElementById("transformers-table-body");
  tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-slate-400">Loading transformers...</td></tr>`;

  try {
    const res = await fetch("/api/v1/transformers?page=1&page_size=100");
    const data = await res.json();

    tbody.innerHTML = data.items.map(dt => `
      <tr class="hover:bg-slate-50">
        <td class="px-4 py-3 font-mono font-semibold text-slate-900">${dt.code}</td>
        <td class="px-4 py-3 text-slate-700 font-medium">${dt.name}</td>
        <td class="px-4 py-3 font-mono text-xs text-slate-600">${dt.feeder_code}</td>
        <td class="px-4 py-3 text-slate-700">${dt.capacity_kva} kVA</td>
        <td class="px-4 py-3 font-semibold text-slate-900">${dt.connected_meters_count ?? "—"}</td>
      </tr>
    `).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="px-4 py-8 text-center text-rose-500">Failed to load transformers.</td></tr>`;
  }
}

// Meter Modal & Consumption Chart
async function openMeterModal(meterId) {
  const modal = document.getElementById("meter-modal");
  modal.classList.remove("hidden");

  document.getElementById("modal-meter-title").innerText = `Meter ${meterId}`;
  document.getElementById("modal-meter-subtitle").innerText = "Loading telemetry & consumption...";
  document.getElementById("modal-nameplate").innerHTML = "<p class='text-xs text-slate-400'>Loading...</p>";
  document.getElementById("modal-hierarchy-path").innerHTML = "<p class='text-xs text-slate-400'>Loading...</p>";
  document.getElementById("modal-consumption-stats").innerHTML = "";

  try {
    const [detailRes, consumptionRes] = await Promise.all([
      fetch(`/api/v1/meters/${meterId}`),
      fetch(`/api/v1/meters/${meterId}/consumption`)
    ]);

    const detail = await detailRes.json();
    const consumption = await consumptionRes.json();

    document.getElementById("modal-meter-subtitle").innerText = `${detail.make} • ${detail.phase_type} Phase • ${detail.install_status}`;

    // Nameplate
    const nameplateEl = document.getElementById("modal-nameplate");
    nameplateEl.innerHTML = Object.entries(detail.nameplate_attributes || {}).map(([k, v]) => `
      <div class="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
        <span class="block text-[10px] text-slate-400 uppercase font-semibold">${k}</span>
        <span class="text-xs font-semibold text-slate-800">${v}</span>
      </div>
    `).join("");

    // Hierarchy Path
    const h = detail.hierarchy || {};
    const pathLevels = [
      h.zone?.name,
      h.circle?.name,
      h.division?.name,
      h.subdivision?.name,
      h.substation?.name,
      h.feeder?.name,
      h.dt?.name
    ].filter(Boolean);

    document.getElementById("modal-hierarchy-path").innerHTML = pathLevels.map((lvl, i) => `
      <span>${lvl}</span> ${i < pathLevels.length - 1 ? '<span class="text-slate-300">›</span>' : ''}
    `).join("");

    // Consumption Stats & Chart
    const summary = consumption.summary || {};
    document.getElementById("modal-consumption-stats").innerText = 
      `Total Consumption: ${summary.total_consumption_kwh ?? '—'} kWh | Avg Voltage: ${summary.avg_voltage ?? '—'} V (${summary.reading_count} readings)`;

    renderConsumptionChart(consumption.readings || []);
  } catch (err) {
    console.error("Failed to load meter details:", err);
  }
}

function renderConsumptionChart(readings) {
  const ctx = document.getElementById("consumptionChart");
  if (!ctx) return;

  if (consumptionChartInstance) consumptionChartInstance.destroy();

  // Downsample if many readings for smooth rendering
  const step = Math.max(1, Math.floor(readings.length / 50));
  const sampled = readings.filter((_, i) => i % step === 0);

  consumptionChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: sampled.map(r => r.timestamp),
      datasets: [
        {
          label: "Cumulative Active Energy (kWh)",
          data: sampled.map(r => r.kwh),
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.1)",
          yAxisID: "yKwh",
          tension: 0.2,
          fill: true
        },
        {
          label: "R-Phase Voltage (V)",
          data: sampled.map(r => r.volt_r),
          borderColor: "#f59e0b",
          borderDash: [5, 5],
          yAxisID: "yVolt",
          tension: 0.2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: { legend: { position: "top" } },
      scales: {
        x: { display: false },
        yKwh: {
          type: "linear",
          display: true,
          position: "left",
          title: { display: true, text: "kWh" }
        },
        yVolt: {
          type: "linear",
          display: true,
          position: "right",
          title: { display: true, text: "Voltage (V)" },
          grid: { drawOnChartArea: false }
        }
      }
    }
  });
}

function closeModal() {
  document.getElementById("meter-modal").classList.add("hidden");
  if (consumptionChartInstance) {
    consumptionChartInstance.destroy();
    consumptionChartInstance = null;
  }
}

// Sync trigger
async function triggerSync() {
  const btn = document.getElementById("sync-btn");
  const icon = document.getElementById("sync-icon");
  const text = document.getElementById("sync-text");

  btn.disabled = true;
  text.innerText = "Syncing...";
  icon.classList.add("animate-spin");

  try {
    const res = await fetch("/api/v1/sync?force=true", { method: "POST" });
    const status = await res.json();
    alert(`Sync completed successfully! Cached ${status.total_meters_cached} meters and ${status.total_transformers_cached} DTs.`);
    await loadOverviewStats();
    await loadMeters(1);
  } catch (err) {
    alert("Sync failed: " + err);
  } finally {
    btn.disabled = false;
    text.innerText = "Sync Portal";
    icon.classList.remove("animate-spin");
  }
}
