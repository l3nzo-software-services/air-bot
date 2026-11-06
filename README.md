<div align="center">
  <img src="assets/logo.svg" width="560" alt="AIR BOT" />
  <p style="margin-top: 10px;"><b>Autonomous Cellular Telemetry &amp; Lost Device Recovery Sentinel</b></p>

  [![Latest Release](https://img.shields.io/github/v/release/vasanth5545/air-bot?color=00f0ff&style=for-the-badge&logo=github)](https://github.com/vasanth5545/air-bot/releases)
  [![License: MIT](https://img.shields.io/badge/License-MIT-38bdf8.svg?style=for-the-badge)](LICENSE)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-a78bfa.svg?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
  [![3GPP Telecom](https://img.shields.io/badge/Telecom-3GPP%20Cellular-10b981.svg?style=for-the-badge)]()
  [![Battery: Zero Drain](https://img.shields.io/badge/Battery-%3C1%25%20Zero%20Drain-f59e0b.svg?style=for-the-badge)]()
  [![Platform: Windows & Android](https://img.shields.io/badge/Platform-Windows%20%7C%20Android-ec4899.svg?style=for-the-badge)]()
</div>

---

## ⚡ What is AIR BOT?

**AIR BOT** is a next-generation, self-hosted anti-theft and device recovery system that tracks lost or stolen smartphones via **cellular base-station airwaves** without relying on active internet packs, open GPS satellite locks, or battery-draining background wakelocks.

Unlike fragile tracking apps that fail the moment a thief toggles Airplane mode or hard-resets the phone, **AIR BOT** leverages **hardware-derived identity**, **out-of-band SMS fallbacks**, and **cellular radio broadcast parameters (MCC, MNC, LAC, CID)** to pinpoint the device.

---

## 🛡️ Core Defense Architecture

```
                  ┌──────────────────────────────────────────────┐
                  │                 AIR BOT CORE                 │
                  └──────────────────────┬───────────────────────┘
                                         │
             ┌───────────────────────────┴───────────────────────────┐
             ▼                                                       ▼
   [ ONLINE HTTPS BEACON ]                                 [ OFFLINE SMS FALLBACK ]
   (When Mobile Data is Active)                            (When Data / Wi-Fi is OFF)
             │                                                       │
             ▼                                                       ▼
   POST /api/telemetry                                     POST /api/telemetry/sms-webhook
             │                                                       │
             └───────────────────────────┬───────────────────────────┘
                                         ▼
                     ┌───────────────────────────────────────┐
                     │     OpenCellID Triangulation Engine   │
                     │ (Resolves Base-Station Coordinates)   │
                     └───────────────────┬───────────────────┘
                                         ▼
                     ┌───────────────────────────────────────┐
                     │   Interactive Cartographic Dashboard  │
                     │  (Leaflet.js + Live Radar Map Marker) │
                     └───────────────────────────────────────┘
```

### 1. 🔒 Hardware-Derived Key (Wipe & Restore Survival)
* Normal apps store tokens in `/data/` which vanish upon factory restore.
* **AIR BOT** deterministically derives its cryptographic authentication token from the processor's immutable hardware identity:
  $$\text{Key} = \text{SHA256}(\text{IMEI} + \text{Baseband Hardware Serial} + \text{Secret Salt})$$
* **Result:** Even if an attacker performs a complete factory reset, the moment the device powers back on, the exact same token is regenerated automatically.

### 2. 🚨 SIM-Swap Trap (`android.intent.action.SIM_STATE_CHANGED`)
* If an attacker ejects the original SIM card and inserts their own, the Sentinel receiver wakes up in **< 2 seconds**.
* It uses the **thief's newly inserted SIM** to fire a stealth SMS to the owner's emergency contact containing:
  - 📞 **Thief's New Phone Number**
  - 🗼 **Current Base-Station Tower ID & Area Code**
  - 📍 **Cellular Coordinates & Timestamp**

### 3. 🔋 Zero Battery Consumption (< 1% Daily)
* Never holds persistent wake-locks or continuous GPS polling.
* Operates strictly on **Event-Driven Android Native Receivers**:
  - `ACTION_BOOT_COMPLETED` (Device restart / startup)
  - `ACTION_SIM_STATE_CHANGED` (SIM swap)
  - `CELL_INFO_CHANGED` (Moving between cell towers)
* Wakes up for 1 second, transmits telemetry, and returns to deep sleep.

### 4. 🕵️ Anti-Reverse Engineering & Stealth Disguise
* **ProGuard / R8 Obfuscation**: Code minification, class flattening, and method name obfuscation prevent decompilers from inspecting telemetry logic.
* **Anti-Tamper & Debugger Checks**: Detects Frida hooks and active debuggers.
* **Disguised System Icon**: App appears in the launcher with a generic system gear icon labeled **System Radio Control**, never alerting thieves of its tracking capabilities.

---

## 🚀 Quickstart & Installation

### Option 1: Run Standalone Dashboard (Windows / Linux / macOS)

```bash
# 1. Clone the repository
git clone https://github.com/<YOUR_USERNAME>/air-bot.git
cd air-bot

# 2. Setup virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch AIR BOT
python run.py
```
👉 Open browser to **`http://localhost:8000`** to access the live dashboard.

---

### Option 2: Build Windows Standalone Executable (.EXE)

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --name "AIR_BOT" --icon="assets/logo.ico" desktop_launcher.py
```
Double-click `dist/AIR_BOT.exe` to run AIR BOT as a native desktop application!

---

### Option 3: Android Companion Client (`android-client/`)

1. Open `android-client/` in **Android Studio**.
2. Build signed/debug APK: **Build > Build Bundle(s) / APK(s) > Build APK(s)**.
3. Install on your Android device:
   ```bash
   adb install app-debug.apk
   ```
4. Enter your AIR BOT Server URL, IMEI, and Emergency Contact.
5. Tap **Activate Sentinel Protection**!

---

## 🧪 Automated Verification Suite

Run the full automated test suite verifying device authentication, OpenCellID resolution, and offline SMS fallback:

```bash
pytest -v
```
```
======================== 20 passed in 0.60s ========================
```

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for full details.
