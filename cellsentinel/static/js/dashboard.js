/**
 * CellSentinel - Live Incident & Map Dashboard Script
 * Handles Leaflet.js cartography, SSE real-time telemetry streaming,
 * device hardware registry, trajectory rendering, and out-of-band simulation.
 */

let map;
let towerMarker = null;
let accuracyCircle = null;
let trajectoryPolyline = null;
let hopMarkers = [];

let devicesData = [];
let selectedDeviceHash = null;
let sseSource = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
    initLeafletMap();
    fetchDashboardSummary();
    fetchDevices();
    initSSE();
    setupEventListeners();

    // Auto-refresh summary every 15s
    setInterval(fetchDashboardSummary, 15000);
});

/**
 * Initialize Leaflet Map with Dark Cartographic Tiles
 */
function initLeafletMap() {
    // Default coordinate: New Delhi Connaught Place
    map = L.map("leafletMap", {
        zoomControl: true,
        attributionControl: false
    }).setView([28.6315, 77.2167], 14);

    // High-tech dark CartoDB tiles
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        maxZoom: 19,
        subdomains: "abcd"
    }).addTo(map);

    // Scale control
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);
}

/**
 * Fetch and update KPI summary counters
 */
async function fetchDashboardSummary() {
    try {
        const res = await fetch("/api/v1/dashboard/summary");
        if (!res.ok) return;
        const data = await res.json();

        document.getElementById("kpiTotalDevices").innerText = data.total_devices;
        document.getElementById("kpiLostDevices").innerText = data.lost_devices;
        document.getElementById("kpiRecoveredDevices").innerText = data.recovered_devices;
        document.getElementById("kpiSecureDevices").innerText = data.secure_devices;
        document.getElementById("kpiPings").innerText = data.total_telemetry_pings;
        document.getElementById("kpiTowers").innerText = data.cached_cell_towers;
    } catch (err) {
        console.error("Error fetching summary:", err);
    }
}

/**
 * Fetch device list and populate sidebar
 */
async function fetchDevices(query = "", stateFilter = "") {
    try {
        let url = "/api/v1/devices";
        const params = new URLSearchParams();
        if (query) params.append("q", query);
        if (stateFilter) params.append("state", stateFilter);
        if (params.toString()) url += `?${params.toString()}`;

        const res = await fetch(url);
        if (!res.ok) return;
        devicesData = await res.json();

        renderDeviceList(devicesData);

        // Auto-select first device if none selected
        if (!selectedDeviceHash && devicesData.length > 0) {
            selectDevice(devicesData[0].imei_hash);
        } else if (selectedDeviceHash) {
            // Re-render selected
            const dev = devicesData.find(d => d.imei_hash === selectedDeviceHash);
            if (dev) renderSelectedDeviceHeader(dev);
        }
    } catch (err) {
        console.error("Error fetching devices:", err);
    }
}

/**
 * Render devices list cards
 */
function renderDeviceList(devices) {
    const container = document.getElementById("deviceListContainer");
    container.innerHTML = "";

    if (devices.length === 0) {
        container.innerHTML = `<div style="padding:1rem; text-align:center; color:var(--text-muted); font-size:0.75rem;">No devices matching criteria.</div>`;
        return;
    }

    devices.forEach(dev => {
        const card = document.createElement("div");
        card.className = `device-card ${dev.imei_hash === selectedDeviceHash ? 'selected' : ''}`;
        card.onclick = () => selectDevice(dev.imei_hash);

        const badgeClass = dev.state === "LOST" ? "badge-lost" : (dev.state === "RECOVERED" ? "badge-recovered" : "badge-secure");

        const lastSeen = dev.last_seen_at ? formatTimeAgo(dev.last_seen_at) : "Never";
        const rssi = dev.last_rssi ? `${dev.last_rssi} dBm` : "No Signal";
        const carrier = (dev.last_mcc && dev.last_mnc) ? `MCC:${dev.last_mcc} MNC:${dev.last_mnc}` : "Awaiting Ping";

        card.innerHTML = `
            <div class="device-card-header">
                <span class="device-model-text">${escapeHtml(dev.device_model)}</span>
                <span class="status-badge ${badgeClass}">${dev.state}</span>
            </div>
            <div class="device-imei-hash" title="${dev.imei_hash}">
                SHA256: ${dev.imei_hash.substring(0, 16)}...
            </div>
            <div class="device-meta-row">
                <span class="carrier-tag">${carrier}</span>
                <span>${lastSeen}</span>
                <span style="font-family:var(--font-mono); color:${dev.last_rssi ? 'var(--accent-cyan)' : 'inherit'}">${rssi}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

/**
 * Select a device and load its map location, trajectory, and timeline
 */
async function selectDevice(imeiHash) {
    selectedDeviceHash = imeiHash;

    // Highlight card in list
    document.querySelectorAll(".device-card").forEach(el => el.classList.remove("selected"));
    const matchingCard = [...document.querySelectorAll(".device-card")].find(el => el.innerHTML.includes(imeiHash.substring(0, 16)));
    if (matchingCard) matchingCard.classList.add("selected");

    const device = devicesData.find(d => d.imei_hash === imeiHash);
    if (device) {
        renderSelectedDeviceHeader(device);
    }

    // Load trajectory & timeline
    await Promise.all([
        loadDeviceTrajectory(imeiHash),
        loadDeviceTimeline(imeiHash)
    ]);
}

/**
 * Render detail bar for selected device
 */
function renderSelectedDeviceHeader(device) {
    document.getElementById("overlayDeviceModel").innerText = device.device_model;
    document.getElementById("overlayDeviceState").innerHTML = `
        <span class="status-badge ${device.state === 'LOST' ? 'badge-lost' : (device.state === 'RECOVERED' ? 'badge-recovered' : 'badge-secure')}">
            ${device.state}
        </span>
    `;
    document.getElementById("overlayOwner").innerText = `${device.owner_name} (${device.owner_phone})`;
    document.getElementById("overlayImei").innerText = device.imei_hash.substring(0, 24) + "...";

    // Set simulator default IMEI
    const simImeiInput = document.getElementById("simDeviceSelect");
    if (simImeiInput) simImeiInput.value = device.imei_hash;
}

/**
 * Load and render trajectory trail on Leaflet map
 */
async function loadDeviceTrajectory(imeiHash) {
    try {
        const res = await fetch(`/api/v1/devices/${imeiHash}/trajectory`);
        if (!res.ok) return;
        const trajectory = await res.json();

        // Clear existing map items
        clearMapVisuals();

        if (trajectory.length === 0) {
            return;
        }

        const latLngs = [];

        trajectory.forEach((t, idx) => {
            const pos = [t.latitude, t.longitude];
            latLngs.push(pos);

            // Add numbered hop marker for historical points
            if (idx < trajectory.length - 1) {
                const hopIcon = L.divIcon({
                    className: "hop-div-icon",
                    html: `<div style="background:#475569; color:#fff; border-radius:50%; width:20px; height:20px; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:700; border:1px solid #94a3b8;">${idx + 1}</div>`,
                    iconSize: [20, 20]
                });
                const hm = L.marker(pos, { icon: hopIcon }).addTo(map);
                hm.bindPopup(`<b>Hop #${idx + 1}</b><br>CID: ${t.cid} | LAC: ${t.lac}<br>Signal: ${t.signal_strength} dBm<br>Time: ${t.timestamp}`);
                hopMarkers.push(hm);
            }
        });

        // Trajectory line
        if (latLngs.length > 1) {
            trajectoryPolyline = L.polyline(latLngs, {
                color: "#38bdf8",
                weight: 3,
                dashArray: "6, 6",
                opacity: 0.8
            }).addTo(map);
        }

        // Latest point (Current Pin & Accuracy Circle)
        const latest = trajectory[trajectory.length - 1];
        const latestPos = [latest.latitude, latest.longitude];

        // Custom Cell Tower Pin
        const dev = devicesData.find(d => d.imei_hash === imeiHash);
        const isLost = dev && dev.state === "LOST";

        const towerIcon = L.divIcon({
            className: "custom-tower-marker",
            html: `<div class="marker-inner ${isLost ? '' : 'secure'}">📡</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });

        towerMarker = L.marker(latestPos, { icon: towerIcon }).addTo(map);

        const popupContent = `
            <div style="font-family:var(--font-sans); color:#0f172a; min-width:200px;">
                <h4 style="margin:0 0 4px 0; color:#2563eb;">Cell Tower: CID ${latest.cid}</h4>
                <div style="font-size:12px; margin-bottom:4px;"><b>Carrier:</b> ${latest.carrier_name || 'Cellular'}</div>
                <div style="font-size:12px; margin-bottom:4px;"><b>Sector (LAC):</b> ${latest.lac} | <b>MCC/MNC:</b> ${latest.mcc}/${latest.mnc}</div>
                <div style="font-size:12px; margin-bottom:4px;"><b>Signal (RSSI):</b> <span style="font-weight:700; color:#dc2626;">${latest.signal_strength} dBm</span></div>
                <div style="font-size:12px; margin-bottom:4px;"><b>Coverage Radius:</b> ${latest.accuracy_radius}m</div>
                <div style="font-size:11px; color:#64748b; margin-top:4px;">Transport: ${latest.transport} | Source: ${latest.resolver_source}</div>
            </div>
        `;
        towerMarker.bindPopup(popupContent).openPopup();

        // Dynamic Accuracy Radius Circle
        const circleColor = isLost ? "#f43f5e" : "#10b981";
        accuracyCircle = L.circle(latestPos, {
            radius: latest.accuracy_radius,
            color: circleColor,
            fillColor: circleColor,
            fillOpacity: 0.16,
            weight: 2,
            dashArray: isLost ? "4, 4" : null
        }).addTo(map);

        // Center map to bounds
        if (latLngs.length === 1) {
            map.setView(latestPos, 14);
        } else {
            map.fitBounds(L.latLngBounds(latLngs).pad(0.2));
        }

    } catch (err) {
        console.error("Error loading trajectory:", err);
    }
}

/**
 * Clear existing map markers and polylines
 */
function clearMapVisuals() {
    if (towerMarker) {
        map.removeLayer(towerMarker);
        towerMarker = null;
    }
    if (accuracyCircle) {
        map.removeLayer(accuracyCircle);
        accuracyCircle = null;
    }
    if (trajectoryPolyline) {
        map.removeLayer(trajectoryPolyline);
        trajectoryPolyline = null;
    }
    hopMarkers.forEach(m => map.removeLayer(m));
    hopMarkers = [];
}

/**
 * Load incident audit events and tower transition timeline
 */
async function loadDeviceTimeline(imeiHash) {
    try {
        const [eventsRes, trajRes] = await Promise.all([
            fetch(`/api/v1/devices/${imeiHash}/events`),
            fetch(`/api/v1/devices/${imeiHash}/trajectory?limit=50`)
        ]);

        const events = eventsRes.ok ? await eventsRes.json() : [];
        const trajectory = trajRes.ok ? await trajRes.json() : [];

        const container = document.getElementById("timelineContainer");
        container.innerHTML = "";

        if (trajectory.length === 0 && events.length === 0) {
            container.innerHTML = `<div style="padding:1rem; text-align:center; color:var(--text-muted); font-size:0.75rem;">No telemetry or events recorded yet.</div>`;
            return;
        }

        // Combine events and telemetry into a unified chronological log
        const combined = [];

        trajectory.forEach(t => {
            combined.push({
                type: "telemetry",
                timestamp: t.timestamp,
                transport: t.transport,
                mcc: t.mcc,
                mnc: t.mnc,
                lac: t.lac,
                cid: t.cid,
                rssi: t.signal_strength,
                carrier: t.carrier_name,
                radius: t.accuracy_radius,
                sim_status: t.sim_status,
                raw: t.raw_payload
            });
        });

        events.forEach(e => {
            combined.push({
                type: "event",
                timestamp: e.timestamp,
                event_type: e.event_type,
                severity: e.severity,
                details: e.details
            });
        });

        // Sort descending
        combined.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        combined.forEach(item => {
            const div = document.createElement("div");

            if (item.type === "telemetry") {
                const isSms = item.transport === "SMS_OUT_OF_BAND";
                div.className = `timeline-item ${isSms ? 'sms' : 'https'}`;

                div.innerHTML = `
                    <div class="timeline-header">
                        <span class="timeline-transport ${isSms ? 'transport-sms' : 'transport-https'}">
                            ${isSms ? '📡 SILENT SMS OUT-OF-BAND' : '🌐 REST HTTPS DATA'}
                        </span>
                        <span class="timeline-time">${formatTimeAgo(item.timestamp)}</span>
                    </div>
                    <div class="timeline-body">
                        <div>CID: <span class="timeline-val">${item.cid}</span></div>
                        <div>LAC: <span class="timeline-val">${item.lac}</span></div>
                        <div>MCC/MNC: <span class="timeline-val">${item.mcc}/${item.mnc}</span></div>
                        <div>RSSI: <span class="timeline-val" style="color:var(--accent-cyan)">${item.rssi} dBm</span></div>
                        <div>Carrier: <span class="timeline-val">${escapeHtml(item.carrier || 'Cellular')}</span></div>
                        <div>Accuracy: <span class="timeline-val">±${item.radius}m</span></div>
                    </div>
                    ${item.sim_status === 'CHANGED' ? '<div style="color:var(--status-lost); font-weight:700; margin-top:4px;">⚠️ SIM SWAP DETECTED</div>' : ''}
                `;
            } else {
                div.className = "timeline-item handover";
                const sevColor = item.severity === 'CRITICAL' ? 'var(--status-lost)' : (item.severity === 'WARNING' ? 'var(--accent-amber)' : 'var(--accent-blue)');

                div.innerHTML = `
                    <div class="timeline-header">
                        <span style="font-weight:700; color:${sevColor}">${escapeHtml(item.event_type)}</span>
                        <span class="timeline-time">${formatTimeAgo(item.timestamp)}</span>
                    </div>
                    <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:3px;">
                        ${escapeHtml(item.details)}
                    </div>
                `;
            }

            container.appendChild(div);
        });

    } catch (err) {
        console.error("Error loading timeline:", err);
    }
}

/**
 * Initialize Server-Sent Events (SSE) Live Feed
 */
function initSSE() {
    if (sseSource) sseSource.close();

    sseSource = new EventSource("/api/v1/dashboard/events/stream");

    sseSource.addEventListener("telemetry", (e) => {
        try {
            const data = JSON.parse(e.data);
            handleLiveTelemetryEvent(data);
        } catch (err) {
            console.error("Error processing SSE message:", err);
        }
    });

    sseSource.onerror = () => {
        // Retry connection automatically
        setTimeout(initSSE, 5000);
    };
}

/**
 * Handle incoming live telemetry packet
 */
function handleLiveTelemetryEvent(data) {
    fetchDashboardSummary();
    fetchDevices();

    const incomingHash = data.telemetry.device_imei_hash;
    if (selectedDeviceHash === incomingHash) {
        loadDeviceTrajectory(incomingHash);
        loadDeviceTimeline(incomingHash);
    }
}

/**
 * Setup Event Listeners & Modals
 */
function setupEventListeners() {
    // Search input
    const searchInput = document.getElementById("deviceSearchInput");
    searchInput.addEventListener("input", (e) => {
        const query = e.target.value.trim();
        const activeTab = document.querySelector(".tab-btn.active").dataset.state;
        fetchDevices(query, activeTab === "ALL" ? "" : activeTab);
    });

    // Filter tabs
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const state = btn.dataset.state;
            const query = searchInput.value.trim();
            fetchDevices(query, state === "ALL" ? "" : state);
        });
    });

    // Register Device Modal
    const regModal = document.getElementById("registerModal");
    document.getElementById("btnOpenRegister").onclick = () => regModal.classList.add("active");
    document.getElementById("btnCloseRegister").onclick = () => regModal.classList.remove("active");

    document.getElementById("registerDeviceForm").onsubmit = async (e) => {
        e.preventDefault();
        const payload = {
            imei_or_hash: document.getElementById("regImei").value.trim(),
            device_model: document.getElementById("regModel").value.trim(),
            owner_name: document.getElementById("regOwnerName").value.trim(),
            owner_phone: document.getElementById("regOwnerPhone").value.trim(),
            owner_email: document.getElementById("regOwnerEmail").value.trim(),
            recovery_pin: document.getElementById("regPin").value.trim() || "1234",
            sim_imsi: document.getElementById("regImsi").value.trim() || null
        };

        try {
            const res = await fetch("/api/v1/devices", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const err = await res.json();
                alert(`Registration failed: ${err.detail || 'Unknown error'}`);
                return;
            }

            const device = await res.json();
            regModal.classList.remove("active");
            document.getElementById("registerDeviceForm").reset();
            await fetchDevices();
            selectDevice(device.imei_hash);
            alert(`Device "${device.device_model}" registered successfully!`);
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    };

    // Simulator Modal
    const simModal = document.getElementById("simulatorModal");
    document.getElementById("btnOpenSimulator").onclick = () => {
        populateSimulatorDropdown();
        simModal.classList.add("active");
    };
    document.getElementById("btnCloseSimulator").onclick = () => simModal.classList.remove("active");

    // RSSI slider sync
    const rssiSlider = document.getElementById("simRssi");
    const rssiValLabel = document.getElementById("simRssiVal");
    rssiSlider.oninput = () => rssiValLabel.innerText = `${rssiSlider.value} dBm`;

    // Presets
    document.getElementById("presetCP").onclick = () => setPreset(404, 45, 1234, 5678, -68);
    document.getElementById("presetBarakhamba").onclick = () => setPreset(404, 45, 1234, 5679, -82);
    document.getElementById("presetMandiHouse").onclick = () => setPreset(404, 45, 1234, 5680, -94);
    document.getElementById("presetNYC").onclick = () => setPreset(310, 410, 8910, 3421, -74);

    document.getElementById("simulatorForm").onsubmit = async (e) => {
        e.preventDefault();
        const imeiHash = document.getElementById("simDeviceSelect").value;
        const mcc = parseInt(document.getElementById("simMcc").value);
        const mnc = parseInt(document.getElementById("simMnc").value);
        const lac = parseInt(document.getElementById("simLac").value);
        const cid = parseInt(document.getElementById("simCid").value);
        const rssi = parseFloat(document.getElementById("simRssi").value);
        const transport = document.getElementById("simTransport").value;

        try {
            const url = `/api/v1/dashboard/simulate-hop?imei_hash=${encodeURIComponent(imeiHash)}&mcc=${mcc}&mnc=${mnc}&lac=${lac}&cid=${cid}&rssi=${rssi}&transport=${transport}`;
            const res = await fetch(url, { method: "POST" });

            if (!res.ok) {
                const err = await res.json();
                alert(`Simulation failed: ${err.detail || 'Error'}`);
                return;
            }

            simModal.classList.remove("active");
            selectDevice(imeiHash);
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    };

    // State Change Action
    document.getElementById("btnToggleState").onclick = async () => {
        if (!selectedDeviceHash) return;
        const dev = devicesData.find(d => d.imei_hash === selectedDeviceHash);
        if (!dev) return;

        let nextState = "LOST";
        if (dev.state === "LOST") nextState = "RECOVERED";
        else if (dev.state === "RECOVERED") nextState = "SECURE";

        const pin = prompt(`Enter Recovery PIN to change state to ${nextState}:`, "9876");
        if (!pin) return;

        try {
            const res = await fetch(`/api/v1/devices/${selectedDeviceHash}/state`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    state: nextState,
                    recovery_pin: pin,
                    reason: `Manual state change by operator to ${nextState}`
                })
            });

            if (!res.ok) {
                const err = await res.json();
                alert(`State transition rejected: ${err.detail}`);
                return;
            }

            await fetchDevices();
            selectDevice(selectedDeviceHash);
            alert(`Device state updated to ${nextState}!`);
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    };

    // Seed Demo Button
    document.getElementById("btnSeedDemo").onclick = async () => {
        try {
            const res = await fetch("/api/v1/dashboard/seed-demo", { method: "POST" });
            const data = await res.json();
            await fetchDevices();
            if (data.lost_device_imei_hash) {
                selectDevice(data.lost_device_imei_hash);
            }
            alert("Realistic demo devices and multi-tower handovers re-seeded!");
        } catch (err) {
            alert(`Seed error: ${err.message}`);
        }
    };
}

function setPreset(mcc, mnc, lac, cid, rssi) {
    document.getElementById("simMcc").value = mcc;
    document.getElementById("simMnc").value = mnc;
    document.getElementById("simLac").value = lac;
    document.getElementById("simCid").value = cid;
    document.getElementById("simRssi").value = rssi;
    document.getElementById("simRssiVal").innerText = `${rssi} dBm`;
}

function populateSimulatorDropdown() {
    const sel = document.getElementById("simDeviceSelect");
    sel.innerHTML = "";
    devicesData.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.imei_hash;
        opt.innerText = `${d.device_model} [${d.state}] (${d.imei_hash.substring(0, 10)}...)`;
        if (d.imei_hash === selectedDeviceHash) opt.selected = true;
        sel.appendChild(opt);
    });
}

function formatTimeAgo(dateString) {
    if (!dateString) return "Never";
    const date = new Date(dateString.replace(" ", "T") + (dateString.includes("Z") ? "" : "Z"));
    const now = new Date();
    const diffSec = Math.floor((now - date) / 1000);

    if (diffSec < 60) return `${Math.max(1, diffSec)}s ago`;
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    return `${Math.floor(diffSec / 86400)}d ago`;
}

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/[&<>"']/g, (m) => {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[m];
    });
}

