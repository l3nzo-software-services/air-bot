# 📡 AIR BOT
## Autonomous Cell-Tower Telemetry & Lost Device Recovery Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg?style=flat)](https://www.sqlalchemy.org/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Telecom: 3GPP](https://img.shields.io/badge/Standard-3GPP%20Cellular-purple.svg)]()

`AIR BOT` is an open-source, production-grade anti-theft and telecom recovery platform for tracking cellular devices via base-station airwaves. It ingests live cellular telemetry (MCC, MNC, LAC, Cell ID, RSSI) via online HTTPS and offline out-of-band SMS, resolves physical tower coordinates via OpenCellID and local verified catalogs, and visualizes device locations on an interactive Leaflet.js dashboard.

---

## 🏛️ System Architecture

```
CellSentinel/
│
├── cellsentinel/
│   ├── main.py                     # FastAPI application setup, lifecycle hooks & CORS
│   ├── database.py                 # SQLAlchemy engine, session management & init_db()
│   ├── models.py                   # SQLAlchemy ORM models (Device, Telemetry, CellTowerCache)
│   ├── schemas.py                  # Pydantic schemas, validators & serialization models
│   ├── config.py                   # Environment settings & telecom constants
│   │
│   ├── services/
│   │   ├── device_service.py       # Device registration, SHA-256 IMEI hashing & token auth
│   │   ├── telemetry_service.py    # Authenticated telemetry pipeline & SSE event bus
│   │   └── tower_resolver.py       # OpenCellID & local cache resolution engine
│   │
│   ├── api/
│   │   ├── devices.py              # /api/devices endpoints (register, list, get)
│   │   ├── telemetry.py            # /api/telemetry (authenticated ingest & history)
│   │   └── dashboard.py            # /api/dashboard (stats, search, SSE live stream)
│   │
│   └── templates/
│       └── dashboard.html          # Interactive Leaflet.js cartographic web dashboard
│
├── tests/
│   ├── conftest.py                 # Shared test database fixtures (StaticPool)
│   ├── test_devices.py             # Database init, registration, duplicate & auth tests
│   ├── test_telemetry.py           # Ingestion, history, validation & SSE stream tests
│   └── test_tower_resolver.py      # Cache lookup, OpenCellID mock, fallback & non-fabrication tests
│
├── data/
│   └── verified_towers.json        # Curated offline reference cell-tower catalog
├── .env.example                    # Environment variable template
├── .gitignore                      # Git ignore rules
├── requirements.txt                # Python dependencies
├── README.md                       # Complete platform documentation
└── run.py                          # Single-command launcher
```

---

## ⚡ Quickstart (Single-Command Execution)

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, 3.12, 3.13, 3.14)
- Windows, macOS, or Linux

### 2. Setup Virtual Environment & Install Dependencies

```bash
cd cellsentinel
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate

# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Launch Application

```bash
python run.py
```

The runner automatically:
1. Initializes the SQLite database (`cellsentinel_platform.db`).
2. Verifies connectivity via active `SELECT 1` execution.
3. Creates all tables and indexes.
4. Pre-seeds verified reference cell-tower catalog into the cache.
5. Seeds a default reference device (`Google Pixel 8 Pro`) with initial Connaught Place telemetry.
6. Starts the Uvicorn web server on `http://0.0.0.0:8000`.

Open your browser to:
- **Interactive Map Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive OpenAPI Documentation:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Verification Endpoint:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 🔒 Security & Privacy Model

* **Cryptographic IMEI Hashing:** Raw 14-16 digit hardware IMEIs are normalized and hashed via `SHA-256` upon ingress. Raw IMEIs are never stored or logged in plaintext.
* **Owner-Authorized Registration:** Devices must be explicitly registered prior to submitting telemetry.
* **Device Authentication Token:** Registration returns a cryptographically secure 256-bit API key (`secrets.token_urlsafe(32)`). Telemetry submissions must present this key in the `X-Device-Token` header or `Authorization: Bearer <token>`. Unauthenticated submissions are rejected with `HTTP 401 Unauthorized`.
* **SQL Injection Immunity:** All database access is parameterized through SQLAlchemy ORM.

---

## 📡 Geolocation & Resolution Engine Rules

The resolver strictly adheres to telecom physics principles:

```
                            [ Incoming Cell Broadcast ]
                          (MCC, MNC, LAC, Cell_ID, RSSI)
                                       │
                                       ▼
                         ┌───────────────────────────┐
                         │ 1. Local SQLite Cache     │──► Found ──► Return "CACHE"
                         └─────────────┬─────────────┘
                                       │ Not in cache
                                       ▼
                         ┌───────────────────────────┐
                         │ 2. OpenCellID API Query   │──► Resolved ─► Cache & Return "OPENCELLID"
                         │   (if API key configured) │
                         └─────────────┬─────────────┘
                                       │ Timeout / No key
                                       ▼
                         ┌───────────────────────────┐
                         │ 3. Verified Local Catalog │──► Matched ──► Cache & Return "LOCAL_VERIFIED"
                         │ (data/verified_towers.json│
                         └─────────────┬─────────────┘
                                       │ Unrecognized
                                       ▼
                         ┌───────────────────────────┐
                         │ 4. Explicit UNRESOLVED    │
                         │    lat=None, lon=None     │
                         │    accuracy_radius=None   │
                         └───────────────────────────┘
```

> [!IMPORTANT]
> **Telecom Engineering Notice**: A cell tower's coordinates represent the **fixed geographic position of the carrier's base station antenna**, NOT the physical location of the mobile device. Device proximity is bounded by the broadcast coverage radius circle.
>
> **Strict Non-Fabrication Rule**: `CellSentinel` never fabricates coordinates, never uses country centroids as towers, and never invents accuracy radii when unavailable from the upstream source.

---

## 🌐 API Reference

### 1. Register Device
`POST /api/devices`

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/api/devices \
  -H "Content-Type: application/json" \
  -d '{
    "imei": "358941098765432",
    "device_name": "Google Pixel 8 Pro"
  }'
```

**Response (HTTP 201):**
```json
{
  "id": 1,
  "imei_hash": "a4341568284f65f46717cccf7e01e89c8f99cef63859e750b47a03c3d1633a78",
  "device_name": "Google Pixel 8 Pro",
  "device_status": "ACTIVE",
  "registration_timestamp": "2026-11-06T05:30:00Z",
  "api_key": "YOUR_PRIVATE_DEVICE_API_KEY"
}
```

---

### 2. Ingest Telemetry
`POST /api/telemetry`

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/api/telemetry \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_PRIVATE_DEVICE_API_KEY" \
  -d '{
    "device_id": "1",
    "mcc": 404,
    "mnc": 45,
    "lac": 1234,
    "cell_id": 56789,
    "signal_strength": -75.0
  }'
```

**Response (HTTP 201):**
```json
{
  "success": true,
  "device_id": "a4341568284f65f46717cccf7e01e89c8f99cef63859e750b47a03c3d1633a78",
  "tower": {
    "mcc": 404,
    "mnc": 45,
    "lac": 1234,
    "cell_id": 56789,
    "carrier_name": "Bharti Airtel (Airtel India)",
    "latitude": 28.63152,
    "longitude": 77.21672,
    "accuracy_radius": 750.0,
    "location_source": "LOCAL_VERIFIED"
  },
  "timestamp": "2026-11-06T05:35:12.123456Z",
  "message": "Telemetry ingested and processed successfully."
}
```

---

### 3. Retrieve Telemetry History
`GET /api/telemetry/{device_id}/history`

Returns chronological cell tower observations with transition timestamps, RSSI, and location sources.

---

### 4. Search Devices
`GET /api/dashboard/search?q={query}`

Search by integer device ID or 64-character IMEI SHA-256 hash.

---

### 5. Real-Time Telemetry Stream (SSE)
`GET /api/dashboard/events`

Server-Sent Events streaming updates to connected dashboard clients in real-time.

---

## 🧪 Automated Test Suite

Execute the complete test suite with verbose output:

```bash
pytest -v
```

### Test Coverage Matrix (18/18 Passing):
| Test Module | Coverage Area | Status |
|---|---|:---:|
| `test_devices.py` | Database schema initialization | ✅ PASS |
| `test_devices.py` | Device registration & raw IMEI SHA-256 hashing | ✅ PASS |
| `test_devices.py` | Duplicate IMEI rejection (`HTTP 409`) | ✅ PASS |
| `test_devices.py` | Valid vs invalid device authentication token | ✅ PASS |
| `test_devices.py` | Suspended device rejection (`HTTP 403`) | ✅ PASS |
| `test_tower_resolver.py` | Carrier name resolution from MCC/MNC | ✅ PASS |
| `test_tower_resolver.py` | Local SQLite tower cache lookup | ✅ PASS |
| `test_tower_resolver.py` | Verified reference catalog fallback | ✅ PASS |
| `test_tower_resolver.py` | OpenCellID API mocked integration | ✅ PASS |
| `test_tower_resolver.py` | API failure fallback handling | ✅ PASS |
| `test_tower_resolver.py` | Strict unknown tower non-fabrication | ✅ PASS |
| `test_telemetry.py` | Authenticated telemetry ingestion | ✅ PASS |
| `test_telemetry.py` | Unauthenticated telemetry rejection (`HTTP 401`) | ✅ PASS |
| `test_telemetry.py` | Telemetry parameter boundary validation (`HTTP 422`) | ✅ PASS |
| `test_telemetry.py` | Chronological telemetry history trail | ✅ PASS |
| `test_telemetry.py` | Dashboard device search & aggregate stats | ✅ PASS |
| `test_telemetry.py` | HTML dashboard template rendering | ✅ PASS |
| `test_telemetry.py` | Real-time Server-Sent Events (SSE) stream | ✅ PASS |

---

## 🛠️ Troubleshooting

1. **Port 8000 already in use:**
   ```bash
   # Specify custom port via environment variable:
   PORT=8080 python run.py
   ```

2. **OpenCellID API Key Configuration:**
   Add your OpenCellID API key to `.env`:
   ```bash
   OPENCELLID_API_KEY=pk.your_api_key_here
   ```
   *Note: If no key is provided, CellSentinel operates seamlessly using the local verified reference catalog.*

3. **Running automated tests:**
   Ensure your virtual environment is active before running `pytest -v`. All tests execute with in-memory SQLite isolation.
