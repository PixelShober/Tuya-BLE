"""Helpers for Tuya BLE smart-lock datapoints."""
from __future__ import annotations

import base64
import binascii
import time


def build_accessory_lock_payload(
    reported_value: str | bytes,
    *,
    unlock: bool,
    timestamp: int | None = None,
) -> bytes:
    """Build a fresh DP 71 request from a reported DP 71 value.

    Tuya reports peripheral ID, central ID, and the pairing random value in
    device-to-cloud direction. A command swaps the IDs, keeps the paired random
    value, and adds a fresh timestamp. The final byte marks an administrator
    request, matching the 19-byte mobile-app form of the protocol.
    """
    if isinstance(reported_value, str):
        try:
            reported = base64.b64decode(reported_value, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("ble_unlock_check is not valid base64") from exc
    else:
        reported = bytes(reported_value)

    if len(reported) < 18:
        raise ValueError("ble_unlock_check must contain at least 18 bytes")

    peripheral_id = reported[0:2]
    central_id = reported[2:4]
    pairing_random = reported[4:12]
    if pairing_random == bytes(8):
        raise ValueError("ble_unlock_check contains an unpaired random value")

    command_timestamp = int(time.time()) if timestamp is None else int(timestamp)
    if not 0 <= command_timestamp <= 0xFFFFFFFF:
        raise ValueError("timestamp does not fit in four bytes")

    return b"".join(
        (
            central_id,
            peripheral_id,
            pairing_random,
            b"\x01" if unlock else b"\x00",
            command_timestamp.to_bytes(4, "big"),
            b"\x00",  # mobile-app method
            b"\x01",  # administrator request
        )
    )
