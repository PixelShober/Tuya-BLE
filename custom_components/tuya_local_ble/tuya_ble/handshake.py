"""Product-specific Tuya BLE handshake parameters."""

from __future__ import annotations


def device_info_payload(product_id: str) -> bytes:
    """Return the DEVICE_INFO request payload expected by a product."""
    if product_id == "hc7n0urm":
        return b"\x00\xf3"
    if product_id == "laxpwq3g":
        return b"\x00\x14"
    return bytes(0)
