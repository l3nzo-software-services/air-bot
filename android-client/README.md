# 📱 CellSentinel Android Companion Client

A lightweight, zero-battery Android background sentinel service designed for device recovery and cell-tower geolocation tracking.

## Core Capabilities
* **Automatic Boot Survival (`BOOT_COMPLETED`)**: Wakes up immediately upon device boot/restart at the lockscreen before phone unlock.
* **SIM Change Detection (`SIM_STATE_CHANGED`)**: Detects when a new SIM is inserted by an unauthorized user and fires a stealth SMS to the emergency contact with the thief's new carrier and current cell tower.
* **Dual Telemetry Pipeline**:
  - **Online Mode**: Transmits live cell parameters via HTTPS `POST /api/telemetry` to your self-hosted CellSentinel server.
  - **Offline Out-of-Band Mode**: If mobile data is turned off, automatically falls back to sending a silent SMS (`LOC:<IMEI>:<MCC>:<MNC>:<LAC>:<CID>:<RSSI>`).
* **Anti-Theft Uninstall Lock**: Integrates with Android Device Administration to prevent attackers from removing the app.
* **Zero Battery Drain**: Uses event-driven BroadcastReceivers rather than persistent background wakelocks.

## Quick Build & Installation
1. Open this `android-client` folder in **Android Studio**.
2. Select **Build > Build APK(s)**.
3. Install on your Android device:
   ```bash
   adb install app-debug.apk
   ```
4. Enter your CellSentinel Server URL, Device Token, IMEI, and Emergency Contact.
5. Tap **Activate Sentinel Protection** and enable **Device Administrator**.

