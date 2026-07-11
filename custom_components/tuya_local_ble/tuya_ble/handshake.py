"""Product-specific Tuya BLE handshake parameters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandshakeVariant:
    """Framing used for the DEVICE_INFO request of one connection attempt."""

    payload: bytes
    # None keeps the protocol version advertised by the device.
    header_version: int | None
    # 20 is the default ATT MTU and fragments the request.
    chunk_mtu: int
    # Writing with a response turns a silently dropped write into an ATT error.
    write_with_response: bool = False

    def describe(self) -> str:
        return "payload=%s header_version=%s chunk_mtu=%s write_with_response=%s" % (
            self.payload.hex() or "empty",
            self.header_version or "advertised",
            self.chunk_mtu,
            self.write_with_response,
        )


STANDARD = HandshakeVariant(payload=bytes(0), header_version=None, chunk_mtu=20)

# The GJ-635 never answers a DEVICE_INFO request. Payload, header version and
# fragment size have all been probed against the lock and none of them produced
# a notification, so the request itself is very likely never processed. Writing
# with a response is probed to make the lock report why it drops the write.
_VARIANTS: dict[str, tuple[HandshakeVariant, ...]] = {
    "hc7n0urm": (
        HandshakeVariant(payload=b"\x00\xf3", header_version=2, chunk_mtu=244),
    ),
    "laxpwq3g": (
        HandshakeVariant(
            payload=bytes(0),
            header_version=None,
            chunk_mtu=20,
            write_with_response=True,
        ),
        STANDARD,
    ),
}


def handshake_variant(product_id: str, attempt: int) -> HandshakeVariant:
    """Return the handshake framing to use for a connection attempt."""
    variants = _VARIANTS.get(product_id)
    if not variants:
        return STANDARD
    return variants[min(attempt, len(variants) - 1)]


def connection_attempts(product_id: str) -> int:
    """Return the maximum initial connection attempts for a product."""
    if product_id == "laxpwq3g":
        # One attempt per unprobed variant.
        return max(3, len(_VARIANTS["laxpwq3g"]))
    return 100


def packet_write_delay(product_id: str) -> float:
    """Return the delay between fragmented GATT writes for a product."""
    return 0.05 if product_id == "laxpwq3g" else 0


def response_wait_timeout(product_id: str, default: float) -> float:
    """Return the response timeout for a connected product."""
    return 8 if product_id == "laxpwq3g" else default
