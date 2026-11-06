# 📡 CellSentinel

**Production-Grade Lost Device Recovery & Cell-Tower Telemetry Engine**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telecom: 3GPP](https://img.shields.io/badge/Standard-3GPP%20Cellular-purple.svg)]()

`CellSentinel` is an open-source, carrier-agnostic telecom geolocation and incident response platform designed to locate lost or stolen cellular devices through cell-tower broadcast telemetry (MCC, MNC, LAC, CID, RSSI/RSRP). It features an automated multi-tier triangulation engine with OpenCellID/MLS integration, local cellular persistence, dynamic RF path-loss accuracy envelopes, and dual-mode ingestion supporting both online HTTPS REST and **out-of-band silent SMS hex payloads** when mobile data is disabled.

---

## 🏛️ System Architecture

```
                          ┌──────────────────────────────────────────────┐
                          │            Cellular User Equipment           │
                          │        (Google Pixel, iPhone, Galaxy)        │
                          └──────┬───────────────────────────────┬───────┘
                                 │ Mobile Data                   │ Mobile Data Disabled
                                 │ (Active)                      │ (Offline Recovery)
                                 ▼                               ▼
                     ┌───────────────────────┐       ┌───────────────────────┐
                     │   HTTPS REST Push     │       │ Out-of-Band Silent    │
                     │  /api/v1/telemetry/   │       │ SMS Hex PDU           │
                     │         push          │       │ /api/v1/telemetry/    │
                     └───────────┬───────────┘       │      sms-webhook      │
                                 │                   └───────────┬───────────┘
                                 │                               │
                                 ▼                               ▼
                      ┌─────────────────────────────────────────────┐
                      │            CellSentinel Core Engine         │
                      └──────────────────────┬──────────────────────┘
                                             │
               ┌─────────────────────────────┼─────────────────────────────┐
               ▼                             ▼                             ▼
   ┌───────────────────────┐     ┌───────────────────────┐     ┌───────────────────────┐
   │ Device Identity &     │     │ Cell-Tower Resolver & │     │ Live Leaflet.js       │
   │ Hardware Registry     │     │ RF Triangulation      │     │ Tactical Dashboard    │
   │ • IMEI SHA-256 Hash   │     │ • OpenCellID API      │     │ • Radar Tower Pins    │
   │ • Lifecycle States    │     │ • MLS / Ichnaea API   │     │ • Dynamic Accuracy ⭕ │
   │   [SECURE, LOST,      │     │ • SQLite Cell Cache   │     │ • Handover Trajectory │
   │    RECOVERED]         │     │ • Log-Distance Model  │     │ • Real-time SSE Feed  │
   │ • Salted Recovery PIN │     │ • Fallback Synthesizer│     │ • Telemetry Simulator │
   └───────────────────────┘     └───────────────────────┘     └───────────────────────┘
```

---

## 🚀 Key Capabilities

### 1. Device Identity & Hardware Registry
* **Zero-Knowledge IMEI Storage:** Normalizes incoming 15-digit hardware IMEIs into cryptographically salted SHA-256 hashes (`[a-f0-9]{64}`) to safeguard user privacy against plain-text identifier theft.
* **Hardware Lifecycle Machine:** State management across `SECURE`, `LOST`, and `RECOVERED` with salted recovery PIN protection and immutable incident audit logging.
* **SIM IMSI Integrity Check:** Detects unauthorized SIM swaps on device pings.

### 2. Multi-Tier Cell-Tower Triangulation Engine
* Ingests standard 3GPP cellular broadcast parameters:
  * **MCC** (Mobile Country Code, e.g., `404` for India, `310` for USA, `234` for UK)
  * **MNC** (Mobile Network Code, e.g., `45` Bharti Airtel, `20` Reliance Jio, `410` AT&T)
  * **LAC** (Location Area Code / TAC)
  * **CID** (Cell Tower ID / ECI)
  * **Signal Strength** (RSSI / RSRP in dBm, e.g., `-75 dBm`)
* **Hierarchical Resolver:**
  1. **Persistent SQLite Cache (`cell_cache`):** Sub-millisecond lookup for frequently referenced towers.
  2. **Verified Telecom Directory:** Pre-loaded reference macrocells (Connaught Place, Barakhamba, Manhattan, Trafalgar Square, etc.).
  3. **OpenCellID API:** Live upstream query when `OPENCELLID_API_KEY` is configured.
  4. **Mozilla Location Services (MLS / Ichnaea) API:** Standard query when `MLS_API_KEY` is configured.
  5. **Deterministic RF Synthesizer:** Mathematically sound, country-centroid & LAC cluster synthesizer ensuring 100% resolution even in total offline/air-gapped deployments.
* **RF Propagation Path-Loss Accuracy Model:**
  $$d = 10^{\frac{P_0 - \text{RSSI}}{10 \cdot n}}$$
  Where $P_0$ is antenna reference power (-42 dBm) and $n$ is path-loss exponent (3.2). Produces dynamic accuracy radius envelopes ($\pm 120\text{m}$ for high signal down to $\pm 4500\text{m}$ for cell fringe).

### 3. Out-of-Band Offline Telemetry (No Internet Mode)
* **Silent SMS Webhook Gateway:** Ingests telemetry sent via silent Type 0 SMS / binary PDU when mobile data is disabled:
  * **Packed Binary Hex:** `0xCE` (magic) + 16-byte IMEI prefix + 2-byte MCC + 2-byte MNC + 2-byte LAC + 4-byte CID + 1-byte signed RSSI.
  * **Canonical Bracket Notation:** `[IMEI_HASH:MCC:MNC:LAC:CID]` or `[IMEI_HASH:MCC:MNC:LAC:CID:RSSI]`.
  * **Standard Gateways:** Twilio (`From`, `Body`), generic SMS webhooks, or direct hex payloads.

### 4. Tactical Leaflet.js Dashboard
* High-tech dark telecom NOC (Network Operations Center) interface.
* Exact cell-tower antenna pin and color-coded dynamic coverage uncertainty radius.
* Chronological breadcrumb polyline tracing tower transitions and handovers.
* Real-time Server-Sent Events (SSE) streaming updates to connected browsers with zero page reloads.
* Built-in interactive Telemetry Simulator with presets for rapid live demonstration.

---

## ⚡ Quickstart

### Prerequisites
* Python 3.10+
* Windows, Linux, or macOS

### 1. Clone & Set Up Virtual Environment

```bash
cd cellsentinel
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment (Optional)

```bash
cp .env.example .env
# Edit .env if you wish to add OPENCELLID_API_KEY or custom ports
```

### 3. Run CellSentinel

```bash
python -m uvicorn cellsentinel.main:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to:
* **Interactive Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive OpenAPI Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Endpoint:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🧪 Running the Test Suite

```bash
pytest -v
```

All unit and integration tests cover:
- RF path loss equations & accuracy bounds
- Binary hex & bracket SMS parsing
- Triangulation resolver hierarchy & user sample tower
- Device registration, SHA-256 hashing & state transitions
- FastAPI REST & SMS webhook ingestion

---

## 🎬 Running the Live Handover Simulation

With the server running, execute the standalone demonstration script:

```bash
python demo_simulator.py
```

Watch the terminal and open dashboard animate in real-time as the lost device transitions across cellular towers, simulating both mobile data and out-of-band silent SMS!

---

## 📡 API Reference Overview

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/devices` | Securely register hardware identity (IMEI SHA-256, model, owner) |
| `GET` | `/api/v1/devices` | List registered devices with search and state filter |
| `GET` | `/api/v1/devices/{hash}` | Retrieve device details and current cellular fix |
| `PATCH` | `/api/v1/devices/{hash}/state` | Transition state between `SECURE`, `LOST`, `RECOVERED` |
| `GET` | `/api/v1/devices/{hash}/trajectory` | Retrieve historical tower breadcrumbs for map |
| `GET` | `/api/v1/devices/{hash}/events` | Retrieve audit timeline of handovers & alerts |
| `POST` | `/api/v1/telemetry/push` | HTTPS REST telemetry ingestion (active data) |
| `POST` | `/api/v1/telemetry/sms-webhook` | Out-of-band silent SMS gateway webhook parser |
| `POST` | `/api/v1/resolver/lookup` | Standalone cell tower triangulation resolver |
| `GET` | `/api/v1/dashboard/summary` | Operational KPI metrics |
| `GET` | `/api/v1/dashboard/events/stream` | Real-time Server-Sent Events (SSE) stream |

---

## 📄 License
This project is licensed under the MIT License - open-source for public good and lost device recovery.
