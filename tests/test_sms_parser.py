"""
Unit tests for silent SMS out-of-band compact hex payloads and gateway webhooks.
"""

import pytest
from cellsentinel.models import SMSWebhookPayload
from cellsentinel.services.sms_parser import (
    encode_compact_hex_payload,
    encode_sms_bracket_payload,
    decode_packed_binary_hex,
    decode_bracket_format,
    parse_sms_webhook_payload,
    SMSParseException
)


def test_packed_binary_hex_encode_decode():
    imei_hash = "a1b2c3d4e5f60718293a4b5c6d7e8f90112233445566778899aabbccddeeff00"
    mcc = 404
    mnc = 45
    lac = 1234
    cid = 5678
    rssi = -75.0

    hex_payload = encode_compact_hex_payload(imei_hash, mcc, mnc, lac, cid, rssi)
    assert hex_payload.startswith("CE")

    decoded = decode_packed_binary_hex(hex_payload)
    assert decoded["mcc"] == 404
    assert decoded["mnc"] == 45
    assert decoded["lac"] == 1234
    assert decoded["cid"] == 5678
    assert decoded["signal_strength"] == -75.0
    assert decoded["imei_hash"] == imei_hash[:32]


def test_bracket_format_encode_decode():
    imei_hash = "f1e2d3c4b5a60718293a4b5c6d7e8f90"
    bracket_str = encode_sms_bracket_payload(imei_hash, 404, 45, 1234, 5678, -80.0)
    assert bracket_str == f"[{imei_hash}:404:45:1234:5678:-80]"

    decoded = decode_bracket_format(bracket_str)
    assert decoded["imei_hash"] == imei_hash
    assert decoded["mcc"] == 404
    assert decoded["mnc"] == 45
    assert decoded["lac"] == 1234
    assert decoded["cid"] == 5678
    assert decoded["signal_strength"] == -80.0


def test_twilio_webhook_parser():
    imei_hash = "abcdef0123456789abcdef0123456789"
    sms_body = f"[{imei_hash}:404:45:1234:5678:-72]"

    webhook = SMSWebhookPayload(
        From="+919811000000",
        Body=sms_body
    )

    telemetry = parse_sms_webhook_payload(webhook)
    assert telemetry.mcc == 404
    assert telemetry.mnc == 45
    assert telemetry.lac == 1234
    assert telemetry.cid == 5678
    assert telemetry.signal_strength == -72.0


def test_malformed_sms_raises():
    webhook = SMSWebhookPayload(Body="Hello this is random spam message with no telecom payload")
    with pytest.raises(SMSParseException):
        parse_sms_webhook_payload(webhook)
