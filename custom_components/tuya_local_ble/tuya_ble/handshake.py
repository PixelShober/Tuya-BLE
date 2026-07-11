"""Product-specific Tuya BLE handshake parameters."""

from __future__ import annotations


def device_info_payload(product_id: str) -> bytes:
    """Return the DEVICE_INFO request payload expected by a product."""
    if product_id == "hc7n0urm":
        return b"\x00\xf3"
    if product_id == "laxpwq3g":
        return b"\x00\x14"
    return bytes(0)


def connection_attempts(product_id: str) -> int:
    """Return the maximum initial connection attempts for a product."""
    return 3 if product_id == "laxpwq3g" else 100


def packet_write_delay(product_id: str) -> float:
    """Return the delay between fragmented GATT writes for a product."""
    return 0.05 if product_id == "laxpwq3g" else 0


def device_info_protocol_version(
    product_id: str, advertised_version: int, attempt: int
) -> int:
    """Return the DEVICE_INFO frame version for a connection attempt."""
    if product_id == "laxpwq3g" and attempt == 0:
        return 4
    return advertised_version


def response_wait_timeout(product_id: str, default: float) -> float:
    """Return the response timeout for a connected product."""
    return 8 if product_id == "laxpwq3g" else default
