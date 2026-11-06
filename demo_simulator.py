"""
CellSentinel - Standalone Telecom Simulation & Demonstration CLI.
Simulates a lost device moving across metropolitan cellular towers,
demonstrating both online HTTPS REST telemetry and out-of-band Silent SMS Hex recovery.
"""

import asyncio
import time
import httpx
from cellsentinel.services.sms_parser import encode_compact_hex_payload, encode_sms_bracket_payload


BASE_URL = "http://127.0.0.1:8000"

# Realistic handover path across Delhi Connaught Place -> Barakhamba -> Mandi House
SIMULATION_STOPS = [
    {
        "name": "Connaught Place Central Radial (Stop 1: Initial Loss Location)",
        "mcc": 404, "mnc": 45, "lac": 1234, "cid": 5678, "rssi": -65.0,
        "transport": "HTTPS", "note": "Device active on 4G LTE network"
    },
    {
        "name": "Barakhamba Road Commercial Sector (Stop 2: Device In Transit)",
        "mcc": 404, "mnc": 45, "lac": 1234, "cid": 5679, "rssi": -82.0,
        "transport": "HTTPS", "note": "Tower handover detected. Path loss expanding."
    },
    {
        "name": "Mandi House Transit Exchange (Stop 3: Mobile Data Terminated / Offline Mode)",
        "mcc": 404, "mnc": 45, "lac": 1234, "cid": 5680, "rssi": -94.0,
        "transport": "SMS", "note": "Mobile data CUT OFF by thief! Silent SMS Hex PDU transmitted out-of-band!"
    },
    {
        "name": "Janpath Cultural Corridor (Stop 4: Final Signal Fix)",
        "mcc": 404, "mnc": 45, "lac": 1234, "cid": 5681, "rssi": -74.0,
        "transport": "SMS", "note": "Silent SMS out-of-band triangulation pinpointed recovery zone."
    }
]


async def run_simulation():
    print("=" * 75)
    print("  CellSentinel - Lost Device Recovery & Telemetry Simulation")
    print("=" * 75)

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Health check
        try:
            h = await client.get(f"{BASE_URL}/health")
            if h.status_code != 200:
                print(f"[ERROR] CellSentinel server not responding at {BASE_URL}. Ensure uvicorn is running.")
                return
        except Exception as e:
            print(f"[ERROR] Cannot connect to {BASE_URL}: {e}")
            print("Please run: uvicorn cellsentinel.main:app --reload")
            return

        print("[+] CellSentinel engine ONLINE.")

        # 2. Register Target Device
        imei_raw = "358941098765432"
        reg_payload = {
            "imei_or_hash": imei_raw,
            "device_model": "Google Pixel 8 Pro",
            "owner_name": "Vikramaditya Sharma",
            "owner_phone": "+91-98110-12345",
            "owner_email": "v.sharma@sentinel.org",
            "recovery_pin": "9876"
        }
        res = await client.post(f"{BASE_URL}/api/v1/devices", json=reg_payload)
        device = res.json()
        imei_hash = device["imei_hash"]
        print(f"[+] Device Registered: {device['device_model']}")
        print(f"    IMEI SHA-256: {imei_hash}")

        # 3. Transition to LOST
        await client.patch(
            f"{BASE_URL}/api/v1/devices/{imei_hash}/state",
            json={"state": "LOST", "recovery_pin": "9876", "reason": "Reported lost in metro station"}
        )
        print("[!] Target declared LOST. Emergency cellular triangulation activated.\n")

        # 4. Stream Handovers
        for i, stop in enumerate(SIMULATION_STOPS, 1):
            print(f"--- [Hop {i}/4] {stop['name']} ---")
            print(f"    Parameters: MCC={stop['mcc']} MNC={stop['mnc']} LAC={stop['lac']} CID={stop['cid']} RSSI={stop['rssi']} dBm")
            print(f"    Operational Note: {stop['note']}")

            if stop["transport"] == "HTTPS":
                # Ingest via REST Push
                telemetry = {
                    "imei_hash": imei_hash,
                    "mcc": stop["mcc"],
                    "mnc": stop["mnc"],
                    "lac": stop["lac"],
                    "cid": stop["cid"],
                    "signal_strength": stop["rssi"]
                }
                t_res = await client.post(f"{BASE_URL}/api/v1/telemetry/push", json=telemetry)
            else:
                # Ingest via Out-of-band Silent SMS Hex PDU
                compact_bracket = encode_sms_bracket_payload(
                    imei_hash, stop["mcc"], stop["mnc"], stop["lac"], stop["cid"], stop["rssi"]
                )
                print(f"    [SILENT SMS PDU]: {compact_bracket}")
                t_res = await client.post(
                    f"{BASE_URL}/api/v1/telemetry/sms-webhook",
                    data={"From": "+919811099999", "Body": compact_bracket}
                )

            t_data = t_res.json()
            print(f"    [TRIANGULATION FIX]: Lat: {t_data['latitude']:.5f}, Lon: {t_data['longitude']:.5f}")
            print(f"    [ACCURACY BOUNDARY]: Radius: {t_data['accuracy_radius']:.1f} meters (Source: {t_data['resolver_source']})")
            print(f"    [TRANSPORT CHANNEL]: {t_data['transport']}\n")
            await asyncio.sleep(1.0)

        # 5. Recovery
        await client.patch(
            f"{BASE_URL}/api/v1/devices/{imei_hash}/state",
            json={"state": "RECOVERED", "recovery_pin": "9876", "reason": "Terminal secured at Janpath depot."}
        )
        print("=" * 75)
        print("[✓] TARGET DEVICE RECOVERED SUCCESSFULLY. Incident Closed.")
        print("=" * 75)


if __name__ == "__main__":
    asyncio.run(run_simulation())

