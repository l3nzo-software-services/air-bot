<div align="center">
  <img src="assets/logo.svg" width="560" alt="AIR BOT" />
  <p style="margin-top: 10px;"><b>Autonomous Cellular Telemetry &amp; Lost Device Recovery Sentinel</b></p>

  [![Live Dashboard](https://img.shields.io/badge/Live%20Website-air--bot--ndb9.onrender.com-10b981?style=for-the-badge&logo=render)](https://air-bot-ndb9.onrender.com/)
  [![Latest Release](https://img.shields.io/github/v/release/l3nzo-software-services/air-bot?color=00f0ff&style=for-the-badge&logo=github)](https://github.com/l3nzo-software-services/air-bot/releases)
  [![License: MIT](https://img.shields.io/badge/License-MIT-38bdf8.svg?style=for-the-badge)](LICENSE)
  [![Platform: Android & Windows](https://img.shields.io/badge/Platform-Android%20%7C%20Windows-ec4899.svg?style=for-the-badge)]()
</div>

---

## 🌐 Live Hosted Website
👉 **Open Dashboard:** https://air-bot-ndb9.onrender.com/

---

## 📱 Mobile Setup (3 Easy Steps — No Coding Needed)

1. **Register Your Phone on the Website**
   * Open **https://air-bot-ndb9.onrender.com/**
   * Click **+ Register Device**, enter your phone's **IMEI** and **Device Name**, and submit.
   * Click **Copy API Key** (and keep it safe).

2. **Download & Install the Android App**
   * Tap **Download Android APK** right after registering (or download [`AIR_BOT_Sentinel_Client_v1.0.0.apk`](https://github.com/l3nzo-software-services/air-bot/releases/latest/download/AIR_BOT_Sentinel_Client_v1.0.0.apk) from Releases).
   * Install the APK on your Android phone (it appears discreetly as **System Radio Manager**).

3. **Activate Protection on Mobile**
   * Open **System Radio Manager** and allow **Location**, **Phone**, and **SMS** permissions.
   * Server URL (`https://air-bot-ndb9.onrender.com`) is pre-filled — paste your **Device API Key**, enter your **IMEI** and an **Emergency Phone Number**, then tap **Activate Sentinel Protection**.
   * Tap **Lock Against Uninstall (Device Admin)** so thieves cannot easily uninstall it.

---

## 🛡️ What AIR BOT Does

* **Online Tower Tracking:** Sends cellular base-station parameters (`MCC`, `MNC`, `LAC`, `Cell ID`, signal strength) to the live Leaflet map dashboard via `POST /api/telemetry`.
* **Offline SMS Fallback:** When mobile data/Wi-Fi is turned off, dispatches tower details via silent SMS (`LOC:...`) to your Emergency Contact.
* **SIM-Swap Alert:** `SimChangeReceiver` detects a new SIM insertion and sends an emergency SMS with the new carrier and current tower ID.
* **Zero Background Battery Drain:** Event-driven native receivers (`BOOT_COMPLETED`, `SIM_STATE_CHANGED`) wake only when needed instead of polling GPS continuously.
* **Hardware-Derived Key:** Authentication token can be deterministically derived from hardware IMEI + secret salt (`SHA-256`).

---

## 💻 Optional: Self-Host on Windows or From Source

> You do **not** need the Windows `.exe` if you use the hosted website above. Only download it if you want to run your own private local server on Windows.

* **Windows Standalone App:** Download [`AIR_BOT_v1.0.0_Windows_x64.zip`](https://github.com/l3nzo-software-services/air-bot/releases/latest/download/AIR_BOT_v1.0.0_Windows_x64.zip) from [Releases](https://github.com/l3nzo-software-services/air-bot/releases), extract, and double-click `AIR_BOT.exe` (opens `http://localhost:8000`).

<details>
<summary>Developer / Local Python Setup &amp; Tests</summary>

```bash
git clone https://github.com/l3nzo-software-services/air-bot.git
cd air-bot
python -m venv .venv
# Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Run tests:
```bash
pytest -v
```

</details>

---

## 📜 License
Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for full details.
