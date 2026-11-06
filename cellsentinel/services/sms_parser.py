"""
Out-of-Band Offline Telemetry & SMS Gateway Webhook Parser.
Decodes compact hex payloads, packed binary SMS PDUs, and silent SMS packets
transmitted when cellular mobile data is disabled.
"""

import binascii
import re
import struct
from typing import Dict, Any, Optional, Tuple
from cellsentinel.models import CellTowerTelemetry, SMSWebhookPayload


class SMSParseException(Exception):
    """Raised when an incoming SMS payload cannot be parsed."""
    pass


def encode_compact_hex_payload(
    imei_hash: str,
    mcc: int,
    mnc: int,
    lac: int,
    cid: int,
    rssi_dbm: float = -75.0
) -> str:
    """
    Encode cell telemetry into a compact binary hex string suitable for
    transmission via silent binary SMS PDU.
    
    Binary Format Specification:
    [0xCE]          : 1 byte magic protocol identifier (CellSentinel)
    [IMEI_PREFIX]   : 16 bytes (first 32 hex chars of SHA-256 hash)
    [MCC]           : 2 bytes unsigned big-endian (e.g. 404 -> 0x0194)
    [MNC]           : 2 bytes unsigned big-endian (e.g. 45 -> 0x002D)
    [LAC]           : 2 bytes unsigned big-endian (e.g. 1234 -> 0x04D2)
    [CID]           : 4 bytes unsigned big-endian (e.g. 5678 -> 0x0000162E)
    [RSSI]          : 1 byte signed integer (-128 to 127 dBm)
    """
    clean_hash = imei_hash.lower().replace("-", "").strip()
    if len(clean_hash) < 32:
        clean_hash = clean_hash.ljust(32, "0")
    imei_prefix_bytes = binascii.unhexlify(clean_hash[:32])

    magic = 0xCE
    clamped_rssi = max(-128, min(0, int(round(rssi_dbm))))

    packed = struct.pack(
        ">B16sHHHIb",
        magic,
        imei_prefix_bytes,
        mcc,
        mnc,
        lac,
        cid,
        clamped_rssi
    )
    return packed.hex().upper()


def encode_sms_bracket_payload(
    imei_hash: str,
    mcc: int,
    mnc: int,
    lac: int,
    cid: int,
    rssi_dbm: Optional[float] = None
) -> str:
    """
    Encode cell telemetry into the canonical bracket format:
    `[IMEI_HASH:MCC:MNC:LAC:CID]` or `[IMEI_HASH:MCC:MNC:LAC:CID:RSSI]`
    """
    if rssi_dbm is not None:
        return f"[{imei_hash}:{mcc}:{mnc}:{lac}:{cid}:{int(round(rssi_dbm))}]"
    return f"[{imei_hash}:{mcc}:{mnc}:{lac}:{cid}]"


def decode_packed_binary_hex(hex_str: str) -> Dict[str, Any]:
    """
    Decode raw packed binary hex format (Header 0xCE + 16-byte hash prefix + MCC + MNC + LAC + CID + RSSI).
    """
    try:
        raw_bytes = binascii.unhexlify(hex_str.strip())
    except Exception as e:
        raise SMSParseException(f"Invalid hex string representation: {e}")

    expected_len = 1 + 16 + 2 + 2 + 2 + 4 + 1  # 28 bytes
    if len(raw_bytes) < expected_len:
        raise SMSParseException(
            f"Binary payload length too short: got {len(raw_bytes)} bytes, expected at least {expected_len}."
        )

    magic, imei_prefix, mcc, mnc, lac, cid, rssi = struct.unpack(
        ">B16sHHHIb", raw_bytes[:expected_len]
    )

    if magic != 0xCE:
        raise SMSParseException(f"Unrecognized magic header byte: 0x{magic:02X}, expected 0xCE.")

    imei_hash_prefix = imei_prefix.hex().lower()

    return {
        "imei_hash": imei_hash_prefix,
        "mcc": mcc,
        "mnc": mnc,
        "lac": lac,
        "cid": cid,
        "signal_strength": float(rssi),
        "transport": "SMS_OUT_OF_BAND",
        "format": "BINARY_PACKED_HEX"
    }


def decode_bracket_format(text: str) -> Dict[str, Any]:
    """
    Decode canonical bracket format:
    `[IMEI_HASH:MCC:MNC:LAC:CID]` or `[IMEI_HASH:MCC:MNC:LAC:CID:RSSI]`
    """
    match = re.search(r"\[([a-zA-Z0-9_-]+):(\d+):(\d+):(\d+):(\d+)(?::(-?\d+(?:\.\d+)?))?\]", text)
    if not match:
        # Check without brackets: "IMEI_HASH:MCC:MNC:LAC:CID"
        match = re.search(r"\b([a-zA-Z0-9_-]{8,64}):(\d+):(\d+):(\d+):(\d+)(?::(-?\d+(?:\.\d+)?))?\b", text)

    if not match:
        raise SMSParseException("Text does not contain valid [IMEI_HASH:MCC:MNC:LAC:CID] payload.")

    imei_raw = match.group(1).strip()
    mcc = int(match.group(2))
    mnc = int(match.group(3))
    lac = int(match.group(4))
    cid = int(match.group(5))
    rssi = float(match.group(6)) if match.group(6) is not None else -75.0

    return {
        "imei_hash": imei_raw,
        "mcc": mcc,
        "mnc": mnc,
        "lac": lac,
        "cid": cid,
        "signal_strength": rssi,
        "transport": "SMS_OUT_OF_BAND",
        "format": "DELIMITED_BRACKET"
    }


def parse_sms_webhook_payload(webhook: SMSWebhookPayload) -> CellTowerTelemetry:
    """
    Extract and parse cellular telemetry from diverse SMS gateway webhook models.
    Supports:
    1. Direct hex_payload parameter
    2. Twilio Body parameter (plain text or ASCII hex)
    3. Generic gateway payload or message field
    """
    raw_text: Optional[str] = None

    if webhook.hex_payload and webhook.hex_payload.strip():
        raw_text = webhook.hex_payload.strip()
    elif webhook.Body and webhook.Body.strip():
        raw_text = webhook.Body.strip()
    elif webhook.message and webhook.message.strip():
        raw_text = webhook.message.strip()
    elif webhook.payload and webhook.payload.strip():
        raw_text = webhook.payload.strip()

    if not raw_text:
        raise SMSParseException("No valid SMS text or payload found in webhook request.")

    clean_text = raw_text.strip()

    # 1. Try packed binary hex if starts with CE or is clean hex of appropriate length
    if re.fullmatch(r"^[a-fA-F0-9]{56,}$", clean_text) and clean_text.upper().startswith("CE"):
        try:
            parsed = decode_packed_binary_hex(clean_text)
            return CellTowerTelemetry(
                imei_hash=parsed["imei_hash"],
                mcc=parsed["mcc"],
                mnc=parsed["mnc"],
                lac=parsed["lac"],
                cid=parsed["cid"],
                signal_strength=parsed["signal_strength"],
                radio_type="LTE",
                raw_payload=clean_text
            )
        except SMSParseException:
            pass

    # 2. Try bracket format directly
    try:
        parsed = decode_bracket_format(clean_text)
        return CellTowerTelemetry(
            imei_hash=parsed["imei_hash"],
            mcc=parsed["mcc"],
            mnc=parsed["mnc"],
            lac=parsed["lac"],
            cid=parsed["cid"],
            signal_strength=parsed["signal_strength"],
            radio_type="LTE",
            raw_payload=clean_text
        )
    except SMSParseException:
        pass

    # 3. Try hex-decoded ASCII (sometimes gateways encode text as hex ASCII)
    if re.fullmatch(r"^[a-fA-F0-9]+$", clean_text) and len(clean_text) % 2 == 0:
        try:
            decoded_ascii = binascii.unhexlify(clean_text).decode("utf-8", errors="ignore")
            parsed = decode_bracket_format(decoded_ascii)
            return CellTowerTelemetry(
                imei_hash=parsed["imei_hash"],
                mcc=parsed["mcc"],
                mnc=parsed["mnc"],
                lac=parsed["lac"],
                cid=parsed["cid"],
                signal_strength=parsed["signal_strength"],
                radio_type="LTE",
                raw_payload=clean_text
            )
        except Exception:
            pass

    raise SMSParseException(
        f"Unable to parse cellular telemetry from SMS content: '{clean_text[:60]}...'"
    )

